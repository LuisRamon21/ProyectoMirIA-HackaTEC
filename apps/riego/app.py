"""
B.A.W.I. Riego - app para el agricultor (Streamlit).

Pide el diagnostico al backend (FastAPI) y lo muestra con:
- clima actual, pronostico de 24 h y calculo FAO-56 (ET0, Kc, ETc)
- riesgo de estres del cultivo y cuanto reponer segun la lluvia (motores difusos)
- horas de riego y ahorro de agua, energia y dinero (Tarifa 9-CU)
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


def pedir_diagnostico(datos: dict) -> dict:
    """Llama al backend. Devuelve el reporte o {'error': True, 'mensaje': ...}."""
    try:
        resp = requests.post(f"{API_URL}/api/diagnostico", json=datos, timeout=15)
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

    st.header("Tu sistema de riego")
    tasa_mm_h = st.number_input(
        "Tasa de aplicación (mm/h)", min_value=0.5, max_value=20.0, value=3.0, step=0.5,
        help="Cuántos milímetros de agua aplica tu goteo o microaspersión en una hora.",
    )
    superficie_ha = st.number_input("Superficie que riegas (ha)", min_value=0.5, max_value=500.0, value=10.0, step=0.5)
    potencia_kw = st.number_input(
        "Potencia de la bomba (kW)", min_value=1.0, max_value=300.0, value=45.0, step=1.0,
        help="Viene en la placa del motor. 1 HP ≈ 0.75 kW.",
    )
    horas_habituales = st.number_input(
        "Horas que riegas normalmente al día", min_value=0.0, max_value=24.0, value=4.0, step=0.5,
        help="Con esto calculamos cuánto ahorras siguiendo la recomendación.",
    )

    modo_demo = st.toggle("Modo demostración (sin internet)", value=False,
                          help="Usa un clima de ejemplo. El backend debe estar corriendo.")
    calcular = st.button("Calcular recomendación", type="primary", width="stretch")

if calcular:
    with st.spinner("Consultando el clima y calculando..."):
        st.session_state.reporte = pedir_diagnostico({
            "ciudad": CIUDADES[ciudad_txt],
            "cultivo": CULTIVOS[cultivo_txt],
            "etapa_actual": ETAPAS[etapa_txt],
            "tasa_mm_h": tasa_mm_h,
            "superficie_ha": superficie_ha,
            "potencia_bomba_kw": potencia_kw,
            "horas_habituales": horas_habituales,
            "modo_demo": modo_demo,
        })

reporte = st.session_state.reporte
if reporte is None:
    st.info("Llena los datos de tu parcela en el panel izquierdo y presiona **Calcular recomendación**.")
    st.stop()

if reporte.get("error"):
    st.error(reporte.get("mensaje", "Ocurrió un error."))
    st.caption("Si no hay internet, activa el modo demostración (el backend debe seguir corriendo).")
    st.stop()

clima = reporte["clima_actual"]
pron = reporte["pronostico_24h"]
calc = reporte["calculos"]
diag = reporte["diagnostico_ia"]
riego = reporte["riego"]
ahorro = reporte["ahorro"]
horas = riego["horas"]

if reporte["metadata_app"].get("modo_demo"):
    st.warning("Mostrando clima de ejemplo (modo demostración).")
if not pron["disponible"]:
    st.warning("No se pudo obtener el pronóstico; la recomendación no descuenta lluvia.")

# --- Recomendacion principal ---------------------------------------------------
st.subheader("Recomendación de hoy")
c1, c2, c3 = st.columns(3)
c1.metric("Riego sugerido", f"{horas:.1f} h")
c2.metric("Lámina a reponer", f"{riego['lamina_mm']} mm")
c3.metric("Del déficit del día", f"{riego['factor_reposicion_pct']:.0f} %",
          help="Menos de 100 % cuando se espera lluvia.")

color = COLOR_RIESGO.get(diag["etiqueta"], "gray")
st.markdown(f"#### Riesgo de estrés hídrico si no riegas: :{color}[{diag['etiqueta']}] ({diag['puntaje_riesgo']}/100)")
st.write(diag["mensaje_educativo"])

# --- Ahorro ---------------------------------------------------------------------
st.subheader("Lo que ahorras frente a tu riego habitual")
if ahorro["horas_evitadas"] >= 0:
    c1, c2, c3 = st.columns(3)
    c1.metric("Agua no extraída", f"{ahorro['agua_m3']:,.0f} m³")
    c2.metric("Energía no consumida", f"{ahorro['energia_kwh']:,.1f} kWh")
    c3.metric("Dinero ahorrado hoy", f"${ahorro['dinero_mxn']:,.2f} MXN")
    st.caption(f"Comparado con regar {horas_habituales:g} h. Precio de energía: "
               f"${ahorro['precio_kwh_mxn']} por kWh (Tarifa 9-CU de CFE).")
else:
    st.info(f"Hoy tu cultivo necesita {-ahorro['horas_evitadas']:.1f} h más que tu riego habitual de "
            f"{horas_habituales:g} h. Regar de menos lo deja en déficit y baja el rendimiento.")

# --- Clima ----------------------------------------------------------------------
st.subheader(f"Clima en {ciudad_txt}")
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Temperatura", f"{clima['temperatura_c']} °C")
c2.metric("Humedad", f"{clima['humedad_pct']} %")
c3.metric("Viento", f"{clima['viento_ms']} m/s")
c4.metric("Máxima próximas 24 h", f"{pron['temp_max_c']} °C")
c5.metric("Prob. de lluvia 24 h", f"{pron['prob_lluvia_pct']} %")

# --- Aprende el Porque ---------------------------------------------------------
if pron["prob_lluvia_pct"] > 0:
    texto_lluvia = (
        f"El pronóstico da **{pron['prob_lluvia_pct']} %** de probabilidad de lluvia en las próximas 24 horas "
        f"(**{pron['lluvia_mm']} mm** esperados). Por eso conviene reponer solo el "
        f"**{riego['factor_reposicion_pct']:.0f} %** del déficit: **{riego['lamina_mm']} mm**. "
        "Si la lluvia llega, completa el resto sin que pagues el bombeo."
    )
else:
    texto_lluvia = "No se espera lluvia en las próximas 24 horas, así que conviene reponer el déficit completo."

with st.expander("📘 Aprende el porqué", expanded=True):
    st.markdown(
        f"""
**1. Cuánta agua se pierde.** Hoy en **{ciudad_txt}** hay **{clima['temperatura_c']} °C**,
**{clima['humedad_pct']} %** de humedad y viento de **{clima['viento_ms']} m/s**. Con ese clima, un pasto de
referencia pierde **{calc['et0_mm']} mm** de agua al día entre evaporación del suelo y transpiración de las
hojas (**ET₀**).

**2. Cuánto consume tu cultivo.** Tu **{cultivo_txt.lower()}** en etapa **{etapa_txt.lower()}** consume
**{calc['kc_aplicado']} veces** esa cantidad (coeficiente de cultivo **Kc**): **{calc['etc_mm']} mm**
(**ETc = ET₀ × Kc**).

**3. La lluvia.** {texto_lluvia}

**4. Cuánto tiempo regar.** Tu sistema aplica **{tasa_mm_h} mm por hora**, así que reponer
{riego['lamina_mm']} mm toma **{horas:.1f} horas**. Regar más lava nutrientes y gasta energía del pozo;
regar menos deja al cultivo en déficit.
"""
    )
    st.caption("Método: FAO-56 Penman-Monteith, estándar internacional para calcular el consumo de agua "
               "de los cultivos, con lógica difusa para el riesgo y el ajuste por lluvia.")

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