"""
Servicio de clima (OpenWeather, plan gratuito).

- obtener_clima_actual: temperatura, humedad, viento y descripcion de ahora.
- obtener_pronostico_24h: de las proximas 24 h (8 bloques de 3 h) saca la
  probabilidad maxima de lluvia, la lluvia esperada en mm y la temperatura maxima.
"""
import os
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
        datos_json = respuesta.json()
        
        return {
            "temperatura_c": datos_json["main"]["temp"],
            "temp_max_c": datos_json["main"]["temp_max"], # Vital para el motor difuso
            "humedad_pct": datos_json["main"]["humidity"],
            "viento_ms": datos_json["wind"]["speed"],
            "descripcion": datos_json["weather"][0]["description"]
        }

    except Exception as e:
        print(f"Error al obtener clima: {e}")
        return None

# --- Prueba independiente ---
if __name__ == "__main__":
    mi_api_key = os.getenv("OPENWEATHER_API_KEY")
    if not mi_api_key:
        print("❌ Falla: No hay API Key en el archivo .env")
    else:
        clima = _consultar(URL_ACTUAL, mi_api_key, "Chihuahua, MX")
        print(clima)
