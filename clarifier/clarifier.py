"""
clarifier.py - the Clarifier agent (owner: Anjali). ONE standalone file.

Copy this file into any Python 3.9+ project. It needs nothing else: no other project files,
no packages, no API keys. An AI model is optional (it words the questions more naturally).

WHAT IT DOES
  The Clarifier steps in when a request cannot be acted on yet, and keeps asking until it can:
    1. Danger ("someone is following me")      -> no questions: offer SOS straight away.
    2. A detail is missing ("I'm going out")   -> ask for exactly what is missing.
    3. The request is unclear                  -> ask the user to say more.
  Each answer is added to the original request, and it checks again. It keeps looping until
  nothing is missing. There is no fixed number of questions. Ways out of the loop at any time:
    - danger words (even mid-question)  -> SOS offer
    - "never mind" / "cancel"           -> cancelled
    - a brand-new question              -> the old one is dropped
  Every few questions it also reminds the user they can just say "help".

USE IT IN ANY PROJECT (3 lines)
    from clarifier import Clarifier
    clarifier = Clarifier()                  # optional: Clarifier(ask_llm=my_function)
    turn = clarifier.step("I'm going out")   # call once per user message
  turn.action is one of:
    "ask"       -> speak turn.say, then pass the user's reply to step() again
    "proceed"   -> the request is complete: handle turn.request (it includes every answer)
    "sos"       -> speak turn.say (the SOS offer) and start your emergency flow
    "cancelled" -> speak turn.say
  Optional arguments to step(): session= (one per user), unclear=True (your own classifier says
  the request is unclear), needs=[...] (a tool is missing details), danger_hint=True (your own
  danger detector fired).

AI WORDING (optional)
  ask_llm is any function (system_prompt, user_prompt) -> text. If given, the AI writes each
  question to fit the conversation. Its question is checked (one short question, nothing about
  card numbers, PINs or codes); if it fails the check or the AI is down, a built-in question is
  used instead. The danger message is never AI-written: it must be instant and exact.

SETTINGS
  Change with Clarifier(languages=["en", "fr"], help_every=3, max_questions=None) or configure().

IN JARVIS (the team project) the same logic is used through four hooks in orchestrator.py and
agents.py, all marked "CLARIFIER": needs_clarifier, resume, plan, after_turn.
"""
import re
from dataclasses import dataclass, field

SETTINGS = {
    "languages": ["en"],       # add "fr" to answer French requests in French
    "max_questions": None,     # None = keep asking until complete; a number = stop after that many
    "help_every": 3,           # every Nth question also says "you can just say 'help'"; 0 = never
    "max_question_words": 25,  # longest AI-written question we accept
}


def configure(**changes):
    unknown = set(changes) - set(SETTINGS)
    if unknown:
        raise ValueError(f"Unknown Clarifier settings: {sorted(unknown)}")
    SETTINGS.update(changes)


AP = "['’]"   # straight or curly apostrophe, as speech-to-text may produce either


@dataclass
class ClarifyState:
    # What we are in the middle of clarifying, kept per session.
    original: str                                  # the request that needed clarifying
    question: str                                  # the last question we asked
    asked: list = field(default_factory=list)      # the details that question asked for
    answers: list = field(default_factory=list)    # everything the user said since
    attempts: int = 0                              # how many questions we have asked


@dataclass
class Plan:
    kind: str                       # "ask" | "sos" | "give_up"
    original: str
    question: str = None
    intent: str = None
    missing: list = field(default_factory=list)
    escalate: bool = False          # True = offer the SOS agent as a yes/no
    lang: str = "en"

    def meta(self):
        return {"clarification": True, "kind": self.kind, "intent": self.intent, "lang": self.lang,
                "missing": self.missing, "original": self.original, "escalate": self.escalate}


def _rx(*patterns):
    return [re.compile(p, re.I) for p in patterns]


# ---------------------------------------------------------------- language

