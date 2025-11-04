#!/usr/bin/env python3
"""
Streams a Grok completion using the current Cline bearer token.

Usage:
    python scripts/cline_grok_chat.py [--secrets PATH] [--threshold-seconds N]

The script reuses cline_get_token.get_bearer_token to obtain (and refresh) the token, then
issues a streaming chat completion request with minimal headers.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
import urllib.error
import urllib.request

from cline_get_token import get_bearer_token

CLINE_CHAT_ENDPOINT = "https://api.cline.bot/api/v1/chat/completions"


def parse_args() -> argparse.Namespace:
    home = pathlib.Path.home()
    default_secrets = home / ".cline" / "data" / "secrets.json"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--secrets",
        type=pathlib.Path,
        default=default_secrets,
        help=f"Path to secrets.json (default: {default_secrets})",
    )
    parser.add_argument(
        "--threshold-seconds",
        type=int,
        default=300,
        help="Refresh token when it expires in <= this many seconds (default: 300).",
    )
    return parser.parse_args()


def stream_chat(bearer_token: str) -> None:
    body = json.dumps(
        {
            "model": "x-ai/grok-code-fast-1",
            "messages": [
                {"role": "system", "content": "You are running a short test from Cline CLI."},
                {"role": "user", "content": "Say hello from Grok."},
            ],
            "temperature": 0,
            "stream": True,
            "stream_options": {"include_usage": True},
            "include_reasoning": True,
        }
    ).encode("utf-8")

    req = urllib.request.Request(CLINE_CHAT_ENDPOINT, data=body, method="POST")
    req.add_header("Authorization", f"Bearer {bearer_token}")
    req.add_header("Content-Type", "application/json")

    try:
        with urllib.request.urlopen(req) as resp:
            for raw_line in resp:
                sys.stdout.buffer.write(raw_line)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} error from chat endpoint: {body}") from exc


def main() -> None:
    args = parse_args()
    secrets_path: pathlib.Path = args.secrets

    if not secrets_path.exists():
        raise SystemExit(f"Secrets file not found: {secrets_path}")

    try:
        bearer_token = get_bearer_token(secrets_path, args.threshold_seconds)
    except Exception as exc:  # noqa: BLE001
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    try:
        stream_chat(bearer_token)
    except Exception as exc:  # noqa: BLE001
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
