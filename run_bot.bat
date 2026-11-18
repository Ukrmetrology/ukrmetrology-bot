@echo off
cd /d "%~dp0"
if not exist venv\Scripts\python.exe (
  echo Virtual environment not found. Run install_and_run.bat first.
  pause
  exit /b 1
)
if not exist logs mkdir logs
:loop
echo [%date% %time%] START >> logs\console.log
venv\Scripts\python.exe bot.py >> logs\console.log 2>&1
echo [%date% %time%] STOPPED code %errorlevel%, restart in 15 s >> logs\console.log
ping -n 16 127.0.0.1 >nul
goto loop
