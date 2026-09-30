@echo off
cd /d "%~dp0"
set "PY=python"
python -c "import sys" 1>nul 2>nul
if errorlevel 1 set "PY=py -3"
%PY% -c "import PySide6, pypinyin" 1>nul 2>nul
if errorlevel 1 %PY% -m pip install -r "%~dp0requirements.txt"
%PY% "%~dp0qt_app.py"
if errorlevel 1 pause
