"""OpenAI provider (GPT models) via the official ``openai`` SDK.

Needs:  pip install openai
Key:    export OPENAI_API_KEY="sk-..."
Model:  OPENAI_MODEL env var, or --model flag (default: gpt-4o-mini)
"""

from __future__ import annotations

import os

from . import register
from .base import LLMProvider, ProviderError


@register
class OpenAIProvider(LLMProvider):
    name = "openai"

    def __init__(self, model: str | None = None) -> None:
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise ProviderError(
                "the 'openai' package is missing; install it with: pip install openai"
            ) from exc

        if not os.environ.get("OPENAI_API_KEY"):
            raise ProviderError(
                'OPENAI_API_KEY is not set. Get a key at https://platform.openai.com/api-keys '
                'and run: export OPENAI_API_KEY="sk-..."'
            )

        self._model = model or os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
        self._client = OpenAI()

    def complete(self, system: str, user: str) -> str:
        response = self._client.chat.completions.create(
            model=self._model,
            temperature=0.4,
            # Ask the API for its JSON mode; validation.py still checks the
            # result against the schema, so this is an optimisation, not a
            # substitute for validation.
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return response.choices[0].message.content or ""

    def describe(self) -> str:
        return f"openai ({self._model})"
