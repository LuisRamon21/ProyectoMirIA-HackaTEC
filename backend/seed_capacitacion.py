"""
Carga el contenido de Capacitacion de B.A.W.I. Comunidad.

- Dinamica 1 "Conoce una palabra": una tarjeta con un concepto y su explicacion sencilla.
  Se guarda como un quiz con tema 'palabra' (titulo = palabra, descripcion = explicacion).
- Dinamica 3 "Verdadero o falso": cuestionarios de 4 afirmaciones con explicacion y pista.
  Se guardan como quizzes con tema 'verdadero_falso', sus preguntas y las opciones V/F.

Requiere haber corrido antes database/migracion_d3_capacitacion.sql (columnas pista y ejemplo).
Si un contenido ya existe (mismo titulo y tema), no lo duplica: se puede correr varias veces.

Ejecutar desde la raiz del proyecto:
    python -m backend.seed_capacitacion
"""
from sqlalchemy import text

from backend.db import engine

PUNTOS_POR_ACIERTO = 5

# palabra, explicacion sencilla, ejemplo en campo
PALABRAS = [
    ("Caudal",
     "Cantidad de agua que pasa por un punto durante cierto tiempo. Se mide, por ejemplo, en litros por segundo.",
     "Si tu bomba entrega 30 litros por segundo, ese es su caudal. Con él se sabe cuántas horas hay que regar "
     "para aplicar el agua que necesita el cultivo."),
    ("Evapotranspiración",
     "Agua que se pierde al mismo tiempo por evaporación del suelo y por transpiración de la planta. "
     "Se mide en milímetros por día.",
     "En un día de calor, seco y con viento, el cultivo pierde mucha más agua que en un día fresco y nublado."),
    ("Coeficiente de cultivo (Kc)",
     "Número que ajusta la evapotranspiración de referencia a cada cultivo y a su etapa: ETc = ET0 × Kc.",
     "En B.A.W.Í. Riego, el nogal usa Kc 0.40 en su etapa inicial y 1.15 en su etapa de máximo consumo."),
    ("Lámina de riego",
     "Altura de agua que se aplica sobre el terreno, medida en milímetros.",
     "1 mm de lámina en una hectárea equivale a 10 m³ de agua (10,000 litros)."),
    ("Riego por goteo",
     "Sistema que entrega el agua poco a poco, gota a gota, cerca de la raíz de la planta.",
     "Como moja solo la zona de la raíz, se pierde menos agua por evaporación que regando por inundación."),
    ("Capacidad de campo",
     "Cantidad máxima de agua que el suelo puede retener después de que escurre el exceso.",
     "Regar por encima de ese punto solo manda el agua hacia abajo, lejos del alcance de la raíz."),
    ("Punto de marchitez",
     "Humedad del suelo tan baja que la planta ya no logra sacar agua y se marchita sin recuperarse.",
     "El riego busca que el suelo nunca se acerque a este punto, sobre todo en las etapas de mayor consumo."),
    ("Etapa fenológica",
     "Cada fase de desarrollo del cultivo, como la brotación, la floración o el llenado del fruto.",
     "B.A.W.Í. Riego te pide la etapa del cultivo porque cada una necesita una cantidad distinta de agua."),
    ("Estrés hídrico",
     "Situación en la que la planta recibe menos agua de la que necesita y frena su crecimiento para protegerse.",
     "Si el estrés llega en una etapa clave, como el llenado del fruto, puede bajar el tamaño y la calidad "
     "de la cosecha."),
    ("Lluvia efectiva",
     "Parte de la lluvia que realmente se queda en la zona de la raíz y que el cultivo puede aprovechar.",
     "Una lluvia ligera en un día caluroso se evapora casi toda: aporta poco aunque se haya mojado el suelo."),
]

