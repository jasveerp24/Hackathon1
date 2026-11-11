import logging
import os
from abc import ABC, abstractmethod

from config import CONFIG

log = logging.getLogger("jarvis")

# Text-generating models (Jev cannot write text, so it is not in this list).
# A ProviderChain tries them in order and moves on when one fails or times out.


class LLMProvider(ABC):
    name = "base"

    @abstractmethod
    def available(self): ...

    @abstractmethod
    def complete(self, system, user, max_tokens=600): ...


class ClaudeProvider(LLMProvider):
    name = "claude"

    def __init__(self):
        self.client = None
        if os.getenv("ANTHROPIC_API_KEY"):  # pip install anthropic
            import anthropic
            self.client = anthropic.Anthropic(timeout=CONFIG["llm_timeout_s"], max_retries=1)

    def available(self):
        return self.client is not None

    def complete(self, system, user, max_tokens=600):
        response = self.client.messages.create(
            model=CONFIG["claude_model"],
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return response.content[0].text


class GeminiProvider(LLMProvider):
    name = "gemini"

    def __init__(self):
        self.client = None
        if os.getenv("GEMINI_API_KEY"):  # pip install google-genai
            from google import genai
            self.client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

    def available(self):
        return self.client is not None

    def complete(self, system, user, max_tokens=600):
        from google.genai import types
        response = self.client.models.generate_content(
            model=CONFIG["gemini_model"],
            contents=user,
            config=types.GenerateContentConfig(system_instruction=system, max_output_tokens=max_tokens),
        )
        return response.text


# ADD ANOTHER PROVIDER HERE: copy GeminiProvider, change the client and the complete() call.


class ProviderChain:
    def __init__(self, providers):
        self.providers = providers

    @property
    def live(self):
        return any(provider.available() for provider in self.providers)

    def complete(self, system, user, max_tokens=600):
        failures = []
        for provider in self.providers:
            if not provider.available():
                continue
            try:
                return provider.complete(system, user, max_tokens)
            except Exception as error:
                log.warning("provider %s failed (%s), trying the next one", provider.name, error)
                failures.append(f"{provider.name}: {error}")
        raise RuntimeError(f"No text model answered. {failures}")


claude = ClaudeProvider()
gemini = GeminiProvider()

# The order here IS the priority. Reorder or remove providers on this line only.
text_llm = ProviderChain([claude, gemini])
