"""
Calculo de evapotranspiracion de referencia (ET0) con FAO-56 Penman-Monteith.

Simplificacion: OpenWeather (clima actual) solo da una temperatura y una
humedad, asi que se usan como valores medios del dia. La radiacion solar
no viene en esos datos; se usa un valor tipico para Chihuahua (20 MJ/m2/dia)
que puede reemplazarse cuando haya datos de estacion.
"""
import math
from datetime import date

SIGMA = 4.903e-9  # constante de Stefan-Boltzmann, MJ/K4/m2/dia


def _radiacion_extraterrestre(latitud_grados: float, dia_del_anio: int) -> float:
    """Ra en MJ/m2/dia (FAO-56, ec. 21)."""
    phi = math.radians(latitud_grados)
    dr = 1 + 0.033 * math.cos(2 * math.pi * dia_del_anio / 365)
    decl = 0.409 * math.sin(2 * math.pi * dia_del_anio / 365 - 1.39)
    ws = math.acos(max(-1.0, min(1.0, -math.tan(phi) * math.tan(decl))))
    return (24 * 60 / math.pi) * 0.0820 * dr * (
        ws * math.sin(phi) * math.sin(decl)
        + math.cos(phi) * math.cos(decl) * math.sin(ws)
    )


def calcular_et0_diaria(
    temperatura_c: float,
    humedad_pct: float,
    viento_ms: float,
    altitud_m: float = 1420.0,
    radiacion_solar_mj: float = 20.0,
    latitud_grados: float = 28.6,
    dia_del_anio: int | None = None,
    altura_viento_m: float = 10.0,
) -> float:
    """Devuelve la ET0 en mm/dia."""
    if dia_del_anio is None:
        dia_del_anio = date.today().timetuple().tm_yday
    humedad_pct = min(max(humedad_pct, 0.0), 100.0)
    viento_ms = max(viento_ms, 0.0)

    # Viento medido a altura_viento_m -> viento a 2 m (ec. 47)
    u2 = viento_ms * 4.87 / math.log(67.8 * altura_viento_m - 5.42)

    # Presion y constante psicrometrica (ec. 7 y 8)
    presion = 101.3 * ((293 - 0.0065 * altitud_m) / 293) ** 5.26
    gamma = 0.000665 * presion

    # Presion de vapor de saturacion, real y pendiente de la curva (ec. 11, 19, 13)
    es = 0.6108 * math.exp(17.27 * temperatura_c / (temperatura_c + 237.3))
    ea = es * humedad_pct / 100
    delta = 4098 * es / (temperatura_c + 237.3) ** 2

    # Radiacion neta (ec. 37, 38, 39, 40)
    ra = _radiacion_extraterrestre(latitud_grados, dia_del_anio)
    rso = (0.75 + 2e-5 * altitud_m) * ra
    rns = 0.77 * radiacion_solar_mj
    relacion = min(radiacion_solar_mj / rso, 1.0) if rso > 0 else 1.0
    rnl = (
        SIGMA * (temperatura_c + 273.16) ** 4
        * (0.34 - 0.14 * math.sqrt(ea))
        * (1.35 * relacion - 0.35)
    )
    rn = rns - rnl
    g = 0.0  # flujo de calor del suelo, despreciable a escala diaria

    # Penman-Monteith FAO-56 (ec. 6)
    numerador = 0.408 * delta * (rn - g) + gamma * (900 / (temperatura_c + 273)) * u2 * (es - ea)
    denominador = delta + gamma * (1 + 0.34 * u2)
    return round(max(numerador / denominador, 0.0), 2)


if __name__ == "__main__":
    print("Probando el motor matematico de FAO-56...\n")
    et0_seco = calcular_et0_diaria(temperatura_c=35.0, humedad_pct=15.0, viento_ms=3.5)
    et0_humedo = calcular_et0_diaria(temperatura_c=22.0, humedad_pct=80.0, viento_ms=1.0)
    print(f"Escenario A (caluroso, seco y ventoso): ET0 = {et0_seco} mm/dia")
    print(f"Escenario B (fresco, humedo y sin viento): ET0 = {et0_humedo} mm/dia")