FRENCH_MARKERS = re.compile(
    rf"\b(je|j{AP}|tu|vous|il|elle|on|est-ce|c{AP}est|suis|vais|sors|pars|mon|ma|mes|famille|que|qui|pas|"
    r"une|des|du|au|aux|chez|où|quand|merci|oui|aidez|aide|secours|arnaque|retour|heures?|maison|"
    rf"quelqu{AP}un|suit|frappe|peur|dis|dites|ma|mon)\b", re.I)
ENGLISH_MARKERS = re.compile(
    r"\b(i|i'm|im|my|the|is|are|you|going|will|to|what|when|where|out|home|back|help|please|yes)\b", re.I)


def detect_lang(text):
    # English only unless "fr" is in SETTINGS["languages"].
    if "fr" not in SETTINGS["languages"]:
        return "en"
    fr, en = len(FRENCH_MARKERS.findall(text or "")), len(ENGLISH_MARKERS.findall(text or ""))
    return "fr" if fr > en else "en"


SAY = {
    "sos":        {"en": "It sounds like you may be in danger. Should I alert your emergency contacts now? "
                         "If you can, call 999.",
                   "fr": "On dirait que vous êtes en danger. Voulez-vous que j'alerte vos contacts d'urgence "
                         "maintenant ? Si vous le pouvez, appelez le 999."},
    "sos_no_agent": {"en": "It sounds like you may be in danger. Please call 999 or 112 now.",
                     "fr": "On dirait que vous êtes en danger. Appelez le 999 ou le 112 maintenant."},
    "give_up":    {"en": "I'm still not sure what you need. If you need help, I can alert your emergency "
                         "contacts. Should I do that?",
                   "fr": "Je ne suis toujours pas sûr de ce dont vous avez besoin. Si vous avez besoin d'aide, "
                         "je peux alerter vos contacts d'urgence. Voulez-vous que je le fasse ?"},
    "give_up_no_agent": {"en": "I'm still not sure what you need. If it's an emergency, please call 999 or 112.",
                         "fr": "Je ne suis toujours pas sûr de ce dont vous avez besoin. Si c'est une urgence, "
                               "appelez le 999 ou le 112."},
    "cancelled":  {"en": "Okay, cancelled.", "fr": "D'accord, c'est annulé."},
    "again":      {"en": "Sorry, I didn't catch that. ", "fr": "Désolé, je n'ai pas compris. "},
    "help_hint":  {"en": " If you need urgent help, just say help.",
                   "fr": " Si vous avez besoin d'aide urgente, dites simplement au secours."},
    "unclear":    {"en": "Sorry, I didn't quite understand. Could you say that another way?",
                   "fr": "Désolé, je n'ai pas bien compris. Pouvez-vous le dire autrement ?"},
    "unclear_options": {"en": "I'm not sure I understood. I can help with: {options}. Which one do you need?",
                        "fr": "Je ne suis pas sûr d'avoir compris. Je peux aider avec : {options}. "
                              "Lequel vous faut-il ?"},
}


# ---------------------------------------------------------------- danger and cancel

