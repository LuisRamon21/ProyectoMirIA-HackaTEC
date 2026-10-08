"""
Guarda en la base de datos lo que pasa en B.A.W.I. Riego:

- las parcelas de cada productor (alta y cambios de sus datos)
- la recomendacion del dia de cada parcela (con el clima con que se calculo)
- la decision del productor: aceptada, ajustada o rechazada, y su ahorro

Hay una sola recomendacion por parcela por dia: si se vuelve a calcular,
se actualiza la del dia y regresa a "pendiente".
"""
from datetime import date, datetime

from sqlalchemy import text

from backend.services.ahorro import calcular_ahorro
from backend.services.catalogo import precio_kwh_vigente

DECISIONES = {"aceptada", "ajustada", "rechazada"}
CAMPOS_NUMERICOS = ("latitud", "longitud", "area_ha", "tasa_mm_h", "potencia_bomba_kw", "horas_riego_habitual")

CONSULTA_PARCELAS = (
    "SELECT p.id_parcela, p.id_usuario, p.nombre, p.municipio, p.latitud, p.longitud, p.area_ha, p.sistema, "
    "p.tasa_mm_h, p.potencia_bomba_kw, p.horas_riego_habitual, c.clave AS cultivo, e.clave AS etapa, "
    "u.usuario, u.nombre AS productor "
    "FROM parcelas p "
    "JOIN cultivos c ON c.id_cultivo = p.id_cultivo "
    "JOIN etapas_cultivo e ON e.id_etapa = p.id_etapa "
    "JOIN usuarios u ON u.id_usuario = p.id_usuario "
)


def _parcela(fila) -> dict:
    parcela = dict(fila)
    for campo in CAMPOS_NUMERICOS:
        if parcela[campo] is not None:
            parcela[campo] = float(parcela[campo])  # SQL Server regresa Decimal
    return parcela


def obtener_parcela(conexion, id_parcela: int) -> dict | None:
    """Datos de la parcela con las claves de cultivo y etapa que usa el orquestador."""
    fila = conexion.execute(
        text(CONSULTA_PARCELAS + "WHERE p.id_parcela = :id"), {"id": id_parcela}
    ).mappings().first()
    return _parcela(fila) if fila else None


def parcelas_de_usuario(conexion, id_usuario: int) -> list[dict]:
    filas = conexion.execute(
        text(CONSULTA_PARCELAS + "WHERE p.id_usuario = :u ORDER BY p.id_parcela"), {"u": id_usuario}
    ).mappings().all()
    return [_parcela(f) for f in filas]


def _ids_cultivo_etapa(conexion, cultivo: str, etapa: str):
    ids = conexion.execute(
        text("SELECT c.id_cultivo, e.id_etapa FROM cultivos c JOIN etapas_cultivo e ON e.id_cultivo = c.id_cultivo "
             "WHERE c.clave = :cultivo AND e.clave = :etapa"),
        {"cultivo": cultivo, "etapa": etapa},
    ).first()
    if ids is None:
        raise ValueError(f"No existe el cultivo '{cultivo}' con la etapa '{etapa}'.")
    return ids


def _valores_parcela(conexion, datos: dict) -> dict:
    ids = _ids_cultivo_etapa(conexion, datos["cultivo"], datos["etapa"])
    return {
        "c": ids.id_cultivo, "e": ids.id_etapa, "nombre": datos["nombre"], "municipio": datos["municipio"],
        "lat": datos.get("latitud"), "lon": datos.get("longitud"), "area": datos["area_ha"],
        "sistema": datos["sistema"], "tasa": datos["tasa_mm_h"], "kw": datos["potencia_bomba_kw"],
        "horas": datos["horas_riego_habitual"],
    }


def crear_parcela(conexion, id_usuario: int, datos: dict) -> dict:
    valores = {**_valores_parcela(conexion, datos), "u": id_usuario}
    conexion.execute(
        text("INSERT INTO parcelas (id_usuario, id_cultivo, id_etapa, nombre, municipio, latitud, longitud, area_ha, "
             "sistema, tasa_mm_h, potencia_bomba_kw, horas_riego_habitual) "
             "VALUES (:u, :c, :e, :nombre, :municipio, :lat, :lon, :area, :sistema, :tasa, :kw, :horas)"),
        valores,
    )
    id_parcela = conexion.execute(
        text("SELECT MAX(id_parcela) FROM parcelas WHERE id_usuario = :u"), {"u": id_usuario}
    ).scalar()
    return obtener_parcela(conexion, id_parcela)


