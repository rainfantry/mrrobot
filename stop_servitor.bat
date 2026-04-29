@echo off
title SERVITOR Stop

echo.
echo === STOPPING SERVITOR ===
echo.

REM Kill the bot's python process (matched by working dir / command line)
echo [1/2] Killing bot process...
for /f "tokens=2" %%i in ('wmic process where "name='python.exe' and commandline like '%%mrrobot.py%%'" get processid /value 2^>NUL ^| find "ProcessId="') do (
    taskkill /F /PID %%i 2>NUL
    echo   Killed bot PID %%i
)

REM Unload model from Ollama (don't kill ollama serve itself - it may be used by other things)
echo.
echo [2/2] Unloading model from RAM...
curl -s -X POST http://localhost:11434/api/generate -H "Content-Type: application/json" -d "{\"model\":\"huihui_ai/qwen2.5-coder-abliterate:7b\",\"keep_alive\":0}" >NUL 2>&1
echo   Model unloaded (Ollama service still running, idle).

echo.
echo Done. ~3.7GB RAM freed.
echo To kill Ollama itself too: taskkill /F /IM ollama.exe
timeout /t 4 /nobreak >NUL
