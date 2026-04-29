@echo off
title SERVITOR Launcher

echo.
echo === SERVITOR LAUNCHER ===
echo.

REM ---- Step 1: Ollama service ----
echo [1/3] Checking Ollama...
tasklist /FI "IMAGENAME eq ollama.exe" 2>NUL | find /I "ollama.exe" >NUL
if errorlevel 1 (
    echo   Ollama not running, starting minimised window...
    start "Ollama" /MIN cmd /c "ollama serve"
) else (
    echo   Ollama already running.
)

REM Wait for Ollama to bind port 11434
:wait_ollama
curl -s --connect-timeout 2 http://localhost:11434/api/version >NUL 2>&1
if errorlevel 1 (
    echo   ...waiting for Ollama to bind port 11434
    timeout /t 2 /nobreak >NUL
    goto wait_ollama
)
echo   Ollama is up.

REM ---- Step 2: Preload model with permanent keep-alive ----
echo.
echo [2/3] Preloading model into RAM (cold start can take 30-60s)...
curl -s -X POST http://localhost:11434/api/generate -H "Content-Type: application/json" -d "{\"model\":\"huihui_ai/qwen2.5-coder-abliterate:7b\",\"keep_alive\":-1,\"options\":{\"num_ctx\":4096}}"
echo.
echo   Model warm.

REM ---- Step 3: Launch the bot ----
echo.
echo [3/3] Launching SERVITOR bot in new window...
cd /d "%~dp0"
start "SERVITOR" cmd /k ".\venv\Scripts\python.exe mrrobot.py"

echo.
echo ============================================
echo Done. Look for: SERVITOR online as SERVITOR#2065
echo You can close this launcher window.
echo The SERVITOR window must stay open or the bot dies.
echo ============================================
timeout /t 5 /nobreak >NUL
