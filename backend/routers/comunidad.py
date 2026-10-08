"""
Rutas de B.A.W.I. Comunidad.

C1 - Cuentas: crear cuenta, iniciar sesion y saber quien soy.
C2 - Publicaciones: ver el feed (sin sesion) y publicar con foto o nota de voz (con sesion).
C3 - Respuestas: ver una publicacion con sus respuestas y responder (con nota de voz y,
     si el usuario usa B.A.W.I. Riego, con su dato de campo real).
D1 - Cuentas con correo: se entra con correo (o con el usuario de las cuentas de demo).
D2 - Rangos y puntos: solo Especialista Agronomo y Maestro de la Tierra responden; likes en
     publicaciones y respuestas; "Le funciono al autor"; puntos segun backend/services/puntos.py.
Para las rutas que piden sesion, la app manda la cabecera:
    Authorization: Bearer <token>
"""
import hmac
import os
import re
import uuid
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import APIRouter, File, Form, Header, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import bindparam, text

from backend.db import engine
from backend.services.correo import correo_configurado, enviar_codigo
from backend.services.cuentas import (crear_token, generar_codigo, hash_codigo, hashear_password, leer_token,
                                      verificar_password)
from backend.services import puntos as reglas

router = APIRouter(prefix="/api/comunidad", tags=["Comunidad"])

CAMPOS_USUARIO = "id_usuario, usuario, correo, nombre, municipio, rol, suscripcion_riego, puntos"


def usuario_publico(fila) -> dict:
    """Datos del usuario que se pueden mostrar (nunca el hash de la contrasena)."""
    rango = reglas.calcular_rango(fila["puntos"], bool(fila["suscripcion_riego"]))
    return {
        "id_usuario": fila["id_usuario"],
        "usuario": fila["usuario"],
        "correo": fila["correo"],
        "nombre": fila["nombre"],
        "municipio": fila["municipio"],
        "rol": fila["rol"],
        "usa_riego": bool(fila["suscripcion_riego"]),
        "puntos": fila["puntos"],
        "rango": rango,
        "puede_responder": reglas.puede_responder(rango),
    }


def autor_publico(fila) -> dict:
    """Datos del autor de una publicacion o respuesta (vienen con prefijo autor_ en la consulta)."""
    rango = reglas.calcular_rango(fila["autor_puntos"], bool(fila["autor_riego"]))
    return {
        "id_usuario": fila["id_usuario"],
        "nombre": fila["autor_nombre"],
        "municipio": fila["autor_municipio"],
        "usa_riego": bool(fila["autor_riego"]),
        "rango": {"nombre": rango["nombre"], "insignia": rango["insignia"]},
    }


def buscar_usuario(conexion, *, id_usuario: int | None = None, usuario: str | None = None,
                   correo: str | None = None):
    if id_usuario is not None:
        consulta, valor = "id_usuario = :v", id_usuario
    elif correo is not None:
        consulta, valor = "correo = :v", correo
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


def id_visitante(authorization: str | None) -> int:
    """Id de quien mira (para saber si ya dio like). 0 si no inicio sesion."""
    token = (authorization or "").removeprefix("Bearer ").strip()
    return (leer_token(token) or 0) if token else 0


# ---------------------------------------------------------------------------
# C1 - Cuentas
# ---------------------------------------------------------------------------
PATRON_CORREO = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


class Registro(BaseModel):
    nombre: str = Field(min_length=2, max_length=80, description="nombre que aparece en el perfil")
    correo: str = Field(min_length=5, max_length=120, pattern=PATRON_CORREO)
    municipio: str = Field(min_length=2, max_length=60, description="zona aproximada del cultivo")
    password: str = Field(min_length=6, max_length=100)
    confirmacion: str


class Login(BaseModel):
    correo: str = Field(description="correo; las cuentas de demo tambien entran con su usuario")
    password: str


def _usuario_desde_correo(conexion, correo: str) -> str:
    """Crea un nombre de usuario interno unico a partir del correo (juan.perez@x.com -> juan_perez)."""
    base = re.sub(r"[^a-z0-9_]", "_", correo.split("@")[0].lower())[:24].strip("_") or "usuario"
    candidato, n = base, 1
    while buscar_usuario(conexion, usuario=candidato):
        n += 1
        candidato = f"{base}{n}"
    return candidato


