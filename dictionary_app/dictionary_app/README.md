# Schema-validated AI dictionary — Assignment #5

A Python command-line application that asks the user for a word and
generates a dictionary entry (definitions, synonyms, antonyms, examples)
with a large language model. **Every model reply is validated against a
JSON Schema before it is used** — invalid replies are rejected and the
exact validation errors are fed back to the model so it can correct
itself. The LLM backend is pluggable: you can switch between providers
with a command-line flag, and nothing else in the application changes.

## Assignment requirements and where they live

| Requirement | Implementation |
|---|---|
| Ask the user for a word | `main.py` — interactive loop or `--word` flag |
| Generate entry: definitions, synonyms, antonyms, examples | `prompts.py` (prompt text) + provider reply |
| Validate the model's output before use | `validation.py` (`jsonschema` library) against `schema.py` |
| Empty definition list is invalid | `"minItems": 1` on `definitions` in `schema.py` |
| Switch between ≥ 2 providers without touching the rest | `providers/` package + `--provider` flag |

## Project structure

```
dictionary_app/
├── main.py                    # CLI, retry loop, pretty printing
├── prompts.py                 # all prompt text (system / ask / retry)
├── schema.py                  # JSON Schema: what a valid entry is
├── validation.py              # JSON extraction + schema validation
├── providers/
│   ├── __init__.py            # registry that auto-discovers provider modules
│   ├── base.py                # LLMProvider interface — the only contract
│   ├── openai_provider.py     # GPT via the official openai SDK
│   ├── anthropic_provider.py  # Claude via the official anthropic SDK
│   └── zai_provider.py        # optional keyless testing via the z-ai CLI
├── test_dictionary_app.py     # offline tests (no API keys needed)
├── requirements.txt
└── README.md
```

## Setup

```bash
cd dictionary_app
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# API keys for the two "real" providers (only the one you use is needed):
export OPENAI_API_KEY="sk-..."
export ANTHROPIC_API_KEY="sk-ant-..."
```

## Usage

```bash
python main.py                                   # interactive: keep asking for words
python main.py --word kallis                     # one-shot with the default provider
python main.py --provider anthropic --word kallis
python main.py --list-providers
python main.py --provider openai --model gpt-4o --word kallis
```

The default provider (`openai`) can also be changed permanently with
`export DICTIONARY_PROVIDER=anthropic`.

Example session (`--provider zai --word kallis`):

```
==============================================================
  KALLIS
==============================================================

  DEFINITIONS
   - expensive
   - dear
   - costly

  SYNONYMS
   - hintava
   - arvokas
   - tyyris

  ANTONYMS
   - halpa
   - edullinen

  EXAMPLES
   - "Tämä auto on liian kallis."
   - "Hän on minulle hyvin kallis ystävä."

--------------------------------------------------------------
  provider: zai (glm-4-plus) | schema-validated: yes
==============================================================
```

## How provider switching works

The whole application only knows one interface — `LLMProvider`
(`providers/base.py`):

```python
class LLMProvider(ABC):
    name: str = "abstract"

    @abstractmethod
    def complete(self, system: str, user: str) -> str: ...
```

`providers/__init__.py` auto-discovers every module in the `providers/`
folder, and `create_provider(name)` is the single switch point used by
`main.py`. Adding a third provider is literally one new file:

```python
# providers/my_provider.py
from . import register
from .base import LLMProvider

@register
class MyProvider(LLMProvider):
    name = "myprovider"

    def complete(self, system: str, user: str) -> str:
        ...  # call any HTTP API and return the raw text reply
```

Drop it into `providers/` and `python main.py --provider myprovider`
already works — `main.py`, `prompts.py`, `validation.py` and `schema.py`
are never touched. The bundled `zai_provider.py` is a working example of
exactly this.

## Validation rules (`schema.py`)

- The reply must be an object with **exactly** the five required keys
  (`additionalProperties: false`).
- `word`: a non-empty string.
- `definitions`: **at least one item** (`minItems: 1` — the assignment's
  "empty definition list is invalid" rule), each item a non-empty string.
- `synonyms` / `antonyms` / `examples`: arrays of non-empty strings
  (an empty list is allowed for these).
- Model output wrapped in markdown fences or prose is still parsed —
  `validation.py` extracts the embedded JSON object before validating.
  What gets rejected: missing keys, wrong types, empty `definitions`,
  non-string items, unexpected extra keys.

## Retry behaviour

Each attempt runs: reply → JSON extraction → schema validation.

1. If validation fails, the app prints the exact schema errors and sends
   them back to the model with the rejected answer (`prompts.build_retry_prompt`).
2. Up to `MAX_ATTEMPTS = 3` attempts (1 original + 2 self-corrections).
3. Provider/network errors also consume an attempt and are retried.
4. If every attempt fails, the app reports a clear error instead of ever
   using unvalidated data.

## Tests

Offline, no API keys required:

```bash
python test_dictionary_app.py
```

Covers: a valid entry passes; empty `definitions` is rejected; missing
keys, extra keys and wrong types are rejected; fenced and prose-wrapped
JSON extraction; the retry loop recovering from one bad attempt; and
giving up after `MAX_ATTEMPTS`.

## Troubleshooting

- *"OPENAI_API_KEY is not set"* — export the key (see Setup) or choose
  another provider with `--provider`.
- *Garbled ä/ö characters on old Windows consoles* — run with
  `set PYTHONUTF8=1`.
- *The `zai` provider* — only works where the `z-ai` CLI is installed
  (e.g. the course sandbox); on your own machine just ignore it and use
  `openai` or `anthropic`.
