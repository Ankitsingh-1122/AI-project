#!/usr/bin/env bash
# CivicAI - one-command launcher (macOS / Linux)
# Opens http://localhost:8000 (API + app on one port)
set -e
cd "$(dirname "$0")"

echo "============================================================"
echo " CivicAI - one-command launcher (macOS / Linux)"
echo " Opens http://localhost:8000  (API + app on one port)"
echo "============================================================"
echo

# ---- 1) Python environment (first run only, ~2-5 min) ----------
if [ ! -d "backend/.venv" ]; then
  echo "[1/3] Creating Python env + installing dependencies (first run only)..."
  python3 -m venv backend/.venv
  . backend/.venv/bin/activate
  pip install --upgrade pip -q
  echo "    Installing CPU torch + project packages (this can take a few minutes)..."
  pip install torch --index-url https://download.pytorch.org/whl/cpu -q
  pip install -r backend/requirements.txt -q
else
  echo "[1/3] Python env already present."
  . backend/.venv/bin/activate
fi

# ---- 2) Frontend build (only needed if you change the UI) ------
if [ ! -f "frontend/dist/index.html" ]; then
  echo "[2/3] Building frontend (needs Node.js - https://nodejs.org)..."
  (cd frontend && npm install && npm run build)
else
  echo "[2/3] Frontend build already included - skipping."
fi

# ---- 3) Start ---------------------------------------------------
echo
echo "[3/3] Starting CivicAI at  http://localhost:8000"
echo "    - first start downloads the MiniLM embedding model (~90MB, needs internet)"
echo "    - first start creates/seeds civic.db automatically"
echo "    - Ctrl+C to stop the app"
echo
cd backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
