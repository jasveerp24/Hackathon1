# Clarifier agent (Anjali)

The Clarifier steps in when a request can't be acted on yet, and keeps asking until it can:

- **Danger** ("someone is following me", or Jev's danger score) → no questions, SOS offer straight away.
- **A detail is missing** ("I'm going out", or a tool needs an area) → asks for exactly what is missing.
- **Unclear** (Jev's clear score) → asks the user to say more.

Each answer is added to the original request. It keeps asking until nothing is missing; there is no
fixed number of questions. Danger words, "never mind" or a new question end the loop at any time,
and every 3rd question reminds the user they can just say "help". When an AI model is available it
words the questions; every AI question is safety-checked, with built-in questions as the backup.
Full explanation with diagrams: `Clarifier_Agent_Team_Guide.pdf`.

## What's in this folder

| File | What it is |
|---|---|
| `clarifier.py` | The whole Clarifier in **one standalone file**: no other files, packages or API keys needed |
| `test_clarifier.py` | 23 tests of `clarifier.py` on its own: `python test_clarifier.py` |
| `jarvis_code.patch` | The changes that plug the Clarifier into `jarvis_code/` (not applied yet, for Jasveer to review) |
| `Clarifier_Agent_Team_Guide.pdf` | The team guide |

**Nothing outside this folder was changed.**

## Use it in any project

```python
from clarifier import Clarifier
clarifier = Clarifier()                 # optional: Clarifier(ask_llm=my_ai_function)
turn = clarifier.step("I'm going out")  # once per user message
```

| `turn.action` | What your app does |
|---|---|
| `ask` | Say `turn.say`, then pass the user's reply to `step()` again |
| `proceed` | The request is complete: handle `turn.request` (every answer included) |
| `sos` | Say `turn.say` (the SOS offer) and start your emergency flow |
| `cancelled` | Say `turn.say` |

## Plug it into JARVIS (Jasveer)

From the repo root, check then apply the patch:

```
git apply --check clarifier/jarvis_code.patch
git apply clarifier/jarvis_code.patch
```

It adds `clarifier.py` and two test files to `jarvis_code/`, and makes small changes to `agents.py`,
`orchestrator.py`, `config.py`, `providers.py` and `README.txt`, all marked `CLARIFIER`:

- a "sos" agent now holds `send_alert`, so health searches don't ask to confirm
- tools can carry `asks={...}` questions; agents reply `NEED_DETAILS` instead of guessing
- one extra Jev question, `is_danger`, in the same call
- fix: Claude replies with a "thinking" block crashed every Claude call (`providers.py`)

Then run `python test_clarifier.py` (23/23) and `python test_clarifier_jarvis.py` (21/21) inside `jarvis_code/`.
