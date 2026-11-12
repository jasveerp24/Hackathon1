"""
Tests for clarifier.py ON ITS OWN: no other project files, no API keys, no packages.
Copy clarifier.py + this file into any folder and run:  python test_clarifier.py
(test_clarifier_jarvis.py tests the same Clarifier plugged into JARVIS.)
"""
import os
import shutil
import subprocess
import sys
import tempfile

import clarifier
from clarifier import Clarifier, has_place, has_time, is_danger, missing_details

ASK_BOTH = "Where are you going, and when will you be back?"
AGAIN = "Sorry, I didn't catch that. "
HELP = "If you need urgent help, just say help."


def chat(*messages, **kwargs):
    c = Clarifier(**kwargs)
    return c, [c.step(m) for m in messages]


# ---------------------------------------------------------------- the loop

def test_asks_then_proceeds_with_the_full_request():
    c, t = chat("I'm going out", "Le Pouce, back by two")
    assert (t[0].action, t[0].say) == ("ask", ASK_BOTH), t[0]
    assert t[1].action == "proceed"
    assert t[1].request == "I'm going out. Le Pouce, back by two"
    assert not c.waiting()


def test_asks_only_for_what_is_still_missing():
    _, t = chat("I'm going out", "in ten minutes", "Trou aux Cerfs")
    assert t[1].say == "Where are you going?", t[1]
    assert t[2].action == "proceed"


def test_no_fixed_limit_keeps_asking():
    _, t = chat("I'm going out", *["dunno"] * 7)
    assert all(turn.action == "ask" for turn in t), [turn.action for turn in t]
    assert t[1].say.startswith(AGAIN)                      # asking for the same thing again
    help_turns = [i + 1 for i, turn in enumerate(t) if turn.say.endswith(HELP)]
    assert help_turns == [3, 6], help_turns                # a way out on every 3rd question


def test_optional_limit():
    try:
        _, t = chat("I'm going out", "dunno", "dunno", max_questions=2)
        assert t[2].action == "sos" and "still not sure" in t[2].say, t[2]
    finally:
        clarifier.configure(max_questions=None)


# ---------------------------------------------------------------- ways out of the loop

def test_danger_skips_questions():
    _, t = chat("someone is following me")
    assert t[0].action == "sos" and "may be in danger" in t[0].say


def test_danger_in_the_middle_of_the_loop():
    c, t = chat("I'm going out", "dunno", "help")
    assert t[2].action == "sos", t[2]
    assert not c.waiting()


def test_danger_from_another_detector():
    _, t = chat("there's a man behind me and I don't feel ok")      # not on the keyword list
    assert t[0].action == "proceed"
    c = Clarifier()
    assert c.step("there's a man behind me and I don't feel ok", danger_hint=True).action == "sos"


def test_no_emergency_flow_says_call_999():
    _, t = chat("I can't breathe", sos_available=False)
    assert "call 999" in t[0].say


def test_cancel():
    c, t = chat("I'm going out", "never mind")
    assert (t[1].action, t[1].say) == ("cancelled", "Okay, cancelled.")
    assert not c.waiting()


def test_new_question_drops_the_old_one():
    _, t = chat("I'm going out", "When is the next bus from Curepipe?")
    assert t[1].action == "proceed" and t[1].request == "When is the next bus from Curepipe?"


# ---------------------------------------------------------------- any tool, any theme

def test_tool_question():
    c = Clarifier()
    needs = [{"tool": "find_pharmacy", "param": "area", "question": "Which area are you in?"}]
    assert c.step("Find a pharmacy", needs=needs).say == "Which area are you in?"
    assert c.step("Rose-Hill").request == "Find a pharmacy. Rose-Hill"


def test_tool_without_a_question_gets_one():
    c = Clarifier()
    one = [{"tool": "book_taxi", "param": "pickup_point"}]
    two = [{"tool": "book_taxi", "param": "date"}, {"tool": "book_taxi", "param": "city"}]
    assert c.step("Book a taxi", session="a", needs=one).say == "Could you tell me the pickup point?"
    assert c.step("Book a taxi", session="b", needs=two).say == "Could you tell me the date and city?"


