"""Runtime settings: read the single secret from the environment and build the
OpenAI client. ``OPENAI_API_KEY`` is the *only* env var this project uses."""

import os
from dataclasses import dataclass

from dotenv import load_dotenv
from openai import OpenAI


@dataclass(frozen=True)
class Settings:
    openai_api_key: str

    def client(self) -> OpenAI:
        return OpenAI(api_key=self.openai_api_key)


def load_settings() -> Settings:
    """Load ``OPENAI_API_KEY`` from the environment (or a local ``.env``).

    Raises ``RuntimeError`` if it is missing -- failing loud here is better than
    a confusing 401 deep inside an upload call.
    """
    load_dotenv()
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        raise RuntimeError(
            "OPENAI_API_KEY is not set. Add it to the environment or a .env file "
            "(see .env.example)."
        )
    return Settings(openai_api_key=key)
