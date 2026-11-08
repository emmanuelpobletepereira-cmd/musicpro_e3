@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo No se encontro el entorno virtual .venv. Consulta README_WAMP.md.
    pause
    exit /b 1
)
echo Iniciando servidor...
".venv\Scripts\python.exe" wamp.py servidor %*
if errorlevel 1 pause