def test_unclear_offers_options():
    c = Clarifier(options=["transport", "health", "info"])
    turn = c.step("can you sort it out", unclear=True)
    assert turn.say == "I'm not sure I understood. I can help with: transport, health, info. Which one do you need?"


def test_other_built_in_questions():
    assert chat("Tell my family")[1][0].say == "What would you like me to tell them?"
    assert chat("Is this a scam?")[1][0].say.startswith("Please read me the message")
    assert chat("I'll be late")[1][0].say == "By how long?"


def test_complete_requests_go_straight_through():
    for text in ["Leaving Ebene, home by eleven", "I'm going to Curepipe, back at 5pm",
                 "When is the next bus from Curepipe?", "Tell my family I'm safe",
                 "My bank says my account is blocked, is it real?", "Can you help me find a clinic?"]:
        assert Clarifier().step(text).action == "proceed", text


# ---------------------------------------------------------------- AI-written questions

def test_ai_writes_the_question():
    ai = lambda system, user: "Where are you heading, and roughly when will you be home?"
    _, t = chat("I'm going out", ask_llm=ai)
    assert t[0].say == "Where are you heading, and roughly when will you be home?"


def test_bad_ai_questions_fall_back_to_built_in():
    for bad in ["Sure! Here you go.",                                   # not a question
                "Can you read me your card number so I can check?",    # asks for private data
                "Could you " + "please " * 30 + "tell me where?"]:      # far too long
        _, t = chat("I'm going out", ask_llm=lambda s, u, bad=bad: bad)
        assert t[0].say == ASK_BOTH, (bad, t[0].say)


def test_ai_down_falls_back():
    def broken(system, user):
        raise TimeoutError("no network")
    assert chat("I'm going out", ask_llm=broken)[1][0].say == ASK_BOTH


def test_ai_never_rewords_safety_messages():
    ai = lambda s, u: "What's up?"
    assert chat("Is this a scam?", ask_llm=ai)[1][0].say.startswith("Please read me the message")
    assert "may be in danger" in chat("help me", ask_llm=ai)[1][0].say


# ---------------------------------------------------------------- languages, detectors, sessions

def test_english_by_default_french_optional():
    assert chat("Je sors")[1][0].say == ASK_BOTH
    try:
        clarifier.configure(languages=["en", "fr"])
        assert chat("Je sors")[1][0].say == "Où allez-vous, et quand serez-vous de retour ?"
    finally:
        clarifier.configure(languages=["en"])


def test_detectors():
    assert has_time("back by two") and has_time("in half an hour") and has_time("at 14:30")
    assert has_place("to Le Pouce") and has_place("going home") and not has_place("going out for a walk")
    assert is_danger("Help me!") and is_danger("I can't breathe") and is_danger("au secours")
    assert not is_danger("Can you help me find a clinic?") and not is_danger("What's the emergency number?")
    assert not missing_details("Leaving Ebene, home by eleven")[1]


def test_users_do_not_share_questions():
    c = Clarifier()
    c.step("I'm going out", session="anjali")
    assert c.waiting("anjali") and not c.waiting("ravi")
    assert c.step("When is the next bus?", session="ravi").action == "proceed"


def test_works_alone_in_an_empty_folder():
    # The real proof of "standalone": copy ONLY clarifier.py into an empty folder and use it.
    folder = tempfile.mkdtemp()
    shutil.copy(os.path.join(os.path.dirname(os.path.abspath(__file__)), "clarifier.py"), folder)
    code = "from clarifier import Clarifier; print(Clarifier().step(\"I'm going out\").say)"
    out = subprocess.run([sys.executable, "-c", code], cwd=folder, capture_output=True, text=True)
    assert out.stdout.strip() == ASK_BOTH, out.stderr


if __name__ == "__main__":
    tests = [(n, f) for n, f in globals().items() if n.startswith("test_")]
    failed = 0
    for name, fn in tests:
        try:
            fn()
            print("PASS", name)
        except AssertionError as error:
            failed += 1
            print("FAIL", name, "->", error)
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    raise SystemExit(1 if failed else 0)
