@echo off
rem Arranca B.A.W.I. (API + Riego + Comunidad). Doble clic en este archivo.
cd /d "%~dp0"

if not exist .venv\Scripts\python.exe (
    echo Preparando el entorno de Python por primera vez ^(tarda unos minutos^)...
    python -m venv .venv || goto error
    .venv\Scripts\python.exe -m pip install -r requirements.txt || goto error
)

.venv\Scripts\python.exe iniciar.py
pause
exit /b

:error
echo No se pudo preparar el entorno. Revisa que Python 3.13 este instalado.
pause
