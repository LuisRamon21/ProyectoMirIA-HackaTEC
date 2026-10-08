"""
Rutas de B.A.W.I. Riego.

Se entra con la misma cuenta de Comunidad (POST /api/comunidad/login) y la app manda
la cabecera  Authorization: Bearer <token>. Cada productor solo ve y cambia sus
propias parcelas, recomendaciones e historial.
"""
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.exc import SQLAlchemyError

from backend.db import engine
from backend.routers.comunidad import usuario_actual
from backend.services import catalogo, registro_riego
from backend.services.clima import MUNICIPIOS, ClimaNoDisponible, normalizar_municipio
from backend.services.orquestador import generar_diagnostico_riego

router = APIRouter(prefix="/api/riego", tags=["Riego"])


def _mi_parcela(conexion, id_parcela: int, yo: dict) -> dict:
    parcela = registro_riego.obtener_parcela(conexion, id_parcela)
    if not parcela or parcela["id_usuario"] != yo["id_usuario"]:
        raise HTTPException(status_code=404, detail="La parcela no existe o no es tuya.")
    return parcela


# ---------------------------------------------------------------------------
# Catalogos (sin sesion: llenan los formularios)
# ---------------------------------------------------------------------------
@router.get("/cultivos")
def ver_cultivos():
    """Cultivos con sus etapas y Kc (tabla etapas_cultivo)."""
    with engine.connect() as conexion:
        return catalogo.cultivos_y_etapas(conexion)


@router.get("/municipios")
def ver_municipios():
    return [{"clave": clave, "latitud": lat, "longitud": lon} for clave, (lat, lon) in MUNICIPIOS.items()]


# ---------------------------------------------------------------------------
# Parcelas del productor
# ---------------------------------------------------------------------------
class DatosParcela(BaseModel):
    nombre: str = Field(min_length=2, max_length=60)
    municipio: str = Field(min_length=2, max_length=60)
    cultivo: str
    etapa: str
    area_ha: float = Field(gt=0, le=100_000, description="hectareas que riega el sistema")
    sistema: str = Field(pattern="^(goteo|microaspersion)$")
    tasa_mm_h: float = Field(gt=0, le=50, description="mm por hora que aplica el sistema de riego")
    potencia_bomba_kw: float = Field(gt=0, le=5_000, description="potencia de la bomba del pozo en kW")
    horas_riego_habitual: float = Field(ge=0, le=24, description="horas que riega normalmente al dia")
    latitud: float | None = Field(None, ge=-90, le=90)
    longitud: float | None = Field(None, ge=-180, le=180)

    @model_validator(mode="after")
    def _ubicacion(self):
        self.nombre = self.nombre.strip()
        self.municipio = normalizar_municipio(self.municipio)
        self.cultivo = self.cultivo.strip().lower()
        self.etapa = self.etapa.strip().lower()
        if (self.latitud is None) != (self.longitud is None):
            raise ValueError("Indica latitud y longitud juntas, o ninguna.")
        if self.latitud is None and self.municipio not in MUNICIPIOS:
            raise ValueError(f"Para el municipio {self.municipio} indica la latitud y longitud de la parcela.")
        return self


@router.get("/parcelas")
def mis_parcelas(authorization: str | None = Header(None)):
    yo = usuario_actual(authorization)
    with engine.connect() as conexion:
        return registro_riego.parcelas_de_usuario(conexion, yo["id_usuario"])


@router.post("/parcelas")
def registrar_parcela(datos: DatosParcela, authorization: str | None = Header(None)):
    yo = usuario_actual(authorization)
    try:
        with engine.begin() as conexion:
            return registro_riego.crear_parcela(conexion, yo["id_usuario"], datos.model_dump())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/parcelas/{id_parcela}")
def editar_parcela(id_parcela: int, datos: DatosParcela, authorization: str | None = Header(None)):
    yo = usuario_actual(authorization)
    try:
        with engine.begin() as conexion:
            _mi_parcela(conexion, id_parcela, yo)
            return registro_riego.actualizar_parcela(conexion, id_parcela, datos.model_dump())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ---------------------------------------------------------------------------
# Recomendacion del dia, decision del productor e historial
# ---------------------------------------------------------------------------
@router.post("/parcelas/{id_parcela}/diagnostico")
def diagnostico(id_parcela: int, authorization: str | None = Header(None)):
    """
    Calcula la recomendacion de hoy con los datos guardados de la parcela y el clima
    real de su ubicacion (FAO-56 + logica difusa), y la guarda en la base de datos.
    """
    yo = usuario_actual(authorization)
    try:
        with engine.connect() as conexion:
            parcela = _mi_parcela(conexion, id_parcela, yo)
            reporte = generar_diagnostico_riego(
                conexion,
                municipio=parcela["municipio"],
                cultivo=parcela["cultivo"],
                etapa_actual=parcela["etapa"],
                tasa_mm_h=parcela["tasa_mm_h"],
                superficie_ha=parcela["area_ha"],
                potencia_bomba_kw=parcela["potencia_bomba_kw"],
                horas_habituales=parcela["horas_riego_habitual"],
                latitud=parcela["latitud"],
                longitud=parcela["longitud"],
            )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ClimaNoDisponible as e:
        raise HTTPException(status_code=503, detail=str(e))

    # Si falla el guardado, la recomendacion se muestra igual y se avisa
    reporte["id_recomendacion"] = None
    try:
        with engine.begin() as conexion:
            reporte["id_recomendacion"] = registro_riego.guardar_recomendacion(conexion, id_parcela, reporte)
    except SQLAlchemyError as e:
        reporte["aviso_bd"] = f"No se pudo guardar en la base de datos: {e.__class__.__name__}"
    return reporte


class DecisionRiego(BaseModel):
    id_recomendacion: int
    decision: str = Field(description="aceptada, ajustada o rechazada")
    horas_aplicadas: float = Field(0.0, ge=0, le=24)
    motivo: str = Field("", max_length=120)


@router.post("/decision")
def guardar_decision(datos: DecisionRiego, authorization: str | None = Header(None)):
    yo = usuario_actual(authorization)
    try:
        with engine.begin() as conexion:
            id_parcela = registro_riego.parcela_de_recomendacion(conexion, datos.id_recomendacion)
            if id_parcela is None:
                raise HTTPException(status_code=404, detail="La recomendación no existe.")
            _mi_parcela(conexion, id_parcela, yo)
            return registro_riego.registrar_decision(
                conexion, datos.id_recomendacion, datos.decision, datos.horas_aplicadas, datos.motivo
            )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/parcelas/{id_parcela}/historial")
def ver_historial(id_parcela: int, limite: int = 10, authorization: str | None = Header(None)):
    yo = usuario_actual(authorization)
    with engine.connect() as conexion:
        _mi_parcela(conexion, id_parcela, yo)
        return registro_riego.historial(conexion, id_parcela, min(max(limite, 1), 100))
