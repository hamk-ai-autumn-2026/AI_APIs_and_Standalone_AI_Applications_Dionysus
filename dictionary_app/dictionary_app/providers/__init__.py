"""Provider registry with automatic discovery.

Every module inside this package that defines an ``LLMProvider`` subclass
with a unique ``name`` and decorates it with ``@register`` is picked up
automatically. This is the whole switch point of the application:

    create_provider(name) -> LLMProvider instance

Adding a provider means dropping ONE file into this folder -- no other
file in the application changes. That is how the assignment's
"switch between providers without changing the rest of the application"
is implemented.
"""

from __future__ import annotations

import importlib
import pkgutil

from .base import LLMProvider, ProviderError

__all__ = ["LLMProvider", "ProviderError", "register", "create_provider", "provider_names"]

_REGISTRY: dict[str, type[LLMProvider]] = {}


def register(cls: type[LLMProvider]) -> type[LLMProvider]:
    """Class decorator: add a provider class to the registry."""
    if cls.name in _REGISTRY:
        raise ValueError(f"duplicate provider name: {cls.name!r}")
    _REGISTRY[cls.name] = cls
    return cls


def _discover() -> None:
    """Import every module in this package so their @register decorators run."""
    for module_info in pkgutil.iter_modules(__path__):
        if module_info.name == "base":  # infrastructure, not a provider
            continue
        importlib.import_module(f"{__name__}.{module_info.name}")


_discover()  # run once at import time


def provider_names() -> list[str]:
    """Names of all registered providers, sorted (for CLI help / errors)."""
    return sorted(_REGISTRY)


def create_provider(name: str, model: str | None = None) -> LLMProvider:
    """Factory: build a provider instance by name -- the ONLY switch point."""
    try:
        cls = _REGISTRY[name]
    except KeyError:
        raise ProviderError(
            f"unknown provider {name!r}. Available providers: {', '.join(provider_names())}"
        ) from None
    return cls(model=model) if model else cls()
