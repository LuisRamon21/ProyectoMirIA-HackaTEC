from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

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
            etapa_actual=solicitud.etapa_actual.lower()
        )


        if reporte.get("error"):
            raise HTTPException(status_code=503, detail=reporte["mensaje"])
            
        return reporte

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno del servidor: {str(e)}")


@app.get("/")
async def health_check():
    return {"status": "ok", "mensaje": "B.A.W.Í. Backend operativo."}