def actualizar_parcela(conexion, id_parcela: int, datos: dict) -> dict:
    valores = {**_valores_parcela(conexion, datos), "id": id_parcela}
    conexion.execute(
        text("UPDATE parcelas SET id_cultivo = :c, id_etapa = :e, nombre = :nombre, municipio = :municipio, "
             "latitud = :lat, longitud = :lon, area_ha = :area, sistema = :sistema, tasa_mm_h = :tasa, "
             "potencia_bomba_kw = :kw, horas_riego_habitual = :horas WHERE id_parcela = :id"),
        valores,
    )
    return obtener_parcela(conexion, id_parcela)


def parcela_de_recomendacion(conexion, id_recomendacion: int) -> int | None:
    return conexion.execute(
        text("SELECT id_parcela FROM recomendaciones_riego WHERE id_recomendacion = :id"), {"id": id_recomendacion}
    ).scalar()


def _guardar_clima(conexion, municipio: str, hoy: date, reporte: dict, et0: float) -> int:
    clima, dia, pron = reporte["clima_actual"], reporte["clima_dia"], reporte["pronostico_24h"]
    valores = {
        "municipio": municipio, "fecha": hoy, "temp": clima["temperatura_c"], "tmax": pron["temp_max_c"],
        "tmin": dia["temp_min_c"], "hum": clima["humedad_pct"], "viento": clima["viento_ms"],
        "rad": dia["radiacion_mj_m2"], "prob": pron["prob_lluvia_pct"], "lluvia": pron["lluvia_mm"], "et0": et0,
        "fuente": reporte["metadata_app"]["fuente_clima"],
    }
    id_clima = conexion.execute(
        text("SELECT id_clima FROM clima_diario WHERE municipio = :municipio AND fecha = :fecha"), valores
    ).scalar()
    if id_clima:
        conexion.execute(
            text(
                "UPDATE clima_diario SET temperatura_c = :temp, temp_max_c = :tmax, temp_min_c = :tmin, "
                "humedad_rel_pct = :hum, viento_ms = :viento, radiacion_mj_m2 = :rad, prob_lluvia_pct = :prob, "
                "lluvia_mm = :lluvia, et0_mm = :et0, fuente = :fuente, consultado_en = GETDATE() WHERE id_clima = :id"
            ),
            {**valores, "id": id_clima},
        )
        return id_clima
    conexion.execute(
        text(
            "INSERT INTO clima_diario (municipio, fecha, temperatura_c, temp_max_c, temp_min_c, humedad_rel_pct, "
            "viento_ms, radiacion_mj_m2, prob_lluvia_pct, lluvia_mm, et0_mm, fuente) "
            "VALUES (:municipio, :fecha, :temp, :tmax, :tmin, :hum, :viento, :rad, :prob, :lluvia, :et0, :fuente)"
        ),
        valores,
    )
    return conexion.execute(
        text("SELECT id_clima FROM clima_diario WHERE municipio = :municipio AND fecha = :fecha"), valores
    ).scalar()


def _explicacion(reporte: dict) -> str:
    calc, pron, riego = reporte["calculos"], reporte["pronostico_24h"], reporte["riego"]
    return (
        f"ET0 {calc['et0_mm']} mm x Kc {calc['kc_aplicado']} = ETc {calc['etc_mm']} mm. "
        f"Probabilidad de lluvia {pron['prob_lluvia_pct']}%: reponer {riego['factor_reposicion_pct']}% "
        f"= {riego['lamina_mm']} mm = {riego['horas']} h de riego."
    )


