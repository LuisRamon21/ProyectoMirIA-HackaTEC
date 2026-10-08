from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy.exc import SQLAlchemyError

from backend.db import engine
from backend.routers.capacitacion import router as capacitacion_router
from backend.routers.comunidad import MEDIA_DIR, router as comunidad_router
from backend.services import catalogo, registro_riego
from backend.services.clima import MUNICIPIOS, ClimaNoDisponible
from backend.services.orquestador import generar_diagnostico_riego

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


class SolicitudRiego(BaseModel):
    ciudad: str = Field(description="municipio de la parcela, ej. Delicias")
    cultivo: str
    etapa_actual: str
    tasa_mm_h: float = Field(gt=0, le=50, description="mm por hora que aplica el sistema de riego")
    superficie_ha: float = Field(gt=0, description="hectareas que riega el sistema")
    potencia_bomba_kw: float = Field(ge=0, description="potencia de la bomba del pozo en kW")
    horas_habituales: float = Field(ge=0, le=24, description="horas que el agricultor riega normalmente")
    latitud: float | None = Field(None, ge=-90, le=90, description="si no viene, se usa la de la parcela o el municipio")
    longitud: float | None = Field(None, ge=-180, le=180)
    id_parcela: int | None = Field(None, description="si viene, la recomendacion se guarda en la BD")


@app.post("/api/diagnostico")
def obtener_diagnostico(solicitud: SolicitudRiego):
    """
    Recibe los datos del cultivo desde Streamlit, consulta el clima real de la parcela,
    calcula FAO-56 y la logica difusa, y devuelve el reporte.
    """
    latitud, longitud = solicitud.latitud, solicitud.longitud
    try:
        with engine.connect() as conexion:
            if solicitud.id_parcela is not None and (latitud is None or longitud is None):
                parcela = registro_riego.obtener_parcela(conexion, solicitud.id_parcela)
                if parcela and parcela["latitud"] is not None and parcela["longitud"] is not None:
                    latitud, longitud = parcela["latitud"], parcela["longitud"]
            reporte = generar_diagnostico_riego(
                conexion,
                municipio=solicitud.ciudad,
                cultivo=solicitud.cultivo.strip().lower(),
                etapa_actual=solicitud.etapa_actual.strip().lower(),
                tasa_mm_h=solicitud.tasa_mm_h,
                superficie_ha=solicitud.superficie_ha,
                potencia_bomba_kw=solicitud.potencia_bomba_kw,
                horas_habituales=solicitud.horas_habituales,
                latitud=latitud,
                longitud=longitud,
            )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ClimaNoDisponible as e:
        raise HTTPException(status_code=503, detail=str(e))
    except SQLAlchemyError:
        raise HTTPException(status_code=503, detail=ERROR_BD)

    # Guardar en la BD solo si se indico la parcela. Si falla el guardado,
    # la recomendacion se muestra igual y se avisa.
    reporte["id_recomendacion"] = None
    if solicitud.id_parcela is not None:
        try:
            with engine.begin() as conexion:
                reporte["id_recomendacion"] = registro_riego.guardar_recomendacion(
                    conexion, solicitud.id_parcela, reporte
                )
        except SQLAlchemyError as e:
            reporte["aviso_bd"] = f"No se pudo guardar en la base de datos: {e.__class__.__name__}"
    return reporte


@app.get("/api/riego/cultivos")
def ver_cultivos():
    """Cultivos con sus etapas y Kc (tabla etapas_cultivo)."""
    try:
        with engine.connect() as conexion:
            return catalogo.cultivos_y_etapas(conexion)
    except SQLAlchemyError:
        raise HTTPException(status_code=503, detail=ERROR_BD)


@app.get("/api/riego/municipios")
def ver_municipios():
    return [{"clave": clave, "latitud": lat, "longitud": lon} for clave, (lat, lon) in MUNICIPIOS.items()]


@app.get("/")
async def health_check():
    return {"status": "ok", "mensaje": "B.A.W.Í. Backend operativo."}


# ---------------------------------------------------------------------------
# Riego: parcela, decision del productor e historial (base de datos)
# ---------------------------------------------------------------------------
class DecisionRiego(BaseModel):
    id_recomendacion: int
    decision: str = Field(description="aceptada, ajustada o rechazada")
    horas_aplicadas: float = Field(0.0, ge=0, le=24)
    motivo: str = ""


@app.get("/api/riego/parcelas/{id_parcela}")
def ver_parcela(id_parcela: int):
    with engine.connect() as conexion:
        parcela = registro_riego.obtener_parcela(conexion, id_parcela)
    if not parcela:
        raise HTTPException(status_code=404, detail="La parcela no existe.")
    return parcela


@app.post("/api/riego/decision")
def guardar_decision(datos: DecisionRiego):
    try:
        with engine.begin() as conexion:
            return registro_riego.registrar_decision(
                conexion, datos.id_recomendacion, datos.decision, datos.horas_aplicadas, datos.motivo
            )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/riego/historial/{id_parcela}")
def ver_historial(id_parcela: int, limite: int = 10):
    with engine.connect() as conexion:
        return registro_riego.historial(conexion, id_parcela, limite)