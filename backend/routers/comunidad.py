"""
Rutas de B.A.W.I. Comunidad.

C1 - Cuentas: crear cuenta, iniciar sesion y saber quien soy.
C2 - Publicaciones: ver el feed (sin sesion) y publicar con foto o nota de voz (con sesion).
C3 - Respuestas: ver una publicacion con sus respuestas y responder (con nota de voz y,
     si el usuario usa B.A.W.I. Riego, con su dato de campo real).
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


# ---------------------------------------------------------------------------
# C3 - Respuestas
# ---------------------------------------------------------------------------
CONSULTA_RESPUESTAS = (
    "SELECT c.id_comentario, c.texto, c.audio_ruta, c.creado_en, c.id_recomendacion, "
    "u.id_usuario, u.nombre AS autor_nombre, u.municipio AS autor_municipio, "
    "u.suscripcion_riego AS autor_riego, "
    "r.fecha AS riego_fecha, r.etc_mm, r.horas_sugeridas, r.horas_aplicadas, r.estado AS riego_estado, "
    "r.agua_ahorrada_m3, r.riesgo, cd.temp_max_c, cd.prob_lluvia_pct, cd.fuente, "
    "cu.nombre AS cultivo, ec.nombre AS etapa, pa.municipio AS parcela_municipio "
    "FROM comentarios c "
    "JOIN usuarios u ON u.id_usuario = c.id_usuario "
    "LEFT JOIN recomendaciones_riego r ON r.id_recomendacion = c.id_recomendacion "
    "LEFT JOIN clima_diario cd ON cd.id_clima = r.id_clima "
    "LEFT JOIN parcelas pa ON pa.id_parcela = r.id_parcela "
    "LEFT JOIN cultivos cu ON cu.id_cultivo = pa.id_cultivo "
    "LEFT JOIN etapas_cultivo ec ON ec.id_etapa = pa.id_etapa "
)


def _numero(valor):
    return None if valor is None else float(valor)  # SQL Server regresa Decimal


def respuesta_publica(fila) -> dict:
    dato = None
    if fila["id_recomendacion"] is not None:
        dato = {
            "fecha": fila["riego_fecha"].strftime("%Y-%m-%d"),
            "cultivo": fila["cultivo"],
            "etapa": fila["etapa"],
            "municipio": fila["parcela_municipio"],
            "temp_max_c": _numero(fila["temp_max_c"]),
            "prob_lluvia_pct": fila["prob_lluvia_pct"],
            "etc_mm": _numero(fila["etc_mm"]),
            "horas_sugeridas": _numero(fila["horas_sugeridas"]),
            "horas_aplicadas": _numero(fila["horas_aplicadas"]),
            "estado": fila["riego_estado"],
            "riesgo": fila["riesgo"],
            "agua_ahorrada_m3": _numero(fila["agua_ahorrada_m3"]),
            "clima_de_ejemplo": fila["fuente"] == "ejemplo",
        }
    return {
        "id_respuesta": fila["id_comentario"],
        "texto": fila["texto"],
        "audio": fila["audio_ruta"],
        "creada_en": fila["creado_en"].strftime("%Y-%m-%d %H:%M"),
        "autor": {
            "id_usuario": fila["id_usuario"],
            "nombre": fila["autor_nombre"],
            "municipio": fila["autor_municipio"],
            "usa_riego": bool(fila["autor_riego"]),
        },
        "dato_riego": dato,
    }


@router.get("/publicaciones/{id_publicacion}")
def ver_publicacion(id_publicacion: int):
    """La publicacion con todas sus respuestas, de la mas antigua a la mas nueva. Sin sesion."""
    with engine.connect() as conexion:
        pub = conexion.execute(
            text(CONSULTA_PUBLICACIONES + " WHERE p.id_publicacion = :id"), {"id": id_publicacion}
        ).mappings().first()
        if not pub:
            raise HTTPException(status_code=404, detail="La publicación no existe.")
        respuestas = conexion.execute(
            text(CONSULTA_RESPUESTAS + "WHERE c.id_publicacion = :id ORDER BY c.creado_en, c.id_comentario"),
            {"id": id_publicacion},
        ).mappings().all()
    return {**publicacion_publica(pub), "respuestas": [respuesta_publica(r) for r in respuestas]}


@router.post("/publicaciones/{id_publicacion}/respuestas")
async def responder(
    id_publicacion: int,
    texto: str = Form(..., min_length=2),
    audio: UploadFile | None = File(None),
    adjuntar_riego: bool = Form(False),
    authorization: str | None = Header(None),
):
    yo = usuario_actual(authorization)
    with engine.connect() as conexion:
        existe = conexion.execute(
            text("SELECT COUNT(*) FROM publicaciones WHERE id_publicacion = :id"), {"id": id_publicacion}
        ).scalar()
        if not existe:
            raise HTTPException(status_code=404, detail="La publicación no existe.")

        id_recomendacion = None
        if adjuntar_riego:
            if not yo["usa_riego"]:
                raise HTTPException(status_code=403,
                                    detail="Solo los usuarios de B.A.W.I. Riego pueden adjuntar su dato de campo.")
            # La recomendacion mas reciente de cualquiera de sus parcelas
            id_recomendacion = conexion.execute(
                text(
                    "SELECT r.id_recomendacion FROM recomendaciones_riego r "
                    "JOIN parcelas p ON p.id_parcela = r.id_parcela "
                    "WHERE p.id_usuario = :u ORDER BY r.fecha DESC, r.id_recomendacion DESC"
                ),
                {"u": yo["id_usuario"]},
            ).scalar()
            if id_recomendacion is None:
                raise HTTPException(status_code=400,
                                    detail="Aún no tienes recomendaciones en B.A.W.I. Riego para compartir.")

    audio_ruta = await guardar_archivo(audio, EXT_AUDIO, "audios")
    with engine.begin() as conexion:
        conexion.execute(
            text(
                "INSERT INTO comentarios (id_publicacion, id_usuario, texto, audio_ruta, id_recomendacion) "
                "VALUES (:p, :u, :texto, :audio, :rec)"
            ),
            {"p": id_publicacion, "u": yo["id_usuario"], "texto": texto.strip(),
             "audio": audio_ruta, "rec": id_recomendacion},
        )
        fila = conexion.execute(
            text(CONSULTA_RESPUESTAS + "WHERE c.id_publicacion = :p AND c.id_usuario = :u "
                 "ORDER BY c.id_comentario DESC"),
            {"p": id_publicacion, "u": yo["id_usuario"]},
        ).mappings().first()
    return respuesta_publica(fila)
