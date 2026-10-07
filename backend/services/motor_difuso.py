import numpy as np
import skfuzzy as fuzz
from skfuzzy import control as ctrl

def evaluar_riesgo_cultivo(deficit_etc_mm: float, temp_max_pronostico: float) -> dict:
    """
    Evalúa el nivel de riesgo de estrés hídrico del cultivo.
    Retorna un diccionario con el puntaje (0-100) y la etiqueta de riesgo.
    """
    

    deficit = ctrl.Antecedent(np.arange(0, 16, 0.1), 'deficit')

    temperatura = ctrl.Antecedent(np.arange(10, 46, 1), 'temperatura')
    
    
    riesgo = ctrl.Consequent(np.arange(0, 101, 1), 'riesgo')

  
    deficit.automf(names=['bajo', 'normal', 'alto'])
    temperatura.automf(names=['fresca', 'calida', 'extrema'])

    
    riesgo['bajo'] = fuzz.trimf(riesgo.universe, [0, 0, 40])
    riesgo['moderado'] = fuzz.trimf(riesgo.universe, [30, 50, 70])
    riesgo['critico'] = fuzz.trimf(riesgo.universe, [60, 100, 100])


    regla1 = ctrl.Rule(deficit['bajo'] & temperatura['fresca'], riesgo['bajo'])
    
  
    regla2 = ctrl.Rule(deficit['alto'] & temperatura['fresca'], riesgo['moderado'])
    
    
    regla3 = ctrl.Rule(deficit['normal'] & temperatura['extrema'], riesgo['moderado'])
    
    
    regla4 = ctrl.Rule(deficit['alto'] & (temperatura['calida'] | temperatura['extrema']), riesgo['critico'])

    
    sistema_ctrl = ctrl.ControlSystem([regla1, regla2, regla3, regla4])
    simulador = ctrl.ControlSystemSimulation(sistema_ctrl)

    simulador.input['deficit'] = deficit_etc_mm
    simulador.input['temperatura'] = temp_max_pronostico
    simulador.compute()
    
    puntaje = round(simulador.output['riesgo'], 1)
    
 
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
        "recomendacion_mm": deficit_etc_mm 
    }


if __name__ == "__main__":
   
    resultado = evaluar_riesgo_cultivo(deficit_etc_mm=11.5, temp_max_pronostico=38.0)
    print(f"Riesgo: {resultado['puntaje_riesgo']}% -> {resultado['etiqueta']}")
    print(f"Por qué: {resultado['mensaje_educativo']}")