"""Z.ai gateway provider -- lets the app run end-to-end without API keys.

Shells out to the local ``z-ai`` CLI and reads the OpenAI-style JSON that
the CLI writes via its ``--output`` flag. This provider is mainly useful
for testing the application in an environment where the Z.ai CLI exists
and no OpenAI/Anthropic keys are configured. It also demonstrates how
little code a new backend needs once the ``LLMProvider`` interface exists.

Note: the CLI does not expose model selection, so ``--model`` is accepted
but ignored.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

from . import register
from .base import LLMProvider, ProviderError

_CLI_TIMEOUT_SECONDS = 180
_TMP_DIR = Path(__file__).resolve().parent.parent / ".cache"


@register
class ZAIProvider(LLMProvider):
    name = "zai"

    def __init__(self, model: str | None = None) -> None:
        self._model = model or "glm-4-plus"
        if shutil.which("z-ai") is None:
            raise ProviderError(
                "the 'z-ai' CLI is not on PATH; the 'zai' provider only works "
                "where the Z.ai CLI is installed"
            )

    def complete(self, system: str, user: str) -> str:
        _TMP_DIR.mkdir(exist_ok=True)
        # The CLI writes its full OpenAI-style reply JSON to --output.
        with tempfile.NamedTemporaryFile(
            mode="r", suffix=".json", prefix="zai-", dir=_TMP_DIR
        ) as sink:
            try:
                proc = subprocess.run(
                    ["z-ai", "chat", "-p", user, "-s", system, "-o", sink.name],
                    capture_output=True,
                    text=True,
                    timeout=_CLI_TIMEOUT_SECONDS,
                )
            except subprocess.TimeoutExpired as exc:
                raise ProviderError(
                    f"z-ai CLI timed out after {_CLI_TIMEOUT_SECONDS}s"
                ) from exc

            if proc.returncode != 0:
                detail = (proc.stderr or proc.stdout or "").strip()[:300]
                raise ProviderError(f"z-ai CLI failed (exit {proc.returncode}): {detail}")

            try:
                payload = json.load(sink)
            except json.JSONDecodeError as exc:
                raise ProviderError(
                    f"could not parse z-ai CLI output as JSON: {exc}"
                ) from exc

        try:
            return payload["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderError(f"unexpected z-ai CLI reply structure: {exc}") from exc

    def describe(self) -> str:
        return f"zai ({self._model})"
