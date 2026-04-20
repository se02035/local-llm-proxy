# Shared logging helpers for local-llm-proxy scripts.
# shellcheck shell=bash
# Intended to be sourced from load-model.sh and test-setup.sh; do not rely on
# this file changing shell options (none are set here).

err() {
  printf "[ERROR] %s: %s\n" "$(date '+%Y-%m-%dT%H:%M:%S%z')" "${*}" >&2
}

log() {
  printf "[INFO] %s: %s\n" "$(date '+%Y-%m-%dT%H:%M:%S%z')" "${*}"
}
