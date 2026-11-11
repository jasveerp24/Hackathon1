"""
The conductor. Every request passes through these layers, in this order:

  1. Governance (input)   block injection, hide personal data
  2. Router               Jev decides clarity + which agent; if Jev is unsure -> Claude/Gemini decide
  3. Agent chain          primary agent -> its fallbacks -> clarifier (always last)
        for every attempt:  Safety gate (Jev) -> agent runs -> Verifier (Jev) -> else next agent
  4. Synthesizer          one spoken reply
  5. Governance (output)  hide personal data

Run agents.py (not this file): it registers the agents, then starts the text demo.
"""
import json
import logging
import re
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from config import CONFIG
from jev import JevClient, choice_question, noul_question, read_choice, read_noul
from providers import text_llm

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
log = logging.getLogger("jarvis")

jev = JevClient()

YES_WORDS = {"yes", "y", "confirm", "ok", "go ahead"}


@dataclass
class Step:
    # One unit of work: "agent X, do task Y". fallbacks = agents to try if X cannot do it.
    agent: str
    task: str
    fallbacks: list = field(default_factory=list)


@dataclass
class AgentResult:
    agent: str
    ok: bool   # False means "I could not do this", which sends the request to the next agent
    output: str
    meta: dict = field(default_factory=dict)


@dataclass
class Context:
    user_text: str
    history: list = field(default_factory=list)
    results: list = field(default_factory=list)


# Tools: plain functions agents may call. Agents never import them, they ask via use_tool().
TOOLS = {}


def tool(name, description, risk="low"):
    def wrap(fn):
        TOOLS[name] = {"fn": fn, "description": description, "risk": risk}
        return fn
    return wrap


# Agents: registered by name so the router and the chains can find them.
AGENTS = {}


class BaseAgent(ABC):
    name = "base"
    description = ""         # the router reads this to decide when to pick the agent
    allowed_tools = []       # least privilege: an agent only gets the tools listed here
    risk = "low"             # "high" always asks the user before running
    fallbacks = []           # tried in this order when this agent returns ok=False
    routable = True          # False = never picked by the router, only reached as a fallback
    verify = False           # True = Jev double-checks that the reply really answers the request

    @abstractmethod
    def run(self, task, ctx): ...

    def use_tool(self, tool_name, **kwargs):
        if tool_name not in self.allowed_tools:
            raise PermissionError(f"{self.name} may not use {tool_name}")
        return TOOLS[tool_name]["fn"](**kwargs)


