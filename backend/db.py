"""
Conexion a la base de datos de B.A.W.I. (SQL Server) con SQLAlchemy.

Los datos se leen del archivo .env:
    DB_SERVER=localhost\\SQLEXPRESS
    DB_NAME=bawi
    DB_DRIVER=ODBC Driver 18 for SQL Server
    DB_USER=        (vacio = entrar con el usuario de Windows)
    DB_PASSWORD=

Prueba rapida desde la raiz del proyecto:
    python -m backend.db
"""
import os
from urllib.parse import quote_plus

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

load_dotenv()


def _cadena_conexion() -> str:
    driver = os.getenv("DB_DRIVER", "ODBC Driver 18 for SQL Server")
    servidor = os.getenv("DB_SERVER", r"localhost\SQLEXPRESS")
    base = os.getenv("DB_NAME", "bawi")
    usuario = os.getenv("DB_USER", "")
    clave = os.getenv("DB_PASSWORD", "")

    partes = [
        f"DRIVER={{{driver}}}",
        f"SERVER={servidor}",
        f"DATABASE={base}",
        "TrustServerCertificate=yes",  # necesario con el Driver 18 en servidores locales
    ]
    if usuario:
        partes += [f"UID={usuario}", f"PWD={clave}"]
    else:
        partes.append("Trusted_Connection=yes")  # usuario de Windows
    return ";".join(partes)


engine = create_engine(
    "mssql+pyodbc:///?odbc_connect=" + quote_plus(_cadena_conexion()),
    pool_pre_ping=True,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def obtener_db():
    """Para FastAPI: abre una sesion por peticion y la cierra al terminar."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


if __name__ == "__main__":
    with engine.connect() as conexion:
        print("Conexion OK a", engine.url.render_as_string(hide_password=True)[:40], "...")
        filas = conexion.execute(
            text("SELECT c.clave, e.clave, e.kc FROM etapas_cultivo e "
                 "JOIN cultivos c ON c.id_cultivo = e.id_cultivo ORDER BY c.id_cultivo, e.orden")
        ).fetchall()
        for cultivo, etapa, kc in filas:
            print(f"  {cultivo:8} {etapa:11} Kc = {kc}")