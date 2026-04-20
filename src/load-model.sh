#!/usr/bin/env bash
set -euo pipefail

## load-model.sh
#
# Description: Pulls the recommended quantized model via the Ollama Docker container.
#
# Usage: ./load-model.sh
#
# Globals:
#   OLLAMA_MODEL (defaults to qwen2.5-coder:14b)
#
# Returns:
#   0 on success, non-zero on error.
#
###############################################################################

_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly _SCRIPT_DIR
# shellcheck disable=SC1091
source "${_SCRIPT_DIR}/lib.sh"

# Sourcing .env file if it exists to get OLLAMA_MODEL
if [[ -f "${_SCRIPT_DIR}/config/.env" ]]; then
  # shellcheck disable=SC1091
  source "${_SCRIPT_DIR}/config/.env"
fi

readonly MODEL="${OLLAMA_MODEL:-qwen2.5-coder:14b}"

main() {
  log "Starting model loading process..."

  if ! pgrep -x "ollama" > /dev/null && ! pgrep -f "Ollama.app" > /dev/null; then
    log "Warning: Could not detect Ollama running. Ensure the Ollama app is running natively on your Mac."
  fi

  log "Pulling model: ${MODEL} natively via Ollama..."
  if ! ollama pull "${MODEL}"; then
    err "Failed to pull model ${MODEL}. Make sure the Ollama CLI is installed and running."
    exit 1
  fi

  log "Model ${MODEL} pulled successfully."
}

main "$@"
