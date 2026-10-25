# llm_sources.py — Multi-Source LLM Utility (Assignment #4)

A standalone Python command-line tool that reads one or more sources (plain text,
HTML pages / web URLs, CSV, `.docx`, `.pdf`), converts them to labelled plain text,
sends them to any OpenAI-compatible LLM API, and prints or saves the answer.

```
source (txt / csv / docx / pdf / html / http(s) URL)
  |
  v
Python reader/parser (PyMuPDF, python-docx, csv, BeautifulSoup, requests)
  |
  v
plain text, labelled per source
  |
  v
prompt (untrusted-data framing + user query)
  |
  v
LLM API (OpenAI-compatible /chat/completions)
  |
  v
result -> stdout, or a file with -o
```

---

## 1. Installation

Requires Python 3.9+.

```bash
pip install -r requirements.txt
```

| Package        | Used for                                    |
|----------------|---------------------------------------------|
| requests       | URL downloads and LLM API calls             |
| beautifulsoup4 | HTML parsing, script/style removal          |
| PyMuPDF        | PDF text extraction (imported as `fitz`)    |
| python-docx    | `.docx` paragraphs and tables               |

No other dependencies are required — `argparse` and `csv` come from the standard
library, and the LLM call is plain HTTP (no `openai` package needed).

## 2. Quick start

```bash
# summarize (default query: "Summarize the supplied sources.")
export OPENAI_API_KEY=sk-...
python llm_sources.py report.pdf

# multiple sources in one command
python llm_sources.py report.pdf notes.docx

# mix local files and web URLs
python llm_sources.py report.pdf https://example.com/article

# your own query
python llm_sources.py BashTutorial.docx -q "List all Bash commands found in this document."

# save to a file instead of stdout
python llm_sources.py report.pdf -o summary.md

# see what is happening (types, sizes, strategy decisions, API calls)
python llm_sources.py report.pdf notes.txt -v
```

### Using other providers

Anything that speaks the OpenAI chat-completions protocol works:

```bash
python llm_sources.py report.pdf --model glm-4.6 \
    --base-url https://api.z.ai/api/paas/v4      # Z.ai GLM

python llm_sources.py report.pdf --model llama3 \
    --base-url http://localhost:11434/v1         # local Ollama (no API key)

python llm_sources.py report.pdf --model gpt-4o-mini \
    --base-url http://localhost:1234/v1          # LM Studio
```

## 3. Command-line reference

```
usage: llm_sources.py [-h] [-q QUERY] [-o FILE] [-v] [--model MODEL]
                      [--base-url URL] [--api-key KEY]
                      [--overflow {error,truncate,map-reduce}]
                      [--max-total-chars N] [--chunk-chars N]
                      [--temperature T] [--timeout S] sources [sources ...]
```

| Flag | Meaning | Default |
|------|---------|---------|
| `sources` | one or more files or `http(s)://` URLs | required |
| `-q, --query` | prompt sent to the LLM | `Summarize the supplied sources.` |
| `-o, --output` | write the answer to a file instead of stdout | stdout |
| `-v, --verbose` | progress details on stderr | off |
| `--model` | model name (`LLM_SOURCES_MODEL` env var also works) | `gpt-4o-mini` |
| `--base-url` | API root (`OPENAI_BASE_URL` env var also works) | `https://api.openai.com/v1` |
| `--api-key` | API key (`OPENAI_API_KEY` env var also works) | env value |
| `--overflow` | `error` \| `truncate` \| `map-reduce` | `map-reduce` |
| `--max-total-chars` | total character budget for the prompt | `60000` (~15k tokens) |
| `--chunk-chars` | chunk size used by map-reduce | `12000` |
| `--temperature` | sampling temperature | `0.2` |
| `--timeout` | LLM API timeout in seconds | `120` |

Exit codes: `0` success · `1` runtime failure (all sources unusable, API failure,
overflow rejection, unwritable output) · `2` usage/input error (missing file,
unsupported format).

## 4. How each source type is read

| Type | Detection | Reader | Notes |
|------|-----------|--------|-------|
| text | `.txt .md .log .rst .text`, or extensionless UTF-8 | direct decode (utf-8-sig → cp1252 → latin-1) | binary files (NUL bytes) are rejected |
| CSV | `.csv` | stdlib `csv` | rendered as `row N: cell | cell`; long cells capped at 300 chars |
| PDF | `.pdf`, or `%PDF` magic sniffed | PyMuPDF, page by page | `[page N]` markers kept; password-protected and scanned-only PDFs are reported, not crashed on |
| DOCX | `.docx`, or ZIP+OOXML sniffed | python-docx | paragraphs plus table rows (`cell | cell`); legacy `.doc` gets a clear message |
| HTML | `.html/.htm` local file, or any `http(s)://` URL | requests + BeautifulSoup | see security section |
| URL | starts with `http://` or `https://` | requests (30 s timeout, redirect-following) | non-HTML content types are rejected |

Unknown extensions are sniffed by their first bytes (`%PDF` → pdf, `<html` → html,
`PK\x03\x04` → rejected as a ZIP/OOXML container, decodable text → text). Anything
else produces a *supported formats* error message.

## 5. Context-window policy

