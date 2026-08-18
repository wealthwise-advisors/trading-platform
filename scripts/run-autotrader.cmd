@echo off
REM ---------------------------------------------------------------------------
REM Start AutoTrader locally: FastAPI on :8000, Vite on :5173.
REM
REM Each server opens in its own window. Close a window to stop that server.
REM Kept outside the git repo on purpose so it never shows up as an untracked
REM file in `git status`.
REM
REM Python must be 3.12 -- 3.14 breaks pandas_ta and produces a fake test
REM failure, so the launcher pins it rather than using whatever `python` is.
REM ---------------------------------------------------------------------------
setlocal
set REPO=%~dp0trading-platform

if not exist "%REPO%\api\main.py" (
  echo Could not find the app at "%REPO%".
  echo Expected this script to sit next to the trading-platform folder.
  pause
  exit /b 1
)

echo Freeing ports 8000 and 5173 if anything is holding them...
for %%P in (8000 5173) do (
  for /f "tokens=5" %%A in ('netstat -ano ^| findstr /r /c:"LISTENING" ^| findstr ":%%P "') do (
    taskkill /F /PID %%A >nul 2>&1
  )
)

echo Starting the API on http://127.0.0.1:8000 ...
start "AutoTrader API" cmd /k "cd /d ""%REPO%"" && set AUTOTRADER_CORS_ORIGINS=http://localhost:5173 && py -3.12 -m uvicorn api.main:app --host 127.0.0.1 --port 8000"

echo Starting the web app on http://localhost:5173 ...
start "AutoTrader Web" cmd /k "cd /d ""%REPO%\web"" && npm run dev"

echo.
echo   Open  http://localhost:5173
echo.
echo   Use localhost, NOT 127.0.0.1 -- Vite binds to IPv6 and 127.0.0.1 is
echo   refused. That is the "site can't be reached" error, not a broken app.
echo.
echo Two windows have opened. Give them a few seconds, then open the URL.
echo Closing a window stops that server.
timeout /t 8 >nul
start "" http://localhost:5173
endlocal
