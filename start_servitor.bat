@echo off
title SERVITOR Launcher
chcp 65001 >nul
cd /d "%~dp0"

echo.
echo ============================================
echo === SERVITOR LAUNCHER ===
echo ============================================

REM ---- BOOTSTRAP: ensure system_prompt.txt exists ----
if not exist "%~dp0system_prompt.txt" (
    echo.
    echo [BOOTSTRAP] system_prompt.txt missing - dumping embedded baseline...
    .\venv\Scripts\python.exe mrrobot.py --dump-baseline
)

REM ---- PRE-FLIGHT: PROMPT REVIEW MENU ----
:prompt_menu
echo.
echo --------------------------------------------
echo --- SYSTEM PROMPT REVIEW ---
echo --------------------------------------------
echo   [Enter] launch SERVITOR with current prompt
echo   [E]     edit prompt in notepad (launcher waits)
echo   [V]     view current prompt
echo   [R]     restore embedded baseline (factory reset)
echo   [Q]     quit launcher
echo.
set "CHOICE="
set /p "CHOICE=Choice: "

if /i "%CHOICE%"=="E" (
    echo Opening notepad - close it when done editing.
    notepad "%~dp0system_prompt.txt"
    echo Editor closed. Returning to menu.
    goto prompt_menu
)
if /i "%CHOICE%"=="V" (
    echo.
    echo --- BEGIN PROMPT ---
    .\venv\Scripts\python.exe mrrobot.py --show-prompt
    echo --- END PROMPT ---
    echo.
    pause
    goto prompt_menu
)
if /i "%CHOICE%"=="R" (
    echo.
    echo [RESTORE] Overwriting system_prompt.txt with embedded baseline...
    .\venv\Scripts\python.exe mrrobot.py --dump-baseline
    goto prompt_menu
)
if /i "%CHOICE%"=="Q" (
    echo Aborted by operator.
    timeout /t 2 /nobreak >NUL
    exit /b 0
)
REM Empty input or Enter -> proceed to launch

echo.
echo --------------------------------------------
echo --- LAUNCH SEQUENCE ---
echo --------------------------------------------

REM ---- Step 0: Kill any existing SERVITOR python processes ----
echo.
echo [0/4] Killing any existing SERVITOR processes...
for /f "tokens=2 delims==," %%P in ('wmic process where "name='python.exe' and commandline like '%%mrrobot.py%%'" get processid /format:csv 2^>nul ^| findstr /R "[0-9]"') do (
    echo   Killing PID %%P
    taskkill /F /PID %%P >NUL 2>&1
)
echo   Pre-flight clean.

REM ---- Step 1: Ollama service ----
echo.
echo [1/4] Checking Ollama...
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

REM ---- Step 2: Preload coder model with permanent keep-alive ----
echo.
echo [2/4] Preloading coder model into RAM (cold start can take 30-60s)...
curl -s -X POST http://localhost:11434/api/generate -H "Content-Type: application/json" -d "{\"model\":\"huihui_ai/qwen2.5-coder-abliterate:7b\",\"keep_alive\":-1,\"options\":{\"num_ctx\":4096}}"
echo.
echo   Coder model warm.

REM ---- Step 3: Preload vision model (skipped silently if not yet pulled) ----
REM Check /api/tags FIRST so we never trigger an Ollama background download.
echo.
echo [3/4] Checking vision model...
curl -s --max-time 5 http://localhost:11434/api/tags 2>NUL | findstr /C:"qwen2.5-vl-abliterated:7b" >NUL
if errorlevel 1 (
    echo   Vision model not pulled - skipping preload.
    echo   To enable vision: ollama pull huihui_ai/qwen2.5-vl-abliterated:7b
) else (
    echo   Vision model found - warming up...
    curl -s --max-time 60 -X POST http://localhost:11434/api/generate -H "Content-Type: application/json" -d "{\"model\":\"huihui_ai/qwen2.5-vl-abliterated:7b\",\"keep_alive\":-1,\"options\":{\"num_ctx\":4096}}" >NUL 2>&1
    if errorlevel 1 (
        echo   Vision warm-up timed out - will cold-load on first use.
    ) else (
        echo   Vision model warm.
    )
)

REM ---- Step 4: Launch the bot ----
echo.
echo [4/4] Launching SERVITOR bot in new window...
start "SERVITOR" cmd /k ".\venv\Scripts\python.exe mrrobot.py"

echo.
echo ============================================
echo Done. Look for: SERVITOR online as SERVITOR#2065
echo You can close this launcher window.
echo The SERVITOR window must stay open or the bot dies.
echo ============================================
timeout /t 5 /nobreak >NUL
