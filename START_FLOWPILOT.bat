@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title FlowPilot AI

echo.
echo ==============================================
echo          FLOWPILOT AI - STARTING
echo ==============================================
echo.

where py >nul 2>nul
if %errorlevel%==0 (
  set "PY=py"
) else (
  where python >nul 2>nul
  if %errorlevel%==0 (set "PY=python") else (goto NO_PYTHON)
)

if not exist "backend\.venv\Scripts\python.exe" (
  echo [1/4] Creating local Python environment...
  %PY% -m venv backend\.venv
  if errorlevel 1 goto FAIL
)

echo [2/4] Installing/updating required libraries...
backend\.venv\Scripts\python.exe -m pip install --disable-pip-version-check -q -r backend\requirements.txt
if errorlevel 1 goto FAIL

if not exist "backend\.env" (
  echo [3/4] Creating local configuration...
  backend\.venv\Scripts\python.exe -c "import secrets; open('backend\\.env','w',encoding='utf-8').write('SECRET_KEY='+secrets.token_urlsafe(48)+'\nFRONTEND_URL=http://127.0.0.1:8000\n')"
)

echo [4/4] Starting FlowPilot AI...
start "FlowPilot AI Server" /min cmd /c "cd /d ""%~dp0backend"" && .venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000"
timeout /t 2 /nobreak >nul
start "" http://127.0.0.1:8000/
echo.
echo FlowPilot AI is opening in your browser.
echo Keep the small server window running while using the app.
echo.
pause
exit /b 0

:NO_PYTHON
echo Python was not found on this PC.
echo Install Python 3.11 or newer from https://www.python.org/downloads/
echo Then double-click START_FLOWPILOT.bat again.
pause
exit /b 1

:FAIL
echo.
echo FlowPilot could not finish setup.
echo Read the error above, then send me a screenshot and I will fix it.
pause
exit /b 1
