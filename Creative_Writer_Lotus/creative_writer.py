"""Creative Writer CLI: three independent OpenAI generations and comparison."""

import argparse
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

from openai import (
    OpenAI, AuthenticationError, BadRequestError, RateLimitError,
    APIConnectionError, APITimeoutError, APIStatusError,
)

MODEL = "gpt-4.1-mini"
DEVELOPER_PROMPT = """You are a skilled, original, audience-aware creative writer.
Produce polished content that fulfills the requested genre, tone, and audience.
Avoid cliches, unnecessary repetition, and unsupported factual claims.
For SEO content, use synonyms and semantically related terms naturally;
never keyword-stuff. For claims requiring verification, avoid invented facts,
quotes, statistics, or citations. Follow the user's length limit.
Return only the requested creative writing, without an introduction.
"""


def get_args():
    parser = argparse.ArgumentParser(description="Generate and compare three creative writing versions.")
    parser.add_argument("prompt", nargs="*", help="Your creative writing request (or leave blank for interactive input)")
    parser.add_argument("--max-words", type=int, default=120, help="Target maximum words per version (default: 120)")
    parser.add_argument("--max-tokens", type=int, default=450, help="Hard output-token limit (default: 450)")
    parser.add_argument("--top-p", type=float, default=1.0, help="Nucleus sampling threshold, 0 < value <= 1")
    parser.add_argument("--presence-penalty", type=float, default=0.0, help="Presence penalty, -2 to 2")
    parser.add_argument("--frequency-penalty", type=float, default=0.0, help="Frequency penalty, -2 to 2")
    parser.add_argument("--output", default="creative_writer_results.txt", help="File to save results")
    args = parser.parse_args()
    if not (1 <= args.max_words <= 5000):
        parser.error("--max-words must be from 1 to 5000")
    if not (16 <= args.max_tokens <= 16000):
        parser.error("--max-tokens must be from 16 to 16000")
    if not (0 < args.top_p <= 1):
        parser.error("--top-p must be greater than 0 and at most 1")
    if not (-2 <= args.presence_penalty <= 2 and -2 <= args.frequency_penalty <= 2):
        parser.error("penalties must be from -2 to 2")
    return args


def repetition_rate(text):
    """Approximate repeated-word share; not a quality score."""
    words = re.findall(r"\b[\w']+\b", text.lower())
    return 0.0 if not words else 100 * (len(words) - len(set(words))) / len(words)


def main():
    args = get_args()
    prompt = " ".join(args.prompt).strip()
    if not prompt:
        try:
            prompt = input("What would you like me to write? ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nCancelled.")
            return 1
    if not prompt:
        print("Error: A writing request is required.")
        return 1
    if not os.getenv("OPENAI_API_KEY"):
        print("Error: OPENAI_API_KEY is not set in your environment.")
        return 1

    client = OpenAI(timeout=60.0, max_retries=1)
    variants = [
        ("Focused", 0.3, "Use precise, clear, direct language."),
        ("Balanced", 0.8, "Balance originality, clarity, and emotional appeal."),
        ("Imaginative", 1.2, "Try a distinctive, vivid creative approach while remaining relevant."),
    ]
    records = []
    for index, (style, temperature, style_note) in enumerate(variants, 1):
        print(f"\nGenerating version {index}/3 ({style}, temperature={temperature})...")
        started = time.perf_counter()
        try:
            response = client.responses.create(
                model=MODEL,
                instructions=DEVELOPER_PROMPT,
                input=(
                    f"Writing request: {prompt}\n"
                    f"Target audience: as described in the writing request; otherwise general readers.\n"
                    f"Maximum length: {args.max_words} words.\n"
                    f"Version direction: {style_note}"
                ),
                temperature=temperature,
                top_p=args.top_p,
                max_output_tokens=args.max_tokens,
            )
            elapsed = time.perf_counter() - started
            content = (response.output_text or "").strip()
            if not content:
                print("No text was returned for this version.")
                continue
            words = len(content.split())
            repeated = repetition_rate(content)
            tokens = response.usage.total_tokens if response.usage else "unknown"
            records.append((index, style, temperature, elapsed, words, repeated, tokens, content))
            print(f"\n{'=' * 18} VERSION {index}: {style.upper()} {'=' * 18}")
            print(content)
            print(f"\nTime: {elapsed:.2f}s | Words: {words} | Repeated-word share: {repeated:.1f}% | Tokens: {tokens}")
        except AuthenticationError:
            print("Authentication failed. Check/recreate your API key.")
            break
        except RateLimitError:
            print("Rate limit or quota exceeded. Check billing and usage limits.")
            break
        except (APIConnectionError, APITimeoutError):
            print("Connection/timeout error. Check internet and try again.")
        except BadRequestError as exc:
            print(f"Request rejected. Check model or settings: {exc.message}")
            break
        except APIStatusError as exc:
            print(f"OpenAI API returned HTTP {exc.status_code}. Please try again later.")
        except KeyboardInterrupt:
            print("\nInterrupted.")
            break

    if not records:
        print("No successful results to save.")
        return 1

    lines = [
        "AI CREATIVE WRITER — EXPERIMENT REPORT",
        f"Date: {datetime.now().isoformat(timespec='seconds')}",
        f"Model: {MODEL}", f"Prompt: {prompt}",
        f"Word target: {args.max_words}; output-token cap: {args.max_tokens}",
        f"top_p={args.top_p}; presence_penalty={args.presence_penalty}; frequency_penalty={args.frequency_penalty}",
        "", "COMPARISON (repeat-word share is only a rough indicator)",
        "Version | Style | Temperature | Latency(s) | Words | Repeat-word % | Total tokens",
    ]
    for i, style, temp, secs, words, repeats, tokens, content in records:
        lines.append(f"{i} | {style} | {temp} | {secs:.2f} | {words} | {repeats:.1f} | {tokens}")
    lines.extend(["", "FULL OUTPUTS"])
    for i, style, temp, secs, words, repeats, tokens, content in records:
        lines.extend(["", f"VERSION {i} — {style} (temperature {temp})", content])
    lines.extend(["", "HUMAN REVIEW — complete after reading the outputs:",
                  "Creativity: Which version uses the freshest ideas?", 
                  "Repetition: Which version repeats itself or uses cliches?",
                  "Factual accuracy: Verify any factual claims with reliable sources.",
                  "Writing style: Which tone best suits the task?",
                  "Latency: Compare measured generation times above.",
                  "Reasoning: Not tested; this non-reasoning model uses sampling controls.",
                  "Audience usefulness: Which version would you actually publish or use?"])
    try:
        path = Path(args.output)
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print("\n" + "=" * 16 + " COMPARISON " + "=" * 16)
        for i, style, temp, secs, words, repeats, tokens, _ in records:
            print(f"V{i} {style:11} temp={temp} time={secs:.2f}s words={words} repeated-word={repeats:.1f}% tokens={tokens}")
        print(f"\nSaved outputs and review questions to: {path.resolve()}")
        if len(records) < 3:
            print(f"Only {len(records)} of 3 generations succeeded; rerun to complete the assignment.")
            return 1
    except OSError as exc:
        print(f"Could not save file: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
