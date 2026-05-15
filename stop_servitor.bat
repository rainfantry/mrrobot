@echo off
title SERVITOR Stop

echo.
echo === STOPPING SERVITOR ===
echo.

REM Kill the bot's python process (matched by working dir / command line)
REM Using %WINDIR%\System32\find.exe to avoid Git Bash's `find` shadowing on PATH
echo [1/3] Killing bot process(es)...
for /f "tokens=2" %%i in ('wmic process where "name='python.exe' and commandline like '%%mrrobot.py%%'" get processid /value 2^>NUL ^| %WINDIR%\System32\find.exe "ProcessId="') do (
    taskkill /F /PID %%i 2>NUL
    echo   Killed bot PID %%i
)

REM Unload coder model
echo.
echo [2/3] Unloading coder model from RAM...
curl -s -X POST http://localhost:11434/api/generate -H "Content-Type: application/json" -d "{\"model\":\"huihui_ai/qwen2.5-coder-abliterate:7b\",\"keep_alive\":0}" >NUL 2>&1
echo   Coder model unloaded.

REM Unload vision model (no-op if not loaded)
echo.
echo [3/3] Unloading vision model from RAM...
curl -s -X POST http://localhost:11434/api/generate -H "Content-Type: application/json" -d "{\"model\":\"huihui_ai/qwen2.5-vl-abliterated:7b\",\"keep_alive\":0}" >NUL 2>&1
echo   Vision model unloaded (Ollama service still running, idle).

echo.
echo Done. RAM freed.
echo To kill Ollama itself too: taskkill /F /IM ollama.exe
timeout /t 4 /nobreak >NUL
