"""
B.A.W.I. Riego - app para el agricultor (Streamlit).

Pide el diagnostico al backend (FastAPI) y lo muestra con:
- datos del clima y calculo FAO-56 (ET0, Kc, ETc)
- riesgo de estres del cultivo (motor difuso)
- "Aprende el Porque": la explicacion en lenguaje sencillo
- decision del agricultor: Aceptar / Ajustar / Rechazar

Ejecutar desde la raiz del proyecto (con la API corriendo):
    streamlit run apps/riego/app.py --server.port 8502
"""
import os
from datetime import datetime

import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv()
API_URL = os.getenv("API_URL", "http://localhost:8000")

CIUDADES = {
    "Delicias": "Delicias,MX",
    "Cuauhtémoc": "Cuauhtemoc,MX",
    "Camargo": "Camargo,MX",
    "Chihuahua": "Chihuahua,MX",
}
CULTIVOS = {"Nogal": "nogal", "Manzana": "manzana"}
ETAPAS = {
    "Inicial": "inicial",
    "Desarrollo": "desarrollo",
    "Media (máximo consumo)": "media",
    "Final": "final",
}
MOTIVOS_AJUSTE = ["Sección en mantenimiento", "Fertilización programada", "Limitación de agua en el pozo", "Otro"]
RAZONES_RECHAZO = ["Cosecha en curso", "Suelo saturado por lluvia", "Falla en el equipo de bombeo", "Otro"]
COLOR_RIESGO = {"BAJO": "green", "MODERADO": "orange", "CRÍTICO": "red"}

# Respuesta de ejemplo para presentar sin internet (mismo formato que la API)
REPORTE_DEMO = {
    "error": False,
    "clima_actual": {"temperatura_c": 33.0, "humedad_pct": 22, "viento_ms": 4.0, "descripcion": "cielo claro"},
    "calculos": {"et0_mm": 7.44, "kc_aplicado": 1.15, "etc_mm": 8.56},
    "diagnostico_ia": {
        "puntaje_riesgo": 53.7,
        "etiqueta": "MODERADO",
        "mensaje_educativo": "Déficit manejable. Puedes posponer el riego si tienes tareas de fertilización pendientes.",
        "recomendacion_mm": 8.56,
    },
    "metadata_app": {"cultivo": "nogal", "etapa": "media"},
}


def pedir_diagnostico(ciudad: str, cultivo: str, etapa: str) -> dict:
    """Llama al backend. Devuelve el reporte o {'error': True, 'mensaje': ...}."""
    try:
        resp = requests.post(
            f"{API_URL}/api/diagnostico",
            json={"ciudad": ciudad, "cultivo": cultivo, "etapa_actual": etapa},
            timeout=15,
        )
    except requests.exceptions.RequestException:
        return {"error": True, "mensaje": f"No se pudo conectar con el backend en {API_URL}. ¿Está corriendo la API?"}
    if resp.status_code != 200:
        try:
            detalle = resp.json().get("detail", resp.text)
        except ValueError:
            detalle = resp.text
        return {"error": True, "mensaje": f"El backend respondió {resp.status_code}: {detalle}"}
    return resp.json()


def registrar_decision(decision: str, horas: float, motivo: str = "") -> None:
    st.session_state.historial.append({
        "Fecha": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "Decisión": decision,
        "Horas": round(horas, 2),
        "Motivo": motivo,
    })


# --------------------------------------------------------------------------
# Pagina
# --------------------------------------------------------------------------
st.set_page_config(page_title="B.A.W.Í. Riego", page_icon="💧", layout="wide")
st.session_state.setdefault("historial", [])
st.session_state.setdefault("reporte", None)

st.title("💧 B.A.W.Í. Riego")
st.caption("Recomendación de riego explicada, para que decidas tú con información.")

with st.sidebar:
    st.header("Tu parcela")
    ciudad_txt = st.selectbox("Región", list(CIUDADES))
    cultivo_txt = st.selectbox("Cultivo", list(CULTIVOS))
    etapa_txt = st.selectbox("Etapa del cultivo", list(ETAPAS))
    tasa_mm_h = st.number_input(
        "Tasa de aplicación de tu sistema (mm/h)",
        min_value=0.5, max_value=20.0, value=3.0, step=0.5,
        help="Cuántos milímetros de agua aplica tu goteo o microaspersión en una hora.",
    )
    modo_demo = st.toggle("Modo demostración (sin internet)", value=False)
    calcular = st.button("Calcular recomendación", type="primary", width="stretch")

