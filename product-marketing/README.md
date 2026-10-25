# Product Description Generator (CLI)

**Exercise #9** — a command-line application that analyses one or more product
images and generates marketing content (a product description plus several
short marketing slogans) with a multimodal LLM.

The tool is intentionally careful about **where each fact comes from**: facts
that are visible in the images are reported as verified, facts supplied by the
user are labelled as seller-supplied, and the model is instructed never to
invent specifications, materials, features, certifications or other claims
that neither source supports.

---

## Contents

| File | Purpose |
|------|---------|
| `product_marketing.py` | The complete CLI application (single file, Python 3.8+ standard library only) |
| `SETUP_STEPS.md` | **Start here** — full step-by-step guide: config, run, screenshots, GitHub publishing |
| `samples/` | Real product photos (found online) for test runs — use **your own** photos for the submission |
| `package.json` | Declares the `z-ai-web-dev-sdk` dependency — only needed for the `zai` provider |
| `.gitignore` | Keeps `node_modules/`, `.env` and your `.z-ai-config` (API keys) out of GitHub |
| `README.md` | This file |

---

## How it works

The application makes **two AI calls** behind the scenes:

1. **Vision call (image analysis).** Every image is sent to a vision-language
   model with a strict *inventory* prompt: report only what is directly
   visible (product type, colours, materials you can see, printed text,
   packaging) and explicitly state what **cannot** be determined from the
   images. This limits hallucination at the source.

2. **Generation call (copywriting).** The visual inventory plus the
   user-supplied `--info` text are given to a text model with grounding rules:
   - user-supplied facts are the only source for invisible properties
     (materials, capacity, technical specifications, certifications, ...);
   - anything found in neither source must be left out entirely;
   - claims from `--info` should carry natural attribution such as
     *"designed to"*, *"according to the seller"*;
   - the model must also return two explicit fact lists —
     *verified from the product images* and *supplied by the seller* — which
     the CLI prints in the **Information Sources** section.

Because the AI SDK used here is distributed as a Node.js package, the Python
CLI embeds a tiny Node.js "bridge" script and communicates with it over
stdin/stdout using JSON. The bridge is extracted to a temporary directory at
runtime — you do not need to install or run anything besides the steps below.

---

## AI models used

The tool supports **two interchangeable AI backends** (choose with
`--provider`, default is auto-detect):

### Provider 1 — OpenAI (default when `OPENAI_API_KEY` is set)

| Purpose | Model | How it is called |
|---------|-------|------------------|
| Image analysis (call 1) | **GPT-4o mini** (`gpt-4o-mini`, vision-capable) | OpenAI Chat Completions REST API, called directly from Python (`urllib`) with base64 `data:` image URLs |
| Description + slogans (call 2) | **GPT-4o mini** (`gpt-4o-mini`) | same API, second call |

No Node.js, no npm install, no credentials file — just the environment
variable. `OPENAI_MODEL` and `OPENAI_BASE_URL` can override the defaults.

### Provider 2 — z-ai (`--provider zai`)

| Purpose | Model | How it is called |
|---------|-------|------------------|
| Image analysis (call 1) | **GLM-4.6V** (`glm-4.6v`) — vision-language model | `zai.chat.completions.createVision()` with base64 `data:` image URLs |
| Description + slogans (call 2) | **GLM-4-Plus** (`glm-4-plus`) — text model | `zai.chat.completions.create()` |

Accessed through the **`z-ai-web-dev-sdk`** Node.js package (needs Node.js,
`npm install` and a `.z-ai-config` credentials file).

All model identifiers are constants at the top of `product_marketing.py`
(`OPENAI_MODEL`, `VISION_MODEL`, `TEXT_MODEL`), so they can be swapped
without touching any other code.

---

## Requirements

- **Python 3.8+** (standard library only — no `pip install` needed)
- **One AI backend**:
  - OpenAI: `OPENAI_API_KEY` environment variable (no Node.js needed), **or**
  - z-ai: Node.js 18+ and the `z-ai-web-dev-sdk` npm package (see Setup)
- Network access to the AI service

---

## Setup

### 1. Configure credentials (pick one)

**OpenAI (easiest):**

```bash
# Windows (then reopen the terminal)
setx OPENAI_API_KEY "sk-..."
# macOS / Linux
export OPENAI_API_KEY="sk-..."
```

**z-ai:** create a `.z-ai-config` JSON file in the project folder with the
`baseUrl` and `apiKey` provided by your course (see `SETUP_STEPS.md` step 3).

### 2. Install the SDK (z-ai provider only)

```bash
npm install   # only needed for --provider zai
```

### 3. Verify the runtime

```bash
python3 product_marketing.py --help
```

If Node.js or the SDK is missing, the tool prints a specific, actionable
error message telling you exactly what to install.

---

## Usage

```
python3 product_marketing.py --images IMG [IMG ...] [options]
```

### Required options

| Option | Description |
|--------|-------------|
| `--images IMG [IMG ...]` | One or more product images. Supported formats: `.jpg`, `.jpeg`, `.png`, `.webp`, `.gif`, `.bmp` (max 8 files). Files are validated for existence, extension and content signature before any AI call. |

### Optional options