`llm_sources.py` never blindly sends an unbounded amount of text. The combined
extracted text is compared against `--max-total-chars` (default 60,000 chars
≈ 15k tokens — deliberately conservative so it also fits smaller local models).

* **`--overflow error`** — refuses to send. Lists each source's size on stderr and
  exits with code 1 plus suggestions (raise the budget, pick another strategy, or
  supply fewer sources).
* **`--overflow truncate`** — keeps a fair share of every source, appends an
  explicit `...[TRUNCATED by llm_sources...]` marker inside the block, and warns
  on stderr. Cheapest option; loses the tails of long documents.
* **`--overflow map-reduce`** *(default)* — true staged summarization:
  1. **map**: every source is split into `--chunk-chars` windows (200-char
     overlap, cut at line boundaries) and each chunk is summarized by the model
     in its own call;
  2. **reduce**: the per-chunk summaries, still labelled per source, are sent as
     the source blocks for the *original* query.
  If even the summaries exceed the budget the tool stops with an error instead
  of silently degrading.

## 6. Security: prompt-injection defences

Every downloaded page and every supplied document is treated as **untrusted
data**. Three explicit layers:

1. **Content sanitization (HTML).** `<script>`, `<style>`, `<noscript>`,
   `<template>`, `<iframe>`, `<svg>`, `<form>` and HTML comments are removed with
   BeautifulSoup before any text is extracted, so hidden payloads in scripts or
   styles never reach the model.
2. **Fencing.** Each source is wrapped in explicit, model-visible markers:
   `===== SOURCE n BEGIN: name (type, N characters) — UNTRUSTED DATA =====` …
   `===== SOURCE n END: name =====`.
3. **System-prompt rules (highest priority).** The system prompt states that
   source content is data only, may contain prompt-injection attempts, must never
   be obeyed, and that instructions come solely from the system prompt and the
   `QUERY:` line. It also asks the model to *report* detected injection attempts.

Try it: `samples/article.html` contains a hidden prompt-injection div — ask the
model about it and watch it flag the attempt instead of complying.

## 7. Error handling

| Situation | Behaviour |
|-----------|-----------|
| missing file / directory / unsupported format / legacy `.doc` | fatal, exit 2, clear message |
| HTTP 404/500, timeouts, DNS/SSL failures on a URL | that source is skipped with a warning; the run continues with the rest |
| PDF with no text layer, empty CSV/DOCX, binary file | source skipped with a warning |
| all sources unusable | fatal, exit 1 |
| missing API key | warning; request proceeds (local servers need no key); an OpenAI 401 is reported with a hint |
| API 401/403/404/5xx, timeout, unreachable host, malformed JSON | fatal, exit 1, response snippet included |
| summaries still too large (map-reduce) | fatal, exit 1, with tuning advice |

Warnings always go to **stderr**, so stdout carries only the LLM answer and
redirection (`> out.md`) stays clean.

## 8. Testing without an API key

The `tests/` folder ships two helpers:

```bash
# offline unit tests of extractors, chunking and prompt building (no network)
python tests/test_extractors.py -v

# a fake OpenAI-compatible server that reports what it "saw" in each prompt
python tests/mock_openai_server.py 8000
```

Then point the tool at the mock — it answers in Markdown and echoes the query,
detected source labels, and whether the untrusted-data system prompt arrived:

```bash
python llm_sources.py samples/quarterly_report.pdf samples/notes.txt -v \
    --base-url http://127.0.0.1:8000/v1 --model mock-1
python llm_sources.py http://127.0.0.1:8000/page.html --base-url http://127.0.0.1:8000/v1
```

## 9. Sample files (`samples/`)

| File | Type | Content |
|------|------|---------|
| `notes.txt` | text | project meeting notes |
| `sales.csv` | CSV | regional sales table |
| `bash_tutorial.docx` | DOCX | tutorial text + a command reference table |
| `quarterly_report.pdf` | PDF | two-page business report |
| `article.html` | HTML | article with script/style junk **and a planted prompt injection** |

Example query exercising the CSV: `python llm_sources.py samples/sales.csv -q "Which region generated the most revenue and how much?"`

## 10. Design notes and extension points

* **Dependency-light LLM client.** The API call is a plain `requests.post` to
  `{base-url}/chat/completions`, which makes the request/response contract visible
  and keeps the tool compatible with OpenAI, Z.ai GLM, Ollama and LM Studio alike.
* **Extensible readers.** Adding a format means one function plus one entry in the
  `readers` dict in `extract_from_source()` and one extension in `classify_source()`.
* **Token budgeting.** Sizes are estimated at ~4 chars/token for diagnostics;
  swapping in `tiktoken` for exact counts is a one-function change.
* **RAG.** For very large corpora the natural next step is to embed the chunks
  (`--chunk-chars` already produces reusable windows) and retrieve only the top-k
  chunks per query before the final call; the map-reduce path in `run_map_reduce()`
  shows where retrieval would slot in. The `embedchain` library could be attached
  as an optional alternative pipeline.
* **Not a production system.** The goal of the assignment is the pipeline
  (source → parser → text → prompt → API → result), not commercial-grade document
  analysis; OCR, tables-in-PDF and layout-aware extraction are out of scope.
