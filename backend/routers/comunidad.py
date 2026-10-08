"""
Rutas de B.A.W.I. Comunidad.

C1 - Cuentas: crear cuenta, iniciar sesion y saber quien soy.
C2 - Publicaciones: ver el feed (sin sesion) y publicar con foto o nota de voz (con sesion).
Para las rutas que piden sesion, la app manda la cabecera:
    Authorization: Bearer <token>
"""
import os
import uuid
from pathlib import Path

from fastapi import APIRouter, File, Form, Header, HTTPException, UploadFile
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


# ---------------------------------------------------------------------------
# C2 - Publicaciones
# ---------------------------------------------------------------------------
CATEGORIAS = ["riego", "plagas", "suelo", "cultivo", "otro"]
MEDIA_DIR = Path(os.getenv("MEDIA_DIR", "media"))  # donde se guardan fotos y audios
EXT_FOTO = {".jpg", ".jpeg", ".png", ".webp"}
EXT_AUDIO = {".wav", ".mp3", ".m4a", ".ogg", ".webm"}
MAX_MB = 10


async def guardar_archivo(archivo: UploadFile | None, permitidas: set[str], carpeta: str) -> str | None:
    """Guarda el archivo en media/<carpeta>/ con un nombre unico y regresa su ruta publica /media/..."""
    if archivo is None or not archivo.filename:
        return None
    extension = Path(archivo.filename).suffix.lower()
    if extension not in permitidas:
        raise HTTPException(status_code=400, detail=f"Formato no permitido ({extension}). Usa: {', '.join(sorted(permitidas))}")
    contenido = await archivo.read()
    if len(contenido) > MAX_MB * 1024 * 1024:
        raise HTTPException(status_code=400, detail=f"El archivo pasa de {MAX_MB} MB.")
    destino = MEDIA_DIR / carpeta
    destino.mkdir(parents=True, exist_ok=True)
    nombre = f"{uuid.uuid4().hex}{extension}"
    (destino / nombre).write_bytes(contenido)
    return f"/media/{carpeta}/{nombre}"


def publicacion_publica(fila) -> dict:
    return {
        "id_publicacion": fila["id_publicacion"],
        "titulo": fila["titulo"],
        "texto": fila["texto"],
        "categoria": fila["categoria"],
        "imagen": fila["imagen_ruta"],
        "audio": fila["audio_ruta"],
        "creada_en": fila["creada_en"].strftime("%Y-%m-%d %H:%M"),
        "num_respuestas": fila["num_respuestas"],
        "autor": {
            "id_usuario": fila["id_usuario"],
            "nombre": fila["autor_nombre"],
            "municipio": fila["autor_municipio"],
            "usa_riego": bool(fila["autor_riego"]),
        },
    }


CONSULTA_PUBLICACIONES = (
    "SELECT p.id_publicacion, p.titulo, p.texto, p.categoria, p.imagen_ruta, p.audio_ruta, p.creada_en, "
    "u.id_usuario, u.nombre AS autor_nombre, u.municipio AS autor_municipio, "
    "u.suscripcion_riego AS autor_riego, "
    "(SELECT COUNT(*) FROM comentarios c WHERE c.id_publicacion = p.id_publicacion) AS num_respuestas "
    "FROM publicaciones p JOIN usuarios u ON u.id_usuario = p.id_usuario"
)


@router.get("/publicaciones")
def listar_publicaciones(categoria: str | None = None):
    """Feed: de la mas reciente a la mas antigua. Se puede ver sin iniciar sesion."""
    consulta, valores = CONSULTA_PUBLICACIONES, {}
    if categoria:
        consulta += " WHERE p.categoria = :categoria"
        valores["categoria"] = categoria
    consulta += " ORDER BY p.creada_en DESC, p.id_publicacion DESC"
    with engine.connect() as conexion:
        filas = conexion.execute(text(consulta), valores).mappings().all()
    return [publicacion_publica(f) for f in filas]


@router.post("/publicaciones")
async def publicar(
    titulo: str = Form(..., min_length=3, max_length=150),
    texto: str = Form(..., min_length=3),
    categoria: str = Form(...),
    foto: UploadFile | None = File(None),
    audio: UploadFile | None = File(None),
    authorization: str | None = Header(None),
):
    yo = usuario_actual(authorization)
    if categoria not in CATEGORIAS:
        raise HTTPException(status_code=400, detail=f"Categoría no válida. Usa: {', '.join(CATEGORIAS)}")
    imagen_ruta = await guardar_archivo(foto, EXT_FOTO, "fotos")
    audio_ruta = await guardar_archivo(audio, EXT_AUDIO, "audios")
    with engine.begin() as conexion:
        conexion.execute(
            text(
                "INSERT INTO publicaciones (id_usuario, titulo, texto, imagen_ruta, audio_ruta, categoria) "
                "VALUES (:u, :titulo, :texto, :imagen, :audio, :categoria)"
            ),
            {"u": yo["id_usuario"], "titulo": titulo.strip(), "texto": texto.strip(),
             "imagen": imagen_ruta, "audio": audio_ruta, "categoria": categoria},
        )
        fila = conexion.execute(
            text(CONSULTA_PUBLICACIONES + " WHERE p.id_usuario = :u ORDER BY p.id_publicacion DESC"),
            {"u": yo["id_usuario"]},
        ).mappings().first()
    return publicacion_publica(fila)