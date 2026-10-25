#!/usr/bin/env python3
"""Assignment #5 -- Schema-validated AI dictionary.

Asks the user for a word, asks a configurable LLM provider for a
dictionary entry (definitions, synonyms, antonyms, examples), and
validates the reply against a JSON Schema *before* it is used. Invalid
output is fed back to the model together with the exact validation
errors so it can correct itself (MAX_ATTEMPTS tries in total).

The provider is pluggable (see providers/): switching provider is a
command-line flag and nothing else in the application changes.

Usage:
    python main.py                            # interactive mode
    python main.py --word kallis              # one-shot, default provider
    python main.py --provider anthropic       # switch provider
    python main.py --list-providers           # show all providers
    python main.py --provider openai --model gpt-4o --word kallis
"""

from __future__ import annotations

import argparse
import os
import sys

import prompts
from providers import ProviderError, create_provider, provider_names
from validation import ValidationError, build_validated_entry

MAX_ATTEMPTS = 3  # 1 original attempt + 2 self-correction retries

LINE = "=" * 64
THIN = "-" * 64


def generate_entry(provider, word: str) -> dict:
    """Return a schema-validated dictionary entry for *word*.

    Each attempt: provider reply -> JSON extraction -> schema validation.
    On validation failure the exact schema errors are fed back to the
    provider so the model can fix its own output. Provider/network errors
    are retried the same way. Raises ValidationError when all attempts
    are exhausted.
    """
    user_prompt = prompts.build_user_prompt(word)

    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            raw = provider.complete(prompts.SYSTEM_PROMPT, user_prompt)
        except Exception as exc:  # noqa: BLE001 -- any backend failure is retryable
            print(f"  ! attempt {attempt}/{MAX_ATTEMPTS}: provider error: {exc}")
            continue

        try:
            entry = build_validated_entry(raw)
        except ValidationError as exc:
            print(f"  ! attempt {attempt}/{MAX_ATTEMPTS} rejected, feeding errors back:")
            print(_indent(str(exc)))
            user_prompt = prompts.build_retry_prompt(word, raw, str(exc))
        else:
            if attempt > 1:
                print(f"  + model produced valid output on attempt {attempt}/{MAX_ATTEMPTS}")
            return entry

    raise ValidationError(
        f"the model did not produce schema-valid output in {MAX_ATTEMPTS} attempts"
    )


def _indent(text: str) -> str:
    return "\n".join("      " + line for line in text.splitlines())


def pretty_print(entry: dict, footer: str) -> None:
    """Print a validated entry as a readable dictionary card."""
    print()
    print(LINE)
    print(f"  {entry['word'].upper()}")
    print(LINE)

    for title, key in (
        ("DEFINITIONS", "definitions"),
        ("SYNONYMS", "synonyms"),
        ("ANTONYMS", "antonyms"),
        ("EXAMPLES", "examples"),
    ):
        print(f"\n  {title}")
        items = entry[key]
        if not items:
            print("   (none found)")
        for item in items:
            print(f"   - {item}")

    print()
    print(THIN)
    print(f"  provider: {footer} | schema-validated: yes")
    print(LINE)


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="dictionary",
        description="Assignment #5: schema-validated AI dictionary.",
    )
    parser.add_argument(
        "-w", "--word",
        help="look up this word and exit (omit for interactive mode)",
    )
    parser.add_argument(
        "-p", "--provider",
        default=os.environ.get("DICTIONARY_PROVIDER", "openai"),
        help="LLM backend to use (default: %(default)s). "
             f"Available: {', '.join(provider_names())}",
    )
    parser.add_argument(
        "--model",
        help="override the provider's default model",
    )
    parser.add_argument(
        "--list-providers",
        action="store_true",
        help="list available providers and exit",
    )
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)

    if args.list_providers:
        print("Available providers:")
        for name in provider_names():
            marker = "   (default)" if name == args.provider else ""
            print(f"  - {name}{marker}")
        return 0

    try:
        provider = create_provider(args.provider, model=args.model)
    except ProviderError as exc:
        print(f"Cannot start provider {args.provider!r}: {exc}", file=sys.stderr)
        return 1

    print(f"AI dictionary -- provider: {provider.describe()}")

    one_shot = args.word is not None
    if one_shot:
        words = [args.word]
    else:
        print("Type a word to look it up, or press Enter to quit.")

    while True:
        if one_shot:
            word = args.word
        else:
            try:
                word = input("\nWord to look up: ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nGoodbye!")
                return 0
            if not word:
                print("Goodbye!")
                return 0

        try:
            entry = generate_entry(provider, word)
        except ValidationError as exc:
            print(f"\nCould not produce a valid entry for {word!r}: {exc}")
            if one_shot:
                return 1
            continue

        pretty_print(entry, provider.describe())
        if one_shot:
            return 0


if __name__ == "__main__":
    sys.exit(main())
