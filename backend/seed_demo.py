"""
Carga los datos de demostracion en la base de B.A.W.I.

- Un productor de B.A.W.I. Riego con su parcela (el que se presenta en la laptop)
- Dos usuarios de Comunidad que ya tienen cuenta

Si un usuario ya existe, no lo duplica, asi que se puede correr varias veces.

Ejecutar desde la raiz del proyecto:
    python -m backend.seed_demo
"""
from sqlalchemy import text

from backend.db import engine
from backend.services.cuentas import hashear_password

PASSWORD_DEMO = "bawi2026"

# usuario, nombre, municipio, rol, suscripcion_riego, comparte_datos, puntos
# Rangos: don_ramiro Maestro (usa Riego) · tecnico_beto Especialista (650) · sofia_campo Aprendiz (130)
USUARIOS = [
    ("don_ramiro", "Ramiro Chávez", "Delicias", "productor", 1, 1, 0),
    ("tecnico_beto", "Alberto Meza", "Camargo", "tecnico", 0, 0, 650),
    ("sofia_campo", "Sofía Licón", "Delicias", "productor", 0, 0, 130),
]

# Parcela del productor de Riego (mismos datos por defecto que la app de Riego)
PARCELA = {
    "usuario": "don_ramiro",
    "cultivo": "nogal",
    "etapa": "media",
    "nombre": "Huerta El Nogalito",
    "municipio": "Delicias",
    "area_ha": 10,
    "sistema": "goteo",
    "tasa_mm_h": 3.0,
    "potencia_bomba_kw": 45,
    "horas_riego_habitual": 4,
}


def id_de_usuario(conexion, usuario: str):
    return conexion.execute(
        text("SELECT id_usuario FROM usuarios WHERE usuario = :u"), {"u": usuario}
    ).scalar()


def cargar() -> None:
    with engine.begin() as conexion:  # begin() hace commit al final, o deshace todo si algo falla
        for usuario, nombre, municipio, rol, riego, comparte, puntos in USUARIOS:
            if id_de_usuario(conexion, usuario):
                print(f"  ya existe: {usuario}")
                continue
            conexion.execute(
                text(
                    "INSERT INTO usuarios (nombre, usuario, password_hash, municipio, rol, "
                    "suscripcion_riego, comparte_datos, puntos) "
                    "VALUES (:nombre, :usuario, :hash, :municipio, :rol, :riego, :comparte, :puntos)"
                ),
                {"nombre": nombre, "usuario": usuario, "hash": hashear_password(PASSWORD_DEMO),
                 "municipio": municipio, "rol": rol, "riego": riego, "comparte": comparte, "puntos": puntos},
            )
            print(f"  usuario creado: {usuario}")

        id_dueno = id_de_usuario(conexion, PARCELA["usuario"])
        ya_tiene = conexion.execute(
            text("SELECT COUNT(*) FROM parcelas WHERE id_usuario = :id AND nombre = :n"),
            {"id": id_dueno, "n": PARCELA["nombre"]},
        ).scalar()
        if ya_tiene:
            print(f"  ya existe la parcela: {PARCELA['nombre']}")
        else:
            ids = conexion.execute(
                text(
                    "SELECT c.id_cultivo, e.id_etapa FROM cultivos c "
                    "JOIN etapas_cultivo e ON e.id_cultivo = c.id_cultivo "
                    "WHERE c.clave = :cultivo AND e.clave = :etapa"
                ),
                {"cultivo": PARCELA["cultivo"], "etapa": PARCELA["etapa"]},
            ).one()
            conexion.execute(
                text(
                    "INSERT INTO parcelas (id_usuario, id_cultivo, id_etapa, nombre, municipio, area_ha, "
                    "sistema, tasa_mm_h, potencia_bomba_kw, horas_riego_habitual) "
                    "VALUES (:u, :c, :e, :nombre, :municipio, :area, :sistema, :tasa, :kw, :horas)"
                ),
                {"u": id_dueno, "c": ids.id_cultivo, "e": ids.id_etapa, "nombre": PARCELA["nombre"],
                 "municipio": PARCELA["municipio"], "area": PARCELA["area_ha"], "sistema": PARCELA["sistema"],
                 "tasa": PARCELA["tasa_mm_h"], "kw": PARCELA["potencia_bomba_kw"],
                 "horas": PARCELA["horas_riego_habitual"]},
            )
            print(f"  parcela creada: {PARCELA['nombre']} ({PARCELA['cultivo']}, {PARCELA['area_ha']} ha)")

    print(f"\nListo. Contraseña de los usuarios de demo: {PASSWORD_DEMO}")


if __name__ == "__main__":
    cargar()