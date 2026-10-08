"""
Orquesta el calculo de B.A.W.I. Riego:

clima real de la ubicacion (Open-Meteo) -> ET0 con FAO-56 -> ETc con el Kc de la
base de datos -> riesgo de estres y porcentaje a reponer (motores difusos) ->
horas de riego -> ahorro contra el riego habitual con la tarifa vigente.
"""
from backend.services.ahorro import calcular_ahorro
from backend.services.catalogo import kc_de, precio_kwh_vigente
from backend.services.clima import coordenadas_de, normalizar_municipio, obtener_clima
from backend.services.fao56_calc import calcular_et0_diaria
from backend.services.motor_difuso import calcular_factor_riego, evaluar_riesgo_cultivo


def generar_diagnostico_riego(
    conexion,
    municipio: str,
    cultivo: str,
    etapa_actual: str,
    tasa_mm_h: float,
    superficie_ha: float,
    potencia_bomba_kw: float,
    horas_habituales: float,
    latitud: float | None = None,
    longitud: float | None = None,
) -> dict:
    """
    Regresa el reporte (listo para JSON) de la API de B.A.W.I. Riego.
    Lanza ValueError si faltan datos de referencia y ClimaNoDisponible si no hay clima.
    """
    if tasa_mm_h <= 0:
        raise ValueError("La tasa de aplicación del sistema de riego debe ser mayor que 0 mm/h.")

    # Datos de referencia de la base de datos (se validan antes de consultar el clima)
    kc = kc_de(conexion, cultivo, etapa_actual)
    precio_kwh = precio_kwh_vigente(conexion)

    if latitud is None or longitud is None:
        latitud, longitud = coordenadas_de(municipio)
    clima = obtener_clima(latitud, longitud)
    actual, dia, pronostico = clima["actual"], clima["dia"], clima["pronostico"]

    # 1. Matematica FAO-56
    et0 = calcular_et0_diaria(
        temp_max_c=dia["temp_max_c"],
        temp_min_c=dia["temp_min_c"],
        humedad_max_pct=dia["humedad_max_pct"],
        humedad_min_pct=dia["humedad_min_pct"],
        viento_ms=dia["viento_medio_ms"],
        radiacion_solar_mj=dia["radiacion_mj_m2"],
        altitud_m=dia["altitud_m"],
        latitud_grados=dia["latitud"],
        dia_del_anio=dia["fecha"].timetuple().tm_yday,
    )
    etc = round(et0 * kc, 2)

    # 2. Motor difuso 1: riesgo de estres si no se riega
    diagnostico_ia = evaluar_riesgo_cultivo(
        deficit_etc_mm=etc, temp_max_pronostico=pronostico["temp_max_c"]
    )

    # 3. Motor difuso 2: cuanto del deficit reponer segun la lluvia esperada
    factor = calcular_factor_riego(etc, pronostico["prob_lluvia_pct"])
    lamina = round(etc * factor / 100, 2)
    horas = round(lamina / tasa_mm_h, 2)

    # 4. Ahorro contra el riego habitual del agricultor
    ahorro = calcular_ahorro(
        horas_recomendadas=horas,
        horas_habituales=horas_habituales,
        tasa_mm_h=tasa_mm_h,
        superficie_ha=superficie_ha,
        potencia_bomba_kw=potencia_bomba_kw,
        precio_kwh=precio_kwh,
    )

    return {
        "error": False,
        "clima_actual": actual,
        "clima_dia": {**dia, "fecha": dia["fecha"].isoformat()},
        "pronostico_24h": pronostico,
        "calculos": {
            "et0_mm": et0,
            "kc_aplicado": kc,
            "etc_mm": etc,
        },
        "diagnostico_ia": diagnostico_ia,
        "riego": {
            "factor_reposicion_pct": factor,
            "lamina_mm": lamina,
            "horas": horas,
            "tasa_mm_h": tasa_mm_h,
        },
        "ahorro": ahorro,
        "metadata_app": {
            "municipio": normalizar_municipio(municipio),
            "latitud": latitud,
            "longitud": longitud,
            "cultivo": cultivo,
            "etapa": etapa_actual,
            "superficie_ha": superficie_ha,
            "potencia_bomba_kw": potencia_bomba_kw,
            "horas_habituales": horas_habituales,
            "fuente_clima": "open-meteo",
        },
    }
