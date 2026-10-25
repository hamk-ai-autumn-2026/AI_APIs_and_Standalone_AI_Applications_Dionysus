# SETUP STEPS — from ZIP to submitted GitHub repo (VS Code)

Follow these steps in order. Everything is done inside VS Code.
Time needed: about 15–20 minutes (plus installing Python/Node if missing).

---

## 0. What you need before starting

| Requirement | How to check | Where to get it |
|---|---|---|
| Python 3.8+ | `python --version` (Windows) or `python3 --version` (macOS/Linux) | https://www.python.org/downloads/ — **Windows: tick "Add Python to PATH" in the installer!** |
| AI credentials | see step 3 | **OpenAI API key (easiest)** or course-provided `z-ai` credentials |
| Node.js 18+ | `node --version` — **only needed for the `zai` provider** | https://nodejs.org (LTS version) |
| VS Code | — | https://code.visualstudio.com |
| 1–8 product photos | — | Photograph any real product with a phone (see step 7) |

---

## 1. Get the project onto your computer

1. Download **`product-marketing-vscode.zip`** from this chat to your computer.
2. Right-click the zip → **Extract All…** (Windows) or double-click (macOS).
3. You now have a folder named `product-marketing` containing:
   `product_marketing.py`, `README.md`, `SETUP_STEPS.md`,
   `package.json`, `.gitignore`, `samples/`.

---

## 2. Open the project in VS Code

1. Open VS Code.
2. **File ▸ Open Folder…** → select the extracted `product-marketing` folder.
3. If VS Code asks "Do you trust the authors?", click **Yes, I trust the authors**.

---

## 3. Configure your AI provider (pick ONE — A is easiest)

### Option A — OpenAI API key (recommended; no Node.js, no npm needed)

The tool calls the OpenAI Chat Completions API directly from Python.

**Windows:**
1. In the VS Code terminal run:  `setx OPENAI_API_KEY "sk-...your key..."`
2. **Close and reopen the terminal** (setx only affects NEW terminals).
3. Verify: `echo %OPENAI_API_KEY%` (cmd) or `$env:OPENAI_API_KEY` (PowerShell).

**macOS / Linux:**
```bash
export OPENAI_API_KEY="sk-...your key..."      # current terminal
echo 'export OPENAI_API_KEY="sk-..."' >> ~/.zshrc   # make it permanent (zsh)
```

> The model defaults to `gpt-4o-mini` (vision-capable and inexpensive).
> Override with `OPENAI_MODEL` (e.g. `gpt-4o`) if you want. A few test runs
> with gpt-4o-mini cost only a couple of US cents.

### Option B — course-provided z-ai credentials (only if your teacher says so)

Requires Node.js 18+ and `npm install` (step 4). Create a file named
**`.z-ai-config`** in the project folder:

```json
{
  "baseUrl": "YOUR_API_BASE_URL",
  "apiKey": "YOUR_API_KEY"
}
```

> `baseUrl` must include the `/v1` prefix.

⚠️ **SECURITY — read this:**
- With Option B, `.gitignore` already contains `.z-ai-config`, so git will
  **not** upload it. Never commit, screenshot, or share any API key.
- **Never put your API key in `product_marketing.py` or any committed file.**

---

## 4. Install dependencies (only for Option B)

