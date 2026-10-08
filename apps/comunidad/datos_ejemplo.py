"""
Datos de ejemplo para construir la interfaz de B.A.W.I. Comunidad
mientras la base de datos esta lista.

Tienen la misma forma que las tablas (usuarios, publicaciones, respuestas),
asi que despues solo cambiamos de donde se leen.
"""

USUARIOS = {
    1: {"id": 1, "usuario": "don_ramiro", "nombre": "Ramiro Chávez", "region": "Delicias", "es_riego": True},
    2: {"id": 2, "usuario": "sofia_campo", "nombre": "Sofía Licón", "region": "Delicias", "es_riego": False},
    3: {"id": 3, "usuario": "nuevo_juan", "nombre": "Juan Pérez", "region": "Cuauhtémoc", "es_riego": False},
}

PUBLICACIONES = [
    {
        "id": 1,
        "autor_id": 3,
        "titulo": "¿Cuántas horas regar el manzano después de la cosecha?",
        "texto": "Ya cosechamos y no sé si seguir regando igual. Tengo goteo y riego 4 horas diarias como en verano.",
        "categoria": "riego",
        "foto": None,
        "audio": None,
        "fecha": "2026-10-06 14:00",
        "respuestas": [
            {
                "id": 1,
                "autor_id": 1,
                "texto": "Después de la cosecha el árbol consume mucho menos. Baja el riego poco a poco, no de golpe.",
                "audio": None,
                "dato_riego": None,
                "fecha": "2026-10-06 15:10",
            },
        ],
    },
    {
        "id": 2,
        "autor_id": 2,
        "titulo": "Hojas pequeñas y amarillentas en algunos nogales",
        "texto": "En una parte de la huerta los brotes nuevos salen con hojas chicas y amarillentas. ¿Falta agua o algún nutriente?",
        "categoria": "cultivo",
        "foto": None,
        "audio": None,
        "fecha": "2026-10-07 09:30",
        "respuestas": [],
    },
]