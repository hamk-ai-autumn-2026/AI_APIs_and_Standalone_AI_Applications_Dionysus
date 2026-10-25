"""Provider abstraction -- the contract every LLM backend must fulfil.

The rest of the application only ever talks to this interface:

    provider.complete(system_prompt, user_prompt) -> str

so providers can be added or switched (CLI flag / env var) without
touching main.py, prompts.py, validation.py or schema.py.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class ProviderError(Exception):
    """Raised when a provider cannot be used (missing key, CLI missing, ...)."""


class LLMProvider(ABC):
    """A chat-completion backend: system + user text in, raw text out."""

    #: unique name used on the command line:  --provider <name>
    name: str = "abstract"

    @abstractmethod
    def complete(self, system: str, user: str) -> str:
        """Send one chat turn and return the assistant's raw text reply."""

    def describe(self) -> str:
        """Human-readable one-liner shown in the application footer."""
        return self.name
