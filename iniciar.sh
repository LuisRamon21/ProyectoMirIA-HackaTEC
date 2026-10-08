#!/usr/bin/env bash
# Arranca B.A.W.I. (API + Riego + Comunidad). Uso, desde Git Bash:  ./iniciar.sh
cd "$(dirname "$0")" || exit 1

if [ ! -x .venv/Scripts/python.exe ]; then
    echo "Preparando el entorno de Python por primera vez (tarda unos minutos)..."
    python -m venv .venv && .venv/Scripts/python.exe -m pip install -r requirements.txt || exit 1
fi

exec .venv/Scripts/python.exe iniciar.py