DANGER = _rx(
    # English
    r"^\W*(please\W+)?help(\W+me)?(\W+please)?\W*$",
    r"\bsos\b",
    rf"\b(it{AP}?s an?|this is an?|medical) emergency\b",
    r"\bcall (the )?(police|ambulance|samu|999|112|114)\b",
    rf"\b(i{AP}?m|i am) (so )?(scared|afraid|terrified|in danger|being followed|hurt|bleeding|trapped)\b",
    rf"\bsomeone({AP}?s| is)? (following|attacking|hitting|hurting|chasing|threatening) me\b",
    rf"\b(he|she|they)({AP}?s| is| are) (hitting|hurting|beating|attacking|threatening|following) me\b",
    rf"\b(can{AP}?t|cannot) breathe\b",
    rf"\b(fell|fallen)( down)? and (i )?can{AP}?t get up\b",
    r"\bheart attack\b",
    # French
    r"^\W*(à|a) l['’ ]?aide\W*$",
    r"\bau secours\b|\baidez[- ]moi\b|\baide[- ]moi\b",
    rf"\bc{AP}est une urgence\b|\burgence médicale\b",
    r"\bappel(le|ez|er) (la police|le samu|les secours|une ambulance|le 999|le 112|le 114)\b",
    rf"\bj{AP}\s?ai (très )?peur\b|\bje suis (en danger|blessée?|suivie?|coincée?)\b",
    r"\b(quelqu['’]un|on|il|elle|ils) me (suit|suivent|frappe|frappent|bat|battent|menace|menacent|attaque|"
    r"attaquent|poursuit|poursuivent)\b",
    r"\bje (ne )?(peux|arrive) (pas|plus) (à )?respirer\b",
    r"\bje suis tombée? et je (ne )?(peux|arrive) pas (à )?me relever\b",
    r"\bcrise cardiaque\b",
)

CANCEL = re.compile(
    r"^\W*(cancel|never ?mind|forget it|stop|nothing|no thanks?"
    r"|annule[rz]?|laisse(z)? tomber|oublie[z]?|rien|non merci|c['’]est bon|arrête[z]?)\W*$", re.I)


def is_danger(text):
    # Check each sentence on its own too, so "I'm going out. Help!" (an answer merged in) still counts.
    parts = [text or "", *re.split(r"[.!?]+", text or "")]
    return any(p.search(part) for part in parts for p in DANGER)


def is_cancel(text):
    return bool(CANCEL.match(text or ""))


# ---------------------------------------------------------------- detail detectors

EN_NUMBERS = "one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|fifteen|twenty|thirty|forty|forty-five"
FR_NUMBERS = ("une?|deux|trois|quatre|cinq|six|sept|huit|neuf|dix|onze|douze|quinze|vingt|trente|quarante|"
              "quarante-cinq")
TIME = re.compile(
    r"\b(\d{1,2}[:h.]\d{2}"                                                    # 14:30, 2h30
    r"|\d{1,2}\s*(am|pm|h)\b"                                                   # 2pm, 14h
    r"|\d{1,2}\s+heures?"                                                       # 5 heures
    r"|noon|midday|midnight|tonight|this (morning|afternoon|evening)|tomorrow( morning)?"
    rf"|(by|at|until|till|around|before)\s+(\d{{1,2}}|{EN_NUMBERS})"            # by two, at 5
    rf"|(\d{{1,3}}|{EN_NUMBERS}|an?|half an?)\s+(minutes?|mins?|hours?|hrs?)"    # ten minutes
    r"|half an hour|an hour"
    r"|midi|minuit|ce soir|cet après-midi|ce matin|demain( matin| soir)?|une demi-heure"
    rf"|(vers|avant|à|a|jusqu{AP}à)\s+({FR_NUMBERS})\s+heures?"                 # vers deux heures
    rf"|(\d{{1,3}}|{FR_NUMBERS}|une demi)\s+(minutes?|heures?))\b", re.I)        # dix minutes

PLACE_WORDS = re.compile(
    r"\b(home|work|school|uni|university|campus|the (beach|sea|market|shop|shops|gym|hospital|clinic|"
    r"office|station|airport|mall|bus stop|mountain|trail)|church|temple|mosque|town"
    r"|maison|travail|boulot|école|université|fac|plage|mer|marché|magasin|gym|hôpital|clinique|bureau|"
    r"gare|aéroport|église|mosquée|ville|montagne)\b", re.I)
