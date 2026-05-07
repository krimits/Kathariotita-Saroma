@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

echo Starting dashboard at http://127.0.0.1:8001
python -m uvicorn dashboard_web:app --host 127.0.0.1 --port 8001
