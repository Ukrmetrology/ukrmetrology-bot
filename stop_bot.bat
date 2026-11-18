@echo off
cd /d "%~dp0"
powershell -NoProfile -Command "$root=(Get-Location).Path; Get-CimInstance Win32_Process | Where-Object { $_.Name -match '^python(w)?\.exe$' -and $_.CommandLine -like ('*' + $root + '*bot.py*') } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"
echo Stop command sent for this project's bot process.
pause
