"""
Registra la parcela de un productor para B.A.W.I. Riego.

El productor debe tener cuenta en Comunidad (se busca por correo o por usuario).
Al registrar la parcela su cuenta queda como usuaria de B.A.W.I. Riego.

Ejecutar desde la raiz del proyecto, por ejemplo:
    python -m backend.registrar_parcela --usuario productor@correo.com --nombre "Huerta El Nogalito" ^
        --municipio Delicias --cultivo nogal --etapa media --area 10 --sistema goteo ^
        --tasa 3 --bomba-kw 45 --horas-habituales 4

Opcional: --latitud y --longitud de la parcela (si no, se usa la cabecera del municipio).
Al terminar muestra el id de la parcela: ponlo en .env como RIEGO_ID_PARCELA.
"""
import argparse

from sqlalchemy import text

from backend.db import engine
from backend.services.clima import MUNICIPIOS, normalizar_municipio


def _argumentos() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Registra la parcela de un productor para B.A.W.I. Riego.")
    p.add_argument("--usuario", required=True, help="correo o nombre de usuario del productor")
    p.add_argument("--nombre", required=True, help="nombre de la parcela")
    p.add_argument("--municipio", required=True, help=f"uno de: {', '.join(MUNICIPIOS)}")
    p.add_argument("--cultivo", required=True, help="clave del cultivo (tabla cultivos), ej. nogal")
    p.add_argument("--etapa", required=True, help="clave de la etapa (tabla etapas_cultivo), ej. media")
    p.add_argument("--area", type=float, required=True, help="hectareas")
    p.add_argument("--sistema", choices=["goteo", "microaspersion"], required=True)
    p.add_argument("--tasa", type=float, required=True, help="mm por hora que aplica el sistema")
    p.add_argument("--bomba-kw", type=float, required=True, help="potencia de la bomba en kW")
    p.add_argument("--horas-habituales", type=float, required=True, help="horas que riega normalmente al dia")
    p.add_argument("--latitud", type=float)
    p.add_argument("--longitud", type=float)
    return p.parse_args()


def registrar(a: argparse.Namespace) -> int:
    municipio = normalizar_municipio(a.municipio)
    if municipio not in MUNICIPIOS and (a.latitud is None or a.longitud is None):
        raise SystemExit(f"El municipio '{a.municipio}' no tiene coordenadas; indica --latitud y --longitud.")
    with engine.begin() as conexion:
        id_usuario = conexion.execute(
            text("SELECT id_usuario FROM usuarios WHERE correo = :u OR usuario = :u"), {"u": a.usuario.strip().lower()}
        ).scalar()
        if id_usuario is None:
            raise SystemExit(f"No existe una cuenta con el correo o usuario '{a.usuario}'. Crea la cuenta en Comunidad.")
        ids = conexion.execute(
            text("SELECT c.id_cultivo, e.id_etapa FROM cultivos c JOIN etapas_cultivo e ON e.id_cultivo = c.id_cultivo "
                 "WHERE c.clave = :cultivo AND e.clave = :etapa"),
            {"cultivo": a.cultivo, "etapa": a.etapa},
        ).first()
        if ids is None:
            raise SystemExit(f"No existe el cultivo '{a.cultivo}' con la etapa '{a.etapa}' en la base de datos.")
        conexion.execute(
            text("INSERT INTO parcelas (id_usuario, id_cultivo, id_etapa, nombre, municipio, latitud, longitud, "
                 "area_ha, sistema, tasa_mm_h, potencia_bomba_kw, horas_riego_habitual) "
                 "VALUES (:u, :c, :e, :nombre, :municipio, :lat, :lon, :area, :sistema, :tasa, :kw, :horas)"),
            {"u": id_usuario, "c": ids.id_cultivo, "e": ids.id_etapa, "nombre": a.nombre.strip(),
             "municipio": municipio, "lat": a.latitud, "lon": a.longitud, "area": a.area, "sistema": a.sistema,
             "tasa": a.tasa, "kw": a.bomba_kw, "horas": a.horas_habituales},
        )
        conexion.execute(text("UPDATE usuarios SET suscripcion_riego = 1 WHERE id_usuario = :u"), {"u": id_usuario})
        return conexion.execute(
            text("SELECT MAX(id_parcela) FROM parcelas WHERE id_usuario = :u"), {"u": id_usuario}
        ).scalar()


if __name__ == "__main__":
    id_parcela = registrar(_argumentos())
    print(f"Parcela registrada con id {id_parcela}. Pon en .env:  RIEGO_ID_PARCELA={id_parcela}")
