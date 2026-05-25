@echo off
title SERVITOR Setup
chcp 65001 >nul
cd /d "%~dp0"

echo.
echo ============================================
echo === SERVITOR FIRST-TIME SETUP ===
echo ============================================
echo.
echo Run this once after cloning. Safe to re-run — it won't
echo overwrite your .env or reinstall things that are already there.
echo.

REM ════════════════════════════════════════════
REM [1/6] Python check
REM ════════════════════════════════════════════
echo [1/6] Checking Python...
set PYTHON=

py -3.12 --version >NUL 2>&1
if not errorlevel 1 (
    set "PYTHON=py -3.12"
    echo   [OK]   Python 3.12 ^(py launcher^)
    goto python_ok
)

python --version >NUL 2>&1
if errorlevel 1 (
    echo   [FAIL] Python not found in PATH.
    echo.
    echo          Install from https://python.org/downloads
    echo          Tick "Add Python to PATH" during install.
    echo          Re-run this setup after installing.
    echo.
    pause
    exit /b 1
)
for /f "tokens=2" %%V in ('python --version 2^>^&1') do set PYVER=%%V
echo   [OK]   Python %PYVER%
set "PYTHON=python"

:python_ok

REM ════════════════════════════════════════════
REM [2/6] Ollama check
REM ════════════════════════════════════════════
echo.
echo [2/6] Checking Ollama...
ollama --version >NUL 2>&1
if errorlevel 1 (
    echo   [WARN] Ollama not found in PATH.
    echo          Download from https://ollama.com/download
    echo          Run this setup again after installing.
    echo          ^(Bot will still launch, but won't respond until Ollama is up^)
) else (
    for /f "delims=" %%V in ('ollama --version 2^>^&1') do echo   [OK]   %%V
)

REM ════════════════════════════════════════════
REM [3/6] Python venv + requirements
REM ════════════════════════════════════════════
echo.
echo [3/6] Setting up venv + dependencies...
if not exist "%~dp0venv\Scripts\activate.bat" (
    echo   Creating venv...
    %PYTHON% -m venv venv
    if errorlevel 1 (
        echo   [FAIL] venv creation failed. Check Python install and try again.
        pause
        exit /b 1
    )
    echo   [OK]   venv created
) else (
    echo   [OK]   venv already exists
)

echo   Installing requirements.txt...
.\venv\Scripts\python.exe -m pip install --upgrade pip --quiet
.\venv\Scripts\python.exe -m pip install -r requirements.txt --quiet
if errorlevel 1 (
    echo   [WARN] Some requirements failed to install. Check output above.
) else (
    echo   [OK]   requirements installed
)

REM -- TTS deps (optional — SAPI fallback for ElevenLabs)
.\venv\Scripts\python.exe -c "import pyttsx3" >NUL 2>&1
if errorlevel 1 (
    echo   Installing pyttsx3 ^(TTS SAPI fallback^)...
    .\venv\Scripts\python.exe -m pip install pyttsx3 --quiet
)
.\venv\Scripts\python.exe -c "import pyttsx3" >NUL 2>&1
if errorlevel 1 (
    echo   [WARN] pyttsx3 install failed — SAPI fallback TTS unavailable
) else (
    echo   [OK]   pyttsx3 ^(SAPI TTS fallback^)
)

REM ════════════════════════════════════════════
REM [4/6] .env config
REM ════════════════════════════════════════════
echo.
echo [4/6] Config...
if not exist "%~dp0.env" (
    copy /Y "%~dp0.env.example" "%~dp0.env" >NUL
    echo   [OK]   .env created from .env.example
    echo.
    echo   !! ACTION REQUIRED: fill in .env before launching.
    echo      Minimum fields:
    echo        DISCORD_BOT_TOKEN=   ^(Discord Developer Portal ^> Bot ^> Reset Token^)
    echo        WHITELIST_USERS=     ^(ur Discord username in lowercase^)
    echo.
    echo   Opening .env in notepad now — edit, save, close to continue.
    notepad "%~dp0.env"
    echo   Notepad closed. Continuing setup...
) else (
    echo   [OK]   .env already exists ^(not overwritten^)
)

REM Check minimum fields are filled
findstr /C:"DISCORD_BOT_TOKEN=PASTE_TOKEN_HERE" "%~dp0.env" >NUL 2>&1
if not errorlevel 1 (
    echo   [WARN] DISCORD_BOT_TOKEN is still the placeholder value.
    echo          Edit .env and paste the real token from Discord Developer Portal.
)
findstr /C:"DISCORD_BOT_TOKEN=" "%~dp0.env" | findstr /V "PASTE_TOKEN_HERE" >NUL 2>&1
if errorlevel 1 (
    echo   [WARN] DISCORD_BOT_TOKEN may not be set — bot won't start without it.
)

REM ════════════════════════════════════════════
REM [5/6] Network / firewall check
REM ════════════════════════════════════════════
echo.
echo [5/6] Network check...

REM Is OLLAMA_URL pointing at localhost or a remote machine?
set IS_REMOTE=0
findstr /B /C:"OLLAMA_URL=http://localhost" "%~dp0.env" >NUL 2>&1
if not errorlevel 1 goto ollama_local
findstr /B /C:"OLLAMA_URL=http://127.0.0.1" "%~dp0.env" >NUL 2>&1
if not errorlevel 1 goto ollama_local
set IS_REMOTE=1

:ollama_local
if "%IS_REMOTE%"=="0" (
    echo   [OK]   OLLAMA_URL is localhost
    REM Check if Ollama is actually responding
    curl -s --connect-timeout 3 http://localhost:11434/api/version >NUL 2>&1
    if errorlevel 1 (
        echo   [WARN] Ollama is not running at localhost:11434.
        echo          Start it: run "ollama serve" or launch Ollama from the tray.
    ) else (
        echo   [OK]   Ollama is responding at localhost:11434
    )
) else (
    echo   [INFO] OLLAMA_URL points to a remote machine.
    echo.
    echo          Remote Ollama setup notes:
    echo          1. Port 11434 must be open on the remote machine's firewall:
    echo.
    echo             Windows ^(run on the remote machine^):
    echo             netsh advfirewall firewall add rule name="Ollama" ^
    echo                   dir=in action=allow protocol=TCP localport=11434
    echo.
    echo             Linux ^(run on the remote machine^):
    echo             sudo ufw allow 11434/tcp
    echo.
    echo          2. Ollama must bind to 0.0.0.0, not just localhost.
    echo             Set on the remote machine before starting Ollama:
    echo             Windows ^(set env var^): OLLAMA_HOST=0.0.0.0
    echo             Linux ^(set env var^):   export OLLAMA_HOST=0.0.0.0
    echo.
    REM Try to extract and ping the remote host
    for /f "tokens=1,* delims==" %%A in ('findstr /B "OLLAMA_URL" "%~dp0.env"') do set OLLAMA_RAW=%%B
    REM strip http:// and port — rough parse
    set OLLAMA_HOST_PART=%OLLAMA_RAW:http://=%
    for /f "tokens=1 delims=:" %%H in ("%OLLAMA_HOST_PART%") do (
        echo   Pinging %%H...
        ping -n 1 -w 2000 %%H >NUL 2>&1
        if errorlevel 1 (
            echo   [WARN] Cannot reach %%H — check the machine is online and firewall allows ICMP.
        ) else (
            echo   [OK]   %%H is reachable
        )
    )
    REM Check if Ollama endpoint is actually responding
    for /f "tokens=1,* delims==" %%A in ('findstr /B "OLLAMA_URL" "%~dp0.env"') do set OL_URL=%%B
    set OL_BASE=%OL_URL:/api/chat=%
    curl -s --connect-timeout 5 %OL_BASE%/api/version >NUL 2>&1
    if errorlevel 1 (
        echo   [WARN] Ollama endpoint not responding at %OL_BASE%
        echo          Check: firewall open, OLLAMA_HOST=0.0.0.0 set, ollama serve running.
    ) else (
        echo   [OK]   Ollama is responding at %OL_BASE%
    )
)

REM ════════════════════════════════════════════
REM [6/6] ElevenLabs TTS check (optional)
REM ════════════════════════════════════════════
echo.
echo [6/6] ElevenLabs TTS check ^(optional^)...
set "EL_API_KEY="
set "EL_VOICE_ID="
if exist "%~dp0.env" (
    for /f "tokens=1,* delims==" %%A in ('findstr /B /C:"EL_API_KEY=" "%~dp0.env"') do set "EL_API_KEY=%%B"
    for /f "tokens=1,* delims==" %%A in ('findstr /B /C:"EL_VOICE_ID=" "%~dp0.env"') do set "EL_VOICE_ID=%%B"
)

if not defined EL_API_KEY (
    echo   [SKIP] EL_API_KEY not set — TTS disabled. Add to .env to enable.
    goto setup_done
)
if "%EL_API_KEY%"=="" (
    echo   [SKIP] EL_API_KEY is empty — TTS disabled. Add to .env to enable.
    goto setup_done
)
if not defined EL_VOICE_ID (
    echo   [WARN] EL_API_KEY set but EL_VOICE_ID missing from .env.
    goto setup_done
)

echo   Hitting ElevenLabs voice endpoint...
curl -s -o NUL -w "%%{http_code}" --max-time 8 ^
    -H "xi-api-key: %EL_API_KEY%" ^
    "https://api.elevenlabs.io/v1/voices/%EL_VOICE_ID%" > "%TEMP%\el_check.txt" 2>NUL
set /p EL_STATUS=<"%TEMP%\el_check.txt"
del "%TEMP%\el_check.txt" >NUL 2>&1
if "%EL_STATUS%"=="200" (
    echo   [OK]   ElevenLabs responding ^(voice %EL_VOICE_ID:~0,8%...^)
) else (
    echo   [WARN] ElevenLabs returned HTTP %EL_STATUS%
    echo          Check EL_API_KEY and EL_VOICE_ID in .env
    echo          Get key:      https://elevenlabs.io ^> Profile ^> API Key
    echo          Get voice ID: https://elevenlabs.io ^> Voices
)

:setup_done
echo.
echo ============================================
echo Setup complete.
echo Next step: double-click start_servitor.bat
echo ============================================
echo.
pause
