@echo off
title SERVITOR Launcher
chcp 65001 >nul
cd /d "%~dp0"

REM ---- Read model names from .env (fallback defaults if missing) ----
set "MODEL_NAME=huihui_ai/qwen2.5-vl-abliterated:3b"
set "VISION_MODEL_NAME=huihui_ai/qwen2.5-vl-abliterated:3b"
if exist "%~dp0.env" (
    for /f "tokens=1,* delims==" %%A in ('findstr /B /C:"MODEL_NAME=" "%~dp0.env"') do set "MODEL_NAME=%%B"
    for /f "tokens=1,* delims==" %%A in ('findstr /B /C:"VISION_MODEL_NAME=" "%~dp0.env"') do set "VISION_MODEL_NAME=%%B"
)

echo.
echo ============================================
echo === SERVITOR LAUNCHER ===
echo ============================================
echo   Text model:   %MODEL_NAME%
echo   Vision model: %VISION_MODEL_NAME%

REM ---- BOOTSTRAP: ensure system_prompt.txt exists ----
if not exist "%~dp0system_prompt.txt" (
    echo.
    echo [BOOTSTRAP] system_prompt.txt missing - dumping embedded baseline...
    .\venv\Scripts\python.exe mrrobot.py --dump-baseline
)

REM ---- BOOTSTRAP: ensure ComfyUI workflow JSONs exist (per-bot — gitignored) ----
if not exist "%~dp0gen_template.json" (
    if exist "%~dp0gen_template.json.example" (
        echo [BOOTSTRAP] gen_template.json missing - copying from .example
        copy /Y "%~dp0gen_template.json.example" "%~dp0gen_template.json" >NUL
    )
)
if not exist "%~dp0scene_template.json" (
    if exist "%~dp0scene_template.json.example" (
        echo [BOOTSTRAP] scene_template.json missing - copying from .example
        copy /Y "%~dp0scene_template.json.example" "%~dp0scene_template.json" >NUL
    )
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

REM ---- Step 2: Preload text model with permanent keep-alive ----
echo.
echo [2/4] Preloading text model into RAM (cold start can take 30-60s)...
echo   -^> %MODEL_NAME%
curl -s -X POST http://localhost:11434/api/generate -H "Content-Type: application/json" -d "{\"model\":\"%MODEL_NAME%\",\"keep_alive\":-1,\"options\":{\"num_ctx\":4096}}"
echo.
echo   Text model warm.

REM ---- Step 3: Preload vision model (skip if same as text model — already warm) ----
echo.
echo [3/4] Checking vision model...
if /i "%VISION_MODEL_NAME%"=="%MODEL_NAME%" (
    echo   Vision model is same as text model - already warm. Skipping preload.
) else (
    curl -s --max-time 5 http://localhost:11434/api/tags 2>NUL | findstr /C:"%VISION_MODEL_NAME%" >NUL
    if errorlevel 1 (
        echo   Vision model not pulled - skipping preload.
        echo   To enable vision: ollama pull %VISION_MODEL_NAME%
    ) else (
        echo   Vision model found - warming up: %VISION_MODEL_NAME%
        curl -s --max-time 60 -X POST http://localhost:11434/api/generate -H "Content-Type: application/json" -d "{\"model\":\"%VISION_MODEL_NAME%\",\"keep_alive\":-1,\"options\":{\"num_ctx\":4096}}" >NUL 2>&1
        if errorlevel 1 (
            echo   Vision warm-up timed out - will cold-load on first use.
        ) else (
            echo   Vision model warm.
        )
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
