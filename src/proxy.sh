#!/usr/bin/env bash
set -euo pipefail

# tools/local-llm-proxy/proxy.sh
#
# Description: Wrapper script to manage the LiteLLM proxy and Ngrok tunnel.

_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly _SCRIPT_DIR

if [[ -f "${_SCRIPT_DIR}/config/.env" ]]; then
  # shellcheck disable=SC1091
  source "${_SCRIPT_DIR}/config/.env"
fi

command="${1:-}"

print_usage() {
  echo "Usage: ./proxy.sh [start|stop|restart]"
}

seed_virtual_key() {
  local master_key="${LITELLM_MASTER_KEY:-sk-local-agent-secure-12345}"
  local alias="local-proxy-key"
  local key_file="${_SCRIPT_DIR}/config/.litellm_virtual_key"

  # Check if key already exists in LiteLLM (by alias)
  local existing_key
  existing_key=$(curl -s -H "Authorization: Bearer ${master_key}" http://localhost:4000/key/list | jq -r ".data[]? | select(.key_alias == \"${alias}\") | .key_id" 2>/dev/null || true)

  if [[ -n "${existing_key}" && "${existing_key}" != "null" ]]; then
    if [[ -f "${key_file}" ]]; then
      VIRTUAL_KEY=$(cat "${key_file}")
      return
    fi
    echo "Virtual key '${alias}' exists in LiteLLM but local cache is missing."
  fi

  echo "Generating automatic virtual key for models..."

  # Get list of models (requires authentication if master key is set)
  local models_json
  models_json=$(curl -s -H "Authorization: Bearer ${master_key}" http://localhost:4000/v1/models)
  local models
  models=$(echo "${models_json}" | jq -c '[.data[]?.id]' 2>/dev/null || echo "[]")

  if [[ -z "${models}" || "${models}" == "[]" ]]; then
    echo "Warning: No models found or failed to fetch models. Response: ${models_json}"
    models="[]"
  fi

  # Generate the key
  local response
  response=$(curl -s -X POST \
    -H "Authorization: Bearer ${master_key}" \
    -H "Content-Type: application/json" \
    -d "{\"models\": ${models}, \"key_alias\": \"${alias}\"}" \
    http://localhost:4000/key/generate)

  VIRTUAL_KEY=$(echo "${response}" | jq -r '.key')

  if [[ "${VIRTUAL_KEY}" != "null" && -n "${VIRTUAL_KEY}" ]]; then
    echo "${VIRTUAL_KEY}" > "${key_file}"
    echo "✅ Created virtual key: ${VIRTUAL_KEY} (saved to .litellm_virtual_key)"
  else
    echo "❌ Failed to generate virtual key. Response: ${response}"
  fi
}

start_proxy() {
  echo "Starting LiteLLM Proxy and Ngrok tunnel..."
  docker compose -f "${_SCRIPT_DIR}/config/docker-compose.yml" --env-file "${_SCRIPT_DIR}/config/.env" up -d

  echo "Waiting for LiteLLM Proxy to become healthy..."
  for _ in {1..30}; do
    if curl -s http://localhost:4000/health/readiness > /dev/null 2>&1; then
      break
    fi
    sleep 1
  done

  if ! curl -s http://localhost:4000/health/readiness > /dev/null 2>&1; then
    echo -e "\n❌ LiteLLM Proxy failed to become healthy. Check logs with: docker compose -f \"${_SCRIPT_DIR}/config/docker-compose.yml\" --env-file \"${_SCRIPT_DIR}/config/.env\" logs litellm"
    exit 1
  fi

  seed_virtual_key

  echo "Waiting for Ngrok tunnel to establish (this may take a few seconds)..."

  # Wait up to 10 seconds for the Ngrok API to become available
  for _ in {1..10}; do
    if curl -s http://localhost:4040/api/tunnels > /dev/null 2>&1; then
      # Give the tunnel an extra second to fully register the public URL
      sleep 1
      break
    fi
    sleep 1
  done

  # Fetch and display the public URL
  PUBLIC_URL=$(curl -s http://localhost:4040/api/tunnels | jq -r '.tunnels[0].public_url')

  if [[ "${PUBLIC_URL}" != "null" && -n "${PUBLIC_URL}" ]]; then
    echo -e "\n✅ Success! Your public Ngrok URL is: \033[1;32m${PUBLIC_URL}\033[0m"
    echo "Use this URL with '/cursor' appended in your Cursor Settings -> Models -> Override OpenAI Base URL"

    if [[ -n "${VIRTUAL_KEY:-}" ]]; then
      echo -e "🔑 Virtual Key (shows in UI): \033[1;32m${VIRTUAL_KEY}\033[0m"
    fi
    echo -e "🔑 Master Key (admin only): \033[1;32m${LITELLM_MASTER_KEY:-sk-local-agent-secure-12345}\033[0m"

    echo -e "\n🔧 Local Ngrok Admin UI: \033[1;36mhttp://localhost:4040\033[0m"
    echo -e "⚙️  Local LiteLLM Admin UI: \033[1;36mhttp://localhost:4000/ui\033[0m"
    echo -e "🦙 Local Ollama API: \033[1;36mhttp://localhost:11434\033[0m"
  else
    echo -e "\n❌ Failed to retrieve Ngrok URL. Make sure your NGROK_AUTHTOKEN is set correctly in .env."
    echo "You can check the logs with: docker compose -f \"${_SCRIPT_DIR}/config/docker-compose.yml\" --env-file \"${_SCRIPT_DIR}/config/.env\" logs ngrok"
    exit 1
  fi
}

stop_proxy() {
  echo "Stopping LiteLLM Proxy and Ngrok tunnel..."
  docker compose -f "${_SCRIPT_DIR}/config/docker-compose.yml" --env-file "${_SCRIPT_DIR}/config/.env" down --remove-orphans
  echo -e "\n✅ Teardown complete."
}

case "${command}" in
  start)
    start_proxy
    ;;
  stop)
    stop_proxy
    ;;
  restart)
    stop_proxy
    start_proxy
    ;;
  *)
    print_usage
    exit 1
    ;;
esac