NOT_A_PLACE = set(f"""a an the my your his her our their be bed get go come see do make about around now later soon
    today tonight tomorrow noon midnight morning afternoon evening night while bit case back minutes minute hours hour
    half time {EN_NUMBERS.replace('|', ' ')}
    la le les l un une mon ma mes ton ta son sa nos vos leur peu moment rien quelques minutes heure heures
    midi minuit demain soir matin retour quel quelle {FR_NUMBERS.replace('|', ' ').replace('?', '')} un une""".split())
PLACE_AFTER = re.compile(
    rf"\b(?:to|at|towards?|up|near|in|from|for|leaving|via|vers|pour|chez|au|aux|à|de|près de)\s+"
    rf"(?:the\s+|la\s+|le\s+|les\s+|l{AP}\s*)?([a-zà-ÿ][\w'’-]*)", re.I)

FILLER = set("""yes yeah no ok okay um uh er erm and back by at i i'm im will be going to it is it's in on about around
    for until till maybe like just so well then the a
    dunno idk know don't dont not sure whatever somewhere anywhere out there here
    oui non euh bah ben je j j'sais sais pas ne vais être suis à au aux vers dans pour de la le les l en et
    c'est bon peut-être reviens rentre serai là quelque part n'importe où sais-pas""".split())


def has_time(text):
    return bool(TIME.search(text))


def has_place(text):
    if PLACE_WORDS.search(text):
        return True
    return any(m.group(1).lower() not in NOT_A_PLACE for m in PLACE_AFTER.finditer(text))


def content_words(text):
    # What is left of an answer once times and filler words are taken out.
    words = re.findall(r"[a-zà-ÿ0-9][\w'’-]*", TIME.sub(" ", text).lower())
    return [w for w in words if w not in FILLER]


# ---------------------------------------------------------------- rules: actions that need details

@dataclass
class Rule:
    name: str
    trigger: re.Pattern
    slots: list                # detail names, in the order we ask for them
    questions: dict            # language -> {tuple of missing slots -> the question to ask}
    detect: dict               # slot -> function(full_text, match) -> True if present


def _message_after(match):
    # For "tell my family ..." style rules: the message is whatever follows the trigger.
    rest = match.group("rest") or match.group("reste") or ""
    return len(content_words(rest)) >= 1


