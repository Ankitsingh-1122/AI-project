@echo off
setlocal
cd /d "%~dp0"

echo ============================================================
echo  CivicAI - one-command launcher (Windows)
echo  Opens http://localhost:8000  (API + app on one port)
echo ============================================================
echo.

REM ---- 1) Python environment (first run only, ~2-5 min) ----------
if not exist "backend\.venv\Scripts\python.exe" (
    echo [1/3] Creating Python env + installing dependencies (first run only)...
    python -m venv backend\.venv
    if errorlevel 1 (
        echo.
        echo Python 3.10+ was not found. Install it from https://python.org
        echo (tick "Add python.exe to PATH" during install) and run this again.
        pause
        exit /b 1
    )
    call backend\.venv\Scripts\activate.bat
    pip install --upgrade pip -q
    echo     Installing CPU torch + project packages (this can take a few minutes)...
    pip install torch --index-url https://download.pytorch.org/whl/cpu -q
    pip install -r backend\requirements.txt -q
) else (
    echo [1/3] Python env already present.
    call backend\.venv\Scripts\activate.bat
)

REM ---- 2) Frontend build (only needed if you change the UI) ------
if not exist "frontend\dist\index.html" (
    echo [2/3] Building frontend (needs Node.js - https://nodejs.org)...
    pushd frontend
    call npm install
    call npm run build
    popd
) else (
    echo [2/3] Frontend build already included - skipping.
)

REM ---- 3) Start ---------------------------------------------------
echo.
echo [3/3] Starting CivicAI at  http://localhost:8000
echo     - first start downloads the MiniLM embedding model (~90MB, needs internet)
echo     - first start creates/seeds civic.db automatically
echo     - close this window (or press Ctrl+C) to stop the app
echo.
cd backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
pause
