"""
Rutas de Capacitacion de B.A.W.I. Comunidad (documento "Dinamicas y sistema de puntos").

Dinamicas:
- Dinamica 1 "Conoce una palabra": la palabra del dia (la misma para todos). Al aprenderla: +5.
- Dinamica 3 "Verdadero o falso": cuestionario de 4 afirmaciones.

Reglas (Formulario diario):
- Acierto en el primer intento: 5 puntos.
- Tres aciertos seguidos en el primer intento: 5 puntos extra, maximo una vez por cuestionario.
- Respuesta incorrecta: pista breve y la racha vuelve a cero.
- Acierto despues de recibir ayuda: aprendizaje completado, sin puntos.
- Repetir un cuestionario o una palabra: se puede practicar, sin volver a ganar puntos.
- Maximo UNA dinamica con puntos al dia. Lo que se haga despues es practica (no se guarda).

Contenido: python -m backend.seed_capacitacion
"""
from datetime import date, datetime, time, timedelta

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy import text

from backend.db import engine
from backend.routers.comunidad import buscar_usuario, id_visitante, usuario_actual, usuario_publico
from backend.services import puntos as reglas

router = APIRouter(prefix="/api/capacitacion", tags=["Capacitacion"])

BONO_RACHA = 5
RACHA_PARA_BONO = 3
TIPOS = {"palabra": "Conoce una palabra", "verdadero_falso": "Verdadero o falso", "formulario": "Formulario"}


# ---------------------------------------------------------------------------
# Ayudantes
# ---------------------------------------------------------------------------
def _dinamica_de_hoy(conexion, id_usuario: int):
    """Intento con puntos que el usuario ya hizo hoy (o None)."""
    inicio = datetime.combine(date.today(), time.min)
    return conexion.execute(
        text("SELECT i.id_quiz, i.puntos_ganados, q.titulo, q.tema FROM intentos_quiz i "
             "JOIN quizzes q ON q.id_quiz = i.id_quiz "
             "WHERE i.id_usuario = :u AND i.realizado_en >= :inicio AND i.realizado_en < :fin "
             "ORDER BY i.id_intento"),
        {"u": id_usuario, "inicio": inicio, "fin": inicio + timedelta(days=1)},
    ).mappings().first()


def _ya_hizo(conexion, id_usuario: int, id_quiz: int) -> bool:
    return bool(conexion.execute(
        text("SELECT COUNT(*) FROM intentos_quiz WHERE id_usuario = :u AND id_quiz = :q"),
        {"u": id_usuario, "q": id_quiz},
    ).scalar())


def _quiz(conexion, id_quiz: int, tema: str):
    """Dinamica activa y aprobada (los formularios en revision no se muestran)."""
    fila = conexion.execute(
        text("SELECT id_quiz, titulo, tema, descripcion, ejemplo, puntos_por_acierto, codigo, contexto, "
             "id_rango_minimo FROM quizzes "
             "WHERE id_quiz = :q AND tema = :tema AND activo = 1 AND estado = 'aprobada'"),
        {"q": id_quiz, "tema": tema},
    ).mappings().first()
    if not fila:
        raise HTTPException(status_code=404, detail="Esa dinámica no existe.")
    return fila


def _palabra_del_dia(conexion):
    """La misma palabra para toda la comunidad; cambia cada dia."""
    palabras = conexion.execute(
        text("SELECT id_quiz, titulo, descripcion, ejemplo FROM quizzes "
             "WHERE tema = 'palabra' AND activo = 1 ORDER BY id_quiz")
    ).mappings().all()
    if not palabras:
        return None
    return palabras[date.today().toordinal() % len(palabras)]


def _siguiente_cuestionario(conexion, id_usuario: int):
    """El primer cuestionario que el usuario no ha hecho; si ya hizo todos, el primero (para practicar)."""
    cuestionarios = conexion.execute(
        text("SELECT id_quiz, titulo, descripcion FROM quizzes "
             "WHERE tema = 'verdadero_falso' AND activo = 1 ORDER BY id_quiz")
    ).mappings().all()
    if not cuestionarios:
        return None
    for quiz in cuestionarios:
        if not id_usuario or not _ya_hizo(conexion, id_usuario, quiz["id_quiz"]):
            return quiz
    return cuestionarios[0]


