#!/usr/bin/env bash
# Outputs a valid Cline WorkOS bearer token, refreshing the stored credentials when needed.
#
# Usage:
#   ./cline_get_token.sh [options] [path/to/secrets.json]
#
# Options:
#   -v, --verbose        Print token expiry details to stderr
#   -f, --force-refresh  Always refresh the token, even if still valid
#
# Environment:
#   SECRETS_JSON       Path to secrets file (defaults to ~/.cline/data/secrets.json)
#   THRESHOLD_SECONDS  Refresh when token expires in <= this many seconds (default: 300)
#
# Prints:
#   Echoes the bearer token (prefixed with workos:) to stdout on success.

set -euo pipefail

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
THRESHOLD_SECONDS=${THRESHOLD_SECONDS:-300}

if [[ ! -f "$SECRETS_JSON" ]]; then
  echo "Secrets file not found: $SECRETS_JSON" >&2
  exit 1
fi

ACCOUNT_JSON=$(jq -c '."cline:clineAccountId" | fromjson' "$SECRETS_JSON")
if [[ -z "$ACCOUNT_JSON" || "$ACCOUNT_JSON" == "null" ]]; then
  echo "No cline:clineAccountId entry in $SECRETS_JSON" >&2
  exit 1
fi

CURRENT_TOKEN=$(jq -r '.idToken // empty' <<<"$ACCOUNT_JSON")
REFRESH_TOKEN=$(jq -r '.refreshToken // empty' <<<"$ACCOUNT_JSON")
EXPIRES_AT=$(jq -r '.expiresAt // 0' <<<"$ACCOUNT_JSON")
NOW=$(date +%s)

NEEDS_REFRESH=0
if (( FORCE_REFRESH )); then
  NEEDS_REFRESH=1
elif [[ -z "$CURRENT_TOKEN" ]]; then
  NEEDS_REFRESH=1
elif (( EXPIRES_AT <= NOW + THRESHOLD_SECONDS )); then
  NEEDS_REFRESH=1
fi

if (( NEEDS_REFRESH )); then
  if [[ -z "$REFRESH_TOKEN" ]]; then
    echo "Refresh required but no refreshToken present in secrets." >&2
    exit 1
  fi

  (( VERBOSE )) && echo "Refreshing WorkOS bearer token..." >&2
  REFRESH_RESPONSE=$(curl -sS 'https://api.cline.bot/api/v1/auth/refresh' \
    -H 'Content-Type: application/json' \
    --data "{\"refreshToken\":\"${REFRESH_TOKEN}\",\"grantType\":\"refresh_token\"}")

  ACCESS_TOKEN=$(jq -r '.data.accessToken // empty' <<<"$REFRESH_RESPONSE")
  if [[ -z "$ACCESS_TOKEN" ]]; then
    echo "Failed to refresh access token. Response: $REFRESH_RESPONSE" >&2
    exit 1
  fi

  NEW_REFRESH_TOKEN=$(jq -r '.data.refreshToken // empty' <<<"$REFRESH_RESPONSE")
  if [[ -z "$NEW_REFRESH_TOKEN" ]]; then
    NEW_REFRESH_TOKEN="$REFRESH_TOKEN"
  fi

  EXPIRES_AT_ISO=$(jq -r '.data.expiresAt // empty' <<<"$REFRESH_RESPONSE")
  if [[ -z "$EXPIRES_AT_ISO" ]]; then
    echo "Refresh response missing expiresAt." >&2
    exit 1
  fi

  NEW_EXPIRES_AT=$(date -u -d "$EXPIRES_AT_ISO" +%s 2>/dev/null || true)
  if [[ -z "$NEW_EXPIRES_AT" ]]; then
    echo "Unable to parse expiresAt timestamp: $EXPIRES_AT_ISO" >&2
    exit 1
  fi

  USER_INFO_JSON=$(jq -c '.data.userInfo // {}' <<<"$REFRESH_RESPONSE")

  jq \
    --arg token "$ACCESS_TOKEN" \
    --arg refresh "$NEW_REFRESH_TOKEN" \
    --argjson expires "$NEW_EXPIRES_AT" \
    --argjson userinfo "$USER_INFO_JSON" \
    '.["cline:clineAccountId"] |= (
      (fromjson
        | .idToken = $token
        | .refreshToken = $refresh
        | .expiresAt = $expires
        | .userInfo = $userinfo
      ) | tostring
    )' "$SECRETS_JSON" > "${SECRETS_JSON}.tmp"
  mv "${SECRETS_JSON}.tmp" "$SECRETS_JSON"

  CURRENT_TOKEN="$ACCESS_TOKEN"
  EXPIRES_AT="$NEW_EXPIRES_AT"
fi

BEARER_TOKEN="workos:${CURRENT_TOKEN}"
if (( VERBOSE )); then
  SECONDS_LEFT=$(( EXPIRES_AT - NOW ))
  if (( SECONDS_LEFT < 0 )); then
    SECONDS_LEFT=0
  fi
  MINUTES_LEFT=$(( SECONDS_LEFT / 60 ))
  echo "Token valid for ~${SECONDS_LEFT}s (~${MINUTES_LEFT} min) until $(date -u -d "@$EXPIRES_AT" '+%Y-%m-%dT%H:%M:%SZ')" >&2
fi
echo "$BEARER_TOKEN"