- **OpenAI (Option A): nothing to install — skip this step.**
- z-ai (Option B): in the VS Code terminal (**Ctrl+`**) run:

  ```bash
  npm install
  ```

  This downloads `z-ai-web-dev-sdk` (declared in `package.json`) into
  `node_modules/` inside the project.

---

## 5. Verify everything works

```bash
node --version
python --version        # Windows  (if that fails, try: py --version)
python3 --version       # macOS / Linux
python product_marketing.py --help     # Windows
python3 product_marketing.py --help    # macOS / Linux
```

You should see the help text listing `--images`, `--info`, `--language`,
`--tone`, `--slogans`, `--output`, `--timeout`.

---

## 6. First test run — bundled demo images

These commands are single-line on purpose (PowerShell does not support
multi-line `\` commands).

**Windows (PowerShell):**

```powershell
python product_marketing.py --images samples/bottle_1.jpg samples/bottle_2.jpg --info "Stainless-steel insulated bottle, 750 ml, keeps drinks cold for 24 hours" --tone friendly --slogans 3 --output bottle_content.md
```

**macOS / Linux:**

```bash
python3 product_marketing.py --images samples/bottle_1.jpg samples/bottle_2.jpg --info "Stainless-steel insulated bottle, 750 ml, keeps drinks cold for 24 hours" --tone friendly --slogans 3 --output bottle_content.md
```

After ~20–60 seconds you get the description, slogans and the
**Information Sources** section, and a `bottle_content.md` file appears.
The first stderr line shows which provider was used
(`Provider: OpenAI (gpt-4o-mini) ...` or `Provider: z-ai-web-dev-sdk ...`).
This only proves the tool works — it is **not** your submission material.

---

## 7. The real run — YOUR OWN product photos (this is what you submit)

The bundled sample photos are real product photos found online — demo
material only. Your report and screenshots must
come from **your own product photos**.

1. **Choose a real product** (mug, shoe, water bottle, headphones, …).
2. **Photograph it 2–4 times** with a phone: front, side, packaging/label.
   Good lighting, product fills most of the frame, label text readable.
3. Copy the photos into the project folder (e.g. create a `photos/` folder),
   named like `front.jpg`, `side.jpg`, `packaging.jpg`.
4. Write a `--info` line with facts **not visible** in the photos:
   material, capacity/dimensions, target audience, intended use, brand.
5. Run (single line — adjust the photo names):

   ```powershell
   python product_marketing.py --images photos/front.jpg photos/side.jpg photos/packaging.jpg --info "Bamboo fibre travel mug, 400 ml, dishwasher safe, designed for commuting" --tone professional --slogans 5 --output my_product_content.md
   ```

6. Try different options for the report if you like:
   `--tone playful`, `--slogans 3`, `--language Finnish`, etc.

---

## 8. Take YOUR screenshots (1–2 for the report)

1. Re-run one of YOUR commands from step 7 (or step 6 as a warm-up).
2. Make sure the whole output is visible — if not, right-click the terminal
   panel and choose **Maximize Panel**, or scroll up.
3. Capture the screenshot **including the command line you typed and the
   full generated output**:
   - **Windows:** press **Win+Shift+S** (Snipping Tool) → drag over the
     terminal area → paste into Paint → save as PNG. Or **Alt+PrtScn** to
     capture the active window.
   - **macOS:** **Cmd+Shift+4** → drag over the terminal area (PNG appears
     on the Desktop).
4. Create a folder `screenshots/` in the project and save the images there:

   ```
   screenshots/screenshot-1.png    <- first run (description + slogans + information sources)
   screenshots/screenshot-2.png    <- second run (different tone/slogans/output option)
   ```

---

## 9. Publish to GitHub

### Option A — entirely inside VS Code (easiest)

1. Left sidebar → **Source Control** icon (branch symbol).
2. Click **Initialize Repository**.
3. Review the changed files (`node_modules/` and `.z-ai-config` must NOT be
   listed — `.gitignore` protects you; if you see them, stop and check
   `.gitignore`).
4. Type a commit message, e.g. `Exercise 9: product description generator CLI`
   → press **Commit**.
5. Click **Publish Branch** → choose *Publish to GitHub public repository*
   (sign in with your GitHub account in the browser popup when asked).
6. Name the repository, e.g. `product-marketing-cli`, and confirm.

### Option B — git command line

Create an empty repo on https://github.com (New repository, **do not** tick
"Add a README"), then:

```bash
git init
git add .
git commit -m "Exercise 9: product description generator CLI"
git branch -M main
git remote add origin https://github.com/YOUR-USERNAME/product-marketing-cli.git
git push -u origin main
```

---

## 10. Final checklist before submitting

- [ ] Repository opens on github.com and shows `README.md` rendered
- [ ] `product_marketing.py`, `package.json`, `samples/`,
      `screenshots/` are all visible in the repo
- [ ] `node_modules/` is **not** in the repo
- [ ] `.z-ai-config` / `.env` is **not** in the repo (no API key leak!)
- [ ] Your screenshots show **your own run**, ideally with **your own product photos**
- [ ] Group name, all member names, repo link and models answer are ready to
      paste into the course submission form
- [ ] Submit: group name, member names, 1–2 screenshots, GitHub link, models used

**Models used (answer for the report — keep the one matching your runs):**

*If you used the OpenAI provider (default when OPENAI_API_KEY is set):*

| Purpose | Model |
|---|---|
| Image analysis (vision) | **GPT-4o mini** (`gpt-4o-mini`) — vision-capable, called via the OpenAI Chat Completions API |
| Description + slogans (text) | **GPT-4o mini** (`gpt-4o-mini`) — same multimodal model, two calls |

*If you used the z-ai provider (`--provider zai`):*

| Purpose | Model |
|---|---|
| Image analysis (vision) | **GLM-4.6V** (`glm-4.6v`) via `zai.chat.completions.createVision()` |
| Description + slogans (text) | **GLM-4-Plus** (`glm-4-plus`) via `zai.chat.completions.create()` |

In both cases the models are defined as constants / defaults at the top of
`product_marketing.py` (`OPENAI_MODEL`, `VISION_MODEL`, `TEXT_MODEL`), and
the two-call design keeps them specialised: the vision model is only asked
to *report what is visible*, and the text model does the copywriting under
strict grounding rules.

---

## 11. Troubleshooting

| Problem | Fix |
|---|---|
| `python: command not found` (Windows) | Reinstall Python with "Add Python to PATH" ticked, or use `py` instead |
| `--provider openai needs the OPENAI_API_KEY environment variable` | The key is not set in THIS terminal. Windows: run `setx OPENAI_API_KEY "sk-..."` and **reopen the terminal**; in the current PowerShell session use `$env:OPENAI_API_KEY="sk-..."`. macOS/Linux: `export OPENAI_API_KEY=sk-...` |
| `OpenAI request failed: the API key was rejected (401)` | The key is wrong/revoked — copy it again from platform.openai.com |
| `rate limit or quota exceeded (429)` | Your OpenAI credit/billing is exhausted or you are rate-limited — check platform.openai.com ▸ Billing, or wait a minute |
| `model or endpoint not found (404)` | Set `OPENAI_MODEL` to a valid vision-capable model (e.g. `gpt-4o-mini`) |
| `node: command not found` (zai provider only) | Install Node.js LTS from nodejs.org, then **restart VS Code** — or switch to the OpenAI provider |
| `The 'z-ai-web-dev-sdk' npm package could not be located` | Run `npm install` inside the project folder (zai provider only) |
| AI error about `.z-ai-config` | Missing or wrong credentials file for the zai provider — see step 3 Option B |
| `error: Image not found` | The photo path/name is wrong — run `dir photos` (Windows) or `ls photos` to check names |
| `does not look like a real image` | The file is corrupted or renamed (e.g. a PDF renamed to .jpg) — re-export the photo |
| Multi-line command with `\` fails in PowerShell | Use the single-line commands from this guide |
| Screenshot shows only part of the output | Right-click terminal panel → **Maximize Panel**, or scroll up before capturing |
