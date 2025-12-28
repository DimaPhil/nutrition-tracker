#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [ -f ".venv/bin/activate" ]; then
  # Optional convenience for local dev.
  source ".venv/bin/activate"
fi

export ENVIRONMENT="${ENVIRONMENT:-local}"
uvicorn nutrition_tracker.api.asgi:app --reload
