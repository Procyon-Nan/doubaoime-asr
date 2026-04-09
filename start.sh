#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-9000}"
LEGACY_PATH="${LEGACY_PATH:-/asr/transcribe}"
STANDARD_PATH="${STANDARD_PATH:-/v1/stt/transcriptions}"
HEALTH_PATH="${HEALTH_PATH:-/healthz}"
CREDENTIAL_PATH="${CREDENTIAL_PATH:-${ROOT_DIR}/credentials.json}"
MAX_BODY_BYTES="${MAX_BODY_BYTES:-320000}"
PYTHON_BIN="${PYTHON_BIN:-python3}"

cd "${ROOT_DIR}"

exec "${PYTHON_BIN}" -m api.cli \
  --host "${HOST}" \
  --port "${PORT}" \
  --path "${LEGACY_PATH}" \
  --standard-path "${STANDARD_PATH}" \
  --health-path "${HEALTH_PATH}" \
  --credential-path "${CREDENTIAL_PATH}" \
  --max-body-bytes "${MAX_BODY_BYTES}"
