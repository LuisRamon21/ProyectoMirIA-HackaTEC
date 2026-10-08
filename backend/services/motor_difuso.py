"""
Motores de logica difusa de B.A.W.I. Riego (scikit-fuzzy):

1. Riesgo de estres hidrico del cultivo si no se riega (deficit + temperatura maxima).
2. Porcentaje del deficit que conviene reponer hoy (deficit + probabilidad de lluvia).
"""
import numpy as np
import skfuzzy as fuzz
from skfuzzy import control as ctrl

DEFICIT_MAX_MM = 16
TEMP_MIN_C, TEMP_MAX_C = 10, 45
DEFICIT_MINIMO_MM = 0.5  # por debajo de esto no vale la pena regar


# ---------------------------------------------------------------------------
# 1. Riesgo de estres hidrico (deficit + temperatura)
# ---------------------------------------------------------------------------
def _construir_sistema_riesgo():
    deficit = ctrl.Antecedent(np.linspace(0, DEFICIT_MAX_MM, 161), "deficit")
    temperatura = ctrl.Antecedent(np.linspace(TEMP_MIN_C, TEMP_MAX_C, 36), "temperatura")
    riesgo = ctrl.Consequent(np.linspace(0, 100, 101), "riesgo")

    deficit.automf(names=["bajo", "normal", "alto"])
    temperatura.automf(names=["fresca", "calida", "extrema"])

    riesgo["bajo"] = fuzz.trimf(riesgo.universe, [0, 0, 40])
    riesgo["moderado"] = fuzz.trimf(riesgo.universe, [30, 50, 70])
    riesgo["critico"] = fuzz.trimf(riesgo.universe, [60, 100, 100])

    # Las 9 combinaciones cubiertas (la ultima regla abarca 2)
    reglas = [
        ctrl.Rule(deficit["bajo"] & temperatura["fresca"], riesgo["bajo"]),
        ctrl.Rule(deficit["bajo"] & temperatura["calida"], riesgo["bajo"]),
        ctrl.Rule(deficit["bajo"] & temperatura["extrema"], riesgo["moderado"]),
        ctrl.Rule(deficit["normal"] & temperatura["fresca"], riesgo["bajo"]),
        ctrl.Rule(deficit["normal"] & temperatura["calida"], riesgo["moderado"]),
        ctrl.Rule(deficit["normal"] & temperatura["extrema"], riesgo["moderado"]),
        ctrl.Rule(deficit["alto"] & temperatura["fresca"], riesgo["moderado"]),
        ctrl.Rule(deficit["alto"] & (temperatura["calida"] | temperatura["extrema"]), riesgo["critico"]),
    ]
    return ctrl.ControlSystem(reglas)


_SISTEMA_RIESGO = _construir_sistema_riesgo()


def evaluar_riesgo_cultivo(deficit_etc_mm: float, temp_max_pronostico: float) -> dict:
    """
    Evalua el nivel de riesgo de estres hidrico del cultivo.
    Retorna un diccionario con el puntaje (0-100) y la etiqueta de riesgo.
    """
    deficit_in = min(max(float(deficit_etc_mm), 0.0), DEFICIT_MAX_MM)
    temp_in = min(max(float(temp_max_pronostico), TEMP_MIN_C), TEMP_MAX_C)

    simulador = ctrl.ControlSystemSimulation(_SISTEMA_RIESGO)
    simulador.input["deficit"] = deficit_in
    simulador.input["temperatura"] = temp_in
    simulador.compute()
    puntaje = round(float(simulador.output["riesgo"]), 1)

    if puntaje >= 65:
        etiqueta = "CRÍTICO"
        mensaje = "La planta entrará en estrés hídrico severo si no se riega hoy. Alta evaporación esperada."
    elif puntaje >= 35:
        etiqueta = "MODERADO"
        mensaje = "Déficit manejable. Puedes posponer el riego si tienes tareas de fertilización pendientes."
    else:
        etiqueta = "BAJO"
        mensaje = "Humedad óptima. No se recomienda regar para evitar asfixia radicular y ahorrar energía."

    return {
        "puntaje_riesgo": puntaje,
        "etiqueta": etiqueta,
        "mensaje_educativo": mensaje,
        "recomendacion_mm": deficit_etc_mm,
    }


# ---------------------------------------------------------------------------
# 2. Porcentaje del deficit a reponer (deficit + probabilidad de lluvia)
#    La lluvia es la unica razon para reponer menos del 100%.
# ---------------------------------------------------------------------------
def _construir_sistema_factor():
    deficit = ctrl.Antecedent(np.linspace(0, DEFICIT_MAX_MM, 161), "deficit")
    lluvia = ctrl.Antecedent(np.linspace(0, 100, 101), "lluvia")
    # La salida va de -15 a 115 para que el centroide pueda llegar
    # a 0% y a 100% exactos; despues se recorta a 0-100.
    factor = ctrl.Consequent(np.linspace(-15, 115, 131), "factor")

    deficit.automf(names=["bajo", "normal", "critico"])
    lluvia.automf(names=["nula", "ligera", "tormenta"])

    factor["nulo"] = fuzz.trimf(factor.universe, [-15, 0, 15])
    factor["reducido"] = fuzz.trimf(factor.universe, [10, 30, 50])
    factor["medio"] = fuzz.trimf(factor.universe, [35, 55, 75])
    factor["alto"] = fuzz.trimf(factor.universe, [60, 80, 100])
    factor["completo"] = fuzz.trimf(factor.universe, [85, 100, 115])

    # Cubre las 9 combinaciones (la primera regla abarca 3)
    reglas = [
        ctrl.Rule(lluvia["nula"], factor["completo"]),
        ctrl.Rule(deficit["critico"] & lluvia["ligera"], factor["alto"]),
        ctrl.Rule(deficit["normal"] & lluvia["ligera"], factor["medio"]),
        ctrl.Rule(deficit["bajo"] & lluvia["ligera"], factor["reducido"]),
        ctrl.Rule(deficit["critico"] & lluvia["tormenta"], factor["reducido"]),
        ctrl.Rule(deficit["normal"] & lluvia["tormenta"], factor["nulo"]),
        ctrl.Rule(deficit["bajo"] & lluvia["tormenta"], factor["nulo"]),
    ]
    return ctrl.ControlSystem(reglas)


_SISTEMA_FACTOR = _construir_sistema_factor()


def calcular_factor_riego(deficit_mm: float, prob_lluvia_pct: float) -> float:
    """Devuelve el porcentaje (0-100) del deficit que conviene reponer hoy."""
    deficit_mm = min(max(float(deficit_mm), 0.0), DEFICIT_MAX_MM)
    prob_lluvia_pct = min(max(float(prob_lluvia_pct), 0.0), 100.0)

    if deficit_mm < DEFICIT_MINIMO_MM:
        return 0.0

    simulador = ctrl.ControlSystemSimulation(_SISTEMA_FACTOR)
    simulador.input["deficit"] = deficit_mm
    simulador.input["lluvia"] = prob_lluvia_pct
    simulador.compute()
    resultado = float(simulador.output["factor"])
    return round(min(max(resultado, 0.0), 100.0), 1)

