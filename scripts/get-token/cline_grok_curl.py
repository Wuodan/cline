#!/usr/bin/env python3
"""
Fetches and refreshes Cline WorkOS tokens, mirrors the curl workflow, and streams a Grok response.

Steps:
1. Load `cline:clineAccountId` from the secrets JSON (default: ~/.cline/data/secrets.json).
2. Refresh the WorkOS bearer token when absent or nearing expiry, and persist the updated payload.
3. Call the x-ai/grok-code-fast-1 model using the latest bearer token, printing SSE output to stdout.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import sys
import time
import urllib.error
import urllib.request
from typing import Any, Dict, Tuple


CLINE_REFRESH_ENDPOINT = "https://api.cline.bot/api/v1/auth/refresh"
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


def load_account_blob(secrets_path: pathlib.Path) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    data = json.loads(secrets_path.read_text(encoding="utf-8"))
    blob = data.get("cline:clineAccountId")
    if not blob:
        raise RuntimeError("Missing cline:clineAccountId entry in secrets file")
    account = json.loads(blob)
    return data, account


def should_refresh(account: Dict[str, Any], threshold_seconds: int) -> bool:
    now = int(time.time())
    expires_at = int(account.get("expiresAt") or 0)
    has_token = bool(account.get("idToken"))
    return (not has_token) or (expires_at <= now + threshold_seconds)


def post_json(url: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            text = resp.read().decode(charset)
            return json.loads(text)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} error from {url}: {body}") from exc


def refresh_account(account: Dict[str, Any]) -> Dict[str, Any]:
    refresh_token = account.get("refreshToken")
    if not refresh_token:
        raise RuntimeError("Stored account is missing refreshToken")

    response = post_json(
        CLINE_REFRESH_ENDPOINT,
        {"refreshToken": refresh_token, "grantType": "refresh_token"},
    )

    payload = response.get("data") or {}
    access_token = payload.get("accessToken")
    if not access_token:
        raise RuntimeError("Refresh response missing accessToken")

    new_refresh = payload.get("refreshToken") or refresh_token
    expires_iso = payload.get("expiresAt")
    if not expires_iso:
        raise RuntimeError("Refresh response missing expiresAt")

    expires_epoch = iso_to_epoch(expires_iso)

    # Update account data in-memory
    account.update(
        {
            "idToken": access_token,
            "refreshToken": new_refresh,
            "expiresAt": expires_epoch,
            "userInfo": payload.get("userInfo") or account.get("userInfo") or {},
        }
    )
    return account


def iso_to_epoch(timestamp: str) -> int:
    # Accept either "...Z" or explicit offsets.
    ts = timestamp.replace("Z", "+00:00")
    return int(dt.datetime.fromisoformat(ts).timestamp())


def save_account(secrets_path: pathlib.Path, secrets: Dict[str, Any], account: Dict[str, Any]) -> None:
    secrets["cline:clineAccountId"] = json.dumps(account)
    tmp_path = secrets_path.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(secrets, indent=2), encoding="utf-8")
    tmp_path.replace(secrets_path)


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

    secrets, account = load_account_blob(secrets_path)

    if should_refresh(account, args.threshold_seconds):
        print("Refreshing WorkOS bearer token...", file=sys.stderr)
        account = refresh_account(account)
        save_account(secrets_path, secrets, account)
    else:
        print("Using cached bearer token.", file=sys.stderr)

    bearer_token = f"workos:{account['idToken']}"
    stream_chat(bearer_token)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001 - produce readable error
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