# ---------------------------------------------------------------------------
# Crear cuenta en dos pasos: 1) datos -> se envia un codigo al correo; 2) codigo -> se crea la cuenta
# ---------------------------------------------------------------------------
MINUTOS_CODIGO = 10
SEGUNDOS_PARA_REENVIAR = 60
MAX_INTENTOS_CODIGO = 5


class Verificacion(BaseModel):
    correo: str
    codigo: str = Field(min_length=6, max_length=6)


class Reenvio(BaseModel):
    correo: str


def _enviar_codigo(correo: str, nombre: str, codigo: str) -> None:
    try:
        enviar_codigo(correo, nombre, codigo, MINUTOS_CODIGO)
    except RuntimeError:
        raise HTTPException(status_code=502, detail="No pudimos enviar el correo. Revisa que esté bien escrito "
                                                    "o intenta de nuevo en un momento.")


def _momentos() -> dict:
    ahora = datetime.now().replace(microsecond=0)
    return {"ahora": ahora, "expira": ahora + timedelta(minutes=MINUTOS_CODIGO),
            "limite_reenvio": ahora - timedelta(seconds=SEGUNDOS_PARA_REENVIAR)}


@router.post("/registro/solicitar")
def solicitar_registro(datos: Registro):
    """Paso 1: guarda los datos como registro pendiente y envia un codigo de 6 numeros al correo."""
    if datos.password != datos.confirmacion:
        raise HTTPException(status_code=400, detail="Las contraseñas no coinciden.")
    correo = datos.correo.strip().lower()
    codigo, t = generar_codigo(), _momentos()
    with engine.begin() as conexion:  # si el correo no sale, no queda nada guardado
        if buscar_usuario(conexion, correo=correo):
            raise HTTPException(status_code=409, detail="Ya existe una cuenta con ese correo. Inicia sesión.")
        if conexion.execute(text("SELECT COUNT(*) FROM registros_pendientes WHERE correo = :c AND enviado_en > :l"),
                            {"c": correo, "l": t["limite_reenvio"]}).scalar():
            raise HTTPException(status_code=429, detail="Ya te enviamos un código hace menos de un minuto. "
                                                        "Revisa tu correo (también la carpeta de spam).")
        conexion.execute(text("DELETE FROM registros_pendientes WHERE correo = :c"), {"c": correo})
        conexion.execute(
            text("INSERT INTO registros_pendientes (correo, nombre, municipio, password_hash, codigo_hash, "
                 "intentos, enviado_en, expira_en) VALUES (:c, :n, :m, :p, :h, 0, :ahora, :expira)"),
            {"c": correo, "n": datos.nombre.strip(), "m": datos.municipio.strip(),
             "p": hashear_password(datos.password), "h": hash_codigo(correo, codigo),
             "ahora": t["ahora"], "expira": t["expira"]},
        )
        _enviar_codigo(correo, datos.nombre.strip(), codigo)
    return {"correo": correo, "minutos": MINUTOS_CODIGO, "modo_prueba": not correo_configurado()}


@router.post("/registro/reenviar")
def reenviar_codigo(datos: Reenvio):
    """Manda un codigo nuevo al mismo registro pendiente (el anterior deja de servir)."""
    correo = datos.correo.strip().lower()
    codigo, t = generar_codigo(), _momentos()
    with engine.begin() as conexion:
        pendiente = conexion.execute(
            text("SELECT nombre, CASE WHEN enviado_en > :l THEN 1 ELSE 0 END AS reciente "
                 "FROM registros_pendientes WHERE correo = :c"),
            {"c": correo, "l": t["limite_reenvio"]},
        ).mappings().first()
        if not pendiente:
            raise HTTPException(status_code=404, detail="No hay una cuenta esperando verificación con ese correo.")
        if pendiente["reciente"]:
            raise HTTPException(status_code=429, detail="Espera un minuto antes de pedir otro código.")
        conexion.execute(
            text("UPDATE registros_pendientes SET codigo_hash = :h, intentos = 0, enviado_en = :ahora, "
                 "expira_en = :expira WHERE correo = :c"),
            {"h": hash_codigo(correo, codigo), "ahora": t["ahora"], "expira": t["expira"], "c": correo},
        )
        _enviar_codigo(correo, pendiente["nombre"], codigo)
    return {"correo": correo, "minutos": MINUTOS_CODIGO, "modo_prueba": not correo_configurado()}


