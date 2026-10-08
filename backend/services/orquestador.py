import os
import logging
from dotenv import load_dotenv


from backend.services.clima import obtener_clima_actual
from backend.services.fao56_calc import calcular_et0_diaria
from backend.services.motor_difuso import evaluar_riesgo_cultivo

load_dotenv()

def obtener_kc_seguro(cultivo: str, etapa: str) -> float:
    """
    Simula la tabla del INIFAP con Graceful Degradation.
    """
    base_datos_inifap = {
        "nogal": {"inicial": 0.4, "desarrollo": 0.8, "media": 1.15, "final": 0.6},
        "manzana": {"inicial": 0.3, "desarrollo": 0.75, "media": 1.0, "final": 0.5}
    }
    kc = base_datos_inifap.get(cultivo, {}).get(etapa)
    if kc is None:
        logging.warning(f"Falta el Kc para {cultivo} en etapa {etapa}. Usando default 1.0")
        return 1.0 
    return kc

def generar_diagnostico_riego(ciudad: str, cultivo: str, etapa_actual: str) -> dict:
    """
    Orquesta la recolección de datos, el cálculo FAO-56 y el diagnóstico difuso.
    Retorna un diccionario (JSON-ready) para la API de B.A.W.Í. Riego.
    """
    api_key = os.getenv("OPENWEATHER_API_KEY")
    clima = obtener_clima_actual(api_key, ciudad)
    
    if not clima:
        return {"error": True, "mensaje": "Fallo al conectar con el servicio meteorológico."}
    
    # 1. Matemática (Diagnóstico puro)
    et0 = calcular_et0_diaria(
        temperatura_c=clima['temperatura_c'],
        humedad_pct=clima['humedad_pct'],
        viento_ms=clima['viento_ms']
    )
    
    kc = obtener_kc_seguro(cultivo, etapa_actual)
    etc = round(et0 * kc, 2)

    
    temp_max = clima.get('temp_max_c', clima['temperatura_c']) 
    
    diagnostico_ia = evaluar_riesgo_cultivo(deficit_etc_mm=etc, temp_max_pronostico=temp_max)
    

    return {
        "error": False,
        "clima_actual": clima,
        "calculos": {
            "et0_mm": et0,
            "kc_aplicado": kc,
            "etc_mm": etc
        },
        "diagnostico_ia": diagnostico_ia,
 
        "metadata_app": {
            "cultivo": cultivo,
            "etapa": etapa_actual
        }
    }


if __name__ == "__main__":
    print("Generando diagnóstico para B.A.W.Í. Riego...\n")
    reporte = generar_diagnostico_riego("Cuauhtemoc,MX", "manzana", "desarrollo")
    import json
    print(json.dumps(reporte, indent=2, ensure_ascii=False))