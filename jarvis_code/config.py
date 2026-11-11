import os

# Every threshold and model name lives here so the logic files never hardcode them.
CONFIG = {
    "claude_model": os.getenv("CLAUDE_MODEL", "claude-sonnet-5-5"),
    "gemini_model": os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),  # check the current model name
    "jev_model": os.getenv("JEV_MODEL", "jev-latest"),

    # How long a layer may take before we give up on it and fall to the next one.
    "jev_timeout_s": 4.0,
    "llm_timeout_s": 20.0,

    # Routing layer: Jev decides first, and only escalates to the text LLM when unsure.
    "route_confidence": 0.70,   # Jev's pick must be at least this confident to be trusted
    "clear_floor": 0.50,        # below this, the request is too vague: go ask the user

    # Safety gate (per agent attempt)
    "jev_proceed": 0.80,        # at or above: run automatically
    "jev_confirm": 0.50,        # between confirm and proceed: ask the user first

    # Verification layer: does the agent's reply really answer the request?
    "answer_floor": 0.50,

    "max_steps": 4,             # cap on how many routed steps one request may chain
    "terminal_agent": "clarifier",   # last resort when every agent in a chain gave up
    "audit_log": "audit.jsonl",
}