def _registrar_intento(conexion, id_usuario: int, id_quiz: int, aciertos: int, total: int, puntos: int) -> int:
    conexion.execute(
        text("INSERT INTO intentos_quiz (id_usuario, id_quiz, aciertos, total, puntos_ganados, realizado_en) "
             "VALUES (:u, :q, :a, :t, :p, :fecha)"),
        {"u": id_usuario, "q": id_quiz, "a": aciertos, "t": total, "p": puntos, "fecha": datetime.now().replace(microsecond=0)},
    )
    return conexion.execute(
        text("SELECT MAX(id_intento) FROM intentos_quiz WHERE id_usuario = :u AND id_quiz = :q"),
        {"u": id_usuario, "q": id_quiz},
    ).scalar()


def _sin_puntos(conexion, id_usuario: int, id_quiz: int) -> str | None:
    """Motivo por el que esta dinamica ya no da puntos (o None si si los da)."""
    hoy = _dinamica_de_hoy(conexion, id_usuario)
    if hoy:
        return (f"Ya hiciste tu dinámica de hoy ({TIPOS.get(hoy['tema'], '')}: {hoy['titulo']}). "
                f"Esto cuenta como práctica, sin puntos. ¡Vuelve mañana!")
    if _ya_hizo(conexion, id_usuario, id_quiz):
        return "Ya habías completado esta dinámica: puedes practicar, pero no vuelve a dar puntos."
    return None


def _resultado_rango(yo_antes: dict, id_usuario: int) -> dict:
    """Usuario actualizado y si subio de rango con los puntos ganados."""
    with engine.connect() as conexion:
        despues = usuario_publico(buscar_usuario(conexion, id_usuario=id_usuario))
    subio = despues["rango"]["id_rango"] > yo_antes["rango"]["id_rango"]
    return {"usuario": despues, "subio_de_rango": subio,
            "rango_nuevo": despues["rango"] if subio else None}


# ---------------------------------------------------------------------------
# Rutas
# ---------------------------------------------------------------------------
@router.get("/hoy")
def capacitacion_de_hoy(authorization: str | None = Header(None)):
    """Lo que el usuario puede hacer hoy. Sin sesion se puede ver y practicar, pero no gana puntos."""
    id_usuario = id_visitante(authorization)
    with engine.connect() as conexion:
        hoy = _dinamica_de_hoy(conexion, id_usuario) if id_usuario else None
        palabra = _palabra_del_dia(conexion)
        quiz = _siguiente_cuestionario(conexion, id_usuario)
        respuesta = {
            "con_sesion": bool(id_usuario),
            "hecha_hoy": bool(hoy),
            "dinamica_de_hoy": ({"tipo": TIPOS.get(hoy["tema"], hoy["tema"]), "titulo": hoy["titulo"],
                                 "puntos": hoy["puntos_ganados"]} if hoy else None),
            "palabra": None,
            "cuestionario": None,
        }
        if palabra:
            aprendida = bool(id_usuario) and _ya_hizo(conexion, id_usuario, palabra["id_quiz"])
            respuesta["palabra"] = {
                "id_quiz": palabra["id_quiz"], "palabra": palabra["titulo"],
                "explicacion": palabra["descripcion"], "ejemplo": palabra["ejemplo"],
                "ya_aprendida": aprendida,
                "con_puntos": bool(id_usuario) and not hoy and not aprendida,
            }
        if quiz:
            total = conexion.execute(text("SELECT COUNT(*) FROM preguntas WHERE id_quiz = :q"),
                                     {"q": quiz["id_quiz"]}).scalar()
            completado = bool(id_usuario) and _ya_hizo(conexion, id_usuario, quiz["id_quiz"])
            respuesta["cuestionario"] = {
                "id_quiz": quiz["id_quiz"], "titulo": quiz["titulo"], "descripcion": quiz["descripcion"],
                "total": total, "ya_completado": completado,
                "con_puntos": bool(id_usuario) and not hoy and not completado,
            }
    return respuesta


