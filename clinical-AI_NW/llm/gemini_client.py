import logging
import os

from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# Fail fast rather than blocking a request indefinitely on a slow/overloaded
# model (observed: a single call taking ~90s against an experimental model
# under high demand). Configurable since acceptable latency varies by model.
DEFAULT_TIMEOUT_MS = 30_000


class GeminiLLM:
    def __init__(self):
        timeout_ms = int(os.getenv("GEMINI_TIMEOUT_MS", DEFAULT_TIMEOUT_MS))
        self.client = genai.Client(
            api_key=os.getenv("GEMINI_API_KEY"),
            http_options=types.HttpOptions(timeout=timeout_ms),
        )
        self.model = os.getenv("GEMINI_MODEL")
        logger.debug("GeminiLLM ready (model=%s, timeout_ms=%s)", self.model, timeout_ms)

    def generate(self, system_prompt, user_prompt):
        response = self.client.models.generate_content(
            model=self.model,
            contents=user_prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=0.2
            )
        )
        return response.text