| Option | Default | Description |
|--------|---------|-------------|
| `--info TEXT` | — | Seller-supplied product facts: name, materials, dimensions, technical specifications, target audience, intended use, features, brand. Used to improve accuracy and to provide information that is not visible in the images. |
| `--language LANG` | `English` | Language of the generated content (e.g. `English`, `Finnish`, `Swedish`). |
| `--tone TONE` | `friendly` | Tone of voice: `friendly`, `professional`, `playful`, `luxurious`, `technical`, ... (free text is accepted). |
| `--slogans N` | `3` | Number of marketing slogans to generate (1–10). |
| `--output FILE` | — | Additionally save the content as a Markdown file. |
| `--timeout SEC` | `120` | Per-AI-call timeout in seconds. |

### Examples

Matching the assignment example:

```bash
python3 product_marketing.py \
    --images front.jpg side.jpg packaging.jpg \
    --info "Stainless-steel insulated bottle, 750 ml, keeps drinks cold for 24 hours"
```

With the optional options:

```bash
python3 product_marketing.py \
    --images shoe1.jpg shoe2.jpg \
    --info "Water-resistant hiking shoe for autumn and winter" \
    --tone professional \
    --slogans 5 \
    --language English \
    --output shoe_content.md
```

Quick demo with the bundled samples (no photography needed):

```bash
python3 product_marketing.py \
    --images samples/bottle_1.jpg samples/bottle_2.jpg \
    --info "Stainless-steel insulated bottle, 750 ml, keeps drinks cold for 24 hours" \
    --tone friendly --slogans 3 --output bottle_content.md
```

---

## Example output

```
==============================================================================
PRODUCT MARKETING CONTENT
==============================================================================

PRODUCT DESCRIPTION:
Stay refreshed all day with these stylish insulated bottles. According to the seller,
these stainless-steel containers are designed to keep drinks cold for 24 hours and have
a 750 ml capacity. The photos show two elegant options: a deep matte navy and a soft
matte sage, both featuring a sophisticated wood grain detail on the lid and a polished
metal handle for easy carrying.

MARKETING SLOGANS:
  - Cold for 24 hours, style for all day
  - Elegant design meets lasting refreshment
  - Your perfect companion for every adventure

INFORMATION SOURCES:
------------------------------------------------------------------------------
  Verified from the product images:
    * Two portable beverage containers with identical design
    * One container in dark matte navy blue, the other in muted matte sage green
    * Polished silver-colored metal neck and cap assembly
    * Light brown wood grain texture on the lid
    * Thin, arched metal wire handle attached to the metal collar
    * No visible branding, text, or capacity markings

  Supplied by the seller (not verified against the images):
    * Stainless-steel insulated bottle
    * 750 ml capacity
    * Keeps drinks cold for 24 hours

------------------------------------------------------------------------------
Note: seller-supplied facts are used as stated and have not been verified
against the product images.
==============================================================================
```

---

## How the two information sources are kept apart

- **Vision-call grounding.** The image analysis prompt forbids speculation:
  the model may only transcribe what is visible and must say when a detail
  (capacity, material, certification, performance) *cannot be determined*
  from the images.
- **Generation-call grounding.** The copywriting prompt receives the two
  sources in clearly separated blocks (`SOURCE A: FACTS VERIFIED FROM THE
  PRODUCT IMAGES`, `SOURCE B: FACTS SUPPLIED BY THE SELLER`) and must follow:
  1. Source B is authoritative for facts the seller stated;
  2. Source-A-only facts are presented as seen in the photos;
  3. nothing that appears in neither source may be invented — no filler
     specifications, materials, certifications, awards or performance claims;
  4. Source-B claims are attributed with wording such as *"according to the
     seller"* / *"designed to"*.
- **Information Sources section.** The model returns per-fact source lists,
  printed in the terminal and in the `--output` file, so a reader can always
  tell which claims are image-verified and which are seller-supplied.
- **Unverified-fact note.** Every output ends with an explicit note that
  seller-supplied facts were used as stated and not verified.

---

## Error handling

The CLI validates everything it can *before* spending an AI call and always
exits with a meaningful status code:

| Situation | Behaviour | Exit code |
|-----------|-----------|-----------|
| Missing/unsupported/oversized/empty image file | `error: ...` message listing the problem and supported formats | 2 |
| Renamed or corrupted file (wrong content signature) | Rejected with a clear message | 2 |
| Duplicate image path | Skipped with a note on stderr | — |
| `--slogans` outside 1–10, bad `--timeout` | Usage error before any AI call | 2 |
| Node.js missing, SDK not found | Specific installation guidance | 1 |
| AI timeout / API error / unparseable reply | Descriptive error (one automatic JSON-format retry inside the bridge) | 1 |
| `--output` path not writable | Warning; still prints content to the terminal | 1 |

---

## Implementation notes

- **Single-file design.** The Node.js bridge is embedded in
  `product_marketing.py` (`EMBEDDED_BRIDGE_JS`) and materialised into a
  temporary directory at runtime, so the whole assignment is one Python file.
- **Models.** `glm-4.6v` for the vision analysis, `glm-4-plus` for the text
  generation (via `z-ai-web-dev-sdk`'s `chat.completions` /
  `chat.completions.createVision`).
- **Strict JSON contract.** The generation call demands a JSON object
  (`product_description`, `slogans`, `sources.from_images`,
  `sources.from_user`); the bridge parses it tolerantly (handles markdown
  fences) and performs one guided retry if the format is broken.
- **Images as data URLs.** Local images are base64-encoded
  (`data:image/...;base64,...`) — the recommended, most reliable way to pass
  local files to the vision model.
