"""Prompt templates for the dictionary app.

Keeping every prompt in one module means the application logic never
changes when the wording changes -- and every provider receives exactly
the same conversation, so switching providers cannot change behaviour.
"""

SYSTEM_PROMPT = """\
You are a careful lexicographer that builds dictionary entries for single words.

You ALWAYS answer with one JSON object and nothing else: no explanations,
no markdown, no code fences.

The JSON object must have exactly these five properties:
  "word"        the word being looked up
  "definitions" 2-5 short English meanings of the word (the list MUST NOT be empty)
  "synonyms"    words with similar meaning, in the same language as the word (list may be empty)
  "antonyms"    words with the opposite meaning, in the same language as the word (list may be empty)
  "examples"    2-3 short, natural example sentences that use the word, in the word's language

Rules:
- Detect the word's language automatically (Finnish, English, Swedish, ...).
- "definitions" are written in English; all other values stay in the word's language.
- If the word has no common synonyms or antonyms, return an empty list for that field.
- Never list the word itself (or a variant of it) as its own synonym or antonym.
- Never leave "definitions" empty.
"""


def build_user_prompt(word: str) -> str:
    """First ask: generate an entry for *word* in the required JSON shape."""
    return (
        f'Create a dictionary entry for the word "{word}".\n'
        "\n"
        "Answer with a single JSON object with exactly this shape:\n"
        "{\n"
        '  "word": "...",\n'
        '  "definitions": ["..."],\n'
        '  "synonyms": ["..."],\n'
        '  "antonyms": ["..."],\n'
        '  "examples": ["..."]\n'
        "}"
    )


def build_retry_prompt(word: str, previous_output: str, error: str) -> str:
    """Follow-up ask: the previous answer failed validation; fix it."""
    previous = previous_output.strip()
    if len(previous) > 1200:
        previous = previous[:1200] + " ... (truncated)"
    return (
        f'Your previous dictionary entry for "{word}" was rejected because it '
        "did not pass schema validation.\n"
        "\n"
        "Validation errors:\n"
        f"{error}\n"
        "\n"
        "Your previous answer was:\n"
        f"{previous}\n"
        "\n"
        f'Produce a corrected dictionary entry for the word "{word}" that passes '
        "validation. Remember: \"definitions\" must contain at least one item. "
        "Answer with a single JSON object only."
    )
