"""
Contrasenas de los usuarios de B.A.W.I.

Nunca se guarda la contrasena tal cual: se guarda un "hash" (PBKDF2-SHA256
con sal aleatoria), que no se puede revertir. Para validar un login se
vuelve a calcular y se compara.
"""
import hashlib
import hmac
import os
import secrets

from dotenv import load_dotenv

load_dotenv()

ITERACIONES = 120_000
# Clave para firmar las sesiones y los codigos de verificacion (SECRET_KEY en .env)
SECRET_KEY = os.getenv("SECRET_KEY", "")
if len(SECRET_KEY) < 32:
    raise RuntimeError(
        "Falta SECRET_KEY en el archivo .env (minimo 32 caracteres). Genera una con:\n"
        "    python -c \"import secrets; print(secrets.token_hex(32))\""
    )


def hashear_password(password: str) -> str:
    sal = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), sal.encode(), ITERACIONES).hex()
    return f"{sal}${digest}"


def verificar_password(password: str, guardado: str) -> bool:
    sal, digest = guardado.split("$", 1)
    calculado = hashlib.pbkdf2_hmac("sha256", password.encode(), sal.encode(), ITERACIONES).hex()
    return hmac.compare_digest(calculado, digest)


# ---------------------------------------------------------------------------
# Sesiones: un "token" firmado que la app guarda despues de iniciar sesion.
# Tiene la forma  <id_usuario>.<firma>  y no se puede falsificar sin SECRET_KEY.
# ---------------------------------------------------------------------------
def _firma(id_usuario: int) -> str:
    return hmac.new(SECRET_KEY.encode(), str(id_usuario).encode(), hashlib.sha256).hexdigest()


def crear_token(id_usuario: int) -> str:
    return f"{id_usuario}.{_firma(id_usuario)}"


def leer_token(token: str) -> int | None:
    """Devuelve el id del usuario si el token es valido; si no, None."""
    try:
        id_texto, firma = token.split(".", 1)
        id_usuario = int(id_texto)
    except (ValueError, AttributeError):
        return None
    return id_usuario if hmac.compare_digest(firma, _firma(id_usuario)) else None

# ---------------------------------------------------------------------------
# Verificacion del correo: codigo de 6 numeros. Se guarda solo su "hash".
# ---------------------------------------------------------------------------
def generar_codigo() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def hash_codigo(correo: str, codigo: str) -> str:
    return hmac.new(SECRET_KEY.encode(), f"{correo}:{codigo}".encode(), hashlib.sha256).hexdigest()