@router.post("/palabras/{id_quiz}/aprender")
def aprender_palabra(id_quiz: int, authorization: str | None = Header(None)):
    """Dinamica 1: marcar la palabra como aprendida. +5 si es la dinamica del dia."""
    yo = usuario_actual(authorization)
    with engine.begin() as conexion:
        palabra = _quiz(conexion, id_quiz, "palabra")
        motivo = _sin_puntos(conexion, yo["id_usuario"], id_quiz)
        if motivo:
            return {"puntos_ganados": 0, "mensaje": motivo, "subio_de_rango": False, "rango_nuevo": None}
        puntos = palabra["puntos_por_acierto"] or 5
        id_intento = _registrar_intento(conexion, yo["id_usuario"], id_quiz, 1, 1, puntos)
        reglas.otorgar_puntos(conexion, yo["id_usuario"], puntos, "quiz", id_intento)
    resultado = _resultado_rango(yo, yo["id_usuario"])
    return {"puntos_ganados": puntos,
            "mensaje": f"¡Aprendiste «{palabra['titulo']}»! Ganaste +{puntos} puntos.", **resultado}


@router.get("/cuestionarios/{id_quiz}")
def ver_cuestionario(id_quiz: int):
    """Afirmaciones con sus opciones (sin decir cual es la correcta)."""
    with engine.connect() as conexion:
        quiz = _quiz(conexion, id_quiz, "verdadero_falso")
        preguntas = conexion.execute(
            text("SELECT id_pregunta, enunciado FROM preguntas WHERE id_quiz = :q ORDER BY orden"),
            {"q": id_quiz},
        ).mappings().all()
        opciones = conexion.execute(
            text("SELECT o.id_opcion, o.id_pregunta, o.texto FROM opciones o "
                 "JOIN preguntas p ON p.id_pregunta = o.id_pregunta WHERE p.id_quiz = :q ORDER BY o.id_opcion"),
            {"q": id_quiz},
        ).mappings().all()
    return {
        "id_quiz": quiz["id_quiz"], "titulo": quiz["titulo"], "descripcion": quiz["descripcion"],
        "puntos_por_acierto": quiz["puntos_por_acierto"], "bono_racha": BONO_RACHA,
        "preguntas": [{"id_pregunta": p["id_pregunta"], "enunciado": p["enunciado"],
                       "opciones": [{"id_opcion": o["id_opcion"], "texto": o["texto"]}
                                    for o in opciones if o["id_pregunta"] == p["id_pregunta"]]}
                      for p in preguntas],
    }


class Revision(BaseModel):
    id_opcion: int


@router.post("/preguntas/{id_pregunta}/revisar")
def revisar_respuesta(id_pregunta: int, datos: Revision):
    """Dice si la opcion es correcta. Si lo es: explicacion. Si no: pista para volver a intentar."""
    with engine.connect() as conexion:
        fila = conexion.execute(
            text("SELECT o.es_correcta, p.explicacion, p.pista FROM opciones o "
                 "JOIN preguntas p ON p.id_pregunta = o.id_pregunta "
                 "WHERE o.id_opcion = :o AND p.id_pregunta = :p"),
            {"o": datos.id_opcion, "p": id_pregunta},
        ).mappings().first()
    if not fila:
        raise HTTPException(status_code=404, detail="Esa respuesta no corresponde a la pregunta.")
    correcta = bool(fila["es_correcta"])
    return {
        "correcta": correcta,
        "explicacion": fila["explicacion"] if correcta else None,
        "pista": None if correcta else (fila["pista"] or "Vuelve a leer la afirmación con calma."),
    }


class PrimerIntento(BaseModel):
    id_pregunta: int
    id_opcion: int


class Entrega(BaseModel):
    respuestas: list[PrimerIntento]


@router.post("/cuestionarios/{id_quiz}/terminar")
def terminar_cuestionario(id_quiz: int, datos: Entrega, authorization: str | None = Header(None)):
    return _calificar(id_quiz, "verdadero_falso", datos, authorization)


