"""Validation layer: raw model text -> validated dictionary entry.

The rest of the application never touches raw model output. It calls
``build_validated_entry()`` and either receives a dictionary matching the
schema or a ``ValidationError`` explaining exactly what was wrong.
"""

from __future__ import annotations

import json
from typing import Any

from jsonschema import Draft202012Validator

from schema import DICTIONARY_ENTRY_SCHEMA


class ValidationError(Exception):
    """Raised when model output cannot be used (bad JSON or schema violation)."""


def extract_json(text: str) -> Any:
    """Extract the first JSON object embedded in the model's reply.

    Handles the common real-world failure modes of chat models:

    * plain JSON (fast path),
    * JSON inside markdown fences (```` ```json ... ``` ````),
    * JSON wrapped in prose ("Here is the entry: {...}"),
    * leading/trailing whitespace.
    """
    if not text or not text.strip():
        raise ValidationError("the model returned an empty response")

    candidate = text.strip()

    # 1. Fast path: the reply is pure JSON.
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        pass

    # 2. Try each fenced code block, e.g. ```json {...} ```
    if "```" in candidate:
        for chunk in candidate.split("```"):
            chunk = chunk.strip()
            if chunk[:4].lower() == "json":  # strip the fence language tag
                chunk = chunk[4:].strip()
            if not chunk:
                continue
            try:
                return json.loads(chunk)
            except json.JSONDecodeError:
                continue

    # 3. Fall back to the outermost {...} span of the reply.
    start, end = candidate.find("{"), candidate.rfind("}")
    if start != -1 and end > start:
        try:
            return json.loads(candidate[start : end + 1])
        except json.JSONDecodeError as exc:
            raise ValidationError(
                f"found a JSON-like fragment but it does not parse: {exc}"
            ) from exc

    raise ValidationError("no JSON object found in the model response")


def validate_entry(data: Any) -> dict:
    """Validate parsed data against ``DICTIONARY_ENTRY_SCHEMA``.

    Returns the data untouched on success. On failure raises
    ``ValidationError`` with a human-readable summary of *all* violations,
    suitable for feeding back to the model.
    """
    validator = Draft202012Validator(DICTIONARY_ENTRY_SCHEMA)
    errors = sorted(validator.iter_errors(data), key=lambda e: list(e.absolute_path))

    if errors:
        lines = []
        for err in errors:
            path = ".".join(str(p) for p in err.absolute_path) or "(root)"
            lines.append(f"- {path}: {err.message}")
        raise ValidationError(
            f"schema validation failed with {len(errors)} error(s):\n"
            + "\n".join(lines)
        )

    return data


def build_validated_entry(raw_text: str) -> dict:
    """Full pipeline: raw model text -> validated dictionary entry dict."""
    return validate_entry(extract_json(raw_text))