@router.post("/registro/verificar")
def verificar_registro(datos: Verificacion):
    """Paso 2: si el codigo es correcto, crea la cuenta (Aprendiz del Campo) e inicia sesion."""
    correo = datos.correo.strip().lower()
    t = _momentos()
    error, fila = None, None
    with engine.begin() as conexion:
        pendiente = conexion.execute(
            text("SELECT nombre, municipio, password_hash, codigo_hash, intentos, "
                 "CASE WHEN expira_en >= :ahora THEN 1 ELSE 0 END AS vigente "
                 "FROM registros_pendientes WHERE correo = :c"),
            {"c": correo, "ahora": t["ahora"]},
        ).mappings().first()
        if not pendiente:
            raise HTTPException(status_code=404, detail="No hay una cuenta esperando verificación con ese correo.")
        if not pendiente["vigente"]:
            raise HTTPException(status_code=410, detail="El código ya venció. Pide uno nuevo.")
        if pendiente["intentos"] >= MAX_INTENTOS_CODIGO:
            raise HTTPException(status_code=429, detail="Demasiados intentos. Pide un código nuevo.")
        if not hmac.compare_digest(hash_codigo(correo, datos.codigo.strip()), pendiente["codigo_hash"]):
            conexion.execute(text("UPDATE registros_pendientes SET intentos = intentos + 1 WHERE correo = :c"),
                             {"c": correo})
            restantes = MAX_INTENTOS_CODIGO - pendiente["intentos"] - 1
            error = (f"Código incorrecto. Te quedan {restantes} intento(s)." if restantes
                     else "Código incorrecto. Pide un código nuevo.")
        elif buscar_usuario(conexion, correo=correo):
            raise HTTPException(status_code=409, detail="Ya existe una cuenta con ese correo. Inicia sesión.")
        else:
            conexion.execute(
                text("INSERT INTO usuarios (nombre, usuario, correo, password_hash, municipio) "
                     "VALUES (:nombre, :usuario, :correo, :hash, :municipio)"),
                {"nombre": pendiente["nombre"], "usuario": _usuario_desde_correo(conexion, correo),
                 "correo": correo, "hash": pendiente["password_hash"], "municipio": pendiente["municipio"]},
            )
            conexion.execute(text("DELETE FROM registros_pendientes WHERE correo = :c"), {"c": correo})
            fila = buscar_usuario(conexion, correo=correo)
    if error:  # fuera del "with" para que si se guarde el intento fallido
        raise HTTPException(status_code=400, detail=error)
    return {"token": crear_token(fila["id_usuario"]), "usuario": usuario_publico(fila)}


@router.post("/login")
def iniciar_sesion(datos: Login):
    identificador = datos.correo.strip().lower()
    with engine.connect() as conexion:
        fila = buscar_usuario(conexion, correo=identificador) or buscar_usuario(conexion, usuario=identificador)
    if not fila or not verificar_password(datos.password, fila["password_hash"]):
        raise HTTPException(status_code=401, detail="Correo o contraseña incorrectos.")
    return {"token": crear_token(fila["id_usuario"]), "usuario": usuario_publico(fila)}


@router.get("/yo")
def quien_soy(authorization: str | None = Header(None)):
    return usuario_actual(authorization)


@router.get("/rangos")
def ver_rangos():
    return reglas.lista_rangos()


@router.get("/yo/actividad")
def mi_actividad(authorization: str | None = Header(None)):
    """Resumen para el perfil: publicaciones, respuestas y ultimos puntos ganados."""
    yo = usuario_actual(authorization)
    with engine.connect() as conexion:
        publicaciones = conexion.execute(
            text("SELECT COUNT(*) FROM publicaciones WHERE id_usuario = :u"), {"u": yo["id_usuario"]}
        ).scalar()
        respuestas = conexion.execute(
            text("SELECT COUNT(*) FROM comentarios WHERE id_usuario = :u"), {"u": yo["id_usuario"]}
        ).scalar()
        movimientos = conexion.execute(
            text("SELECT puntos, motivo, fecha FROM movimientos_puntos WHERE id_usuario = :u "
                 "ORDER BY fecha DESC, id_movimiento DESC"),
            {"u": yo["id_usuario"]},
        ).mappings().fetchmany(10)
    return {
        "publicaciones": publicaciones,
        "respuestas": respuestas,
        "movimientos": [{"puntos": m["puntos"], "motivo": m["motivo"],
                         "fecha": m["fecha"].strftime("%Y-%m-%d %H:%M")} for m in movimientos],
    }


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
        "editada": fila["editada_en"] is not None,
        "num_respuestas": fila["num_respuestas"],
        "likes": fila["likes"],
        "yo_di_like": bool(fila["yo_like"]),
        "autor": autor_publico(fila),
    }


