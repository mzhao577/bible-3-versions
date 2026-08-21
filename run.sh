#!/usr/bin/env bash
# Start the Bible comparison app locally.  Usage: ./run.sh [port]
set -euo pipefail
cd "$(dirname "$0")"

PORT="${1:-8501}"
PY="${PYTHON:-python3}"

if ! "$PY" -c "import streamlit" 2>/dev/null; then
    echo "Installing dependencies …"
    "$PY" -m pip install -r requirements.txt
fi

if [ ! -f data/bible.sqlite ]; then
    echo "data/bible.sqlite missing — building it (needs network) …"
    "$PY" -m pip install -r requirements-build.txt
    "$PY" scripts/build_data.py
fi

echo "Starting on http://localhost:$PORT  (Ctrl-C to stop)"
exec "$PY" -m streamlit run app.py --server.port "$PORT"
