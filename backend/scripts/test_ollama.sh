#!/usr/bin/env bash
# test_ollama.sh — run LLM provider tests against a local Ollama server.
#
# Usage (from the repo root):
#   Unit tests only (no Ollama needed — always safe for CI):
#     bash backend/scripts/test_ollama.sh unit
#
#   Integration tests (requires: ollama run llama3.1:8b):
#     bash backend/scripts/test_ollama.sh integration
#
#   Both:
#     bash backend/scripts/test_ollama.sh          # default
#
# Environment overrides (all optional):
#   OLLAMA_BASE_URL   default: http://host.docker.internal:11434/v1
#   OLLAMA_MODEL      default: llama3.1:8b
#   BACKEND_CONTAINER default: ovs_backend

set -euo pipefail

BACKEND_CONTAINER="${BACKEND_CONTAINER:-ovs_backend}"
OLLAMA_BASE_URL="${OLLAMA_BASE_URL:-http://host.docker.internal:11434/v1}"
OLLAMA_MODEL="${OLLAMA_MODEL:-llama3.1:8b}"
MODE="${1:-all}"

_run_tests() {
    local test_target="$1"
    shift
    docker exec "$BACKEND_CONTAINER" bash -lc \
        "cd /app && \
         OLLAMA_BASE_URL='${OLLAMA_BASE_URL}' \
         OLLAMA_MODEL='${OLLAMA_MODEL}' \
         LLM_PROVIDER='ollama' \
         python manage.py test ${test_target} --verbosity=2 --keepdb $*"
}

case "$MODE" in
  unit)
    echo ">>> Running unit tests (mocked — no Ollama required)"
    _run_tests "ai_ml_services.tests.test_interview_engine_providers.EngineUnitTests"
    ;;
  integration)
    echo ">>> Running integration tests (live Ollama at ${OLLAMA_BASE_URL})"
    _run_tests "ai_ml_services.tests.test_interview_engine_providers.OllamaIntegrationTests"
    ;;
  all|*)
    echo ">>> Running unit tests..."
    _run_tests "ai_ml_services.tests.test_interview_engine_providers.EngineUnitTests"
    echo ""
    echo ">>> Running integration tests (live Ollama at ${OLLAMA_BASE_URL})"
    _run_tests "ai_ml_services.tests.test_interview_engine_providers.OllamaIntegrationTests"
    ;;
esac

echo ""
echo "Done."
