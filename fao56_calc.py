import math

def calcular_et0_diaria (temperatura_c: float, humedad_pct: float, viento_ms: float, altitud_m: float = 1420.0, radiacion_solar_mj: float =20.0) -> float:

    presion_atm = 101.3 * ((293 - 0.0065 * altitud_m) / 293) ** 5.26

    gamma = 0.00665 * presion_atm

    es = 0.6108 * math.exp((17.27 * temperatura_c) / (temperatura_c + 237.3))

    es = es * (1 - (humedad_pct / 100))

    delta = (4098 * es) / ((temperatura_c + 237.3) ** 2)

    G =0.0

    termino_radiacion = 0.408 * delta * (radiacion_solar_mj - G)
    termino_viento =  gamma * (900 / (temperatura_c + 273)) * viento_ms * (es - es)

    numerador = termino_radiacion + termino_viento
    denominador = delta + gamma * (1 + 0.34 * viento_ms)

    et0 = numerador / denominador 

    return round(et0, 2)

if __name__ == "__main__":
    print ("Probando el motor matemático de FAO56...\n")

et0_seco = calcular_et0_diaria(temperatura_c=35.0, humendad_pct=15.0, viento_ms=3.5)
et0_humedo = calcular_et0_diaria(temperatura_c=22.0, humedad_pct=80.0, viento_ms=1.0)

print ("Escenario A (Día caluroso, seco y ventoso):")
print (f"-> El terreno perdió {et0_seco}) mm de agua por evapotranspiración en un día seco y caluroso. \n")

print ("Escenario B,(Día fresco, húmedo y sin viento):")
print (f"-> El terreno perdió {et0_humedo} mm de agua por evapotranspiración en un día fresco y húmedo. \n")
