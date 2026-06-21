@echo off
REM Claude Code localization launcher. ASCII-only on purpose:
REM Chinese text in an executable line gets corrupted by cmd.exe's
REM GBK code page on Chinese-locale Windows even with chcp 65001,
REM so this file avoids non-ASCII bytes entirely and finds the
REM (Chinese-named) entry script dynamically via the OS file list.
chcp 65001 >nul
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] python was not found in PATH.
    echo Install Python 3 and make sure "python" works from a terminal.
    pause
    exit /b 1
)

set SCRIPT=
for %%F in (*.py) do set SCRIPT=%%F
if not defined SCRIPT (
    echo [ERROR] No .py entry script found in this folder.
    echo Make sure this file stays in the cloned repo root.
    pause
    exit /b 1
)

echo Found script: %SCRIPT%
echo Scanning translation tables and generating a preview list...
echo (you will be asked to confirm before anything real gets changed)
echo.
python "%SCRIPT%" --tui --audit

echo.
echo Done. Press any key to close this window.
pause >nul
