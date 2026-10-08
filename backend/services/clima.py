"""
Servicio de clima (OpenWeather, plan gratuito).

- obtener_clima_actual: temperatura, humedad, viento y descripcion de ahora.
- obtener_pronostico_24h: de las proximas 24 h (8 bloques de 3 h) saca la
  probabilidad maxima de lluvia, la lluvia esperada en mm y la temperatura maxima.
"""
from typing import Optional, Dict

import requests

URL_ACTUAL = "https://api.openweathermap.org/data/2.5/weather"
URL_PRONOSTICO = "https://api.openweathermap.org/data/2.5/forecast"
BLOQUES_24H = 8  # el pronostico viene en bloques de 3 horas


def _consultar(url: str, api_key: str, ciudad: str, extra: Optional[Dict] = None) -> Optional[Dict]:
    parametros = {"q": ciudad, "appid": api_key, "units": "metric", "lang": "es"}
    if extra:
        parametros.update(extra)
    try:
        respuesta = requests.get(url, params=parametros, timeout=5)
        respuesta.raise_for_status()
        return respuesta.json()
    except requests.exceptions.HTTPError as error_http:
        print(f"Error de HTTP (revisa tu API Key o el nombre de la ciudad): {error_http}")
    except requests.exceptions.ConnectionError:
        print("Error de conexion: no se pudo conectar a OpenWeatherMap.")
    except requests.exceptions.Timeout:
        print("Error de tiempo de espera: la API tardo demasiado en responder.")
    except Exception as e:
        print(f"Ocurrio un error inesperado: {e}")
    return None


def obtener_clima_actual(api_key: str, ciudad: str = "Chihuahua,MX") -> Optional[Dict]:
    datos = _consultar(URL_ACTUAL, api_key, ciudad)
    if not datos:
        return None
    return {
        "temperatura_c": datos["main"]["temp"],
        "humedad_pct": datos["main"]["humidity"],
        "viento_ms": datos["wind"]["speed"],
        "descripcion": datos["weather"][0]["description"],
    }


def obtener_pronostico_24h(api_key: str, ciudad: str = "Chihuahua,MX") -> Optional[Dict]:
    datos = _consultar(URL_PRONOSTICO, api_key, ciudad, {"cnt": BLOQUES_24H})
    if not datos or not datos.get("list"):
        return None
    bloques = datos["list"][:BLOQUES_24H]
    return {
        "prob_lluvia_pct": round(max(b.get("pop", 0) for b in bloques) * 100),
        "lluvia_mm": round(sum(b.get("rain", {}).get("3h", 0) for b in bloques), 1),
        "temp_max_c": round(max(b["main"]["temp_max"] for b in bloques), 1),
    }


if __name__ == "__main__":
    import os
    from dotenv import load_dotenv

    load_dotenv()
    clave = os.getenv("OPENWEATHER_API_KEY")
    print("Clima actual:", obtener_clima_actual(clave, "Delicias,MX"))
    print("Pronostico 24 h:", obtener_pronostico_24h(clave, "Delicias,MX"))