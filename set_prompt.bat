@echo off
setlocal

set DIR=%~dp0

if "%1"=="" goto usage

set MODE=%1

if /i "%MODE%"=="servitor" goto servitor
if /i "%MODE%"=="tafe" goto tafe
if /i "%MODE%"=="lyrical" goto lyrical
if /i "%MODE%"=="list" goto list

echo [ERR] Unknown mode: %MODE%
goto usage

:servitor
if exist "%DIR%prompt_servitor.txt" (
    copy /y "%DIR%prompt_servitor.txt" "%DIR%system_prompt.txt" >nul
    echo [OK] Switched to SERVITOR mode.
    goto done
) else (
    echo [ERR] prompt_servitor.txt not found.
    echo       Save your configured SERVITOR prompt as prompt_servitor.txt first.
    echo       Or copy system_prompt.example.txt ^> prompt_servitor.txt and configure it.
    exit /b 1
)

:tafe
if exist "%DIR%prompt_tafe_ict_analysis.txt" (
    copy /y "%DIR%prompt_tafe_ict_analysis.txt" "%DIR%system_prompt.txt" >nul
    echo [OK] Switched to TAFE ICT Analysis mode.
    goto done
) else (
    echo [ERR] prompt_tafe_ict_analysis.txt not found.
    exit /b 1
)

:lyrical
if exist "%DIR%prompt_lyrical.txt" (
    copy /y "%DIR%prompt_lyrical.txt" "%DIR%system_prompt.txt" >nul
    echo [OK] Switched to Lyrical Forge mode.
    goto done
) else (
    echo [ERR] prompt_lyrical.txt not found.
    echo       Copy prompt_lyrical.example.txt ^> prompt_lyrical.txt first.
    exit /b 1
)

:list
echo Available modes:
echo   servitor  — SERVITOR war-engine persona (requires prompt_servitor.txt)
echo   tafe      — TAFE ICT Analysis tutor (requires prompt_tafe_ict_analysis.txt)
echo   lyrical   — Lyrical Forge, pure image generation (requires prompt_lyrical.txt)
echo.
echo First-time setup:
echo   copy system_prompt.example.txt prompt_servitor.txt   [then edit with your data]
echo   copy prompt_lyrical.example.txt prompt_lyrical.txt   [optional: personalise]
goto end

:done
echo Hot-reload active — next bot message uses the new prompt.
goto end

:usage
echo.
echo Usage: set_prompt.bat [mode]
echo.
echo Modes:
echo   servitor   SERVITOR war-engine persona
echo   tafe       TAFE ICT Analysis aggressive tutor
echo   lyrical    Lyrical Forge — pure image generation
echo   list       Show all modes and setup instructions
echo.
echo Hot-reload is active. No bot restart needed after switching.

:end
endlocal
