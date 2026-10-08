"""
Rutas de B.A.W.I. Comunidad.

C1 - Cuentas: crear cuenta, iniciar sesion y saber quien soy.
Para las rutas que piden sesion, la app manda la cabecera:
    Authorization: Bearer <token>
"""
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text

from backend.db import engine
from backend.services.cuentas import crear_token, hashear_password, leer_token, verificar_password

router = APIRouter(prefix="/api/comunidad", tags=["Comunidad"])

CAMPOS_USUARIO = "id_usuario, usuario, nombre, municipio, rol, suscripcion_riego"


def usuario_publico(fila) -> dict:
    """Datos del usuario que se pueden mostrar (nunca el hash de la contrasena)."""
    return {
        "id_usuario": fila["id_usuario"],
        "usuario": fila["usuario"],
        "nombre": fila["nombre"],
        "municipio": fila["municipio"],
        "rol": fila["rol"],
        "usa_riego": bool(fila["suscripcion_riego"]),
    }


def buscar_usuario(conexion, *, id_usuario: int | None = None, usuario: str | None = None):
    if id_usuario is not None:
        consulta, valor = "id_usuario = :v", id_usuario
    else:
        consulta, valor = "usuario = :v", usuario
    return conexion.execute(
        text(f"SELECT {CAMPOS_USUARIO}, password_hash FROM usuarios WHERE {consulta}"), {"v": valor}
    ).mappings().first()


def usuario_actual(authorization: str | None) -> dict:
    """Lee el token de la cabecera Authorization. Lanza 401 si no hay sesion valida."""
    token = (authorization or "").removeprefix("Bearer ").strip()
    id_usuario = leer_token(token) if token else None
    if id_usuario is None:
        raise HTTPException(status_code=401, detail="Inicia sesión para hacer esto.")
    with engine.connect() as conexion:
        fila = buscar_usuario(conexion, id_usuario=id_usuario)
    if not fila:
        raise HTTPException(status_code=401, detail="Tu sesión ya no es válida. Vuelve a entrar.")
    return usuario_publico(fila)


# ---------------------------------------------------------------------------
# C1 - Cuentas
# ---------------------------------------------------------------------------
class Registro(BaseModel):
    usuario: str = Field(min_length=3, max_length=30, pattern=r"^[A-Za-z0-9_]+$",
                         description="solo letras, numeros y guion bajo")
    nombre: str = Field(min_length=2, max_length=80)
    municipio: str = Field(min_length=2, max_length=60)
    password: str = Field(min_length=6, max_length=100)


class Login(BaseModel):
    usuario: str
    password: str


@router.post("/registro")
def registrar(datos: Registro):
    usuario = datos.usuario.strip().lower()
    with engine.begin() as conexion:
        if buscar_usuario(conexion, usuario=usuario):
            raise HTTPException(status_code=409, detail="Ese nombre de usuario ya existe. Elige otro.")
        conexion.execute(
            text(
                "INSERT INTO usuarios (nombre, usuario, password_hash, municipio) "
                "VALUES (:nombre, :usuario, :hash, :municipio)"
            ),
            {"nombre": datos.nombre.strip(), "usuario": usuario,
             "hash": hashear_password(datos.password), "municipio": datos.municipio.strip()},
        )
        fila = buscar_usuario(conexion, usuario=usuario)
    return {"token": crear_token(fila["id_usuario"]), "usuario": usuario_publico(fila)}


@router.post("/login")
def iniciar_sesion(datos: Login):
    with engine.connect() as conexion:
        fila = buscar_usuario(conexion, usuario=datos.usuario.strip().lower())
    if not fila or not verificar_password(datos.password, fila["password_hash"]):
        raise HTTPException(status_code=401, detail="Usuario o contraseña incorrectos.")
    return {"token": crear_token(fila["id_usuario"]), "usuario": usuario_publico(fila)}


@router.get("/yo")
def quien_soy(authorization: str | None = Header(None)):
    return usuario_actual(authorization)