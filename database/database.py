import os
import pyodbc
from dotenv import load_dotenv


load_dotenv()

def obtener_conexion():
    """Crea y retorna la conexión a SQL Server."""
    server = r'LUISMAPC\SQLEXPRESS'
    database = 'bawi'
    driver = '{ODBC Driver 17 for SQL Server}'
  
  
    cadena_conexion = f'DRIVER={driver};SERVER={server};DATABASE={database};Trusted_Connection=yes;TrustServerCertificate=yes;'
    return pyodbc.connect(cadena_conexion)

def obtener_datos_clima_reciente():
    """Extrae la temperatura y humedad más reciente de la base de datos."""
    conexion = obtener_conexion()
    cursor = conexion.cursor()
    
    try:
        # Obtenemos el registro climático más reciente
        consulta = """
            SELECT TOP 1 id_clima, temp_max_c, humedad_rel_pct, et0_mm 
            FROM clima_diario 
            ORDER BY fecha DESC;
        """
        cursor.execute(consulta)
        resultado = cursor.fetchone()
        return resultado # Retorna (id_clima, temp, humedad, et0)
    finally:
        cursor.close()
        conexion.close()

def guardar_recomendacion_riego(id_parcela, id_clima, et0, horas_calculadas):
    """Guarda el resultado del sistema difuso en la tabla recomendaciones_riego."""
    conexion = obtener_conexion()
    cursor = conexion.cursor()
    
    try:
        consulta = """
            INSERT INTO recomendaciones_riego 
            (id_parcela, id_clima, fecha, et0_mm, kc, etc_mm, lamina_neta_mm, horas_sugeridas, explicacion) 
            VALUES (?, ?, GETDATE(), ?, ?, ?, ?, ?, ?)
        """
        # Usamos valores ficticios para kc, etc_mm y lamina_neta_mm por ahora
        cursor.execute(consulta, (id_parcela, id_clima, et0, 1.10, 5.5, 4.2, horas_calculadas, 'Calculado con Lógica Difusa'))
        conexion.commit()
    finally:
        cursor.close()
        conexion.close()