# Built-in rules: fast, model-free checks for the most common actions. Tools passed in as `needs`
# work without any rule. REPEAT PER ACTION: copy one Rule(...) block; first match wins.
RULES = [
    Rule(
        name="running_late",
        trigger=re.compile(
            rf"\b(i{AP}?ll|i will|i{AP}?m going to|gonna) be late\b|\bextend (my )?(trip|time|check-?in)\b"
            r"|\bje (serai|vais être|vais etre|suis) en retard\b|\bprolonge[rz]? (mon|le) (trajet|temps)\b", re.I),
        slots=["time"],
        questions={"en": {("time",): "By how long?"},
                   "fr": {("time",): "De combien de temps ?"}},
        detect={"time": lambda text, m: has_time(text)},
    ),
    Rule(
        name="scam_check",
        trigger=re.compile(
            r"\b(scam|fraud|phishing)\b|\bis (this|it|that) (real|legit|genuine|true)\b"
            r"|\b(strange|weird|suspicious|fake) (message|sms|text|call|email|whatsapp)\b"
            rf"|\b(arnaque|escroquerie|fraude|hameçonnage)\b|\bc{AP}est (vrai|réel|vraiment ma banque)\b"
            r"|\b(message|sms|appel) (bizarre|suspect|étrange|frauduleux)\b", re.I),
        slots=["message"],
        questions={"en": {("message",): "Please read me the message you received. "
                                        "Don't read out any card numbers or codes."},
                   "fr": {("message",): "Lisez-moi le message que vous avez reçu. "
                                        "Ne lisez pas de numéro de carte ni de code."}},
        detect={"message": lambda text, m: len(content_words(m.re.sub(" ", text))) >= 5},
    ),
    Rule(
        name="tell_family",
        trigger=re.compile(
            r"\b(tell|message|text|warn|remind|let)\s+(my\s+)?(family|mum|mom|mother|dad|father|son|"
            r"daughter|sister|brother|wife|husband|parents?|contacts?|neighbou?r|circle)"
            r"(\s+know)?(\s+that)?\s*[:,]?(?P<rest>.*)$"
            r"|\b(dis|dites|préviens|prévenez|rappelle|rappelez|écris|écrivez)\s+(à\s+)?(ma |mon |mes )?"
            r"(famille|mère|maman|père|papa|fils|fille|sœur|soeur|frère|femme|mari|parents|contacts?|voisine?)"
            r"(\s+que)?\s*[:,]?(?P<reste>.*)$", re.I),
        slots=["message"],
        questions={"en": {("message",): "What would you like me to tell them?"},
                   "fr": {("message",): "Que voulez-vous que je leur dise ?"}},
        detect={"message": lambda text, m: _message_after(m)},
    ),
    Rule(
        name="check_in",
        trigger=re.compile(
            rf"(^\W*|\b(i{AP}?m|i am|we{AP}?re|we are)\s+)(going out|heading( out| to| home| off)?|leaving|"
            r"walking home|going home|going fishing|going hiking|going (out )?to sea|off to|on my way)\b"
            r"|\b(start|begin) (a |my )?(trip|check-?in)\b|\bcheck on me\b"
            rf"|(^\W*|\b(je|on)\s+)(sors|pars|vais sortir|rentre|m{AP}en vais|vais à la pêche|vais pêcher|"
            r"vais à la mer|vais en mer|vais randonner|vais faire une randonnée)\b"
            r"|\bje suis en route\b|\bsurveille[rz]?[- ]moi\b", re.I),
        slots=["place", "time"],
        questions={"en": {("place", "time"): "Where are you going, and when will you be back?",
                          ("place",): "Where are you going?",
                          ("time",): "When should I expect you back?"},
                   "fr": {("place", "time"): "Où allez-vous, et quand serez-vous de retour ?",
                          ("place",): "Où allez-vous ?",
                          ("time",): "À quelle heure dois-je vous attendre ?"}},
        detect={"place": lambda text, m: has_place(text), "time": lambda text, m: has_time(text)},
    ),
]


def match_rule(text):
    for rule in RULES:
        match = rule.trigger.search(text or "")
        if match:
            return rule, match
    return None, None


def missing_details(text, state=None):
    # Which required details are still missing. Returns (rule, [slots]) or (None, []).
    rule, match = match_rule(state.original if state else text)
    if rule is None:
        return None, []
    missing = [s for s in rule.slots if not rule.detect[s](text, match)]
    if state:
        # An answer to our question fills the detail it was asked for, even without keywords:
        # "Where are you going?" -> "Le Pouce" has no "to"/"at", but it is clearly the place.
        for slot in list(missing):
            if slot in state.asked and any(_answer_fills(slot, a) for a in state.answers):
                missing.remove(slot)
    return rule, missing


def _answer_fills(slot, answer):
    if slot == "time":
        return has_time(answer)
    if slot == "message":
        return len(content_words(answer)) >= 2
    return len(content_words(answer)) >= 1


def needs_clarifier(text, state=None):
    # Router hook: True = skip normal routing and send this to the clarifier.
    return is_danger(text) or bool(missing_details(text, state)[1])


# ---------------------------------------------------------------- the decision

SENSITIVE = re.compile(r"\b(card|cvv|pin|password|passcode|otp|one[- ]time|account number|bank details"
                       r"|carte|mot de passe|code)\b", re.I)
KEEP_EXACT_WORDING = {"scam_check"}   # its built-in question carries a safety warning: never reworded


def ask_for_tool_details(needs):
    # Any tool, any theme: build the question from the tool's own `asks`, or from the parameter name.
    if len(needs) == 1:
        need = needs[0]
        return need.get("question") or f"Could you tell me the {need['param'].replace('_', ' ')}?"
    labels = [n["param"].replace("_", " ") for n in needs]
    return f"Could you tell me the {', '.join(labels[:-1])} and {labels[-1]}?"


