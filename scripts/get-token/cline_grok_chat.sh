#!/usr/bin/env bash
# Streams a Grok completion using the current Cline bearer token.
#
# Usage:
#   ./cline_grok_chat.sh [options] [path/to/secrets.json]
#
# Options:
#   -v, --verbose        Print token status/expiry from helper
#   -f, --force-refresh  Always refresh the token, even if still valid
#
# The script invokes cline_get_token.sh to obtain (and refresh) the token.

set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
GET_TOKEN_SCRIPT="${SCRIPT_DIR}/cline_get_token.sh"

VERBOSE=0
FORCE_REFRESH=0
POSITIONAL=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    -v|--verbose)
      VERBOSE=1
      shift
      ;;
    -f|--force-refresh)
      FORCE_REFRESH=1
      shift
      ;;
    -*)
      echo "Unknown option: $1" >&2
      exit 1
      ;;
    *)
      POSITIONAL+=("$1")
      shift
      ;;
  esac
done

set -- "${POSITIONAL[@]}"

SECRETS_JSON=${1:-${SECRETS_JSON:-"$HOME/.cline/data/secrets.json"}}

if [[ ! -x "$GET_TOKEN_SCRIPT" ]]; then
  echo "Token helper not executable: $GET_TOKEN_SCRIPT" >&2
  exit 1
fi

TOKEN_ARGS=()
(( VERBOSE )) && TOKEN_ARGS+=("--verbose")
(( FORCE_REFRESH )) && TOKEN_ARGS+=("--force-refresh")
BEARER_TOKEN=$("$GET_TOKEN_SCRIPT" "${TOKEN_ARGS[@]}" "$SECRETS_JSON")

curl -sS -N 'https://api.cline.bot/api/v1/chat/completions' \
  -H "Authorization: Bearer ${BEARER_TOKEN}" \
  -H 'Content-Type: application/json' \
  --data-raw '{"model":"x-ai/grok-code-fast-1","messages":[{"role":"system","content":"You are running a short test from Cline CLI."},{"role":"user","content":"Say hello from Grok."}],"temperature":0,"stream":true,"stream_options":{"include_usage":true},"include_reasoning":true}'
