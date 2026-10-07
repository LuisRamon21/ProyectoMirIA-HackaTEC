import numpy as np
import skfuzzy as fuzz
from skfuzzy import control as ctrl

def motor_de_riego_difuso(deficit_calculado_mm, prob_lluvia_api_pct):
    
# Definición de las variables
# Entradas de los datos
deficit = ctrl.Antecedent(np.arange(0, 16, 0.1), 'deficit_hidrico')
lluvia = ctrl.Antecedent(np.arange(0,101,1), 'probabilidad_lluvia')

#Salida de los datos 
riego = ctrl.Consequent(np.arange(0, 121, 1), 'tiempo_riego')


# Fuzzificación 
deficit.automf(names:=['bajo','normal','critico'])
lluvia.automf(names:=['nula','ligera','tormenta'])

#Definición manual de las funciones para la salidad de los datos
riego['cero']= fuzz.trimf(riego.universe, [0, 0, 10])
riego['moderado'] = fuzz.trimf(riego.universe,[20, 60, 90])
riego['abundante'] = fuzz.trimf(riego.universe[80,120,120])

# Base de reglas
regla1 = ctrl.Rule(deficit['critico'] & lluvia ['tormenta'], riego['cero']) #Si hace falta mucha agua, pero se aproxima una tormenta, el riego es igual a cero
regla2 = ctrl.Rule(deficit['normal'] & lluvia ['nula'], riego['moderado']) # Si el déficit es normal, pero la lluvia es nula, el riego es igual a moderado
regla3 = ctrl.Rule(deficit['bajo'] & lluvia ['ligera'], riego['abundante'])# Si el déficit es bajol, pero la lluvia el ligera, el riego es igual a abundante

sistema_ctrl = ctrl.ControlSystem([regla1, regla2, regla3])
simulador = ctrl.ControlSystemSimulation(sistema_ctrl)

# Ingreso de los datos verídicos
simualador.input['deficit_hidrico'] = deficit_calculado_mm
simualador.input['probabilidad_lluvia'] = prob_lluvia_api_pct

simualador.compute()

return round(simulador.output['tiempo_riego'], 2)


tiempo = motor_de_riego_difuso(deficit_calculado_mm=12.5, prob_lluvia_api_pct=95.0)

print (f"El tiempo de riego calculado es: {tiempo} minutos")

