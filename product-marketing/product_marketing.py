#!/usr/bin/env python3
"""
product_marketing.py -- Product Description Generator (CLI)
============================================================

Exercise #9: a command-line application that analyses one or more product
images and generates marketing content (a product description plus several
short marketing slogans) with the help of a multimodal LLM.

Usage example
-------------
    python product_marketing.py \
        --images front.jpg side.jpg packaging.jpg \
        --info "Stainless-steel insulated bottle, 750 ml, keeps drinks cold for 24 hours"

    python product_marketing.py \
        --images shoe1.jpg shoe2.jpg \
        --info "Water-resistant hiking shoe for autumn and winter" \
        --tone professional --slogans 5 --language English --output content.md

How it works (two-call design)
------------------------------
1. VISION CALL -- every image is sent to a vision-language model (VLM) with a
   strict "inventory" prompt. The model may only report what is actually
   visible (shapes, colours, printed text, packaging, labels) and must
   explicitly say when something cannot be determined from the image.
2. GENERATION CALL -- the image inventory plus the user-supplied --info text
   are sent to a text LLM with a system prompt that enforces fact grounding:
   * user-supplied facts are the ONLY source for invisible properties
     (materials, capacity, technical specs, certifications, ...);
   * the model must NOT invent anything that appears in neither source;
   * the model must return, alongside the description and the slogans, two
     explicit fact-source lists ("verified from images" vs "user-supplied"),
     which the CLI prints in an "Information Sources" section.

The request payloads are dispatched through a small Node.js bridge script
(EMBEDDED_BRIDGE_JS below) because the AI SDK used here is distributed as a
Node.js package. The bridge is written to a temporary directory at runtime,
invoked once per AI call via subprocess, and communicates over stdin/stdout
using single-line JSON documents.

Runtime requirements
--------------------
* Python 3.8+ (standard library only)
* ONE of two AI backends (choose with --provider, default is auto):
    - "openai": set the OPENAI_API_KEY environment variable. The OpenAI Chat
      Completions API is called directly from Python -- no Node.js, no npm
      install, no credentials file. Model defaults to gpt-4o-mini (vision
      capable) and can be overridden with OPENAI_MODEL / OPENAI_BASE_URL.
    - "zai": Node.js 18+ on PATH plus the "z-ai-web-dev-sdk" npm package
      (resolvable via NODE_PATH, ./node_modules, ~/node_modules, or the
      directory pointed to by PRODUCT_MARKETING_SDK_PATH) and a .z-ai-config
      credentials file (project, home, or /etc directory).

Exit codes: 0 success, 1 runtime error, 2 usage error (bad arguments/files).
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
import urllib.error
import urllib.request
from pathlib import Path

PROG = "product_marketing.py"

DEFAULT_LANGUAGE = "English"
DEFAULT_TONE = "friendly"
DEFAULT_SLOGANS = 3
MAX_SLOGANS = 10
MAX_IMAGES = 8
WARN_IMAGE_BYTES = 8 * 1024 * 1024   # > 8 MiB: print a performance warning
MAX_IMAGE_BYTES = 20 * 1024 * 1024   # > 20 MiB: hard reject

DEFAULT_CALL_TIMEOUT = 120           # seconds per AI call
DEFAULT_BRIDGE_TIMEOUT = 180         # seconds for the whole subprocess

SUPPORTED_EXTENSIONS = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".gif": "image/gif",
    ".bmp": "image/bmp",
}

# Minimal "magic byte" signatures so that a text file renamed to .jpg is
# rejected with a clear message instead of a confusing model/API error.
MAGIC_BYTES = {
    "image/jpeg": [b"\xff\xd8\xff"],
    "image/png": [b"\x89PNG\r\n\x1a\n"],
    "image/gif": [b"GIF87a", b"GIF89a"],
    "image/bmp": [b"BM"],
    # WebP: bytes 8..12 of a RIFF container must spell "WEBP"
    "image/webp": None,
}

VISION_MODEL = "glm-4.6v"   # multimodal model used for the image inventory
TEXT_MODEL = "glm-4-plus"   # text model used for description + slogans

# OpenAI provider (--provider openai, or auto-selected when OPENAI_API_KEY is
# set). gpt-4o-mini is multimodal: it handles BOTH the image inventory and
# the copywriting call, so no Node.js bridge is needed at all.
OPENAI_MODEL = "gpt-4o-mini"
DEFAULT_OPENAI_BASE_URL = "https://api.openai.com/v1"


class UsageError(Exception):
    """Raised for invalid user input (bad files, bad option values)."""


class AiCallError(Exception):
    """Raised when an AI call fails (missing runtime, timeout, API error)."""


# ---------------------------------------------------------------------------
# Embedded Node.js bridge
# ---------------------------------------------------------------------------
# The z-ai-web-dev-sdk is a Node.js package, while this tool is a Python CLI.
# The bridge below is the entire glue layer: it reads one JSON request object
# from stdin, performs either a text completion or a vision (image) completion
# against the multimodal LLM, attempts to parse the model's reply as strict
# JSON (with one guided retry), and prints one JSON result object to stdout.
# Keeping it embedded means the whole assignment ships as a single file.

EMBEDDED_BRIDGE_JS = r"""
#!/usr/bin/env node
// Internal bridge used by product_marketing.py. Not meant to be run by hand.
// stdin : {"kind":"text"|"vision", "messages":[...], "timeout_ms":number,
//          "model":string, "expect_json":bool}
// stdout: {"ok":true,"content":"..."} or {"ok":false,"error":"..."}
'use strict';

