"""
Datos de referencia que viven en la base de datos de B.A.W.I.:

- Coeficiente de cultivo (Kc) por cultivo y etapa (tabla etapas_cultivo)
- Precio vigente de la energia de la Tarifa 9-CU de CFE (tabla tarifas_energia)
"""
from datetime import date

from sqlalchemy import text


def kc_de(conexion, cultivo: str, etapa: str) -> float:
    """Kc de la etapa del cultivo. Lanza ValueError si la combinacion no existe."""
    kc = conexion.execute(
        text("SELECT e.kc FROM etapas_cultivo e JOIN cultivos c ON c.id_cultivo = e.id_cultivo "
             "WHERE c.clave = :cultivo AND e.clave = :etapa"),
        {"cultivo": cultivo, "etapa": etapa},
    ).scalar()
    if kc is None:
        raise ValueError(f"No hay Kc registrado para el cultivo '{cultivo}' en la etapa '{etapa}'.")
    return float(kc)


def cultivos_y_etapas(conexion) -> list[dict]:
    """Cultivos con sus etapas en orden, para llenar los selectores de la app."""
    filas = conexion.execute(
        text("SELECT c.clave AS cultivo, c.nombre AS cultivo_nombre, e.clave AS etapa, e.nombre AS etapa_nombre, e.kc "
             "FROM cultivos c JOIN etapas_cultivo e ON e.id_cultivo = c.id_cultivo ORDER BY c.id_cultivo, e.orden")
    ).mappings().all()
    cultivos: dict[str, dict] = {}
    for f in filas:
        cultivo = cultivos.setdefault(f["cultivo"], {"clave": f["cultivo"], "nombre": f["cultivo_nombre"], "etapas": []})
        cultivo["etapas"].append({"clave": f["etapa"], "nombre": f["etapa_nombre"], "kc": float(f["kc"])})
    return list(cultivos.values())


def precio_kwh_vigente(conexion, tarifa: str = "9-CU") -> float:
    """Precio por kWh de la tarifa vigente hoy. Lanza ValueError si no hay tarifa registrada."""
    precio = conexion.execute(
        text("SELECT TOP 1 precio_kwh FROM tarifas_energia WHERE nombre = :t AND vigente_desde <= :hoy "
             "ORDER BY vigente_desde DESC"),
        {"t": tarifa, "hoy": date.today()},
    ).scalar()
    if precio is None:
        raise ValueError(f"No hay un precio vigente de la tarifa {tarifa} en la tabla tarifas_energia.")
    return float(precio)
