"""
Servicio de clima (Open-Meteo, gratuito y sin clave de API).

- MUNICIPIOS: coordenadas de las cabeceras municipales donde trabaja B.A.W.I.
  Si la parcela tiene latitud y longitud guardadas, se usan esas.
- obtener_clima(lat, lon) regresa:
    actual:      temperatura, humedad, viento y descripcion de ahora
    dia:         Tmax, Tmin, humedad maxima y minima, viento medio, radiacion solar,
                 altitud y fecha de hoy (lo que necesita FAO-56)
    pronostico:  de las proximas 24 h, la probabilidad maxima de lluvia,
                 la lluvia esperada en mm y la temperatura maxima
"""
from datetime import date

import requests

URL_PRONOSTICO = "https://api.open-meteo.com/v1/forecast"
TIEMPO_ESPERA_S = 10

# Cabeceras municipales (latitud, longitud). Las claves son las que usan las apps.
MUNICIPIOS = {
    "Delicias": (28.1901, -105.4701),
    "Cuauhtemoc": (28.4063, -106.8667),
    "Camargo": (27.6833, -105.1667),
    "Chihuahua": (28.6353, -106.0889),
}

# Codigos WMO que usa Open-Meteo para describir el cielo
DESCRIPCION_WMO = {
    0: "cielo despejado", 1: "mayormente despejado", 2: "parcialmente nublado", 3: "nublado",
    45: "niebla", 48: "niebla con escarcha",
    51: "llovizna ligera", 53: "llovizna", 55: "llovizna intensa",
    56: "llovizna helada", 57: "llovizna helada intensa",
    61: "lluvia ligera", 63: "lluvia", 65: "lluvia intensa",
    66: "lluvia helada", 67: "lluvia helada intensa",
    71: "nevada ligera", 73: "nevada", 75: "nevada intensa", 77: "granizo fino",
    80: "chubascos ligeros", 81: "chubascos", 82: "chubascos fuertes",
    85: "chubascos de nieve", 86: "chubascos de nieve fuertes",
    95: "tormenta", 96: "tormenta con granizo", 99: "tormenta con granizo fuerte",
}


class ClimaNoDisponible(Exception):
    """El servicio de clima no respondio o no hay datos para el lugar."""


def normalizar_municipio(nombre: str) -> str:
    """'Cuauhtémoc,MX' -> 'Cuauhtemoc' (la forma que se usa en MUNICIPIOS y en la base de datos)."""
    base = nombre.split(",")[0].strip()
    sin_acentos = base.translate(str.maketrans("áéíóúÁÉÍÓÚ", "aeiouAEIOU"))
    for clave in MUNICIPIOS:
        if clave.lower() == sin_acentos.lower():
            return clave
    return sin_acentos


def coordenadas_de(municipio: str) -> tuple[float, float]:
    clave = normalizar_municipio(municipio)
    if clave not in MUNICIPIOS:
        raise ValueError(
            f"No hay coordenadas para el municipio '{municipio}'. "
            f"Municipios disponibles: {', '.join(MUNICIPIOS)}, o registra la latitud y longitud de la parcela."
        )
    return MUNICIPIOS[clave]


def obtener_clima(latitud: float, longitud: float) -> dict:
    parametros = {
        "latitude": latitud,
        "longitude": longitud,
        "current": "temperature_2m,relative_humidity_2m,wind_speed_10m,weather_code",
        "daily": ("temperature_2m_max,temperature_2m_min,relative_humidity_2m_max,relative_humidity_2m_min,"
                  "wind_speed_10m_mean,shortwave_radiation_sum"),
        "hourly": "temperature_2m,precipitation_probability,precipitation",
        "forecast_days": 2,
        "forecast_hours": 24,
        "wind_speed_unit": "ms",
        "timezone": "auto",
    }
    try:
        respuesta = requests.get(URL_PRONOSTICO, params=parametros, timeout=TIEMPO_ESPERA_S)
        respuesta.raise_for_status()
        datos = respuesta.json()
    except requests.exceptions.Timeout:
        raise ClimaNoDisponible("El servicio de clima tardó demasiado en responder. Intenta de nuevo.")
    except requests.exceptions.ConnectionError:
        raise ClimaNoDisponible("No hay conexión con el servicio de clima. Revisa tu conexión a internet.")
    except (requests.exceptions.RequestException, ValueError) as error:
        raise ClimaNoDisponible(f"El servicio de clima respondió con un error: {error}")

    try:
        actual, diario, horario = datos["current"], datos["daily"], datos["hourly"]
        dia = {
            "fecha": date.fromisoformat(diario["time"][0]),
            "temp_max_c": float(diario["temperature_2m_max"][0]),
            "temp_min_c": float(diario["temperature_2m_min"][0]),
            "humedad_max_pct": float(diario["relative_humidity_2m_max"][0]),
            "humedad_min_pct": float(diario["relative_humidity_2m_min"][0]),
            "viento_medio_ms": float(diario["wind_speed_10m_mean"][0]),
            "radiacion_mj_m2": float(diario["shortwave_radiation_sum"][0]),
            "altitud_m": float(datos["elevation"]),
            "latitud": float(datos["latitude"]),
        }
        clima_actual = {
            "temperatura_c": round(float(actual["temperature_2m"]), 1),
            "humedad_pct": round(float(actual["relative_humidity_2m"])),
            "viento_ms": round(float(actual["wind_speed_10m"]), 1),
            "descripcion": DESCRIPCION_WMO.get(actual.get("weather_code"), "sin descripción"),
        }
        probabilidades = [p for p in horario["precipitation_probability"] if p is not None]
        lluvias = [p for p in horario["precipitation"] if p is not None]
        temperaturas = [t for t in horario["temperature_2m"] if t is not None]
        pronostico = {
            "prob_lluvia_pct": round(max(probabilidades, default=0)),
            "lluvia_mm": round(sum(lluvias), 1),
            "temp_max_c": round(max(temperaturas, default=dia["temp_max_c"]), 1),
        }
    except (KeyError, IndexError, TypeError, ValueError):
        raise ClimaNoDisponible("El servicio de clima no tiene datos completos para esta ubicación hoy.")

    return {"actual": clima_actual, "dia": dia, "pronostico": pronostico}