const PAGE_JSON_RULE =
  'CRITICAL OUTPUT FORMAT: Your reply must be a single valid JSON object and nothing else. ' +
  'No markdown fences, no code blocks, no commentary before or after the JSON.';

async function performCall(request) {
  const mod = await import('z-ai-web-dev-sdk');
  const ZAI = mod.default;
  const zai = await ZAI.create();

  if (request.kind === 'vision') {
    return await zai.chat.completions.createVision({
      model: request.model || 'glm-4.6v',
      messages: request.messages,
      thinking: { type: 'disabled' },
    });
  }
  return await zai.chat.completions.create({
    model: request.model || undefined,
    messages: request.messages,
    stream: false,
    thinking: { type: 'disabled' },
  });
}

function extractReply(response) {
  return (
    response &&
    response.choices &&
    response.choices[0] &&
    response.choices[0].message &&
    typeof response.choices[0].message.content === 'string'
  )
    ? response.choices[0].message.content
    : null;
}

// Tolerant JSON extraction: handles ```json fences and stray prose, then
// validates the minimal shape the CLI expects.
function tryParseJson(raw) {
  if (!raw) return null;
  let text = raw.trim();
  const fence = text.match(/```(?:json)?\s*([\s\S]*?)```/i);
  if (fence && fence[1]) text = fence[1].trim();
  const start = text.indexOf('{');
  const end = text.lastIndexOf('}');
  if (start === -1 || end === -1 || end <= start) return null;
  let parsed;
  try {
    parsed = JSON.parse(text.slice(start, end + 1));
  } catch (err) {
    return null;
  }
  if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) return null;
  const description =
    parsed.product_description ?? parsed.description ?? parsed.Product_Description;
  const slogans = parsed.slogans ?? parsed.Slogans;
  if (typeof description !== 'string' || !Array.isArray(slogans)) return null;
  return parsed;
}

function withTimeout(promise, ms) {
  if (!ms || ms <= 0) return promise;
  return Promise.race([
    promise,
    new Promise((_, reject) =>
      setTimeout(() => reject(new Error('AI request timed out after ' + ms + ' ms')), ms)
    ),
  ]);
}

async function main() {
  let request;
  try {
    const chunks = [];
    for await (const chunk of process.stdin) chunks.push(chunk);
    request = JSON.parse(Buffer.concat(chunks).toString('utf8'));
  } catch (err) {
    process.stdout.write(JSON.stringify({ ok: false, error: 'Bad bridge request: ' + err.message }));
    process.exit(1);
  }

  try {
    let response = await withTimeout(performCall(request), request.timeout_ms);
    let raw = extractReply(response);

    if (request.expect_json) {
      let parsed = tryParseJson(raw);
      if (!parsed) {
        // One guided retry: show the model what went wrong, ask for pure JSON.
        const retryMessages = request.messages.concat([
          { role: 'assistant', content: raw || '(empty reply)' },
          {
            role: 'user',
            content:
              'Your previous reply could not be parsed as JSON. ' +
              PAGE_JSON_RULE +
              ' Return ONLY the JSON object with keys "product_description" and "slogans" (and, if required, "sources").',
          },
        ]);
        response = await withTimeout(performCall({ ...request, messages: retryMessages }), request.timeout_ms);
        raw = extractReply(response);
        parsed = tryParseJson(raw);
      }
      if (!parsed) {
        process.stdout.write(
          JSON.stringify({
            ok: false,
            error: 'The model reply could not be parsed as the expected JSON object.',
            raw: raw ? String(raw).slice(0, 1200) : undefined,
          })
        );
        process.exit(1);
      }
      process.stdout.write(JSON.stringify({ ok: true, json: parsed }));
      return;
    }

    if (raw == null) {
      process.stdout.write(JSON.stringify({ ok: false, error: 'Empty reply from the AI model.' }));
      process.exit(1);
    }
    process.stdout.write(JSON.stringify({ ok: true, content: raw }));
  } catch (err) {
    process.stdout.write(JSON.stringify({ ok: false, error: (err && err.message) || String(err) }));
    process.exit(1);
  }
}