class Governance:
    # REPLACE LATER: add rules for your theme, or ask Jev a noul question instead of regex.
    INJECTION = re.compile(r"ignore (all|previous) instructions|reveal.*system prompt", re.I)
    PII = [
        (re.compile(r"\b\d{8,}\b"), "[NUMBER]"),
        (re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"), "[EMAIL]"),
    ]

    def check_input(self, text):
        if self.INJECTION.search(text):
            return False, "That request looks like an attempt to override my rules."
        for pattern, replacement in self.PII:
            text = pattern.sub(replacement, text)
        return True, text

    def check_output(self, text):
        for pattern, replacement in self.PII:
            text = pattern.sub(replacement, text)
        return text

    def audit(self, event, **data):
        with open(CONFIG["audit_log"], "a") as f:
            f.write(json.dumps({"t": time.time(), "event": event, **data}) + "\n")


@dataclass
class RouteDecision:
    agent: str
    confidence: float
    clear: float


class Router:
    # Layer 1 is Jev (fast, calibrated). Layer 2 is the text LLM chain. Layer 3 is keywords.
    # Jev answers two questions in ONE request: is the request clear, and who should handle it.

    def plan(self, ctx):
        terminal = CONFIG["terminal_agent"]
        decision = self.ask_jev(ctx)

        if decision is not None:
            if decision.clear < CONFIG["clear_floor"]:
                log.info("route: Jev says the request is unclear (%.2f) -> %s", decision.clear, terminal)
                return [Step(terminal, ctx.user_text)]
            if decision.confidence >= CONFIG["route_confidence"]:
                log.info("route: Jev -> %s (%.2f)", decision.agent, decision.confidence)
                if decision.agent == "none":
                    return [Step(terminal, ctx.user_text)]
                return [Step(decision.agent, ctx.user_text)]
            log.info("route: Jev unsure (%.2f) -> escalating to the text LLM", decision.confidence)

        steps = self.ask_text_llm(ctx)
        if steps:
            return steps
        log.info("route: no model answered -> keyword fallback")
        return self.keyword(ctx)

    def routable(self):
        return {name: agent for name, agent in AGENTS.items() if agent.routable}

    def ask_jev(self, ctx):
        agents = self.routable()
        if not jev.live or not agents:
            return None
        options = {name: agent.description[:255] for name, agent in agents.items()}
        options["none"] = "No specialist fits this request."
        questions = {
            "is_clear": noul_question(
                "Is the request clear enough to act on without asking the user a follow-up question? "
                "Use recent_turns for context."),
            "route": choice_question("Which specialist should handle this request?", options),
        }
        state = {"request": ctx.user_text, "recent_turns": ctx.history[-4:]}
        try:
            answers = jev.ask(state, questions)
            if answers is None:
                return None
            label, confidence, _ = read_choice(answers["route"])
            if label != "none" and label not in agents:
                confidence = 0.0   # Jev named something we do not have: do not trust it
            return RouteDecision(label, confidence, read_noul(answers["is_clear"]))
        except Exception as error:
            log.warning("could not read Jev's routing answer (%s)", error)
            return None

    def ask_text_llm(self, ctx):
        agents = self.routable()
        if not text_llm.live or not agents:
            return []
        menu = "\n".join(f"- {name}: {agent.description}" for name, agent in agents.items())
        system = (
            "You are a router. Pick the agents needed for the user's request.\n"
            f"Available agents:\n{menu}\n"
            'Reply with JSON only: [{"agent": "<name>", "task": "<what it should do>"}]. '
            "If no agent fits, reply with []."
        )
        try:
            raw = text_llm.complete(system, ctx.user_text)
            raw = re.sub(r"```json|```", "", raw).strip()
            steps = [Step(item["agent"], item["task"]) for item in json.loads(raw)]
        except Exception as error:
            log.warning("text-LLM routing failed (%s)", error)
            return []
        return [step for step in steps if step.agent in agents][: CONFIG["max_steps"]]

    def keyword(self, ctx):
        agents = self.routable()
        if not agents:
            return [Step(CONFIG["terminal_agent"], ctx.user_text)]
        words = set(re.findall(r"\w+", ctx.user_text.lower()))

        def overlap(agent):
            return len(words & set(re.findall(r"\w+", agent.description.lower())))

        best = max(agents.values(), key=overlap)
        return [Step(best.name, ctx.user_text)]


class SafetyGate:
    # Before an agent acts, ask Jev how safe it is. Jev returns a probability and WE decide.
    QUESTIONS = {
        "is_safe": noul_question(
            "Is carrying out this task safe and appropriate for a public-service voice assistant?"),
        # ADD MORE QUESTIONS HERE if you want more checks. The lowest probability wins.
    }

    def score(self, step):
        if not jev.live:
            return 0.9   # no key: mock mode always proceeds
        agent = AGENTS[step.agent]
        state = {"agent": step.agent, "agent_purpose": agent.description, "task": step.task}
        try:
            answers = jev.ask(state, self.QUESTIONS)
            if answers is None:
                return self.unsure_score()
            probabilities = {key: read_noul(answers[key]) for key in self.QUESTIONS}
        except Exception as error:
            log.warning("could not read Jev's safety answer (%s)", error)
            return self.unsure_score()
        log.info("gate: %s -> %s", step.agent, probabilities)
        return min(probabilities.values())

    def unsure_score(self):
        # Jev unavailable: fail safe by asking the user, never by silently running.
        return (CONFIG["jev_proceed"] + CONFIG["jev_confirm"]) / 2

    def decide(self, step):
        probability = self.score(step)
        if probability >= CONFIG["jev_proceed"]:
            return "proceed"
        if probability >= CONFIG["jev_confirm"]:
            return "confirm"
        return "refuse"


class Verifier:
    # After an agent replies, ask Jev if the reply really answers the request.
    # This is how "agent A could not do it" is detected with a probability, not string matching.
    QUESTIONS = {
        "answered": noul_question(
            "Does the reply give concrete, useful information or a completed action for the request, "
            "rather than saying it does not know or cannot help?"),
    }

    def accepts(self, request, result):
        if not jev.live:
            return True
        try:
            answers = jev.ask({"request": request, "reply": result.output}, self.QUESTIONS)
            if answers is None:
                return True   # no verdict: do not block a possibly good answer
            probability = read_noul(answers["answered"])
        except Exception as error:
            log.warning("could not read Jev's verification (%s)", error)
            return True
        log.info("verify: %s answered=%.2f", result.agent, probability)
        return probability >= CONFIG["answer_floor"]


class Synthesizer:
    def compose(self, ctx):
        outputs = [r.output for r in ctx.results if r.ok]
        if not outputs:
            return "Sorry, I couldn't complete that."
        if len(outputs) == 1:
            return outputs[0]   # one agent already wrote a spoken-style reply: skip an extra model call
        if text_llm.live:
            try:
                system = "You are JARVIS. Combine these results into a short, natural spoken reply."
                return text_llm.complete(system, f"Question: {ctx.user_text}\nResults: {outputs}", 300)
            except Exception as error:
                log.warning("synthesis failed (%s), joining results instead", error)
        return " ".join(outputs)


class Orchestrator:
    def __init__(self):
        self.gov = Governance()
        self.router = Router()
        self.gate = SafetyGate()
        self.verifier = Verifier()
        self.synth = Synthesizer()
        self.history = []
        self.pending = None   # a Step waiting for the user's yes/no

    def handle(self, user_text):
        if self.pending:
            step, self.pending = self.pending, None
            if user_text.strip().lower() in YES_WORDS:
                ctx = Context(step.task, self.history)
                prompt = self.run_chain(step, ctx, confirmed=True)
                if prompt is not None:
                    return prompt
                return self.reply(ctx)
            return "Okay, cancelled."

        ok, text = self.gov.check_input(user_text)
        if not ok:
            self.gov.audit("blocked_input", text=user_text)
            return text

        ctx = Context(text, self.history)
        for step in self.router.plan(ctx)[: CONFIG["max_steps"]]:
            prompt = self.run_chain(self.with_chain(step), ctx)
            if prompt is not None:
                return prompt   # a confirmation question or a refusal ends the turn
        return self.reply(ctx)

    def with_chain(self, step):
        # Fallback order = the agent's own fallbacks, then the terminal agent (clarifier) last.
        agent = AGENTS.get(step.agent)
        if agent is None:
            return step
        chain = []
        for name in [*agent.fallbacks, CONFIG["terminal_agent"]]:
            if name != step.agent and name not in chain:
                chain.append(name)
        return Step(step.agent, step.task, chain)

    def run_chain(self, step, ctx, confirmed=False):
        # Returns a message to say to the user right now, or None when a result was stored.
        names = [step.agent, *step.fallbacks]
        for index, name in enumerate(names):
            agent = AGENTS.get(name)
            if agent is None:
                log.warning("chain: agent '%s' is not registered, skipping", name)
                continue
            attempt = Step(name, step.task, names[index + 1:])

            already_approved = confirmed and index == 0
            if not already_approved:
                decision = self.gate.decide(attempt)
                self.gov.audit("attempt", agent=name, task=step.task, gate=decision)
                if decision == "refuse":
                    # Unsafe is not a capability problem, so do NOT fall through to another agent.
                    return "I'm not confident enough to do that safely."
                if decision == "confirm" or agent.risk == "high":
                    self.pending = attempt
                    return f"Just to confirm: {name} will do '{step.task}'. Shall I go ahead?"

            result = self.run_agent(agent, attempt, ctx)
            if result.ok and (not agent.verify or self.verifier.accepts(step.task, result)):
                ctx.results.append(result)
                return None
            log.info("chain: %s could not do it -> next agent", name)
            self.gov.audit("fallthrough", agent=name, output=result.output)

        ctx.results.append(AgentResult("none", False, "No agent could complete the request."))
        return None

    @staticmethod
    def run_agent(agent, step, ctx):
        try:
            return agent.run(step.task, ctx)
        except Exception as error:
            log.exception("agent %s crashed", agent.name)
            return AgentResult(agent.name, False, str(error))

    def reply(self, ctx):
        text = self.gov.check_output(self.synth.compose(ctx))
        self.history += [{"role": "user", "content": ctx.user_text}, {"role": "assistant", "content": text}]
        return text
