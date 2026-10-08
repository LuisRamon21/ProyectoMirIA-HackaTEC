from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# Importamos el Orquestador que ya validamos
from backend.services.orquestador import generar_diagnostico_riego

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


class SolicitudRiego(BaseModel):
    ciudad: str
    cultivo: str
    etapa_actual: str
    tasa_mm_h: float = Field(3.0, gt=0, description="mm por hora que aplica el sistema de riego")
    superficie_ha: float = Field(1.0, gt=0, description="hectareas que riega el sistema")
    potencia_bomba_kw: float = Field(45.0, ge=0, description="potencia de la bomba del pozo en kW")
    horas_habituales: float = Field(4.0, ge=0, description="horas que el agricultor riega normalmente")
    modo_demo: bool = Field(False, description="usa clima de ejemplo, sin internet")


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
            
        return reporte
    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno del servidor: {str(e)}")


@app.get("/")
async def health_check():
    return {"status": "ok", "mensaje": "B.A.W.Í. Backend operativo."}