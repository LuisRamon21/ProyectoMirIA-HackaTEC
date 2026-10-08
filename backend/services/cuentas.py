"""
Contrasenas de los usuarios de B.A.W.I.

Nunca se guarda la contrasena tal cual: se guarda un "hash" (PBKDF2-SHA256
con sal aleatoria), que no se puede revertir. Para validar un login se
vuelve a calcular y se compara.
"""
import hashlib
import hmac
import secrets

ITERACIONES = 120_000


def hashear_password(password: str) -> str:
    sal = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), sal.encode(), ITERACIONES).hex()
    return f"{sal}${digest}"


def verificar_password(password: str, guardado: str) -> bool:
    sal, digest = guardado.split("$", 1)
    calculado = hashlib.pbkdf2_hmac("sha256", password.encode(), sal.encode(), ITERACIONES).hex()
    return hmac.compare_digest(calculado, digest)