#!/bin/sh
set -eu

# Use Railway-assigned port when available, fallback for local container runs.
PORT_TO_USE="${PORT:-8000}"
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT_TO_USE}"
