"""
Arranca B.A.W.I. completo con un solo comando: la API, la app de Riego y la de Comunidad.

    ./iniciar.sh        (Git Bash / terminal de VS Code)
    iniciar.bat         (doble clic en Windows)

Abre Riego en el navegador y muestra los links para otras computadoras de la misma red.
Ctrl + C detiene todo.
"""
import os
import secrets
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
PUERTO_API = int(os.getenv("PUERTO_API", "8000"))
PUERTO_RIEGO = int(os.getenv("PUERTO_RIEGO", "8502"))
PUERTO_COMUNIDAD = int(os.getenv("PUERTO_COMUNIDAD", "8503"))


def preparar_env() -> None:
    """Crea .env a partir de .env.example la primera vez, con una SECRET_KEY nueva."""
    env, ejemplo = RAIZ / ".env", RAIZ / ".env.example"
    if env.exists():
        return
    shutil.copy(ejemplo, env)
    texto = env.read_text(encoding="utf-8").replace("SECRET_KEY=\n", f"SECRET_KEY={secrets.token_hex(32)}\n", 1)
    env.write_text(texto, encoding="utf-8")
    print("Se creó el archivo .env (revisa los datos de SQL Server si no es localhost\\SQLEXPRESS).")


def puerto_ocupado(puerto: int) -> bool:
    with socket.socket() as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", puerto)) == 0


def ip_local() -> str:
    """IP de esta computadora en la red local (no envia nada a internet)."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("10.255.255.255", 1))
            return s.getsockname()[0]
    except OSError:
        return "localhost"


def esperar_api(segundos: int = 60) -> bool:
    limite = time.time() + segundos
    while time.time() < limite:
        try:
            with urllib.request.urlopen(f"http://localhost:{PUERTO_API}/", timeout=2):
                return True
        except OSError:
            time.sleep(1)
    return False


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)  # acentos y mensajes al momento en Git Bash
    os.chdir(RAIZ)
    preparar_env()

    ocupados = [p for p in (PUERTO_API, PUERTO_RIEGO, PUERTO_COMUNIDAD) if puerto_ocupado(p)]
    if ocupados:
        print(f"Los puertos {', '.join(map(str, ocupados))} ya están en uso: B.A.W.Í. (u otro programa) ya está "
              "corriendo. Ciérralo (Ctrl + C en su terminal) y vuelve a intentar.")
        return 1

    ip = ip_local()
    entorno = {
        **os.environ,
        "API_URL": f"http://localhost:{PUERTO_API}",
        # El icono de Riego lleva a Comunidad; con la IP de la red funciona tambien desde otras computadoras
        "COMUNIDAD_URL": f"http://{ip}:{PUERTO_COMUNIDAD}",
        "PYTHONIOENCODING": "utf-8",
    }
    streamlit = [sys.executable, "-m", "streamlit", "run"]
    opciones = ["--server.headless", "true", "--browser.gatherUsageStats", "false"]
    comandos = {
        "API": [sys.executable, "-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0",
                "--port", str(PUERTO_API), "--log-level", "warning"],
        "Riego": streamlit + ["apps/riego/app.py", "--server.port", str(PUERTO_RIEGO)] + opciones,
        "Comunidad": streamlit + ["apps/comunidad/app.py", "--server.port", str(PUERTO_COMUNIDAD)] + opciones,
    }

    procesos: dict[str, subprocess.Popen] = {}
    try:
        print("Iniciando la API...")
        procesos["API"] = subprocess.Popen(comandos["API"], env=entorno)
        if not esperar_api():
            print("La API no arrancó. Revisa el mensaje de error de arriba (SQL Server, .env).")
            return 1
        for nombre in ("Riego", "Comunidad"):
            print(f"Iniciando {nombre}...")
            procesos[nombre] = subprocess.Popen(comandos[nombre], env=entorno, stdout=subprocess.DEVNULL)
        time.sleep(4)

        print("\n" + "=" * 60)
        print(" B.A.W.Í. está corriendo")
        print(f"   Riego:      http://localhost:{PUERTO_RIEGO}")
        print(f"   Comunidad:  http://localhost:{PUERTO_COMUNIDAD}")
        if ip != "localhost":
            print("\n Desde otras computadoras en la misma red:")
            print(f"   Riego:      http://{ip}:{PUERTO_RIEGO}")
            print(f"   Comunidad:  http://{ip}:{PUERTO_COMUNIDAD}")
        print("\n Presiona Ctrl + C para detener todo.")
        print("=" * 60 + "\n")
        if os.getenv("BAWI_ABRIR_NAVEGADOR", "1") != "0":
            webbrowser.open(f"http://localhost:{PUERTO_RIEGO}")

        while True:
            for nombre, proceso in procesos.items():
                if proceso.poll() is not None:
                    print(f"{nombre} se detuvo (código {proceso.returncode}). Deteniendo todo.")
                    return 1
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nDeteniendo B.A.W.Í....")
        return 0
    finally:
        for proceso in procesos.values():
            if proceso.poll() is None:
                proceso.terminate()
        for proceso in procesos.values():
            try:
                proceso.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proceso.kill()


if __name__ == "__main__":
    sys.exit(main())
