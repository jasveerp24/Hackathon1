import logging
import os

from config import CONFIG

log = logging.getLogger("jarvis")

# Jev is a System One model: it never writes text. You send a `state` plus typed questions
# and get typed answers with calibrated probabilities back. The SDK accepts plain dicts,
# so we build questions as dicts and do not need to import the SDK until a key exists.


def noul_question(instructions):
    # Yes/no question. The answer's .noul is the probability of yes.
    return {"type": "noul", "instructions": instructions}


def choice_question(instructions, options):
    # Pick one label. `options` maps label -> short description (descriptions max 255 chars).
    return {"type": "choice", "instructions": instructions, "criteria": options}


def _get(answer, key):
    if isinstance(answer, dict):
        return answer.get(key)
    return getattr(answer, key, None)


def read_noul(answer):
    return float(_get(answer, "noul"))


def read_choice(answer):
    # Returns (label, confidence, probabilities)
    return (
        _get(answer, "choice"),
        float(_get(answer, "confidence")),
        dict(_get(answer, "probabilities") or {}),
    )


class JevClient:
    def __init__(self):
        self.client = None
        if os.getenv("TYPESAFE_API_KEY"):  # pip install typesafe-sdk
            from typesafe_sdk import TypeSafeClient
            self.client = TypeSafeClient()

    @property
    def live(self):
        return self.client is not None

    def ask(self, state, questions):
        # Returns {question_name: answer}, or None if Jev is unavailable or failed.
        # None is the signal for every caller to fall to the next layer.
        if not self.live:
            return None
        try:
            response = self.client.system_one(
                state=state,
                questions=questions,
                model=CONFIG["jev_model"],
                timeout=CONFIG["jev_timeout_s"],
            )
            return response.answers
        except Exception as error:
            log.warning("Jev call failed (%s)", error)
            return None
