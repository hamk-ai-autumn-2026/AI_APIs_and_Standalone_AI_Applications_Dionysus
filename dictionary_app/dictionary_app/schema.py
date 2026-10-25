"""JSON Schema describing a valid dictionary entry.

This schema is the single source of truth for what the application accepts
from the model. It is checked with the ``jsonschema`` library *before* any
model output is used by the rest of the application.

Assignment rule: an empty ``definitions`` list must be considered invalid.
That is enforced declaratively with ``"minItems": 1`` on ``definitions``.
"""

DICTIONARY_ENTRY_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "DictionaryEntry",
    "description": "A generated dictionary entry for a single word.",
    "type": "object",
    "properties": {
        "word": {
            "type": "string",
            "minLength": 1,
            "description": "The word that was looked up.",
        },
        "definitions": {
            "type": "array",
            "minItems": 1,  # <-- an empty definition list is INVALID
            "items": {"type": "string", "minLength": 1},
            "description": "At least one short English meaning of the word.",
        },
        "synonyms": {
            "type": "array",
            "items": {"type": "string", "minLength": 1},
            "description": "Words with similar meaning (may be empty).",
        },
        "antonyms": {
            "type": "array",
            "items": {"type": "string", "minLength": 1},
            "description": "Words with opposite meaning (may be empty).",
        },
        "examples": {
            "type": "array",
            "items": {"type": "string", "minLength": 1},
            "description": "Example sentences using the word.",
        },
    },
    "required": ["word", "definitions", "synonyms", "antonyms", "examples"],
    "additionalProperties": False,
}
