from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Importamos el Orquestador que ya validamos
from backend.services.orquestador import generar_diagnostico_riego

# NUEVO: Importamos la función para guardar en SQL Server desde tu archivo database.py
from database import guardar_recomendacion_riego

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
    # En el futuro puedes agregar 'id_parcela: int' aquí
    ciudad: str
    cultivo: str
    etapa_actual: str

@app.post("/api/diagnostico")
async def obtener_diagnostico(solicitud: SolicitudRiego):
    """
    Recibe los datos del cultivo desde Streamlit, procesa el clima, 
    las matemáticas (FAO-56) y la lógica difusa, y guarda el reporte en SQL Server.
    """
    try:
        # 1. El orquestador hace la magia (Lógica Difusa + Matemáticas)
        reporte = generar_diagnostico_riego(
            ciudad=solicitud.ciudad,
            cultivo=solicitud.cultivo.lower(),
            etapa_actual=solicitud.etapa_actual.lower()
        )

        if reporte.get("error"):
            raise HTTPException(status_code=503, detail=reporte["mensaje"])
            
        # 2. NUEVO: Guardar en la base de datos SQL Server
        # Extraemos los valores calculados por tu orquestador
        horas_calculadas = reporte.get("horas_sugeridas", 0)
        et0_calculado = reporte.get("et0", 0.0) 
        
        # Asignamos IDs temporales para la prueba (Luego pueden venir en 'solicitud')
        id_parcela_prueba = 1 
        id_clima_prueba = 1   

        # Disparamos la función que guarda la fila en la tabla 'recomendaciones_riego'
        guardar_recomendacion_riego(
            id_parcela=id_parcela_prueba, 
            id_clima=id_clima_prueba, 
            et0=et0_calculado, 
            horas_calculadas=horas_calculadas
        )

        # 3. Devolver la respuesta a Streamlit
        return reporte

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno del servidor: {str(e)}")

@app.get("/")
async def health_check():
    return {"status": "ok", "mensaje": "B.A.W.Í. Backend operativo."}