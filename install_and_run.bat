@echo off
cd /d "%~dp0"
if not exist .env (
  echo File .env is missing. Copy .env.example to .env and enter the current Telegram bot token.
  pause
  exit /b 1
)
if not exist venv\Scripts\python.exe (
  py -m venv venv
  if errorlevel 1 pause & exit /b 1
)
venv\Scripts\python.exe -m pip install --upgrade pip
if errorlevel 1 pause & exit /b 1
venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 pause & exit /b 1
call run_bot.bat