def _calificar(id_quiz: int, tema: str, datos: Entrega, authorization: str | None, por_nivel: bool = False):
    """Recibe la respuesta del PRIMER intento de cada pregunta y calcula los puntos.
    Los puntos se calculan aqui (no en la app) con la respuesta correcta guardada en la base.
    por_nivel=True (formularios): solo dan puntos los del rango actual del usuario."""
    yo = usuario_actual(authorization)
    primeras = {r.id_pregunta: r.id_opcion for r in datos.respuestas}
    with engine.begin() as conexion:
        quiz = _quiz(conexion, id_quiz, tema)
        correctas = conexion.execute(
            text("SELECT p.id_pregunta, o.id_opcion FROM preguntas p "
                 "JOIN opciones o ON o.id_pregunta = p.id_pregunta AND o.es_correcta = 1 "
                 "WHERE p.id_quiz = :q ORDER BY p.orden"),
            {"q": id_quiz},
        ).mappings().all()
        if not correctas or any(c["id_pregunta"] not in primeras for c in correctas):
            raise HTTPException(status_code=400, detail="Responde todas las afirmaciones para terminar.")

        # Aciertos al primer intento, racha y bono (una vez por cuestionario)
        aciertos, racha, bono = 0, 0, 0
        detalle = []
        for c in correctas:
            acerto = primeras[c["id_pregunta"]] == c["id_opcion"]
            detalle.append((c["id_pregunta"], primeras[c["id_pregunta"]], acerto))
            if acerto:
                aciertos += 1
                racha += 1
                if racha >= RACHA_PARA_BONO and not bono:
                    bono = BONO_RACHA
            else:
                racha = 0
        puntos_aciertos = aciertos * (quiz["puntos_por_acierto"] or 5)
        resumen = {"aciertos": aciertos, "total": len(correctas)}

        motivo = (_motivo_nivel(quiz, yo) if por_nivel else None) or _sin_puntos(conexion, yo["id_usuario"], id_quiz)
        if motivo:  # practica: no se guarda nada
            return {**resumen, "puntos_aciertos": 0, "bono_racha": 0, "puntos_ganados": 0,
                    "con_puntos": False, "mensaje": motivo, "subio_de_rango": False, "rango_nuevo": None}

        total_puntos = puntos_aciertos + bono
        id_intento = _registrar_intento(conexion, yo["id_usuario"], id_quiz, aciertos, len(correctas),
                                        total_puntos)
        for id_pregunta, id_opcion, acerto in detalle:
            conexion.execute(
                text("INSERT INTO respuestas_usuario (id_intento, id_pregunta, id_opcion, es_correcta) "
                     "VALUES (:i, :p, :o, :c)"),
                {"i": id_intento, "p": id_pregunta, "o": id_opcion, "c": 1 if acerto else 0},
            )
        if total_puntos:
            reglas.otorgar_puntos(conexion, yo["id_usuario"], total_puntos, "quiz", id_intento)

    resultado = _resultado_rango(yo, yo["id_usuario"])
    mensaje = (f"Terminaste «{quiz['titulo']}»: {aciertos} de {len(correctas)} al primer intento. "
               f"Ganaste +{total_puntos} puntos.")
    return {**resumen, "puntos_aciertos": puntos_aciertos, "bono_racha": bono, "puntos_ganados": total_puntos,
            "con_puntos": True, "mensaje": mensaje, **resultado}                     

# ---------------------------------------------------------------------------
# Formularios (documento "Formularios para B.A.W.I"): 10 por rango, 5 preguntas y 4 opciones.
# - Solo se muestran los formularios aprobados (python -m backend.seed_formularios --aprobar).
# - Dan puntos solo los de tu rango actual; los de rangos anteriores son practica; los de
#   rangos mas altos estan bloqueados. Cuentan como la dinamica del dia (maximo 30 puntos).
# ---------------------------------------------------------------------------
def _nivel_usuario(conexion, id_usuario: int) -> int:
    fila = buscar_usuario(conexion, id_usuario=id_usuario) if id_usuario else None
    return usuario_publico(fila)["rango"]["id_rango"] if fila else 1


