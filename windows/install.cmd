@echo off
setlocal DisableDelayedExpansion
chcp 65001 >nul
where uv >nul 2>nul
if errorlevel 1 (
  echo Please install uv, reopen this window, and try again.
  echo Official instructions: https://docs.astral.sh/uv/getting-started/installation/
  pause
  exit /b 1
)
uv run --no-project --python 3.13 "%~dp0install.py" %*
set RESULT=%ERRORLEVEL%
echo.
pause
exit /b %RESULT%