def guardar_recomendacion(conexion, id_parcela: int, reporte: dict) -> int:
    """Guarda (o actualiza) la recomendacion de hoy y regresa su id."""
    hoy = date.fromisoformat(reporte["clima_dia"]["fecha"])  # fecha local de la parcela
    municipio = reporte["metadata_app"]["municipio"]
    calc, riego = reporte["calculos"], reporte["riego"]
    id_clima = _guardar_clima(conexion, municipio, hoy, reporte, calc["et0_mm"])
    valores = {
        "parcela": id_parcela, "clima": id_clima, "fecha": hoy, "et0": calc["et0_mm"],
        "kc": calc["kc_aplicado"], "etc": calc["etc_mm"], "riesgo": reporte["diagnostico_ia"]["etiqueta"],
        "factor": riego["factor_reposicion_pct"], "lamina": riego["lamina_mm"], "horas": riego["horas"],
        "explicacion": _explicacion(reporte),
    }
    id_rec = conexion.execute(
        text("SELECT id_recomendacion FROM recomendaciones_riego WHERE id_parcela = :parcela AND fecha = :fecha"),
        valores,
    ).scalar()
    if id_rec:
        conexion.execute(
            text(
                "UPDATE recomendaciones_riego SET id_clima = :clima, et0_mm = :et0, kc = :kc, etc_mm = :etc, "
                "riesgo = :riesgo, factor_reposicion_pct = :factor, lamina_neta_mm = :lamina, "
                "horas_sugeridas = :horas, explicacion = :explicacion, estado = 'pendiente', "
                "horas_aplicadas = NULL, motivo = NULL, agua_ahorrada_m3 = NULL, kwh_ahorrados = NULL, "
                "ahorro_mxn = NULL, decidida_en = NULL WHERE id_recomendacion = :id"
            ),
            {**valores, "id": id_rec},
        )
        return id_rec
    conexion.execute(
        text(
            "INSERT INTO recomendaciones_riego (id_parcela, id_clima, fecha, et0_mm, kc, etc_mm, riesgo, "
            "factor_reposicion_pct, lamina_neta_mm, horas_sugeridas, explicacion) "
            "VALUES (:parcela, :clima, :fecha, :et0, :kc, :etc, :riesgo, :factor, :lamina, :horas, :explicacion)"
        ),
        valores,
    )
    return conexion.execute(
        text("SELECT id_recomendacion FROM recomendaciones_riego WHERE id_parcela = :parcela AND fecha = :fecha"),
        valores,
    ).scalar()


def registrar_decision(conexion, id_recomendacion: int, decision: str, horas_aplicadas: float, motivo: str = "") -> dict:
    """Guarda la decision del productor y, si riega, el ahorro contra su riego habitual."""
    if decision not in DECISIONES:
        raise ValueError(f"Decision no valida: {decision}. Usa {sorted(DECISIONES)}")
    rec = conexion.execute(
        text("SELECT id_parcela FROM recomendaciones_riego WHERE id_recomendacion = :id"),
        {"id": id_recomendacion},
    ).scalar()
    if rec is None:
        raise ValueError(f"No existe la recomendacion {id_recomendacion}")
    parcela = obtener_parcela(conexion, rec)

    if decision == "rechazada":
        horas_aplicadas = 0.0
        ahorro = {"agua_m3": None, "energia_kwh": None, "dinero_mxn": None}  # no regar hoy no es un ahorro atribuible
    else:
        ahorro = calcular_ahorro(
            horas_recomendadas=horas_aplicadas,
            horas_habituales=parcela["horas_riego_habitual"],
            tasa_mm_h=parcela["tasa_mm_h"],
            superficie_ha=parcela["area_ha"],
            potencia_bomba_kw=parcela["potencia_bomba_kw"],
            precio_kwh=precio_kwh_vigente(conexion),
        )
    conexion.execute(
        text(
            "UPDATE recomendaciones_riego SET estado = :estado, horas_aplicadas = :horas, motivo = :motivo, "
            "agua_ahorrada_m3 = :agua, kwh_ahorrados = :kwh, ahorro_mxn = :mxn, decidida_en = :ahora "
            "WHERE id_recomendacion = :id"
        ),
        {"estado": decision, "horas": round(horas_aplicadas, 2), "motivo": motivo or None,
         "agua": ahorro["agua_m3"], "kwh": ahorro["energia_kwh"], "mxn": ahorro["dinero_mxn"],
         "ahora": datetime.now(), "id": id_recomendacion},
    )
    return {"estado": decision, "horas_aplicadas": round(horas_aplicadas, 2), **ahorro}


def historial(conexion, id_parcela: int, limite: int = 10) -> list[dict]:
    """Ultimas recomendaciones de la parcela, de la mas reciente a la mas antigua."""
    filas = conexion.execute(
        text(
            "SELECT fecha, horas_sugeridas, estado, horas_aplicadas, motivo, agua_ahorrada_m3, "
            "kwh_ahorrados, ahorro_mxn FROM recomendaciones_riego "
            "WHERE id_parcela = :id ORDER BY fecha DESC"
        ),
        {"id": id_parcela},
    ).mappings().fetchmany(limite)
    return [
        {k: (float(v) if v is not None and k not in ("fecha", "estado", "motivo") else v) for k, v in f.items()}
        for f in filas
    ]

