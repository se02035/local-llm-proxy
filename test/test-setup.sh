#!/usr/bin/env bash
set -euo pipefail

## test-setup.sh
#
# Description: Validates the end-to-end proxy setup.
# Checks if Ollama is reachable and the LiteLLM proxy responds.
#
# Usage: ./test-setup.sh
#
# Returns:
#   0 on success, non-zero on error.
#
###############################################################################

_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly _SCRIPT_DIR
# shellcheck disable=SC1091
source "${_SCRIPT_DIR}/../src/lib.sh"

# Set default values
OLLAMA_HOST_DEFAULT="http://localhost:11434"
LITELLM_PORT_DEFAULT="4000"
OLLAMA_MODEL_DEFAULT="qwen2.5-coder:14b"

if [[ -f "${_SCRIPT_DIR}/../src/config/.env" ]]; then
  # shellcheck disable=SC1091
  source "${_SCRIPT_DIR}/../src/config/.env"
fi

readonly OLLAMA_HOST="${OLLAMA_HOST:-${OLLAMA_HOST_DEFAULT}}"
readonly LITELLM_PORT="${LITELLM_PORT:-${LITELLM_PORT_DEFAULT}}"

if [[ -z "${LITELLM_MASTER_KEY:-}" ]]; then
  err "LITELLM_MASTER_KEY is not set or is empty. Set it in src/config/.env (see src/config/.env.example), then retry."
  exit 1
fi
readonly CURSOR_KEY="${LITELLM_MASTER_KEY}"

main() {
  local -r model="${OLLAMA_MODEL:-${OLLAMA_MODEL_DEFAULT}}"

  log "Validating Local LLM Proxy Setup..."

  if ! command -v jq >/dev/null 2>&1; then
    err "jq is required to parse JSON. Please install jq first."
    exit 1
  fi

  if ! command -v curl >/dev/null 2>&1; then
    err "curl is required to send HTTP requests."
    exit 1
  fi

  # Replace host.docker.internal or ollama for local ping if running on host
  local ping_host="${OLLAMA_HOST}"
  if [[ "${ping_host}" == *"host.docker.internal"* ]]; then
    ping_host="${ping_host/host.docker.internal/localhost}"
  elif [[ "${ping_host}" == *"ollama"* ]]; then
    ping_host="${ping_host/ollama/localhost}"
  fi

  log "1. Checking Ollama instance at ${ping_host} (model: ${model})..."
  if ! curl -sf --connect-timeout 5 --max-time 10 "${ping_host}/api/tags" >/dev/null; then
    err "Ollama is not reachable at ${ping_host}."
    exit 1
  fi
  log "Ollama is running."

  log "2. Sending chat completion (alias model: ${model}.local → Ollama: ${model}) to LiteLLM on port ${LITELLM_PORT}..."
  local request_body
  request_body=$(cat <<EOF
{
  "model": "${model}.local",
  "messages": [{"role": "user", "content": "Say 'hello world' and nothing else."}]
}
EOF
)

  local response
  if ! response=$(curl -s --connect-timeout 5 --max-time 30 -X POST \
    "http://localhost:${LITELLM_PORT}/v1/chat/completions" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer ${CURSOR_KEY}" \
    -d "${request_body}"); then
    err "Failed to connect to LiteLLM Proxy on port ${LITELLM_PORT}."
    exit 1
  fi

  # Validate response
  local content
  local jq_exit=0
  content="$(jq -r '.choices[0].message.content // empty' <<<"${response}" 2>/dev/null)" || jq_exit=$?

  if [[ "${jq_exit}" -ne 0 ]]; then
    err "Failed to parse JSON response or extract content."
    err "Full response: ${response}"
    exit 1
  fi

  if [[ -z "${content}" || "${content}" == "null" ]]; then
    err "Failed to get valid response from proxy."
    err "Full response: ${response}"
    exit 1
  fi

  log "Response received successfully: ${content}"
  log "Validation passed. Setup is working correctly."
}

main "$@"
