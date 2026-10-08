from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

# Importamos el Orquestador que ya validamos
from backend.services.orquestador import generar_diagnostico_riego
from backend.db import engine
from backend.services import registro_riego
from backend.routers.comunidad import MEDIA_DIR, router as comunidad_router
# 1. Inicializar la aplicación FastAPI
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


# Fotos y notas de voz de Comunidad: se sirven en /media/...
MEDIA_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/media", StaticFiles(directory=MEDIA_DIR), name="media")

class SolicitudRiego(BaseModel):
    ciudad: str
    cultivo: str
    etapa_actual: str
    tasa_mm_h: float = Field(3.0, gt=0, description="mm por hora que aplica el sistema de riego")
    superficie_ha: float = Field(1.0, gt=0, description="hectareas que riega el sistema")
    potencia_bomba_kw: float = Field(45.0, ge=0, description="potencia de la bomba del pozo en kW")
    horas_habituales: float = Field(4.0, ge=0, description="horas que el agricultor riega normalmente")
    modo_demo: bool = Field(False, description="usa clima de ejemplo, sin internet")
    id_parcela: int | None = Field(None, description="si viene, la recomendacion se guarda en la BD")


@app.post("/api/diagnostico")
async def obtener_diagnostico(solicitud: SolicitudRiego):
    """
    Recibe los datos del cultivo desde Streamlit, procesa el clima, 
    las matemáticas (FAO-56) y la lógica difusa, y devuelve el reporte.
    """
    try:

        reporte = generar_diagnostico_riego(
            ciudad=solicitud.ciudad,
            cultivo=solicitud.cultivo.lower(),
            etapa_actual=solicitud.etapa_actual.lower(),
            tasa_mm_h=solicitud.tasa_mm_h,
            superficie_ha=solicitud.superficie_ha,
            potencia_bomba_kw=solicitud.potencia_bomba_kw,
            horas_habituales=solicitud.horas_habituales,
            modo_demo=solicitud.modo_demo,
        )


        if reporte.get("error"):
            raise HTTPException(status_code=503, detail=reporte["mensaje"])

        # Guardar en la BD solo si se indico la parcela. Si la BD falla,
        # la recomendacion se muestra igual (no se cae la demo).
        reporte["id_recomendacion"] = None
        if solicitud.id_parcela is not None:
            try:
                with engine.begin() as conexion:
                    reporte["id_recomendacion"] = registro_riego.guardar_recomendacion(
                        conexion, solicitud.id_parcela, solicitud.ciudad.split(",")[0], reporte
                    )
            except Exception as e:
                reporte["aviso_bd"] = f"No se pudo guardar en la base de datos: {e}"

        return reporte
    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno del servidor: {str(e)}")


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