CONSULTA_PUBLICACIONES = (
    "SELECT p.id_publicacion, p.titulo, p.texto, p.categoria, p.imagen_ruta, p.audio_ruta, p.creada_en, p.editada_en, "
    "u.id_usuario, u.nombre AS autor_nombre, u.municipio AS autor_municipio, "
    "u.suscripcion_riego AS autor_riego, u.puntos AS autor_puntos, "
    "(SELECT COUNT(*) FROM comentarios c WHERE c.id_publicacion = p.id_publicacion) AS num_respuestas, "
    "(SELECT COUNT(*) FROM likes_publicacion l WHERE l.id_publicacion = p.id_publicacion) AS likes, "
    "(SELECT COUNT(*) FROM likes_publicacion l2 "
    " WHERE l2.id_publicacion = p.id_publicacion AND l2.id_usuario = :visitante) AS yo_like "
    "FROM publicaciones p JOIN usuarios u ON u.id_usuario = p.id_usuario"
)


@router.get("/publicaciones")
def listar_publicaciones(categoria: str | None = None, orden: str = "recientes", buscar: str | None = None,
                         con_respuestas: bool = False, authorization: str | None = Header(None)):
    """Feed. orden = recientes o likes. Con con_respuestas=true incluye las respuestas de cada publicacion."""
    condiciones, valores = [], {"visitante": id_visitante(authorization)}
    if categoria:
        condiciones.append("p.categoria = :categoria")
        valores["categoria"] = categoria
    if buscar and buscar.strip():
        condiciones.append("(p.titulo LIKE :buscar OR p.texto LIKE :buscar)")
        valores["buscar"] = f"%{buscar.strip()}%"
    consulta = CONSULTA_PUBLICACIONES
    if condiciones:
        consulta += " WHERE " + " AND ".join(condiciones)
    if orden == "likes":
        consulta += " ORDER BY likes DESC, p.creada_en DESC, p.id_publicacion DESC"
    else:
        consulta += " ORDER BY p.creada_en DESC, p.id_publicacion DESC"
    with engine.connect() as conexion:
        publicaciones = [publicacion_publica(f) for f in conexion.execute(text(consulta), valores).mappings().all()]
        if con_respuestas and publicaciones:
            ids = [p["id_publicacion"] for p in publicaciones]
            consulta_resp = text(
                CONSULTA_RESPUESTAS + "WHERE c.id_publicacion IN :ids ORDER BY c.creado_en, c.id_comentario"
            ).bindparams(bindparam("ids", expanding=True))
            por_publicacion = {i: [] for i in ids}
            for fila in conexion.execute(consulta_resp, {"ids": ids, "visitante": valores["visitante"]}).mappings():
                por_publicacion[fila["id_publicacion"]].append(respuesta_publica(fila))
            for p in publicaciones:
                p["respuestas"] = por_publicacion[p["id_publicacion"]]
    return publicaciones


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
            {"u": yo["id_usuario"], "visitante": yo["id_usuario"]},
        ).mappings().first()
    return publicacion_publica(fila)


@router.post("/publicaciones/{id_publicacion}/like")
def like_publicacion(id_publicacion: int, authorization: str | None = Header(None)):
    """Pone o quita el like de una publicacion. No da puntos; solo cuenta para Tendencias."""
    yo = usuario_actual(authorization)
    valores = {"p": id_publicacion, "u": yo["id_usuario"]}
    with engine.begin() as conexion:
        if not conexion.execute(text("SELECT COUNT(*) FROM publicaciones WHERE id_publicacion = :p"),
                                valores).scalar():
            raise HTTPException(status_code=404, detail="La publicación no existe.")
        ya = conexion.execute(
            text("SELECT COUNT(*) FROM likes_publicacion WHERE id_publicacion = :p AND id_usuario = :u"), valores
        ).scalar()
        if ya:
            conexion.execute(text("DELETE FROM likes_publicacion WHERE id_publicacion = :p AND id_usuario = :u"),
                             valores)
        else:
            conexion.execute(text("INSERT INTO likes_publicacion (id_publicacion, id_usuario) VALUES (:p, :u)"),
                             valores)
        likes = conexion.execute(
            text("SELECT COUNT(*) FROM likes_publicacion WHERE id_publicacion = :p"), valores
        ).scalar()
    return {"likes": likes, "yo_di_like": not ya}


