#!/usr/bin/env python3
"""
Outputs a valid Cline WorkOS bearer token, refreshing stored credentials when needed.

Usage:
    python scripts/cline_get_token.py [--secrets PATH] [--threshold-seconds N]

It reads the `cline:clineAccountId` blob from the secrets JSON (default: ~/.cline/data/secrets.json),
refreshes the access token if it is missing or close to expiry, persists any updates, and prints the
current bearer token (prefixed with `workos:`) to stdout.
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
    req = urllib.request.Request(url, data=data, method="POST", headers={"Content-Type": "application/json"})
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
    ts = timestamp.replace("Z", "+00:00")
    return int(dt.datetime.fromisoformat(ts).timestamp())


def save_account(secrets_path: pathlib.Path, secrets: Dict[str, Any], account: Dict[str, Any]) -> None:
    secrets["cline:clineAccountId"] = json.dumps(account)
    tmp_path = secrets_path.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(secrets, indent=2), encoding="utf-8")
    tmp_path.replace(secrets_path)


def get_bearer_token(secrets_path: pathlib.Path, threshold_seconds: int) -> str:
    secrets, account = load_account_blob(secrets_path)

    if should_refresh(account, threshold_seconds):
        print("Refreshing WorkOS bearer token...", file=sys.stderr)
        account = refresh_account(account)
        save_account(secrets_path, secrets, account)
    else:
        print("Using cached bearer token.", file=sys.stderr)

    return f"workos:{account['idToken']}"


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

    print(bearer_token)


if __name__ == "__main__":
    main()
