@echo off
cd /d "%~dp0"
set "PY=python"
python -c "import sys" 1>nul 2>nul
if errorlevel 1 set "PY=py -3"
%PY% -m pip install -r "%~dp0requirements.txt" -r "%~dp0requirements-build.txt"
%PY% -m PyInstaller --noconfirm "%~dp0打字练习.spec"
echo.
echo Built: %~dp0dist\打字练习\打字练习.exe