class EdicionPublicacion(BaseModel):
    titulo: str = Field(min_length=3, max_length=150)
    texto: str = Field(min_length=3)
    categoria: str


def _mi_publicacion(conexion, id_publicacion: int, yo: dict) -> None:
    """Revisa que la publicacion exista y sea de quien la quiere cambiar."""
    autor = conexion.execute(text("SELECT id_usuario FROM publicaciones WHERE id_publicacion = :p"),
                             {"p": id_publicacion}).scalar()
    if autor is None:
        raise HTTPException(status_code=404, detail="La publicación no existe.")
    if autor != yo["id_usuario"]:
        raise HTTPException(status_code=403, detail="Solo quien la publicó puede editarla o eliminarla.")


@router.put("/publicaciones/{id_publicacion}")
def editar_publicacion(id_publicacion: int, datos: EdicionPublicacion, authorization: str | None = Header(None)):
    """Cambia titulo, texto y tema. La foto y la nota de voz se quedan igual."""
    yo = usuario_actual(authorization)
    if datos.categoria not in CATEGORIAS:
        raise HTTPException(status_code=400, detail=f"Categoría no válida. Usa: {', '.join(CATEGORIAS)}")
    with engine.begin() as conexion:
        _mi_publicacion(conexion, id_publicacion, yo)
        conexion.execute(
            text("UPDATE publicaciones SET titulo = :t, texto = :x, categoria = :c, editada_en = :ahora "
                 "WHERE id_publicacion = :p"),
            {"t": datos.titulo.strip(), "x": datos.texto.strip(), "c": datos.categoria,
             "ahora": datetime.now().replace(microsecond=0), "p": id_publicacion},
        )
    return {"ok": True}


@router.delete("/publicaciones/{id_publicacion}")
def eliminar_publicacion(id_publicacion: int, authorization: str | None = Header(None)):
    """Borra la publicacion con sus respuestas y likes (la base los borra en cascada) y sus archivos.
    Los puntos que ya se ganaron con ella se conservan en el historial."""
    yo = usuario_actual(authorization)
    with engine.begin() as conexion:
        _mi_publicacion(conexion, id_publicacion, yo)
        archivos = [r for (r,) in conexion.execute(
            text("SELECT imagen_ruta FROM publicaciones WHERE id_publicacion = :p UNION ALL "
                 "SELECT audio_ruta FROM publicaciones WHERE id_publicacion = :p UNION ALL "
                 "SELECT audio_ruta FROM comentarios WHERE id_publicacion = :p"),
            {"p": id_publicacion},
        ) if r]
        conexion.execute(text("DELETE FROM publicaciones WHERE id_publicacion = :p"), {"p": id_publicacion})
    for ruta in archivos:
        (MEDIA_DIR / ruta.removeprefix("/media/")).unlink(missing_ok=True)
    return {"ok": True}


# ---------------------------------------------------------------------------
# C3 - Respuestas
# ---------------------------------------------------------------------------
CONSULTA_RESPUESTAS = (
    "SELECT c.id_comentario, c.id_publicacion, c.texto, c.audio_ruta, c.creado_en, c.id_recomendacion, "
    "u.id_usuario, u.nombre AS autor_nombre, u.municipio AS autor_municipio, "
    "u.suscripcion_riego AS autor_riego, u.puntos AS autor_puntos, "
    "(SELECT COUNT(*) FROM votos_comentario v WHERE v.id_comentario = c.id_comentario) AS likes, "
    "(SELECT COUNT(*) FROM votos_comentario v2 JOIN publicaciones pp ON pp.id_publicacion = c.id_publicacion "
    " WHERE v2.id_comentario = c.id_comentario AND v2.id_usuario = pp.id_usuario) AS le_funciono, "
    "(SELECT COUNT(*) FROM votos_comentario v3 "
    " WHERE v3.id_comentario = c.id_comentario AND v3.id_usuario = :visitante) AS yo_like, "
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
        "autor": autor_publico(fila),
        "likes": fila["likes"],
        "le_funciono_al_autor": bool(fila["le_funciono"]),
        "yo_di_like": bool(fila["yo_like"]),
        "dato_riego": dato,
    }


