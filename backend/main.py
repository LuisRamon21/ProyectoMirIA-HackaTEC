from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import SQLAlchemyError

from backend.routers.capacitacion import router as capacitacion_router
from backend.routers.comunidad import MEDIA_DIR, router as comunidad_router
from backend.routers.riego import router as riego_router

app = FastAPI(
    title="API B.A.W.Í. Backend",
    description="Motor de cálculo y lógica difusa para ecosistema de capacitación agrícola",
    version="1.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# B.A.W.I. Riego, servicio de pago con sesion (backend/routers/riego.py)
app.include_router(riego_router)
# Rutas de B.A.W.I. Comunidad (backend/routers/comunidad.py)
app.include_router(comunidad_router)
# Capacitacion: dinamicas "Conoce una palabra" y "Verdadero o falso" (backend/routers/capacitacion.py)
app.include_router(capacitacion_router)


# Fotos y notas de voz de Comunidad: se sirven en /media/...
MEDIA_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/media", StaticFiles(directory=MEDIA_DIR), name="media")

ERROR_BD = "No se pudo conectar con la base de datos. Revisa que SQL Server esté encendido y los datos de .env."


@app.exception_handler(SQLAlchemyError)
def error_de_base_de_datos(_: Request, __: SQLAlchemyError):
    """Cualquier falla de SQL Server en cualquier ruta se responde con un mensaje claro."""
    return JSONResponse(status_code=503, content={"detail": ERROR_BD})


@app.get("/")
async def health_check():
    return {"status": "ok", "mensaje": "B.A.W.Í. Backend operativo."}
