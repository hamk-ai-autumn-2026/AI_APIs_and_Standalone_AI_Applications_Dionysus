"""Anthropic provider (Claude models) via the official ``anthropic`` SDK.

Needs:  pip install anthropic
Key:    export ANTHROPIC_API_KEY="sk-ant-..."
Model:  ANTHROPIC_MODEL env var, or --model flag (default: claude-3-5-haiku-latest)
"""

from __future__ import annotations

import os

from . import register
from .base import LLMProvider, ProviderError


@register
class AnthropicProvider(LLMProvider):
    name = "anthropic"

    def __init__(self, model: str | None = None) -> None:
        try:
            import anthropic
        except ImportError as exc:
            raise ProviderError(
                "the 'anthropic' package is missing; install it with: pip install anthropic"
            ) from exc

        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise ProviderError(
                'ANTHROPIC_API_KEY is not set. Get a key at https://console.anthropic.com/ '
                'and run: export ANTHROPIC_API_KEY="sk-ant-..."'
            )

        self._model = model or os.environ.get("ANTHROPIC_MODEL", "claude-3-5-haiku-latest")
        self._client = anthropic.Anthropic()

    def complete(self, system: str, user: str) -> str:
        response = self._client.messages.create(
            model=self._model,
            max_tokens=1024,
            temperature=0.4,
            system=system,  # Claude takes the system prompt as a top-level argument
            messages=[{"role": "user", "content": user}],
        )
        return "".join(
            block.text for block in response.content if getattr(block, "type", "") == "text"
        )

    def describe(self) -> str:
        return f"anthropic ({self._model})"
