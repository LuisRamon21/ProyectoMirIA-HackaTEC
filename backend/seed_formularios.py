"""
Carga los Formularios de Capacitacion (documento "Formularios para B.A.W.I") desde
database/formularios.json: 40 formularios (10 por rango), 5 preguntas y 4 opciones cada uno.

Se guardan como quizzes con tema 'formulario':
    codigo (N1-F01), titulo, contexto (el caso simulado), id_rango_minimo (1 a 4) y estado.
Cada pregunta guarda su explicacion (tambien se usa como ayuda tras un error) y sus fuentes.

Todos entran como 'pendiente' (en revision) y NO se muestran en la app hasta aprobarlos.

Requiere database/migracion_d4_cuentas_formularios.sql. No duplica: se puede correr varias veces.
Ejecutar desde la raiz del proyecto:
    python -m backend.seed_formularios                        carga los formularios (en revision)
    python -m backend.seed_formularios --aprobar              aprueba TODOS (ya revisados)
    python -m backend.seed_formularios --aprobar N1-F01 N2-F03   aprueba solo esos
"""
import json
import sys
from pathlib import Path

from sqlalchemy import text

from backend.db import engine

ARCHIVO = Path(__file__).resolve().parent.parent / "database" / "formularios.json"
PUNTOS_POR_ACIERTO = 5


def _id_formulario(conexion, codigo: str):
    return conexion.execute(text("SELECT id_quiz FROM quizzes WHERE tema = 'formulario' AND codigo = :c"),
                            {"c": codigo}).scalar()


def cargar(conexion) -> int:
    nuevos = 0
    for f in json.loads(ARCHIVO.read_text(encoding="utf-8"))["formularios"]:
        if _id_formulario(conexion, f["codigo"]):
            continue
        conexion.execute(
            text("INSERT INTO quizzes (titulo, tema, descripcion, id_rango_minimo, puntos_por_acierto, activo, "
                 "codigo, contexto, estado) VALUES (:t, 'formulario', :d, :n, :p, 1, :c, :ctx, :e)"),
            {"t": f["titulo"], "d": f"{f['codigo']} · {f['rango']}", "n": f["nivel"], "p": PUNTOS_POR_ACIERTO,
             "c": f["codigo"], "ctx": f["contexto"] or None, "e": f["estado"]},
        )
        id_quiz = _id_formulario(conexion, f["codigo"])
        for orden, p in enumerate(f["preguntas"], start=1):
            conexion.execute(
                text("INSERT INTO preguntas (id_quiz, enunciado, explicacion, pista, fuentes, orden) "
                     "VALUES (:q, :e, :x, :x, :f, :o)"),
                {"q": id_quiz, "e": p["enunciado"], "x": p["explicacion"], "f": p["fuentes"], "o": orden},
            )
            id_pregunta = conexion.execute(
                text("SELECT id_pregunta FROM preguntas WHERE id_quiz = :q AND orden = :o"),
                {"q": id_quiz, "o": orden},
            ).scalar()
            for i, opcion in enumerate(p["opciones"]):
                conexion.execute(
                    text("INSERT INTO opciones (id_pregunta, texto, es_correcta) VALUES (:p, :t, :c)"),
                    {"p": id_pregunta, "t": opcion, "c": 1 if i == p["correcta"] else 0},
                )
        nuevos += 1
    return nuevos


def aprobar(conexion, codigos: list[str]) -> int:
    if codigos:
        total = 0
        for codigo in codigos:
            total += conexion.execute(
                text("UPDATE quizzes SET estado = 'aprobada' WHERE tema = 'formulario' AND codigo = :c"),
                {"c": codigo.upper()},
            ).rowcount
        return total
    return conexion.execute(text("UPDATE quizzes SET estado = 'aprobada' WHERE tema = 'formulario'")).rowcount


if __name__ == "__main__":
    with engine.begin() as conexion:
        if "--aprobar" in sys.argv:
            codigos = sys.argv[sys.argv.index("--aprobar") + 1:]
            print(f"Formularios aprobados: {aprobar(conexion, codigos)}")
        else:
            print(f"Formularios nuevos: {cargar(conexion)}")
        filas = conexion.execute(
            text("SELECT estado, COUNT(*) FROM quizzes WHERE tema = 'formulario' GROUP BY estado")
        ).all()
    for estado, cantidad in filas:
        print(f"  {estado}: {cantidad}")