@router.get("/publicaciones/{id_publicacion}")
def ver_publicacion(id_publicacion: int, authorization: str | None = Header(None)):
    """La publicacion con todas sus respuestas, de la mas antigua a la mas nueva. Sin sesion."""
    valores = {"id": id_publicacion, "visitante": id_visitante(authorization)}
    with engine.connect() as conexion:
        pub = conexion.execute(
            text(CONSULTA_PUBLICACIONES + " WHERE p.id_publicacion = :id"), valores
        ).mappings().first()
        if not pub:
            raise HTTPException(status_code=404, detail="La publicación no existe.")
        respuestas = conexion.execute(
            text(CONSULTA_RESPUESTAS + "WHERE c.id_publicacion = :id ORDER BY c.creado_en, c.id_comentario"),
            valores,
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
    if not yo["puede_responder"]:
        raise HTTPException(
            status_code=403,
            detail=f"Solo Especialista Agrónomo y Maestro de la Tierra pueden responder. "
                   f"Tu rango es {yo['rango']['nombre']}: sigue preguntando y capacitándote para subir.",
        )
    with engine.connect() as conexion:
        id_autor_pub = conexion.execute(
            text("SELECT id_usuario FROM publicaciones WHERE id_publicacion = :id"), {"id": id_publicacion}
        ).scalar()
        if id_autor_pub is None:
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
        # Dinamica 4: quien pregunto gana puntos cuando un rango alto le responde
        puntos_al_autor = 0
        if id_autor_pub != yo["id_usuario"]:
            puntos_al_autor = reglas.premiar_pregunta_respondida(conexion, id_publicacion, id_autor_pub)
        fila = conexion.execute(
            text(CONSULTA_RESPUESTAS + "WHERE c.id_publicacion = :p AND c.id_usuario = :u "
                 "ORDER BY c.id_comentario DESC"),
            {"p": id_publicacion, "u": yo["id_usuario"], "visitante": yo["id_usuario"]},
        ).mappings().first()
    return {**respuesta_publica(fila), "puntos_al_autor": puntos_al_autor}


@router.post("/respuestas/{id_respuesta}/like")
def like_respuesta(id_respuesta: int, authorization: str | None = Header(None)):
    """
    Pone o quita el like de una respuesta.
    Si quien da like es el autor de la publicacion, la respuesta queda como "Le funciono al autor"
    y quien respondio gana 10 puntos (una sola vez por publicacion).
    """
    yo = usuario_actual(authorization)
    with engine.begin() as conexion:
        resp = conexion.execute(
            text("SELECT c.id_usuario AS autor_respuesta, c.id_publicacion, p.id_usuario AS autor_publicacion "
                 "FROM comentarios c JOIN publicaciones p ON p.id_publicacion = c.id_publicacion "
                 "WHERE c.id_comentario = :c"),
            {"c": id_respuesta},
        ).mappings().first()
        if not resp:
            raise HTTPException(status_code=404, detail="La respuesta no existe.")
        if resp["autor_respuesta"] == yo["id_usuario"]:
            raise HTTPException(status_code=400, detail="No puedes dar like a tu propia respuesta.")
        valores = {"c": id_respuesta, "u": yo["id_usuario"]}
        ya = conexion.execute(
            text("SELECT COUNT(*) FROM votos_comentario WHERE id_comentario = :c AND id_usuario = :u"), valores
        ).scalar()
        puntos_dados = 0
        if ya:
            conexion.execute(text("DELETE FROM votos_comentario WHERE id_comentario = :c AND id_usuario = :u"),
                             valores)
        else:
            conexion.execute(text("INSERT INTO votos_comentario (id_comentario, id_usuario) VALUES (:c, :u)"),
                             valores)
            if yo["id_usuario"] == resp["autor_publicacion"]:
                puntos_dados = reglas.premiar_respuesta_util(conexion, resp["id_publicacion"],
                                                             resp["autor_respuesta"])
        likes = conexion.execute(
            text("SELECT COUNT(*) FROM votos_comentario WHERE id_comentario = :c"), valores
        ).scalar()
    return {"likes": likes, "yo_di_like": not ya, "puntos_a_quien_respondio": puntos_dados}