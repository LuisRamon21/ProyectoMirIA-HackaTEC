"""
Traduce la recomendacion de riego a ahorro de agua, energia y dinero,
comparandola con lo que el agricultor riega normalmente.

1 mm de lamina sobre 1 hectarea = 10 m3 de agua.
Energia = horas de bombeo evitadas x potencia de la bomba (kW).
Dinero  = kWh x precio vigente de la Tarifa 9-CU de CFE (tabla tarifas_energia).
"""
M3_POR_MM_HA = 10.0


def calcular_ahorro(
    horas_recomendadas: float,
    horas_habituales: float,
    tasa_mm_h: float,
    superficie_ha: float,
    potencia_bomba_kw: float,
    precio_kwh: float,
) -> dict:
    """Valores positivos = ahorro; negativos = el cultivo necesita mas que el riego habitual."""
    horas_evitadas = horas_habituales - horas_recomendadas
    lamina_evitada_mm = horas_evitadas * tasa_mm_h
    agua_m3 = lamina_evitada_mm * M3_POR_MM_HA * superficie_ha
    energia_kwh = horas_evitadas * potencia_bomba_kw
    return {
        "horas_evitadas": round(horas_evitadas, 2),
        "agua_m3": round(agua_m3, 1),
        "energia_kwh": round(energia_kwh, 1),
        "dinero_mxn": round(energia_kwh * precio_kwh, 2),
        "precio_kwh_mxn": precio_kwh,
    }
