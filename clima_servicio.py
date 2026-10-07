import os
import requests
from typing import Optional, Dict
from dotenv import load_dotenv

def obtener_clima_actual(api_key: str, ciudad: str = "Chihuahua,MX") -> Optional[Dict]:
   
    url = "https://api.openweathermap.org/data/2.5/weather"
    parametros = {
        "q": ciudad,
        "appid": api_key,
        "units": "metric",  # Sistema métrico (Celsius, m/s)
        "lang": "es"        # Respuestas en español
    }

    try:
     
        respuesta = requests.get(url, params=parametros, timeout=5)
        
        
        respuesta.raise_for_status()
        
       
        datos_json = respuesta.json()
        
        
        clima_limpio = {
            "temperatura_c": datos_json["main"]["temp"],
            "humedad_pct": datos_json["main"]["humidity"],
            "viento_ms": datos_json["wind"]["speed"],
            "descripcion": datos_json["weather"][0]["description"]
        }
        
        return clima_limpio

    except requests.exceptions.HTTPError as error_http:
        print(f"Error de HTTP (Revisa tu API Key o el nombre de la ciudad): {error_http}")
    except requests.exceptions.ConnectionError:
        print("Error de conexión: No se pudo conectar a los servidores de OpenWeatherMap.")
    except requests.exceptions.Timeout:
        print("Error de tiempo de espera: La API tardó demasiado en responder.")
    except Exception as e:
        print(f"Ocurrió un error inesperado: {e}")
        
    return None

if __name__ == "__main__":

  
    MI_API_KEY = "TU_API_KEY_AQUI" 
    
    print("Consultando el clima para Chihuahua...")
    datos_actuales = obtener_clima_actual(MI_API_KEY)
    
    if datos_actuales:
        print("\n--- Datos recibidos con éxito ---")
        print(f"Temperatura: {datos_actuales['temperatura_c']} °C")
        print(f"Humedad:     {datos_actuales['humedad_pct']} %")
        print(f"Viento:      {datos_actuales['viento_ms']} m/s")
        print(f"Condición:   {datos_actuales['descripcion'].capitalize()}")
    else:
        print("\nNo se pudieron obtener los datos. Revisa los mensajes de error arriba.")