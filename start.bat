@echo off
chcp 65001 >/dev/null
echo ==========================================
echo   Vibe-Lens
echo ==========================================
echo.

cd /d "%~dp0backend"

if not exist ".venv" (
    echo [1/4] Creating virtual environment...
    python -m venv .venv
)

call .venv\Scripts\activate.bat

if not exist ".venv\Lib\site-packages\fastapi" (
    echo [2/4] Installing dependencies...
    pip install -r requirements.txt -q
) else (
    echo [2/4] Dependencies OK
)

echo [3/4] Initializing database...
python -m app.services.seed

if not exist ".env" (
    echo.
    echo !! No .env file found. Creating from template...
    copy .env.example .env >/dev/null
    echo !! Please edit backend\.env and set your LLM_API_KEY
    echo !! Then run this script again.
    echo.
    notepad .env
    pause
    exit /b
)

echo [4/4] Starting server...
echo.
echo   Web UI:  http://localhost:8000
echo   Ctrl+C to stop
echo.
start http://localhost:8000
uvicorn app.main:app --host 0.0.0.0 --port 8000