main();
"""


def run_bridge(request: dict, sdk_root: str, timeout_s: float) -> dict:
    """Materialise the embedded bridge and execute one AI call through it."""
    with tempfile.TemporaryDirectory(prefix="pm_bridge_") as tmp:
        bridge_path = os.path.join(tmp, "bridge.mjs")
        with open(bridge_path, "w", encoding="utf-8") as fh:
            # lstrip: the shebang MUST be on line 1 for Node to accept it
            fh.write(EMBEDDED_BRIDGE_JS.lstrip("\n"))

        env = dict(os.environ)
        existing = env.get("NODE_PATH", "")
        env["NODE_PATH"] = f"{sdk_root}{os.pathsep}{existing}" if existing else sdk_root

        # ESM resolution ignores NODE_PATH, so make the SDK resolvable the
        # standard way: link its node_modules next to the bridge file.
        sdk_node_modules = Path(sdk_root) / "node_modules"
        if sdk_node_modules.is_dir():
            try:
                (Path(tmp) / "node_modules").symlink_to(sdk_node_modules, target_is_directory=True)
            except OSError:
                pass  # best effort; NODE_PATH still helps CommonJS-style setups
            # Run from the SDK directory as well: resolution then also walks
            # up from cwd if the symlink was not possible.
            cwd = sdk_root
        else:
            cwd = None

        try:
            proc = subprocess.run(
                ["node", bridge_path],
                input=json.dumps(request),
                capture_output=True,
                text=True,
                timeout=max(5, int(timeout_s)),
                env=env,
                cwd=cwd,
            )
        except FileNotFoundError:
            raise AiCallError(
                "Node.js executable not found on PATH. Install Node.js 18+ "
                "(https://nodejs.org) and try again."
            )
        except subprocess.TimeoutExpired:
            raise AiCallError(
                f"The AI bridge did not finish within {int(timeout_s)} s. "
                "Increase --timeout or check your network connection."
            )

        payload = None
        for line in reversed((proc.stdout or "").strip().splitlines()):
            line = line.strip()
            if line.startswith("{"):
                try:
                    payload = json.loads(line)
                    break
                except json.JSONDecodeError:
                    continue
        if payload is None:
            detail = (proc.stderr or proc.stdout or "").strip()
            raise AiCallError(
                f"AI bridge produced no valid result (exit code {proc.returncode})."
                + (f" Bridge output: {detail[:800]}" if detail else "")
            )
        return payload


# ---------------------------------------------------------------------------
# SDK (Node.js) discovery
# ---------------------------------------------------------------------------

def discover_sdk_root() -> str:
    """Locate a directory containing node_modules/z-ai-web-dev-sdk.

    Search order:
      1. $PRODUCT_MARKETING_SDK_PATH         (explicit override)
      2. ./node_modules                      (project-local install)
      3. ~/node_modules
      4. the script's own directory tree     (convenience when the CLI and
                                              node_modules live together)
    Returns the PARENT directory of node_modules (suitable for NODE_PATH).
    """
    candidates = []
    override = os.environ.get("PRODUCT_MARKETING_SDK_PATH")
    if override:
        candidates.append(Path(override))
    candidates += [Path.cwd(), Path.home(), Path(__file__).resolve().parent]

    for base in candidates:
        try:
            base = base.resolve()
        except OSError:
            continue
        node_modules = base / "node_modules"
        if (node_modules / "z-ai-web-dev-sdk").exists():
            return str(base)
    return ""


def ensure_runtime() -> str:
    """Make sure `node` and the SDK are available; return the NODE_PATH root."""
    if shutil.which("node") is None:
        raise AiCallError(
            "Node.js is required but was not found on PATH. "
            "Install Node.js 18+ from https://nodejs.org and try again."
        )
    sdk_root = discover_sdk_root()
    if not sdk_root:
        raise AiCallError(
            "The 'z-ai-web-dev-sdk' npm package could not be located.\n"
            "Fix it with either of the following:\n"
            "  1) cd to a directory that has node_modules/z-ai-web-dev-sdk "
            "(e.g. your project root) and run this script from there\n"
            "  2) export PRODUCT_MARKETING_SDK_PATH=/dir/containing/node_modules\n"
            "  3) npm install z-ai-web-dev-sdk   # in the directory you run from"
        )
    return sdk_root


# ---------------------------------------------------------------------------
# Image loading and validation
# ---------------------------------------------------------------------------

def sniff_mime(path: Path) -> str | None:
    """Return the MIME type suggested by the file's magic bytes.

    Returns None when the content does not match ANY known image signature,
    which for a file with a known image extension indicates a fake/renamed
    or corrupted file.
    """
    try:
        with open(path, "rb") as fh:
            header = fh.read(16)
    except OSError:
        return None
    if len(header) >= 12 and header[:4] == b"RIFF" and header[8:12] == b"WEBP":
        return "image/webp"
    for mime, magics in MAGIC_BYTES.items():
        if magics and any(header.startswith(m) for m in magics):
            return mime
    return None


def load_images(paths: list[str]) -> list[dict]:
    """Validate, deduplicate and base64-encode the input images."""
    seen: set[str] = set()
    encoded: list[dict] = []

    for raw in paths:
        path = Path(raw).expanduser()
        display = str(path)

        if not path.exists() or not path.is_file():
            raise UsageError(f"Image not found: {display}")
        ext = path.suffix.lower()
        if ext not in SUPPORTED_EXTENSIONS:
            allowed = ", ".join(sorted(SUPPORTED_EXTENSIONS))
            raise UsageError(
                f"Unsupported image type '{path.suffix or '(none)'}' for {display}. "
                f"Supported: {allowed}"
            )
        try:
            size = path.stat().st_size
        except OSError as err:
            raise UsageError(f"Cannot read {display}: {err}")
        if size == 0:
            raise UsageError(f"Image file is empty: {display}")
        if size > MAX_IMAGE_BYTES:
            raise UsageError(
                f"Image too large ({size / 1048576:.1f} MiB, limit "
                f"{MAX_IMAGE_BYTES // 1048576} MiB): {display}"
            )

        key = str(path.resolve()).lower()
        if key in seen:
            print(f"Note: duplicate image skipped: {display}", file=sys.stderr)
            continue
        seen.add(key)

        sniffed = sniff_mime(path)
        if sniffed is None:
            raise UsageError(
                f"File {display} does not look like a real image (unrecognised "
                "content signature). It may be a renamed or corrupted file."
            )
        if sniffed != SUPPORTED_EXTENSIONS[ext]:
            raise UsageError(
                f"File {display} does not look like a real "
                f"{SUPPORTED_EXTENSIONS[ext]} image (content signature says "
                f"{sniffed}). Re-export or rename it correctly."
            )
        if size > WARN_IMAGE_BYTES:
            print(
                f"Warning: {display} is {size / 1048576:.1f} MiB; large images "
                "make requests slower.",
                file=sys.stderr,
            )

        data = path.read_bytes()
        b64 = base64.b64encode(data).decode("ascii")
        encoded.append(
            {
                "label": path.name,
                "data_url": f"data:{SUPPORTED_EXTENSIONS[ext]};base64,{b64}",
            }
        )
    return encoded


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------
# Grounding strategy: the vision call is ONLY allowed to report what is
# visible; the generation call treats the user's --info text as the sole
# authority for anything not observable, and must label every fact with its
# origin. This is what makes the "no invented claims" requirement testable.

VISION_INVENTORY_PROMPT = """You are a meticulous product analyst. Study the attached product \
photo(s) and write a purely factual VISUAL INVENTORY.

