JARVIS voice assistant - code

BACKEND (Python, folder root) - keep all the .py files together
  config.py        every threshold, timeout and model name
  jev.py           Jev (System One) client: yes/no and choice questions with probabilities
  providers.py     text models in priority order: Claude -> Gemini (add more here)
  orchestrator.py  the layers: governance, router, agent chains, safety gate, verifier
  agents.py        ActionAgent, RagAgent, ClarifierAgent + YOUR specs and tools
  server.py        FastAPI door: POST /chat
  pip install fastapi uvicorn anthropic google-genai typesafe-sdk
  python agents.py                                   text demo (mock mode works with no keys)
  uvicorn server:app --host 0.0.0.0 --port 8000      backend for the phone app
  Optional keys: TYPESAFE_API_KEY (Jev), ANTHROPIC_API_KEY (Claude), GEMINI_API_KEY (Gemini)
  Each layer that has no key is skipped, so the cascade degrades instead of crashing.

APP (React Native / Expo, folder app/)
  see the file list in app/src ; settings are all in app/src/config.js
  Copy the contents of app/ into your Expo project (replace its App.js), then:
    npx expo install expo-speech
    npm install @react-native-voice/voice
  Speech recognition needs a DEVELOPMENT BUILD (npx expo run:android / run:ios), not Expo Go.

Search the .py files for "REPEAT" (copy a block for a new agent) and "REPLACE LATER" (placeholders).
