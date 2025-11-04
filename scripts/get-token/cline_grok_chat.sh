#!/usr/bin/env bash
# Streams a Grok completion using the current Cline bearer token.
#
# Usage:
#   ./scripts/cline_grok_chat.sh [path/to/secrets.json]
#
# The script invokes cline_get_token.sh to obtain (and refresh) the token.

set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
GET_TOKEN_SCRIPT="${SCRIPT_DIR}/cline_get_token.sh"

SECRETS_JSON=${1:-${SECRETS_JSON:-"$HOME/.cline/data/secrets.json"}}

if [[ ! -x "$GET_TOKEN_SCRIPT" ]]; then
  echo "Token helper not executable: $GET_TOKEN_SCRIPT" >&2
  exit 1
fi

BEARER_TOKEN=$("$GET_TOKEN_SCRIPT" "$SECRETS_JSON")

curl -sS -N 'https://api.cline.bot/api/v1/chat/completions' \
  -H "Authorization: Bearer ${BEARER_TOKEN}" \
  -H 'Content-Type: application/json' \
  --data-raw '{"model":"x-ai/grok-code-fast-1","messages":[{"role":"system","content":"You are running a short test from Cline CLI."},{"role":"user","content":"Say hello from Grok."}],"temperature":0,"stream":true,"stream_options":{"include_usage":true},"include_reasoning":true}'
