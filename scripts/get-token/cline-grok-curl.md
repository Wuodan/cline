# Cline Provider Curl Reference

Use these commands to simulate the requests Cline sends when calling the `x-ai/grok-code-fast-1` model through the Cline provider. Replace environment variables only if you rotate credentials.

```bash
# 1) Refresh the WorkOS access token (mirrors AuthService.refreshToken)
curl -sS 'https://api.cline.bot/api/v1/auth/refresh' \
  -H 'Content-Type: application/json' \
  --data '{"refreshToken":"M2bxYnSff0tppEGy19vd8vTZa","grantType":"refresh_token"}'
```

The response returns a fresh `accessToken` (`expiresAt` controls reuse). Plug that token into the streaming chat request below.

```bash
# 2) Stream chat completion (only Authorization + Content-Type needed)
curl -sS -N 'https://api.cline.bot/api/v1/chat/completions' \
  -H 'Authorization: Bearer workos:eyJhbGciOiJSUzI1NiIsImtpZCI6InNzb19vaWRjX2tleV9wYWlyXzAxSzNBNTQxREZLR1FaRjE1R0Y4UkZNUDBWIn0.eyJleHRlcm5hbF9pZCI6InVzci0wMUs2SkQxQUdaOEJGSEU4WEdKSkVDMktSUyIsImxhc3RfbmFtZSI6IkFHKSIsImZpcnN0X25hbWUiOiJTdGVmYW4iLCJlbWFpbCI6InN0ZWZhbi5rdWhuQGFrcm9zLmNoIiwiaXNzIjoiaHR0cHM6Ly9hcGkud29ya29zLmNvbS91c2VyX21hbmFnZW1lbnQvY2xpZW50XzAxSzNBNTQxRk44VEEzRVBQSFREMjMyNUFSIiwic3ViIjoidXNlcl8wMUs4TjFQNUVSQzZZOVBaMVZBSDU0OTRIQSIsInNpZCI6InNlc3Npb25fMDFLOTVRRldCRFNZWjhBS1haNVowTTNKOTAiLCJqdGkiOiIwMUs5OE1NM0FBQTkxRjFERlg0UUtCREhSVCIsImV4cCI6MTc2MjMwMDk5OCwiaWF0IjoxNzYyMzAwMzk4fQ.C1Efq6Ze3qchiY1RIA1x7jtqJFtpgcaGxlG0UYDMTOXHzmVAjZuq5dpErdfd-pAcBlDhT2CXk58ujOsrl8tw30ubj-V9ArTYenJscKOcyQ4EgiFE7AjZbCp_-ueL0osISUQFI7MNRTuYqPZkSu8A1bCWRfiHkLCwTLc68H6g57TLkg7vtZz8AMdJq4N2LB28QypvPNwe0BXFKfluegz3EBgsx6MStSZozDq-_DC1NoUx23OkqvfRGpfcXPtsB_y-JUWgwd5667MgKA5T7GP7hdmRhFVcu90KzX_fS1u4pmIwPXgy2yQ8Lewh1wuDi-Le2l8iS2qEGygQPeGXfMTKLA' \
  -H 'Content-Type: application/json' \
  --data-raw '{"model":"x-ai/grok-code-fast-1","messages":[{"role":"system","content":"You are running a short test from Cline CLI."},{"role":"user","content":"Say hello from Grok."}],"temperature":0,"stream":true,"stream_options":{"include_usage":true},"include_reasoning":true}'
```

The chat command yields streaming Server-Sent Events identical to the Cline IDE/CLI client, ending with `data: [DONE]` once the model finishes.

## Automating in Bash

For a ready-to-run helper that keeps the bearer token fresh, updates the secrets file, and calls the Grok model with the minimal header set, run `scripts/cline_grok_curl.sh`.

```bash
chmod +x scripts/cline_grok_curl.sh          # one-time setup
scripts/cline_grok_curl.sh temp/secrets.json # or rely on $SECRETS_JSON default
```

Prefer Python? `scripts/cline_grok_curl.py` performs the same workflow with the standard library.
