"""
Calculo de evapotranspiracion de referencia (ET0) diaria con FAO-56 Penman-Monteith
(Allen et al., 1998, Estudio FAO Riego y Drenaje 56).

Se usan los datos del dia de la ubicacion de la parcela: temperatura maxima y
minima, humedad relativa maxima y minima, viento medio, radiacion solar medida/modelada,
latitud y altitud. Los numeros de ecuacion son los del documento FAO-56.
"""
import math

SIGMA = 4.903e-9  # constante de Stefan-Boltzmann, MJ/K4/m2/dia
ALBEDO = 0.23      # pasto de referencia


def _presion_vapor_saturacion(temperatura_c: float) -> float:
    """e°(T) en kPa (ec. 11)."""
    return 0.6108 * math.exp(17.27 * temperatura_c / (temperatura_c + 237.3))


def _radiacion_extraterrestre(latitud_grados: float, dia_del_anio: int) -> float:
    """Ra en MJ/m2/dia (ec. 21 a 25)."""
    phi = math.radians(latitud_grados)
    dr = 1 + 0.033 * math.cos(2 * math.pi * dia_del_anio / 365)
    decl = 0.409 * math.sin(2 * math.pi * dia_del_anio / 365 - 1.39)
    ws = math.acos(max(-1.0, min(1.0, -math.tan(phi) * math.tan(decl))))
    return (24 * 60 / math.pi) * 0.0820 * dr * (
        ws * math.sin(phi) * math.sin(decl)
        + math.cos(phi) * math.cos(decl) * math.sin(ws)
    )


def calcular_et0_diaria(
    temp_max_c: float,
    temp_min_c: float,
    humedad_max_pct: float,
    humedad_min_pct: float,
    viento_ms: float,
    radiacion_solar_mj: float,
    altitud_m: float,
    latitud_grados: float,
    dia_del_anio: int,
    altura_viento_m: float = 10.0,
) -> float:
    """Devuelve la ET0 en mm/dia."""
    if temp_min_c > temp_max_c:
        temp_min_c, temp_max_c = temp_max_c, temp_min_c
    humedad_max_pct = min(max(humedad_max_pct, 0.0), 100.0)
    humedad_min_pct = min(max(humedad_min_pct, 0.0), humedad_max_pct)
    viento_ms = max(viento_ms, 0.0)
    radiacion_solar_mj = max(radiacion_solar_mj, 0.0)
    temp_media = (temp_max_c + temp_min_c) / 2

    # Viento medido a altura_viento_m -> viento a 2 m (ec. 47)
    u2 = viento_ms * 4.87 / math.log(67.8 * altura_viento_m - 5.42)

    # Presion atmosferica y constante psicrometrica (ec. 7 y 8)
    presion = 101.3 * ((293 - 0.0065 * altitud_m) / 293) ** 5.26
    gamma = 0.000665 * presion

    # Presion de vapor: saturacion media, real (con HR maxima y minima) y pendiente de la curva (ec. 12, 17, 13)
    e_tmax, e_tmin = _presion_vapor_saturacion(temp_max_c), _presion_vapor_saturacion(temp_min_c)
    es = (e_tmax + e_tmin) / 2
    ea = (e_tmin * humedad_max_pct / 100 + e_tmax * humedad_min_pct / 100) / 2
    delta = 4098 * _presion_vapor_saturacion(temp_media) / (temp_media + 237.3) ** 2

    # Radiacion neta (ec. 37, 38, 39, 40)
    ra = _radiacion_extraterrestre(latitud_grados, dia_del_anio)
    rso = (0.75 + 2e-5 * altitud_m) * ra
    rns = (1 - ALBEDO) * radiacion_solar_mj
    relacion = min(radiacion_solar_mj / rso, 1.0) if rso > 0 else 1.0
    rnl = (
        SIGMA * ((temp_max_c + 273.16) ** 4 + (temp_min_c + 273.16) ** 4) / 2
        * (0.34 - 0.14 * math.sqrt(ea))
        * (1.35 * relacion - 0.35)
    )
    rn = rns - rnl
    g = 0.0  # flujo de calor del suelo, despreciable a escala diaria (ec. 42)

    # Penman-Monteith FAO-56 (ec. 6)
    numerador = 0.408 * delta * (rn - g) + gamma * (900 / (temp_media + 273)) * u2 * (es - ea)
    denominador = delta + gamma * (1 + 0.34 * u2)
    return round(max(numerador / denominador, 0.0), 2)
