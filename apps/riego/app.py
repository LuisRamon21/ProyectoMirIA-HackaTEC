"""
B.A.W.I. Riego - app para el agricultor (Streamlit).

Pide el diagnostico al backend (FastAPI) y lo muestra con:
- clima actual, pronostico de 24 h y calculo FAO-56 (ET0, Kc, ETc)
- riesgo de estres del cultivo y cuanto reponer segun la lluvia (motores difusos)
- horas de riego y ahorro de agua, energia y dinero (Tarifa 9-CU)
- "Aprende el Porque": la explicacion en lenguaje sencillo
- decision del agricultor: Aceptar / Ajustar / Rechazar (se guarda en la base de datos)
- historial de decisiones leido de la base de datos

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
ID_PARCELA = int(os.getenv("RIEGO_ID_PARCELA", "1"))  # parcela del productor de la demo

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


@st.cache_resource
def sesion_http() -> requests.Session:
    """Una sola conexion reutilizable hacia la API (keep-alive): cada clic es mas rapido."""
    return requests.Session()


def llamar_api(metodo: str, ruta: str, **kwargs) -> dict | list:
    """Llama al backend. Devuelve la respuesta o {'error': True, 'mensaje': ...}."""
    try:
        resp = sesion_http().request(metodo, f"{API_URL}{ruta}", timeout=15, **kwargs)
    except requests.exceptions.RequestException:
        return {"error": True, "mensaje": f"No se pudo conectar con el backend en {API_URL}. ¿Está corriendo la API?"}
    if resp.status_code != 200:
        try:
            detalle = resp.json().get("detail", resp.text)
        except ValueError:
            detalle = resp.text
        return {"error": True, "mensaje": f"El backend respondió {resp.status_code}: {detalle}"}
    return resp.json()


def es_error(respuesta) -> bool:
    return isinstance(respuesta, dict) and respuesta.get("error") is True


def cargar_parcela() -> dict | None:
    """Datos de la parcela guardados en la BD (una vez por sesion)."""
    if "parcela" not in st.session_state:
        respuesta = llamar_api("GET", f"/api/riego/parcelas/{ID_PARCELA}")
        st.session_state.parcela = None if es_error(respuesta) else respuesta
    return st.session_state.parcela


def registrar_decision(decision: str, horas: float, motivo: str = "") -> None:
    """Guarda la decision en la BD; si no hay recomendacion guardada, solo en la sesion."""
    id_rec = (st.session_state.reporte or {}).get("id_recomendacion")
    if id_rec:
        respuesta = llamar_api("POST", "/api/riego/decision", json={
            "id_recomendacion": id_rec, "decision": decision, "horas_aplicadas": horas, "motivo": motivo,
        })
        if es_error(respuesta):
            st.error(respuesta["mensaje"])
            return
        st.session_state.ultima_decision = respuesta
        st.session_state.historial_bd = None  # se vuelve a leer con la decision nueva
    else:
        st.session_state.historial.append({
            "fecha": datetime.now().strftime("%Y-%m-%d %H:%M"), "estado": decision,
            "horas_aplicadas": round(horas, 2), "motivo": motivo,
        })


# --------------------------------------------------------------------------
# Pagina
# --------------------------------------------------------------------------
st.set_page_config(page_title="B.A.W.Í. Riego", page_icon="💧", layout="wide")
st.session_state.setdefault("historial", [])  # solo se usa si no hay base de datos
st.session_state.setdefault("reporte", None)
st.session_state.setdefault("ultima_decision", None)
parcela = cargar_parcela()

st.title("💧 B.A.W.Í. Riego")
st.caption("Recomendación de riego explicada, para que decidas tú con información.")

def indice_de(opciones: dict, valor, por_defecto: int = 0) -> int:
    """Posicion de un valor guardado (ej. 'nogal') dentro de un selectbox."""
    valores = list(opciones.values())
    return valores.index(valor) if valor in valores else por_defecto


p = parcela or {}
with st.sidebar:
    if parcela:
        st.success(f"👨‍🌾 **{parcela['productor']}**  \n🌳 {parcela['nombre']}")
    else:
        st.warning("No se pudo cargar tu parcela de la base de datos. Llena los datos a mano.")

    # Formulario: mover un numero no recarga la pagina; todo se aplica al presionar "Calcular"
    with st.form("form_parcela", border=False):
        st.header("Tu parcela")
        ciudad_txt = st.selectbox("Región", list(CIUDADES), index=indice_de(CIUDADES, f"{p.get('municipio')},MX"))
        cultivo_txt = st.selectbox("Cultivo", list(CULTIVOS), index=indice_de(CULTIVOS, p.get("cultivo")))
        etapa_txt = st.selectbox("Etapa del cultivo", list(ETAPAS), index=indice_de(ETAPAS, p.get("etapa")))

        st.header("Tu sistema de riego")
        tasa_mm_h = st.number_input(
            "Tasa de aplicación (mm/h)", min_value=0.5, max_value=20.0, value=float(p.get("tasa_mm_h", 3.0)), step=0.5,
            help="Cuántos milímetros de agua aplica tu goteo o microaspersión en una hora.",
        )
        superficie_ha = st.number_input("Superficie que riegas (ha)", min_value=0.5, max_value=500.0,
                                        value=float(p.get("area_ha", 10.0)), step=0.5)
        potencia_kw = st.number_input(
            "Potencia de la bomba (kW)", min_value=1.0, max_value=300.0, value=float(p.get("potencia_bomba_kw", 45.0)),
            step=1.0, help="Viene en la placa del motor. 1 HP ≈ 0.75 kW.",
        )
        horas_habituales = st.number_input(
            "Horas que riegas normalmente al día", min_value=0.0, max_value=24.0,
            value=float(p.get("horas_riego_habitual", 4.0)), step=0.5,
            help="Con esto calculamos cuánto ahorras siguiendo la recomendación.",
        )

        modo_demo = st.toggle("Modo demostración (sin internet)", value=False,
                              help="Usa un clima de ejemplo. El backend debe estar corriendo.")
        calcular = st.form_submit_button("Calcular recomendación", type="primary", width="stretch")

if calcular:
    st.session_state.ultima_decision = None
    st.session_state.historial_bd = None
    with st.spinner("Consultando el clima y calculando..."):
        st.session_state.reporte = llamar_api("POST", "/api/diagnostico", json={
            "ciudad": CIUDADES[ciudad_txt],
            "cultivo": CULTIVOS[cultivo_txt],
            "etapa_actual": ETAPAS[etapa_txt],
            "tasa_mm_h": tasa_mm_h,
            "superficie_ha": superficie_ha,
            "potencia_bomba_kw": potencia_kw,
            "horas_habituales": horas_habituales,
            "modo_demo": modo_demo,
            "id_parcela": parcela["id_parcela"] if parcela else None,
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
if reporte.get("aviso_bd"):
    st.warning("La recomendación no se guardó en la base de datos; tus decisiones quedarán solo en esta sesión.")
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
        registrar_decision("aceptada", horas)

with tab_ajuste:
    horas_ajustadas = st.number_input("Horas que vas a regar", min_value=0.0, max_value=24.0,
                                      value=round(horas, 1), step=0.25)
    motivo = st.selectbox("Motivo del ajuste", MOTIVOS_AJUSTE)
    if st.button("Guardar ajuste", key="btn_ajustar"):
        registrar_decision("ajustada", horas_ajustadas, motivo)

with tab_no:
    razon = st.selectbox("¿Por qué no riegas hoy?", RAZONES_RECHAZO)
    if st.button("Rechazar recomendación", key="btn_rechazar"):
        registrar_decision("rechazada", 0.0, razon)

decision = st.session_state.ultima_decision
if decision:
    if decision["estado"] == "rechazada":
        st.info("Registrado: hoy no se riega. Quedó guardado en tu historial.")
    elif decision["agua_m3"] is not None and decision["agua_m3"] >= 0:
        st.success(
            f"Riego de {decision['horas_aplicadas']} h registrado ({decision['estado']}). "
            f"Hoy ahorras **{decision['agua_m3']:,.0f} m³** de agua, **{decision['energia_kwh']:,.1f} kWh** "
            f"y **${decision['dinero_mxn']:,.2f} MXN** frente a tu riego habitual."
        )
    else:
        st.success(f"Riego de {decision['horas_aplicadas']} h registrado ({decision['estado']}).")

# --- Historial (base de datos) ------------------------------------------------
ESTADOS = {"aceptada": "✔ Aceptada", "ajustada": "✏ Ajustada", "rechazada": "✖ Rechazada", "pendiente": "⏳ Pendiente"}
# El historial se pide una vez y se vuelve a pedir solo despues de calcular o decidir
if st.session_state.get("historial_bd") is None and parcela:
    respuesta = llamar_api("GET", f"/api/riego/historial/{parcela['id_parcela']}")
    st.session_state.historial_bd = [] if es_error(respuesta) else respuesta
historial = st.session_state.get("historial_bd") or []
filas = [
    {"Fecha": h["fecha"], "Sugeridas (h)": h["horas_sugeridas"], "Decisión": ESTADOS.get(h["estado"], h["estado"]),
     "Aplicadas (h)": h["horas_aplicadas"], "Motivo": h["motivo"] or "", "Agua ahorrada (m³)": h["agua_ahorrada_m3"],
     "Ahorro ($)": h["ahorro_mxn"]}
    for h in historial
] or [
    {"Fecha": h["fecha"], "Decisión": ESTADOS.get(h["estado"], h["estado"]),
     "Aplicadas (h)": h["horas_aplicadas"], "Motivo": h["motivo"]}
    for h in st.session_state.historial
]
if filas:
    st.subheader("Historial de decisiones")
    st.dataframe(filas, width="stretch", hide_index=True)