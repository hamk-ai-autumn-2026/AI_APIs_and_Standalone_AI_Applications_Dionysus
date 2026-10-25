"""Offline test suite for the dictionary app -- no API keys needed.

Run from the project directory:

    python test_dictionary_app.py

Covers the validation layer (JSON extraction + schema rules, including
the assignment rule that an empty definitions list is invalid) and the
retry loop in main.generate_entry() using a scripted fake provider.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import main  # noqa: E402
from validation import ValidationError, extract_json, validate_entry  # noqa: E402

GOOD_ENTRY = {
    "word": "kallis",
    "definitions": ["expensive", "dear", "costly"],
    "synonyms": ["hintava", "arvokas", "tyyris"],
    "antonyms": ["halpa", "edullinen"],
    "examples": ["Tämä auto on liian kallis.", "Hän on minulle hyvin kallis ystävä."],
}


class FakeProvider:
    """Scripted provider: returns queued replies, counts calls."""

    name = "fake"

    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = 0

    def complete(self, system, user):
        self.calls += 1
        return self.replies.pop(0)

    def describe(self):
        return "fake"


TESTS = []


def test(fn):
    TESTS.append(fn)
    return fn


@test
def valid_example_entry_passes():
    assert validate_entry(GOOD_ENTRY) == GOOD_ENTRY


@test
def empty_definitions_is_invalid():
    """The assignment's explicit rule: [] for definitions must be rejected."""
    bad = {**GOOD_ENTRY, "definitions": []}
    try:
        validate_entry(bad)
    except ValidationError as exc:
        assert "definitions" in str(exc)
        return
    raise AssertionError("an empty definitions list was accepted")


@test
def missing_key_is_invalid():
    bad = {k: v for k, v in GOOD_ENTRY.items() if k != "synonyms"}
    try:
        validate_entry(bad)
    except ValidationError:
        return
    raise AssertionError("a missing required key was accepted")


@test
def non_string_item_is_invalid():
    bad = {**GOOD_ENTRY, "definitions": ["expensive", 42]}
    try:
        validate_entry(bad)
    except ValidationError:
        return
    raise AssertionError("a non-string definition was accepted")


@test
def extra_property_is_invalid():
    bad = {**GOOD_ENTRY, "translation": "surprise"}
    try:
        validate_entry(bad)
    except ValidationError:
        return
    raise AssertionError("an unexpected extra key was accepted")


@test
def non_object_reply_is_invalid():
    try:
        validate_entry(["not", "a", "dict"])
    except ValidationError:
        return
    raise AssertionError("a non-object reply was accepted")


@test
def plain_json_is_extracted():
    assert extract_json(json.dumps(GOOD_ENTRY)) == GOOD_ENTRY


@test
def fenced_json_is_extracted():
    text = "```json\n" + json.dumps(GOOD_ENTRY, ensure_ascii=False) + "\n```"
    assert extract_json(text) == GOOD_ENTRY


@test
def prose_wrapped_json_is_extracted():
    text = "Here is your entry:\n" + json.dumps(GOOD_ENTRY, ensure_ascii=False) + "\nHope it helps!"
    assert extract_json(text) == GOOD_ENTRY


@test
def empty_response_is_invalid():
    for empty in ("", "   ", None):
        try:
            extract_json(empty)
        except ValidationError:
            continue
        raise AssertionError(f"empty response {empty!r} was accepted")


@test
def retry_recovers_from_invalid_output():
    """Attempt 1 returns empty definitions, attempt 2 returns a valid entry."""
    bad = json.dumps({**GOOD_ENTRY, "definitions": []})
    good = json.dumps(GOOD_ENTRY, ensure_ascii=False)
    provider = FakeProvider([bad, good])
    entry = main.generate_entry(provider, "kallis")
    assert entry == GOOD_ENTRY
    assert provider.calls == 2


@test
def gives_up_after_max_attempts():
    bad = json.dumps({**GOOD_ENTRY, "definitions": []})
    provider = FakeProvider([bad] * 10)
    try:
        main.generate_entry(provider, "kallis")
    except ValidationError:
        assert provider.calls == main.MAX_ATTEMPTS
        return
    raise AssertionError("generate_entry should have raised after MAX_ATTEMPTS")


def run() -> int:
    failed = 0
    for fn in TESTS:
        try:
            fn()
            print(f"PASS  {fn.__name__}")
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print(f"FAIL  {fn.__name__}: {exc}")
    print(f"\n{len(TESTS) - failed}/{len(TESTS)} tests passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(run())