def _motivo_nivel(quiz, yo: dict) -> str | None:
    nivel = yo["rango"]["id_rango"]
    if quiz["id_rango_minimo"] > nivel:
        raise HTTPException(status_code=403, detail="Este formulario se desbloquea al subir de rango.")
    if quiz["id_rango_minimo"] < nivel:
        return "Este formulario es de un rango anterior: cuenta como práctica, sin puntos."
    return None


@router.get("/formularios")
def listar_formularios(authorization: str | None = Header(None)):
    id_usuario = id_visitante(authorization)
    with engine.connect() as conexion:
        nivel = _nivel_usuario(conexion, id_usuario)
        hoy = _dinamica_de_hoy(conexion, id_usuario) if id_usuario else None
        filas = conexion.execute(
            text("SELECT q.id_quiz, q.codigo, q.titulo, q.id_rango_minimo AS nivel, "
                 "(SELECT COUNT(*) FROM intentos_quiz i WHERE i.id_quiz = q.id_quiz AND i.id_usuario = :u) AS hechos "
                 "FROM quizzes q WHERE q.tema = 'formulario' AND q.activo = 1 AND q.estado = 'aprobada' "
                 "ORDER BY q.codigo"),
            {"u": id_usuario},
        ).mappings().all()
        en_revision = conexion.execute(
            text("SELECT COUNT(*) FROM quizzes WHERE tema = 'formulario' AND estado <> 'aprobada'")
        ).scalar()
    return {
        "nivel_usuario": nivel,
        "con_sesion": bool(id_usuario),
        "en_revision": en_revision,
        "formularios": [{
            "id_quiz": f["id_quiz"], "codigo": f["codigo"], "titulo": f["titulo"], "nivel": f["nivel"],
            "completado": f["hechos"] > 0, "bloqueado": f["nivel"] > nivel,
            "con_puntos": bool(id_usuario) and not hoy and not f["hechos"] and f["nivel"] == nivel,
        } for f in filas],
    }


@router.get("/formularios/{id_quiz}")
def ver_formulario(id_quiz: int, authorization: str | None = Header(None)):
    """Caso (si lo tiene), preguntas y opciones, sin decir cual es la correcta."""
    with engine.connect() as conexion:
        quiz = _quiz(conexion, id_quiz, "formulario")
        if quiz["id_rango_minimo"] > _nivel_usuario(conexion, id_visitante(authorization)):
            raise HTTPException(status_code=403, detail="Este formulario se desbloquea al subir de rango.")
        preguntas = conexion.execute(
            text("SELECT id_pregunta, enunciado, fuentes FROM preguntas WHERE id_quiz = :q ORDER BY orden"),
            {"q": id_quiz},
        ).mappings().all()
        opciones = conexion.execute(
            text("SELECT o.id_opcion, o.id_pregunta, o.texto FROM opciones o "
                 "JOIN preguntas p ON p.id_pregunta = o.id_pregunta WHERE p.id_quiz = :q ORDER BY o.id_opcion"),
            {"q": id_quiz},
        ).mappings().all()
    return {
        "id_quiz": quiz["id_quiz"], "codigo": quiz["codigo"], "titulo": quiz["titulo"],
        "nivel": quiz["id_rango_minimo"], "contexto": quiz["contexto"],
        "puntos_por_acierto": quiz["puntos_por_acierto"], "bono_racha": BONO_RACHA,
        "preguntas": [{"id_pregunta": p["id_pregunta"], "enunciado": p["enunciado"], "fuentes": p["fuentes"],
                       "opciones": [{"id_opcion": o["id_opcion"], "texto": o["texto"]}
                                    for o in opciones if o["id_pregunta"] == p["id_pregunta"]]}
                      for p in preguntas],
    }


@router.post("/formularios/{id_quiz}/terminar")
def terminar_formulario(id_quiz: int, datos: Entrega, authorization: str | None = Header(None)):
    return _calificar(id_quiz, "formulario", datos, authorization, por_nivel=True)