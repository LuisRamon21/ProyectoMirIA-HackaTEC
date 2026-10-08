import os
import requests
from typing import Optional, Dict
from dotenv import load_dotenv


load_dotenv()

def obtener_clima_actual(api_key: str, ciudad: str = "Chihuahua,MX") -> Optional[Dict]:
    """
    Se conecta a la API de OpenWeatherMap y extrae el clima actual.
    """
    url = "https://api.openweathermap.org/data/2.5/weather"
    parametros = {
        "q": "Chihuahua,MX",
        "appid": api_key,
        "units": "metric",  
        "lang": "es"        
    }

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
    MI_API_KEY = os.getenv("OPENWEATHER_API_KEY")
    if not MI_API_KEY:
        print("❌ Falla: No hay API Key en el archivo .env")
    else:
        clima = obtener_clima_actual(MI_API_KEY, "Chihuahua ,MX")
        print(clima)