@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
set "SPREADSHEET_URL=https://docs.google.com/spreadsheets/d/1Y1lvKhBIEEh5AceA580jSTXlB3ms5AwX5Mo5RC9b5wM/edit?gid=1505732445#gid=1505732445"
set "CREDENTIALS=%SCRIPT_DIR%service-account.json"
set "OUTPUT_DIR=%SCRIPT_DIR%output"

if not exist "%CREDENTIALS%" (
  echo Missing credentials file:
  echo %CREDENTIALS%
  echo.
  echo Put the Google service account JSON in this folder and name it service-account.json.
  echo Then share the Google Sheet with the service account email as Viewer.
  exit /b 1
)

python "%SCRIPT_DIR%google_sheets_extractor.py" --spreadsheet "%SPREADSHEET_URL%" --credentials "%CREDENTIALS%" --output-dir "%OUTPUT_DIR%"
if errorlevel 1 exit /b %errorlevel%

python "%SCRIPT_DIR%dashboard_hybrid.py" --output-dir "%OUTPUT_DIR%"