Rules:
1. Report ONLY what is directly visible in the images: product category, shape, \
colours, approximate proportions, visible materials, textures, and any text or \
branding printed on the product or its packaging.
2. If several photos are provided, they usually show the SAME product from \
different angles or its packaging. Treat them as one product unless they are \
clearly different items.
3. Do NOT guess or infer anything that is not observable. Never speculate about \
capacity, dimensions, weight, materials you cannot confirm, certifications, \
price, country of origin, or performance (e.g. insulation duration, waterproof \
ratings). If such details are not visible, state that they cannot be determined \
from the images.
4. Quote any readable text (brand names, labels, capacity markings) exactly as \
written; transcribe the text in section 3 even if it is in another language.
5. Keep the inventory under 250 words.
6. Output plain prose only - no markdown, no headings, no bullet lists.

Structure your answer in numbered sections:
1. Product type and overall appearance.
2. Colours, shapes and visible materials or textures.
3. All visible text and branding (quote exactly; say "none legible" if there \
is no readable text).
4. Packaging and accessories, if any (otherwise "no packaging visible").
5. Details that cannot be determined from the images alone."""


def build_generation_prompt(
    inventory: str,
    info: str | None,
    language: str,
    tone: str,
    n_slogans: int,
) -> str:
    """User-turn prompt for the generation (text LLM) call."""
    parts = [
        "Create marketing content for ONE product based on the two sources below.\n",
        "=== SOURCE A: FACTS VERIFIED FROM THE PRODUCT IMAGES (via vision analysis) ===\n"
        f"{inventory.strip()}\n",
    ]
    if info and info.strip():
        parts.append(
            "=== SOURCE B: FACTS SUPPLIED BY THE SELLER (unverified) ===\n"
            f"{info.strip()}\n"
        )
    else:
        parts.append(
            "=== SOURCE B: FACTS SUPPLIED BY THE SELLER ===\n"
            "(none provided)\n"
        )
    parts.append(
        "=== TASK ===\n"
        "Write the product description, the marketing slogans and the fact-source "
        "lists in "
        f"{language}. Use a {tone} tone throughout.\n\n"
        "STRICT GROUNDING RULES:\n"
        "1. Source B is authoritative for any product facts the seller stated; treat "
        "its details (name, materials, dimensions, technical specifications, target "
        "audience, intended use, features, brand) as given.\n"
        "2. Facts that appear ONLY in Source A must be presented as what is seen in "
        "the product photos.\n"
        "3. NEVER invent or imply any specification, material, feature, measurement, "
        "certification, award, price or performance claim that appears in neither "
        "source. If a typical product detail is unknown, simply leave it out - do "
        "not fill gaps.\n"
        "4. In the description, when a claim comes from Source B, attribute it "
        "naturally with wording such as 'designed to', 'stated to', 'according to "
        "the seller' or 'the seller states' (adapt to the tone and language; keep "
        "it readable, do not over-qualify every sentence).\n"
        "5. Slogans must stay truthful to the sources too; they may mention "
        "user-supplied selling points but must not invent new specifics.\n\n"
        f"Return exactly {n_slogans} distinct slogan(s), each a single punchy line "
        "without quotation marks or numbering.\n\n"
        "OUTPUT FORMAT (mandatory): reply with a single valid JSON object and "
        "nothing else - no markdown fences, no commentary:\n"
        "{\n"
        '  "product_description": "<2-5 sentence marketing description>",\n'
        '  "slogans": ["<slogan 1>", "<slogan 2>", ...],\n'
        '  "sources": {\n'
        '    "from_images": ["<fact visible in / readable on the product photos>", ...],\n'
        '    "from_user": ["<fact taken from the seller-supplied information>", ...]\n'
        "  }\n"
        "}\n"
        "If Source B was empty, set \"from_user\" to an empty list."
    )
    return "\n".join(parts)


GENERATION_SYSTEM_PROMPT = (
    "You are a senior marketing copywriter who produces accurate, well-grounded "
    "product content for e-commerce listings. You never fabricate product "
    "attributes. You separate what is visible in product photos from what the "
    "seller has stated, and you always follow the requested JSON output contract."
)

JSON_RETRY_INSTRUCTION = (
    "Your previous reply could not be parsed as JSON. Reply again with a single "
    "valid JSON object and nothing else - no markdown fences, no commentary - "
    "with keys \"product_description\", \"slogans\" and \"sources\"."
)


# ---------------------------------------------------------------------------
# AI providers (two interchangeable backends)
# ---------------------------------------------------------------------------
#   * "openai" - OpenAI Chat Completions REST API, called directly from
#     Python with urllib. Needs only OPENAI_API_KEY; no Node.js, no npm.
#   * "zai"    - z-ai-web-dev-sdk through the embedded Node.js bridge.
# Both speak the same OpenAI-style message format, so the prompt logic is
# shared; only the transport and the system-role name differ (OpenAI uses
# "system", the legacy SDK uses "assistant" for the system prompt).

def resolve_provider(choice: str) -> str:
    """Turn the --provider choice into a concrete backend with clear errors."""
    if choice == "openai":
        if not (os.environ.get("OPENAI_API_KEY") or "").strip():
            raise UsageError(
                "--provider openai needs the OPENAI_API_KEY environment variable. "
                "Set it first, e.g.: setx OPENAI_API_KEY \"sk-...\" (Windows, then "
                "reopen the terminal) or export OPENAI_API_KEY=sk-... (macOS/Linux)."
            )
        return "openai"
    if choice == "zai":
        return "zai"
    # auto: prefer OpenAI when a key is present, otherwise the z-ai SDK
    if (os.environ.get("OPENAI_API_KEY") or "").strip():
        return "openai"
    return "zai"


def openai_chat(messages: list[dict], timeout_s: float) -> str:
    """Call the OpenAI-compatible Chat Completions API with urllib."""
    api_key = os.environ["OPENAI_API_KEY"].strip()
    base = (os.environ.get("OPENAI_BASE_URL") or DEFAULT_OPENAI_BASE_URL).rstrip("/")
    model = (os.environ.get("OPENAI_MODEL") or OPENAI_MODEL).strip()
    body = json.dumps({"model": model, "messages": messages}).encode("utf-8")
    req = urllib.request.Request(
        f"{base}/chat/completions",
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as err:
        try:
            detail = err.read().decode("utf-8", "replace")[:400]
        except Exception:
            detail = ""
        if err.code == 401:
            hint = "the API key was rejected (401). Check OPENAI_API_KEY."
        elif err.code == 429:
            hint = ("rate limit or quota exceeded (429). Check your OpenAI "
                    "billing/usage page, or retry in a moment.")
        elif err.code == 404:
            hint = (f"model or endpoint not found (404). Check OPENAI_MODEL "
                    f"(currently '{model}') and OPENAI_BASE_URL ('{base}').")
        else:
            hint = f"HTTP {err.code}."
        raise AiCallError(f"OpenAI request failed: {hint} API said: {detail}")
    except urllib.error.URLError as err:
        raise AiCallError(
            f"Could not reach {base}: {err.reason}. Check your internet connection."
        )
    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        raise AiCallError(f"Unexpected OpenAI response shape: {json.dumps(data)[:400]}")
    if not content or not content.strip():
        raise AiCallError("OpenAI returned an empty reply.")
    return content


def extract_json_object(raw: str) -> dict | None:
    """Tolerant JSON extraction (handles markdown fences and stray prose)."""
    if not raw:
        return None
    text = raw.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL | re.IGNORECASE)
    if fence and fence.group(1).strip():
        text = fence.group(1).strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        parsed = json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, dict):
        return None
    description = parsed.get("product_description") or parsed.get("description")
    slogans = parsed.get("slogans")
    if not isinstance(description, str) or not isinstance(slogans, list):
        return None
    return parsed


def zai_call(sdk_root: str, request: dict, timeout_s: float) -> dict:
    """Send one request through the Node bridge and validate the envelope."""
    request.setdefault("timeout_ms", int(timeout_s * 1000))
    payload = run_bridge(request, sdk_root, timeout_s=timeout_s + 60.0)
    if not payload.get("ok"):
        error = payload.get("error", "unknown error")
        raw = payload.get("raw")
        raise AiCallError(f"AI request failed: {error}" + (f"\nModel reply was: {raw}" if raw else ""))
    return payload


def vision_inventory(provider: str, sdk_root: str, images: list[dict], timeout_s: float) -> str:
    """Call 1: build a strictly visual inventory of the product."""
    content: list[dict] = [
        {"type": "text", "text": VISION_INVENTORY_PROMPT}
    ]
    for img in images:
        content.append({"type": "image_url", "image_url": {"url": img["data_url"]}})
    messages = [{"role": "user", "content": content}]

    if provider == "openai":
        inventory = openai_chat(messages, timeout_s)
    else:
        payload = zai_call(
            sdk_root,
            {
                "kind": "vision",
                "model": VISION_MODEL,
                "messages": messages,
                "expect_json": False,
            },
            timeout_s,
        )
        inventory = payload.get("content") or ""

    inventory = (inventory or "").strip()
    if not inventory:
        raise AiCallError("The vision model returned an empty inventory.")
    return inventory


def generate_content(
    provider: str,
    sdk_root: str,
    inventory: str,
    info: str | None,
    language: str,
    tone: str,
    n_slogans: int,
    timeout_s: float,
) -> dict:
    """Call 2: produce description + slogans + fact-source lists as JSON."""
    prompt = build_generation_prompt(inventory, info, language, tone, n_slogans)

    if provider == "openai":
        messages = [
            {"role": "system", "content": GENERATION_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ]
        raw = openai_chat(messages, timeout_s)
        parsed = extract_json_object(raw)
        if parsed is None:
            # one guided retry with the parse error shown to the model
            retry = messages + [
                {"role": "assistant", "content": raw},
                {"role": "user", "content": JSON_RETRY_INSTRUCTION},
            ]
            parsed = extract_json_object(openai_chat(retry, timeout_s))
        if parsed is None:
            raise AiCallError(
                "The model reply could not be parsed as the expected JSON "
                f"object. Last reply started with: {raw[:300]!r}"
            )
        return parsed

    payload = zai_call(
        sdk_root,
        {
            "kind": "text",
            "model": TEXT_MODEL,
            "messages": [
                {"role": "assistant", "content": GENERATION_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            "expect_json": True,
        },
        timeout_s,
    )
    return payload["json"]


# ---------------------------------------------------------------------------
# Output rendering
# ---------------------------------------------------------------------------

RULE = "=" * 78
THIN = "-" * 78


def wrap(text: str, width: int = 88) -> str:
    return "\n".join(textwrap.wrap(text, width=width)) if text else ""


def render_terminal(result: dict) -> str:
    """Plain-text rendering shown in the terminal."""
    lines = [RULE, "PRODUCT MARKETING CONTENT", RULE, ""]
    lines += ["PRODUCT DESCRIPTION:", wrap(result["product_description"]), ""]
    lines.append("MARKETING SLOGANS:")
    for slogan in result["slogans"]:
        lines.append(f"  - {slogan}")
    lines += ["", "INFORMATION SOURCES:", THIN]
    sources = result.get("sources") or {}
    from_images = sources.get("from_images") or []
    from_user = sources.get("from_user") or []

    if from_images:
        lines.append("  Verified from the product images:")
        for fact in from_images:
            lines.append(f"    * {fact}")
    else:
        lines.append("  Verified from the product images: (none reported)")
    lines.append("")
    if from_user:
        lines.append("  Supplied by the seller (not verified against the images):")
        for fact in from_user:
            lines.append(f"    * {fact}")
    else:
        lines.append("  Supplied by the seller: (no user information was provided)")
    lines += ["", THIN]
    lines.append(
        "Note: seller-supplied facts are used as stated and have not been "
        "verified against the product images."
    )
    lines.append(RULE)
    return "\n".join(lines)


def render_markdown(result: dict, meta: dict) -> str:
    """Markdown rendering used for --output."""
    md = [
        "# Product Marketing Content",
        "",
        "## Product Description",
        "",
        result["product_description"],
        "",
        "## Marketing Slogans",
        "",
    ]
    md += [f"- {slogan}" for slogan in result["slogans"]]
    sources = result.get("sources") or {}
    from_images = sources.get("from_images") or []
    from_user = sources.get("from_user") or []
    md += ["", "## Information Sources", ""]
    md.append("**Verified from the product images:**")
    md.append("")
    md += [f"- {fact}" for fact in from_images] if from_images else ["- (none reported)"]
    md += ["", "**Supplied by the seller (not verified against the images):**", ""]
    md += [f"- {fact}" for fact in from_user] if from_user else ["- (none)"]
    md += [
        "",
        "---",
        "",
        f"*Generated with {PROG} on {meta['timestamp']} - images analysed: "
        f"{meta['image_count']} ({meta['image_names']}); tone: {meta['tone']}; "
        f"language: {meta['language']}.*",
        "",
    ]
    return "\n".join(md)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=PROG,
        description=(
            "Generate a product description and marketing slogans from one or "
            "more product images, optionally combined with seller-supplied "
            "product information. The output clearly separates facts verified "
            "from the images from facts supplied by the user."
        ),
        epilog=(
            "examples:\n"
            f"  python {PROG} --images front.jpg side.jpg packaging.jpg \\\n"
            "      --info \"Stainless-steel insulated bottle, 750 ml, keeps drinks cold for 24 hours\"\n"
            f"  python {PROG} --images shoe1.jpg shoe2.jpg \\\n"
            "      --info \"Water-resistant hiking shoe for autumn and winter\" \\\n"
            "      --tone professional --slogans 5 --output content.md\n"
            "\n"
            "runtime:\n"
            "  Requires Node.js 18+ and the z-ai-web-dev-sdk npm package. Point\n"
            "  PRODUCT_MARKETING_SDK_PATH at a directory containing node_modules/\n"
            "  if the package is not found automatically."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--images",
        required=True,
        nargs="+",
        metavar="IMG",
        help=f"one or more product images (supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}; max {MAX_IMAGES})",
    )
    parser.add_argument(
        "--info",
        default=None,
        help=(
            "optional seller-supplied product facts: name, materials, dimensions, "
            "technical specifications, target audience, intended use, features, brand"
        ),
    )
    parser.add_argument(
        "--language",
        default=DEFAULT_LANGUAGE,
        metavar="LANG",
        help=f"language of the generated content (default: {DEFAULT_LANGUAGE})",
    )
    parser.add_argument(
        "--tone",
        default=DEFAULT_TONE,
        metavar="TONE",
        help="tone of voice, e.g. friendly, professional, playful, luxurious, technical "
             f"(default: {DEFAULT_TONE}); free text is accepted",
    )
    parser.add_argument(
        "--slogans",
        type=int,
        default=DEFAULT_SLOGANS,
        metavar="N",
        help=f"number of slogans to generate, 1-{MAX_SLOGANS} (default: {DEFAULT_SLOGANS})",
    )
    parser.add_argument(
        "--output",
        default=None,
        metavar="FILE",
        help="also write the generated content to FILE as Markdown",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_CALL_TIMEOUT,
        metavar="SEC",
        help=f"per-call AI timeout in seconds (default: {DEFAULT_CALL_TIMEOUT})",
    )
    parser.add_argument(
        "--provider",
        choices=("auto", "openai", "zai"),
        default="auto",
        help=(
            "AI backend: 'openai' calls the OpenAI API directly with "
            "OPENAI_API_KEY (no Node.js needed); 'zai' uses the "
            "z-ai-web-dev-sdk Node bridge; 'auto' (default) picks OpenAI when "
            "OPENAI_API_KEY is set, otherwise the z-ai SDK"
        ),
    )
    return parser


def validate_args(args: argparse.Namespace) -> None:
    if len(args.images) > MAX_IMAGES:
        raise UsageError(f"Too many images ({len(args.images)}); the maximum is {MAX_IMAGES}.")
    if not (1 <= args.slogans <= MAX_SLOGANS):
        raise UsageError(f"--slogans must be between 1 and {MAX_SLOGANS} (got {args.slogans}).")
    if args.timeout <= 0:
        raise UsageError("--timeout must be a positive number of seconds.")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        validate_args(args)
    except UsageError as err:
        parser.exit(2, f"{PROG}: error: {err}\n")

    try:
        provider = resolve_provider(args.provider)
        images = load_images(args.images)
        if not args.info or not args.info.strip():
            print(
                "Note: no --info given; content will be based only on what is "
                "visible in the images.",
                file=sys.stderr,
            )

        sdk_root = ""
        if provider == "openai":
            model = (os.environ.get("OPENAI_MODEL") or OPENAI_MODEL).strip()
            print(
                f"Provider: OpenAI ({model}) - key loaded from OPENAI_API_KEY.",
                file=sys.stderr,
            )
        else:
            sdk_root = ensure_runtime()
            print("Provider: z-ai-web-dev-sdk (Node bridge).", file=sys.stderr)

        names = ", ".join(img["label"] for img in images)
        print(
            f"Analysing {len(images)} image(s) [{names}] with the vision model...",
            file=sys.stderr,
        )
        inventory = vision_inventory(provider, sdk_root, images, args.timeout)

        print("Generating description and slogans...", file=sys.stderr)
        result = generate_content(
            provider,
            sdk_root,
            inventory,
            args.info,
            args.language,
            args.tone,
            args.slogans,
            args.timeout,
        )

        output_text = render_terminal(result)
        print(output_text)

        if args.output:
            from datetime import datetime

            meta = {
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "image_count": len(images),
                "image_names": names,
                "tone": args.tone,
                "language": args.language,
            }
            out_path = Path(args.output).expanduser()
            try:
                if out_path.parent and not out_path.parent.exists():
                    out_path.parent.mkdir(parents=True, exist_ok=True)
                out_path.write_text(
                    render_markdown(result, meta), encoding="utf-8"
                )
                print(f"Saved Markdown output to: {out_path}", file=sys.stderr)
            except OSError as err:
                print(f"Warning: could not write output file: {err}", file=sys.stderr)
                return 1
        return 0

    except UsageError as err:
        print(f"{PROG}: error: {err}", file=sys.stderr)
        return 2
    except AiCallError as err:
        print(f"{PROG}: AI error: {err}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