# titulo, descripcion, [(afirmacion, es_verdadera, explicacion, pista)]
CUESTIONARIOS = [
    ("El agua y tu riego",
     "Afirmaciones básicas sobre fugas, horas de riego, lluvia y decisiones del productor.",
     [
         ("Una conexión que pierde agua puede causar desperdicio mientras funciona el riego.", True,
          "Conviene revisar las uniones y reparar las fugas para aprovechar mejor el agua.",
          "Piensa a dónde va el agua que sale por una unión rota: ¿llega a la raíz del cultivo?"),
         ("Todos los cultivos necesitan las mismas horas de riego.", False,
          "La recomendación depende del cultivo, su etapa, el clima y el caudal del sistema.",
          "Recuerda la palabra Kc: cambia con cada cultivo y con su etapa."),
         ("Si se pronostica lluvia, siempre debemos cancelar el riego.", False,
          "Hay que revisar cuánta lluvia se espera y cuánto puede aportar a la necesidad del cultivo.",
          "No toda la lluvia llega a la raíz. Importa cuánta cae, no solo que llueva."),
         ("El agricultor puede ajustar una recomendación y explicar su motivo.", True,
          "B.A.W.Í. propone y explica; el agricultor conserva la decisión.",
          "¿Quién conoce mejor su parcela: el programa o el productor?"),
     ]),
    ("Clima y necesidad del cultivo",
     "Cómo el clima y la etapa del cultivo cambian el agua que necesita.",
     [
         ("En un día caluroso y con viento, el cultivo pierde más agua que en un día fresco y nublado.", True,
          "El calor, el viento, el sol y el aire seco aumentan la evapotranspiración, por eso sube la necesidad "
          "de riego.",
          "Piensa en qué tan rápido se seca la ropa tendida en un día de calor con viento."),
         ("Regar de más siempre es mejor, porque así la planta guarda una reserva.", False,
          "El exceso de agua se va por debajo de la raíz, arrastra nutrientes, gasta energía de bombeo y puede "
          "dañar las raíces por falta de aire.",
          "Recuerda la palabra capacidad de campo: el suelo solo retiene cierta cantidad."),
         ("Un nogal en su etapa inicial necesita la misma agua que en su etapa de máximo consumo.", False,
          "En B.A.W.Í. el Kc del nogal pasa de 0.40 en la etapa inicial a 1.15 en la de máximo consumo: con el "
          "mismo clima, necesita casi el triple de agua.",
          "Las etapas fenológicas cambian el Kc del cultivo."),
         ("La evapotranspiración se mide en milímetros por día.", True,
          "Se expresa como la lámina de agua que se pierde cada día; así se puede comparar directo con la lluvia "
          "y con el riego.",
          "La lluvia y la lámina de riego también se miden en milímetros."),
     ]),
    ("Ahorro de agua y energía",
     "Cuentas sencillas para entender cuánto se ahorra al regar lo justo.",
     [
         ("Regar una hora menos, cuando no hace falta, también ahorra energía de la bomba.", True,
          "La bomba consume kWh por cada hora que funciona: evitar horas innecesarias ahorra agua y pago de luz.",
          "¿Qué está haciendo la bomba mientras dura el riego?"),
         ("Un milímetro de agua aplicado en una hectárea equivale a 10 metros cúbicos.", True,
          "Una hectárea mide 10,000 m²; por 0.001 m de lámina da 10 m³, es decir, 10,000 litros.",
          "1 hectárea = 10,000 m² y 1 mm = 0.001 m. Multiplica."),
         ("Con riego por aspersión, regar al mediodía en verano pierde menos agua que regar de madrugada.", False,
          "Al mediodía hay más calor, sol y viento, y una parte del agua se evapora antes de llegar al suelo; "
          "de madrugada se pierde menos.",
          "¿A qué hora del día se evapora más rápido un charco?"),
         ("Las recomendaciones de B.A.W.Í. Riego se calculan solo con la temperatura del día.", False,
          "Usan la temperatura, la humedad, el viento y la lluvia pronosticada, además del cultivo, su etapa (Kc) "
          "y el sistema de riego.",
          "Recuerda todos los datos que toma en cuenta la app de Riego."),
     ]),
]


def _id_quiz(conexion, titulo: str, tema: str):
    return conexion.execute(text("SELECT id_quiz FROM quizzes WHERE titulo = :t AND tema = :tema"),
                            {"t": titulo, "tema": tema}).scalar()


def cargar_palabras(conexion) -> int:
    nuevas = 0
    for palabra, explicacion, ejemplo in PALABRAS:
        if _id_quiz(conexion, palabra, "palabra"):
            continue
        conexion.execute(
            text("INSERT INTO quizzes (titulo, tema, descripcion, ejemplo, puntos_por_acierto, activo) "
                 "VALUES (:t, 'palabra', :d, :e, :p, 1)"),
            {"t": palabra, "d": explicacion, "e": ejemplo, "p": PUNTOS_POR_ACIERTO},
        )
        nuevas += 1
    return nuevas


def cargar_cuestionarios(conexion) -> int:
    nuevos = 0
    for titulo, descripcion, afirmaciones in CUESTIONARIOS:
        if _id_quiz(conexion, titulo, "verdadero_falso"):
            continue
        conexion.execute(
            text("INSERT INTO quizzes (titulo, tema, descripcion, puntos_por_acierto, activo) "
                 "VALUES (:t, 'verdadero_falso', :d, :p, 1)"),
            {"t": titulo, "d": descripcion, "p": PUNTOS_POR_ACIERTO},
        )
        id_quiz = _id_quiz(conexion, titulo, "verdadero_falso")
        for orden, (enunciado, es_verdadera, explicacion, pista) in enumerate(afirmaciones, start=1):
            conexion.execute(
                text("INSERT INTO preguntas (id_quiz, enunciado, explicacion, pista, orden) "
                     "VALUES (:q, :e, :x, :pista, :o)"),
                {"q": id_quiz, "e": enunciado, "x": explicacion, "pista": pista, "o": orden},
            )
            id_pregunta = conexion.execute(
                text("SELECT id_pregunta FROM preguntas WHERE id_quiz = :q AND orden = :o"),
                {"q": id_quiz, "o": orden},
            ).scalar()
            for texto_opcion, correcta in (("Verdadero", es_verdadera), ("Falso", not es_verdadera)):
                conexion.execute(
                    text("INSERT INTO opciones (id_pregunta, texto, es_correcta) VALUES (:p, :t, :c)"),
                    {"p": id_pregunta, "t": texto_opcion, "c": 1 if correcta else 0},
                )
        nuevos += 1
    return nuevos


if __name__ == "__main__":
    with engine.begin() as conexion:
        palabras = cargar_palabras(conexion)
        cuestionarios = cargar_cuestionarios(conexion)
        total_palabras = conexion.execute(text("SELECT COUNT(*) FROM quizzes WHERE tema = 'palabra'")).scalar()
        total_vf = conexion.execute(text("SELECT COUNT(*) FROM quizzes WHERE tema = 'verdadero_falso'")).scalar()
    print(f"Palabras nuevas: {palabras} (total {total_palabras})")
    print(f"Cuestionarios de verdadero o falso nuevos: {cuestionarios} (total {total_vf})")
    print("Listo. Capacitación tiene contenido.")