if calcular:
    if modo_demo:
        st.session_state.reporte = REPORTE_DEMO
    else:
        with st.spinner("Consultando el clima y calculando..."):
            st.session_state.reporte = pedir_diagnostico(
                CIUDADES[ciudad_txt], CULTIVOS[cultivo_txt], ETAPAS[etapa_txt]
            )

reporte = st.session_state.reporte
if reporte is None:
    st.info("Elige tu región, cultivo y etapa en el panel izquierdo y presiona **Calcular recomendación**.")
    st.stop()

if reporte.get("error"):
    st.error(reporte.get("mensaje", "Ocurrió un error."))
    st.caption("Puedes activar el modo demostración para presentar sin conexión.")
    st.stop()

clima = reporte["clima_actual"]
calc = reporte["calculos"]
diag = reporte["diagnostico_ia"]
lamina_mm = calc["etc_mm"]
horas = lamina_mm / tasa_mm_h

if modo_demo:
    st.warning("Mostrando datos de ejemplo (modo demostración).")

# --- Clima y calculo ---------------------------------------------------------
st.subheader(f"Clima actual en {ciudad_txt}")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Temperatura", f"{clima['temperatura_c']} °C")
c2.metric("Humedad", f"{clima['humedad_pct']} %")
c3.metric("Viento", f"{clima['viento_ms']} m/s")
c4.metric("Cielo", str(clima.get("descripcion", "")).capitalize())

st.subheader("Necesidad de agua de tu cultivo")
c1, c2, c3, c4 = st.columns(4)
c1.metric("ET₀ (referencia)", f"{calc['et0_mm']} mm/día")
c2.metric("Kc del cultivo", f"{calc['kc_aplicado']}")
c3.metric("ETc (tu cultivo)", f"{lamina_mm} mm/día")
c4.metric("Riego sugerido", f"{horas:.1f} h")

color = COLOR_RIESGO.get(diag["etiqueta"], "gray")
st.markdown(f"### Riesgo de estrés hídrico: :{color}[{diag['etiqueta']}] ({diag['puntaje_riesgo']}/100)")
st.write(diag["mensaje_educativo"])

# --- Aprende el Porque ---------------------------------------------------------
with st.expander("📘 Aprende el porqué", expanded=True):
    st.markdown(
        f"""
Hoy en **{ciudad_txt}** hay **{clima['temperatura_c']} °C**, **{clima['humedad_pct']} %** de humedad
y viento de **{clima['viento_ms']} m/s**. Con ese clima, un pasto de referencia pierde
**{calc['et0_mm']} mm** de agua al día entre evaporación del suelo y transpiración de las hojas (**ET₀**).

Tu **{cultivo_txt.lower()}** en etapa **{etapa_txt.lower()}** consume **{calc['kc_aplicado']} veces** esa
cantidad (coeficiente de cultivo **Kc**). Por eso necesita reponer
**{lamina_mm} mm** (**ETc = ET₀ × Kc**).

Tu sistema aplica **{tasa_mm_h} mm por hora**, así que reponer {lamina_mm} mm toma
**{horas:.1f} horas**. Regar más que eso lava nutrientes y gasta energía del pozo; regar menos deja
al cultivo en déficit.
"""
    )
    st.caption("Método: FAO-56 Penman-Monteith, estándar internacional para calcular el consumo de agua de los cultivos.")

# --- Decision del agricultor (human-in-the-loop) -----------------------------
st.subheader("¿Qué decides?")
tab_ok, tab_ajuste, tab_no = st.tabs(["✔ Aceptar", "✏ Ajustar horas", "✖ Rechazar"])

with tab_ok:
    st.write(f"Aplicar **{horas:.1f} horas** de riego hoy.")
    if st.button("Aceptar y aplicar", key="btn_aceptar"):
        registrar_decision("Aceptado", horas)
        st.success("Riego registrado. ¡Buena decisión!")

with tab_ajuste:
    horas_ajustadas = st.number_input("Horas que vas a regar", min_value=0.0, max_value=24.0,
                                      value=round(horas, 1), step=0.25)
    motivo = st.selectbox("Motivo del ajuste", MOTIVOS_AJUSTE)
    if st.button("Guardar ajuste", key="btn_ajustar"):
        registrar_decision("Ajustado", horas_ajustadas, motivo)
        st.success(f"Ajuste registrado: {horas_ajustadas} h ({motivo}).")

with tab_no:
    razon = st.selectbox("¿Por qué no riegas hoy?", RAZONES_RECHAZO)
    if st.button("Rechazar recomendación", key="btn_rechazar"):
        registrar_decision("Rechazado", 0.0, razon)
        st.info(f"Registrado: hoy no se riega ({razon}).")

if st.session_state.historial:
    st.subheader("Historial de decisiones")
    st.dataframe(st.session_state.historial, width="stretch", hide_index=True)