def check_ai_question(text):
    # Accept the AI's question only if it is one short, safe question. None = use the built-in one.
    lines = [line.strip().strip('"“”') for line in (text or "").splitlines() if line.strip()]
    if not lines:
        return None
    question = lines[0]
    if not question.endswith("?") or question.count("?") > 2:
        return None
    if len(question.split()) > SETTINGS["max_question_words"]:
        return None
    if SENSITIVE.search(question) or "NEED_DETAILS" in question or "CANNOT_HELP" in question:
        return None
    return question


def ai_question(ask_llm, original, answers, missing, fallback, options, lang):
    # Let a model word the question to fit the conversation. Any failure -> the built-in question.
    language = "French" if lang == "fr" else "English"
    system = ("You are the Clarifier of a voice safety assistant. Write ONE short question the "
              "assistant will say out loud. Ask only for what is missing. Plain, friendly words, "
              f"at most {SETTINGS['max_question_words']} words. Never ask for card numbers, PINs, "
              f"passwords or codes. Reply with the question only, in {language}.")
    lines = [f"What the user asked: {original}"]
    if answers:
        lines.append("Their answers so far (they did not give what was needed): " + " | ".join(answers))
        lines.append("Rephrase rather than repeating the same question.")
    lines.append("Missing: " + (", ".join(m.replace("_", " ") for m in missing) if missing
                                else "it is not clear what they need"))
    if options:
        lines.append("What the assistant can help with: " + ", ".join(options))
    lines.append(f"A plain version of the question: {fallback}")
    try:
        return check_ai_question(ask_llm(system, "\n".join(lines))) or fallback
    except Exception:
        return fallback


def plan(text, state=None, sos_ready=False, needs=None, danger_hint=False, ask_llm=None, options=None):
    # Decide what the Clarifier says this turn. `text` is the request (already merged with answers).
    # needs: details a tool is missing. danger_hint: another detector (e.g. Jev) thinks it is an emergency.
    # ask_llm: optional AI to word the question. options: names of what the assistant can help with.
    original = state.original if state else text
    attempts = state.attempts if state else 0
    answers = state.answers if state else []
    lang = detect_lang(original)

    # 1. Danger always wins, even in the middle of the loop. Fixed wording, no AI.
    if danger_hint or is_danger(text):
        say = SAY["sos" if sos_ready else "sos_no_agent"][lang]
        return Plan("sos", original, say, escalate=sos_ready, lang=lang)

    # 2. Optional limit. By default there is none: it keeps asking until the request is complete.
    limit = SETTINGS["max_questions"]
    if limit is not None and attempts >= limit:
        say = SAY["give_up" if sos_ready else "give_up_no_agent"][lang]
        return Plan("give_up", original, say, escalate=sos_ready, lang=lang)

    # 3. What is missing, and the built-in question for it.
    if needs:
        intent, missing, fallback = needs[0]["tool"], [n["param"] for n in needs], ask_for_tool_details(needs)
    else:
        rule, missing = missing_details(text, state)
        if rule and missing:
            intent, fallback = rule.name, rule.questions[lang][tuple(missing)]
        else:
            intent, missing = (rule.name if rule else None), []
            fallback = (SAY["unclear_options"][lang].format(options=", ".join(options)) if options
                        else SAY["unclear"][lang])
    if state and missing and set(missing) == set(state.asked):
        fallback = SAY["again"][lang] + fallback          # asking for the same thing again

    # 4. The AI words it (optional), except where the exact wording matters.
    question = fallback
    if ask_llm is not None and intent not in KEEP_EXACT_WORDING:
        question = ai_question(ask_llm, original, answers, missing, fallback, options, lang)

    # 5. Every few questions, remind them there is always a way out.
    every = SETTINGS["help_every"]
    if every and (attempts + 1) % every == 0:
        question += SAY["help_hint"][lang]
    return Plan("ask", original, question, intent, missing, lang=lang)


