#!/bin/bash
echo "=========================================="
echo "  Vibe-Lens"
echo "=========================================="
echo

cd "$(dirname "$0")/backend"

if [ ! -d ".venv" ]; then
    echo "[1/4] Creating virtual environment..."
    python3 -m venv .venv
fi

source .venv/bin/activate

if ! python -c "import fastapi" 2>/dev/null; then
    echo "[2/4] Installing dependencies..."
    pip install -r requirements.txt -q
else
    echo "[2/4] Dependencies OK"
fi

echo "[3/4] Initializing database..."
python -m app.services.seed

if [ ! -f ".env" ]; then
    echo
    echo "!! No .env file found. Creating from template..."
    cp .env.example .env
    echo "!! Please edit backend/.env and set your LLM_API_KEY"
    echo "!! Then run this script again."
    exit 1
fi

echo "[4/4] Starting server..."
echo
echo "  Web UI:  http://localhost:8000"
echo "  Ctrl+C to stop"
echo

open http://localhost:8000 2>/dev/null || xdg-open http://localhost:8000 2>/dev/null || true
uvicorn app.main:app --host 0.0.0.0 --port 8000
