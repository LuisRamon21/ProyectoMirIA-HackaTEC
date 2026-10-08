"""
Rangos y puntos de B.A.W.I. Comunidad (documento "Dinamicas y sistema de puntos").

Rangos (mismos valores que la tabla `rangos` de la base de datos):
    Aprendiz del Campo 0-249 · Tecnico de Riego 250-599 ·
    Especialista Agronomo 600-1199 · Maestro de la Tierra 1200+
Quien contrata B.A.W.I. Riego es Maestro de la Tierra por defecto.

Reglas de la Dinamica 4 (dudas en el foro):
- Solo Especialista Agronomo y Maestro de la Tierra pueden responder.
- Quien pregunta gana 5 puntos por publicacion cuando le responde un rango alto
  (una vez por publicacion, maximo 20 puntos en total por esta via).
- Si el autor marca una respuesta como "Le funciono", quien respondio gana 10 puntos
  (una sola recompensa por publicacion; quitar y volver a poner el like no da mas).
"""
from sqlalchemy import text

RANGOS = [
    # id, nombre, insignia, puntos minimos
    (1, "Aprendiz del Campo", "🌱", 0),
    (2, "Técnico de Riego", "💧", 250),
    (3, "Especialista Agrónomo", "🌾", 600),
    (4, "Maestro de la Tierra", "👑", 1200),
]
RANGO_MINIMO_PARA_RESPONDER = 3

PUNTOS_POR_RESPUESTA_EXPERTA = 5
TOPE_PUNTOS_POR_PREGUNTAR = 20
PUNTOS_POR_RESPUESTA_UTIL = 10


def calcular_rango(puntos: int, usa_riego: bool) -> dict:
    """Rango actual, y cuanto falta para el siguiente."""
    if usa_riego:
        actual = RANGOS[-1]
    else:
        actual = [r for r in RANGOS if puntos >= r[3]][-1]
    siguiente = next((r for r in RANGOS if r[0] == actual[0] + 1), None)
    return {
        "id_rango": actual[0],
        "nombre": actual[1],
        "insignia": actual[2],
        "siguiente": siguiente[1] if siguiente else None,
        "puntos_siguiente": siguiente[3] if siguiente else None,
        "faltan": max(siguiente[3] - puntos, 0) if siguiente else None,
    }


def puede_responder(rango: dict) -> bool:
    return rango["id_rango"] >= RANGO_MINIMO_PARA_RESPONDER


def lista_rangos() -> list[dict]:
    resultado = []
    for i, (id_rango, nombre, insignia, minimo) in enumerate(RANGOS):
        maximo = RANGOS[i + 1][3] - 1 if i + 1 < len(RANGOS) else None
        resultado.append({"id_rango": id_rango, "nombre": nombre, "insignia": insignia,
                          "puntos_min": minimo, "puntos_max": maximo,
                          "puede_responder": id_rango >= RANGO_MINIMO_PARA_RESPONDER})
    return resultado


def otorgar_puntos(conexion, id_usuario: int, puntos: int, motivo: str, id_referencia: int | None) -> None:
    """Suma puntos al usuario y deja el movimiento registrado (historial)."""
    conexion.execute(text("UPDATE usuarios SET puntos = puntos + :p WHERE id_usuario = :u"),
                     {"p": puntos, "u": id_usuario})
    conexion.execute(
        text("INSERT INTO movimientos_puntos (id_usuario, puntos, motivo, id_referencia) "
             "VALUES (:u, :p, :motivo, :ref)"),
        {"u": id_usuario, "p": puntos, "motivo": motivo, "ref": id_referencia},
    )


def premiar_pregunta_respondida(conexion, id_publicacion: int, id_autor: int) -> int:
    """+5 a quien pregunto cuando un rango alto le responde. Regresa los puntos dados (0 si no aplica)."""
    ya_premiada = conexion.execute(
        text("SELECT COUNT(*) FROM movimientos_puntos WHERE id_usuario = :u "
             "AND motivo = 'publicacion' AND id_referencia = :pub"),
        {"u": id_autor, "pub": id_publicacion},
    ).scalar()
    if ya_premiada:
        return 0
    acumulado = conexion.execute(
        text("SELECT COALESCE(SUM(puntos), 0) FROM movimientos_puntos "
             "WHERE id_usuario = :u AND motivo = 'publicacion'"),
        {"u": id_autor},
    ).scalar()
    puntos = min(PUNTOS_POR_RESPUESTA_EXPERTA, TOPE_PUNTOS_POR_PREGUNTAR - int(acumulado))
    if puntos <= 0:
        return 0
    otorgar_puntos(conexion, id_autor, puntos, "publicacion", id_publicacion)
    return puntos


def premiar_respuesta_util(conexion, id_publicacion: int, id_autor_respuesta: int) -> int:
    """+10 a la primera respuesta que le funciono al autor de la publicacion."""
    ya_premiada = conexion.execute(
        text("SELECT COUNT(*) FROM movimientos_puntos "
             "WHERE motivo = 'comentario_util' AND id_referencia = :pub"),
        {"pub": id_publicacion},
    ).scalar()
    if ya_premiada:
        return 0
    otorgar_puntos(conexion, id_autor_respuesta, PUNTOS_POR_RESPUESTA_UTIL, "comentario_util", id_publicacion)
    return PUNTOS_POR_RESPUESTA_UTIL