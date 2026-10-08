import os
import logging
from dotenv import load_dotenv

from backend.services.clima import obtener_clima_actual, obtener_pronostico_24h
from backend.services.fao56_calc import calcular_et0_diaria
from backend.services.motor_difuso import evaluar_riesgo_cultivo, calcular_factor_riego
from backend.services.ahorro import calcular_ahorro

load_dotenv()

# Clima de ejemplo para presentar sin internet (modo demostracion)
CLIMA_DEMO = {"temperatura_c": 33.0, "humedad_pct": 22, "viento_ms": 4.0, "descripcion": "cielo claro"}
PRONOSTICO_DEMO = {"prob_lluvia_pct": 30, "lluvia_mm": 0.8, "temp_max_c": 35.0}


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


def generar_diagnostico_riego(
    ciudad: str,
    cultivo: str,
    etapa_actual: str,
    tasa_mm_h: float = 3.0,
    superficie_ha: float = 1.0,
    potencia_bomba_kw: float = 45.0,
    horas_habituales: float = 4.0,
    modo_demo: bool = False,
) -> dict:
    """
    Orquesta clima + pronostico, FAO-56, los dos motores difusos,
    la conversion a horas de riego y el ahorro.
    Retorna un diccionario (JSON-ready) para la API de B.A.W.I. Riego.
    """
    if modo_demo:
        clima, pronostico = dict(CLIMA_DEMO), dict(PRONOSTICO_DEMO)
    else:
        api_key = os.getenv("OPENWEATHER_API_KEY")
        clima = obtener_clima_actual(api_key, ciudad)
        if not clima:
            return {"error": True, "mensaje": "Fallo al conectar con el servicio meteorologico."}
        # Si el pronostico falla, se sigue sin descuento por lluvia
        pronostico = obtener_pronostico_24h(api_key, ciudad)

    if pronostico:
        pronostico["disponible"] = True
    else:
        pronostico = {
            "disponible": False,
            "prob_lluvia_pct": 0,
            "lluvia_mm": 0.0,
            "temp_max_c": clima["temperatura_c"],
        }

    # 1. Matematica FAO-56
    et0 = calcular_et0_diaria(
        temperatura_c=clima["temperatura_c"],
        humedad_pct=clima["humedad_pct"],
        viento_ms=clima["viento_ms"],
    )
    kc = obtener_kc_seguro(cultivo, etapa_actual)
    etc = round(et0 * kc, 2)

    # 2. Motor difuso 1: riesgo de estres si no se riega
    diagnostico_ia = evaluar_riesgo_cultivo(
        deficit_etc_mm=etc, temp_max_pronostico=pronostico["temp_max_c"]
    )

    # 3. Motor difuso 2: cuanto del deficit reponer segun la lluvia esperada
    factor = calcular_factor_riego(etc, pronostico["prob_lluvia_pct"])
    lamina = round(etc * factor / 100, 2)
    horas = round(lamina / tasa_mm_h, 2) if tasa_mm_h > 0 else 0.0

    # 4. Ahorro contra el riego habitual del agricultor
    ahorro = calcular_ahorro(
        horas_recomendadas=horas,
        horas_habituales=horas_habituales,
        tasa_mm_h=tasa_mm_h,
        superficie_ha=superficie_ha,
        potencia_bomba_kw=potencia_bomba_kw,
    )

    return {
        "error": False,
        "clima_actual": clima,
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
            "cultivo": cultivo,
            "etapa": etapa_actual,
            "superficie_ha": superficie_ha,
            "potencia_bomba_kw": potencia_bomba_kw,
            "horas_habituales": horas_habituales,
            "modo_demo": modo_demo,
        },
    }


if __name__ == "__main__":
    import json
    print("Generando diagnostico para B.A.W.I. Riego...\n")
    reporte = generar_diagnostico_riego("Cuauhtemoc,MX", "manzana", "desarrollo")
    print(json.dumps(reporte, indent=2, ensure_ascii=False))