# ---------------------------------------------------------------- the loop (turn by turn)

QUESTION_START = re.compile(
    r"^\W*(what|when|where|who|why|how|which|is|are|can|could|should|do|does|will|would"
    r"|qu['’]est-ce|est-ce|que|quoi|quand|où|qui|pourquoi|comment|quel|quelle|quels|quelles|puis-je|pouvez-vous)\b",
    re.I)


def looks_like_new_request(user_text, state):
    # An answer is short and is not itself a question. A new question, or a long reply to a
    # general "what do you need?" question, is a fresh request rather than an answer.
    if is_danger(user_text):
        return False
    if "?" in user_text or QUESTION_START.match(user_text):
        return True
    return not state.asked and len(user_text.split()) > 6


def resume(state, user_text):
    # Start of a turn. Returns (state, text_to_handle, reply_now).
    if state is None:
        return None, user_text, None
    if is_cancel(user_text):
        return None, None, SAY["cancelled"][detect_lang(state.original)]
    if looks_like_new_request(user_text, state):
        return None, user_text, None   # they moved on: drop the old question, route this on its own
    state.answers.append(user_text)
    merged = ". ".join([state.original.rstrip(" .?!"), *(a.strip(" .") for a in state.answers)])
    return state, merged, None


def after_turn(state, results):
    # End of a turn. `results`: objects with .output and .meta (the Clarifier's reply among them).
    # Returns (new_state, sos_task). new_state set = we asked a question and wait for the answer.
    # sos_task set = offer the SOS agent as a yes/no.
    for result in results:
        meta = getattr(result, "meta", {}) or {}
        if not meta.get("clarification"):
            continue
        if meta["kind"] != "ask":
            task = ("Send an emergency alert to the user's emergency contacts now. "
                    f"What the user said: '{meta['original']}'")
            return None, task if meta["escalate"] else None
        attempts = (state.attempts if state else 0) + 1
        answers = state.answers if state else []
        return ClarifyState(meta["original"], result.output, list(meta["missing"]), list(answers), attempts), None
    return None, None


# ---------------------------------------------------------------- simple interface for any project

@dataclass
class Turn:
    action: str          # "ask" | "proceed" | "sos" | "cancelled"
    say: str = None      # what to say to the user (None on "proceed")
    request: str = None  # the full request so far, every answer included


@dataclass
class _Reply:
    output: str
    meta: dict


class Clarifier:
    """Drop-in Clarifier. Keeps each user's half-finished request until it is complete."""

    def __init__(self, ask_llm=None, sos_available=True, options=None, **settings):
        # ask_llm: optional function (system, user) -> text. sos_available: you have an emergency flow.
        # options: names of what your assistant can do, offered when a request is unclear.
        if settings:
            configure(**settings)
        self.ask_llm, self.sos_available, self.options = ask_llm, sos_available, options or []
        self.sessions = {}

    def step(self, user_text, session="default", unclear=False, needs=None, danger_hint=False):
        state = self.sessions.pop(session, None)
        state, text, cancelled = resume(state, user_text)
        if cancelled:
            return Turn("cancelled", cancelled)
        if not (unclear or needs or danger_hint or needs_clarifier(text, state)):
            return Turn("proceed", request=text)
        decision = plan(text, state, self.sos_available, needs, danger_hint, self.ask_llm, self.options)
        new_state, _ = after_turn(state, [_Reply(decision.question, decision.meta())])
        if new_state is not None:
            self.sessions[session] = new_state
            return Turn("ask", decision.question, text)
        return Turn("sos", decision.question, text)

    def waiting(self, session="default"):
        # True while this user owes us an answer.
        return session in self.sessions
