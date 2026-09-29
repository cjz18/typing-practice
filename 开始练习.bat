@echo off
cd /d "%~dp0"
if exist "%~dp0dist\打字练习\打字练习.exe" (
  start "" "%~dp0dist\打字练习\打字练习.exe"
  exit /b 0
)
set "PY=python"
python -c "import sys" 1>nul 2>nul
if errorlevel 1 set "PY=py -3"
%PY% -c "import pypinyin" 1>nul 2>nul
if errorlevel 1 %PY% -m pip install -r "%~dp0requirements.txt"
%PY% "%~dp0app.py"
