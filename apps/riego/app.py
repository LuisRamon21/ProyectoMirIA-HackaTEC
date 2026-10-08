"""
B.A.W.I. Riego - app para el agricultor (Streamlit).

- Iniciar sesion (misma cuenta que Comunidad) o crear cuenta con codigo al correo
- Boton para abrir Comunidad con la misma sesion
- El productor registra sus parcelas (cultivo, etapa, sistema de riego, bomba...) y las edita
- Recomendacion del dia con el clima real de la parcela (Open-Meteo), FAO-56 (ET0, Kc, ETc),
  riesgo de estres y cuanto reponer segun la lluvia (motores difusos)
- Horas de riego y ahorro de agua, energia y dinero (Tarifa 9-CU)
- "Aprende el Porque": la explicacion en lenguaje sencillo
- Decision del agricultor: Aceptar / Ajustar / Rechazar e historial (base de datos)

Ejecutar desde la raiz del proyecto (con la API corriendo):
    streamlit run apps/riego/app.py --server.port 8502
"""
import os

import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv()
API_URL = os.getenv("API_URL", "http://localhost:8000")
COMUNIDAD_URL = os.getenv("COMUNIDAD_URL", "http://localhost:8503").rstrip("/")

# Nombre que se muestra -> clave del municipio en el backend (backend/services/clima.py)
CIUDADES = {
    "Delicias": "Delicias",
    "Cuauhtémoc": "Cuauhtemoc",
    "Camargo": "Camargo",
    "Chihuahua": "Chihuahua",
}
SISTEMAS = {"Goteo": "goteo", "Microaspersión": "microaspersion"}
MOTIVOS_AJUSTE = ["Sección en mantenimiento", "Fertilización programada", "Limitación de agua en el pozo", "Otro"]
RAZONES_RECHAZO = ["Cosecha en curso", "Suelo saturado por lluvia", "Falla en el equipo de bombeo", "Otro"]
COLOR_RIESGO = {"BAJO": "green", "MODERADO": "orange", "CRÍTICO": "red"}
ESTADOS = {"aceptada": "✔ Aceptada", "ajustada": "✏ Ajustada", "rechazada": "✖ Rechazada", "pendiente": "⏳ Pendiente"}


# --------------------------------------------------------------------------
# Conexion con la API
# --------------------------------------------------------------------------
@st.cache_resource
def sesion_http() -> requests.Session:
    """Una sola conexion reutilizable hacia la API (keep-alive): cada clic es mas rapido."""
    return requests.Session()


def llamar_api(metodo: str, ruta: str, **kwargs):
    """Regresa (True, datos) o (False, mensaje de error para mostrar)."""
    headers = kwargs.pop("headers", {})
    if st.session_state.get("token"):
        headers["Authorization"] = f"Bearer {st.session_state.token}"
    try:
        resp = sesion_http().request(metodo, f"{API_URL}{ruta}", headers=headers, timeout=20, **kwargs)
    except requests.exceptions.RequestException:
        return False, f"No se pudo conectar con el servidor ({API_URL}). ¿Está corriendo la API?"
    if resp.status_code == 200:
        return True, resp.json()
    try:
        detalle = resp.json().get("detail", resp.text)
    except ValueError:
        detalle = resp.text
    if isinstance(detalle, list):  # errores de validacion de FastAPI
        detalle = " ".join(str(e.get("msg", "")).removeprefix("Value error, ") for e in detalle)
    if resp.status_code == 401 and st.session_state.get("token"):
        cerrar_sesion()  # la sesion ya no es valida
    return False, detalle


def iniciar_sesion(datos: dict) -> None:
    st.session_state.token = datos["token"]
    st.session_state.usuario = datos["usuario"]


def cerrar_sesion() -> None:
    for clave in ("token", "usuario", "parcelas", "id_parcela", "reporte", "ultima_decision", "historial_bd",
                  "nueva_parcela"):
        st.session_state[clave] = None


def requiere_codigo() -> bool:
    """Si la API pide el codigo del correo al crear cuenta (depende de si tiene correo configurado)."""
    ok, datos = llamar_api("GET", "/api/comunidad/registro/verificacion")
    return datos["requiere_codigo"] if ok else True


def limpiar_resultado() -> None:
    st.session_state.reporte = None
    st.session_state.ultima_decision = None
    st.session_state.historial_bd = None


def indice_de(opciones: dict, valor, por_defecto: int = 0) -> int:
    """Posicion de un valor guardado (ej. 'nogal') dentro de un selectbox."""
    valores = list(opciones.values())
    return valores.index(valor) if valor in valores else por_defecto


# --------------------------------------------------------------------------
# Acceso: iniciar sesion y crear cuenta
# --------------------------------------------------------------------------
def pantalla_acceso() -> None:
    _, centro, _ = st.columns([1, 2, 1])
    with centro:
        st.title("💧 B.A.W.Í. Riego")
        st.caption("Recomendación de riego explicada, para que decidas tú con información.")
        if st.session_state.registro:
            pantalla_codigo()
        elif st.session_state.vista_acceso == "crear":
            pantalla_crear_cuenta()
        else:
            pantalla_entrar()


def pantalla_entrar() -> None:
    st.subheader("Iniciar sesión")
    st.caption("Usa la misma cuenta de B.A.W.Í. Comunidad.")
    with st.form("form_entrar", border=False):
        correo = st.text_input("Correo electrónico o usuario")
        password = st.text_input("Contraseña", type="password")
        entrar = st.form_submit_button("Iniciar sesión", type="primary", width="stretch")
    if entrar:
        ok, datos = llamar_api("POST", "/api/comunidad/login", json={"correo": correo, "password": password})
        if ok:
            iniciar_sesion(datos)
            st.rerun()
        st.error(datos)
    st.divider()
    st.caption("¿No tienes una cuenta?")
    if st.button("Crear cuenta", width="stretch"):
        st.session_state.vista_acceso = "crear"
        st.rerun()


def pantalla_crear_cuenta() -> None:
    st.subheader("Crear cuenta")
    con_codigo = requiere_codigo()
    st.caption("Paso 1 de 2 · Te enviaremos un código a tu correo para confirmar que es tuyo."
               if con_codigo else "Llena tus datos para crear tu cuenta.")
    with st.form("form_crear", border=False):
        nombre = st.text_input("Nombre completo")
        correo = st.text_input("Correo electrónico", placeholder="tu@correo.com")
        municipio = st.selectbox("Municipio de tu parcela", list(CIUDADES))
        password = st.text_input("Contraseña (mínimo 6)", type="password")
        confirmacion = st.text_input("Confirma tu contraseña", type="password")
        crear = st.form_submit_button("Enviarme el código" if con_codigo else "Crear cuenta",
                                      type="primary", width="stretch")
    if crear:
        if password != confirmacion:
            st.error("Las contraseñas no coinciden.")
        else:
            with st.spinner("Enviando el código a tu correo..." if con_codigo else "Creando tu cuenta..."):
                ok, datos = llamar_api("POST", "/api/comunidad/registro/solicitar", json={
                    "nombre": nombre, "correo": correo, "municipio": municipio,
                    "password": password, "confirmacion": confirmacion,
                })
            if ok and "token" in datos:  # sin correo configurado la cuenta se crea de una vez
                st.session_state.vista_acceso = "entrar"
                iniciar_sesion(datos)
                st.rerun()
            if ok:
                st.session_state.registro = datos
                st.rerun()
            st.error(datos)
    st.divider()
    if st.button("Ya tengo cuenta", width="stretch"):
        st.session_state.vista_acceso = "entrar"
        st.rerun()


def pantalla_codigo() -> None:
    registro = st.session_state.registro
    st.subheader("Escribe tu código")
    st.caption(f"Paso 2 de 2 · Enviamos un código de 6 números a **{registro['correo']}**. "
               f"Vence en {registro['minutos']} minutos. Si no lo ves, revisa la carpeta de spam.")
    with st.form("form_codigo", border=False):
        codigo = st.text_input("Código de verificación", max_chars=6, placeholder="000000")
        verificar = st.form_submit_button("Verificar y crear cuenta", type="primary", width="stretch")
    if verificar:
        ok, datos = llamar_api("POST", "/api/comunidad/registro/verificar",
                               json={"correo": registro["correo"], "codigo": codigo.strip()})
        if ok:
            st.session_state.registro = None
            st.session_state.vista_acceso = "entrar"
            iniciar_sesion(datos)
            st.rerun()
        st.error(datos)
    if st.button("Reenviar código", width="stretch"):
        ok, datos = llamar_api("POST", "/api/comunidad/registro/reenviar", json={"correo": registro["correo"]})
        if ok:
            st.session_state.registro = datos
            st.success("Te enviamos un código nuevo. El anterior ya no sirve.")
        else:
            st.warning(datos)
    if st.button("Usar otro correo", width="stretch"):
        st.session_state.registro = None
        st.rerun()


# --------------------------------------------------------------------------
# Parcelas
# --------------------------------------------------------------------------
def formulario_parcela(parcela: dict, cultivos: dict, etapas: dict, clave: str, boton: str) -> dict | None:
    """Campos de la parcela. Regresa los datos cuando se presiona el boton."""
    with st.form(clave, border=False):
        nombre = st.text_input("Nombre de la parcela", value=parcela.get("nombre", ""), max_chars=60,
                               placeholder="Ej. Huerta El Nogalito")
        ciudad_txt = st.selectbox("Municipio", list(CIUDADES), index=indice_de(CIUDADES, parcela.get("municipio")))
        cultivo_txt = st.selectbox("Cultivo", list(cultivos), index=indice_de(cultivos, parcela.get("cultivo")))
        etapa_txt = st.selectbox("Etapa del cultivo", list(etapas), index=indice_de(etapas, parcela.get("etapa")))
        sistema_txt = st.selectbox("Sistema de riego", list(SISTEMAS), index=indice_de(SISTEMAS, parcela.get("sistema")))
        area_ha = st.number_input("Superficie que riegas (ha)", min_value=0.1, max_value=100_000.0,
                                  value=float(parcela.get("area_ha") or 1.0), step=0.5)
        tasa_mm_h = st.number_input(
            "Tasa de aplicación (mm/h)", min_value=0.1, max_value=50.0, value=float(parcela.get("tasa_mm_h") or 3.0),
            step=0.5, help="Cuántos milímetros de agua aplica tu goteo o microaspersión en una hora.",
        )
        potencia_kw = st.number_input(
            "Potencia de la bomba (kW)", min_value=0.1, max_value=5_000.0,
            value=float(parcela.get("potencia_bomba_kw") or 30.0), step=1.0,
            help="Viene en la placa del motor. 1 HP ≈ 0.75 kW.",
        )
        horas_habituales = st.number_input(
            "Horas que riegas normalmente al día", min_value=0.0, max_value=24.0,
            value=float(parcela.get("horas_riego_habitual") or 4.0), step=0.5,
            help="Con esto calculamos cuánto ahorras siguiendo la recomendación.",
        )
        st.caption("Ubicación exacta (opcional). Si la dejas vacía se usa la cabecera del municipio.")
        c1, c2 = st.columns(2)
        latitud = c1.number_input("Latitud", min_value=-90.0, max_value=90.0, value=parcela.get("latitud"),
                                  format="%.5f", placeholder="Ej. 28.19013")
        longitud = c2.number_input("Longitud", min_value=-180.0, max_value=180.0, value=parcela.get("longitud"),
                                   format="%.5f", placeholder="Ej. -105.47012")
        enviar = st.form_submit_button(boton, type="primary", width="stretch")
    if not enviar:
        return None
    return {
        "nombre": nombre, "municipio": CIUDADES[ciudad_txt], "cultivo": cultivos[cultivo_txt],
        "etapa": etapas[etapa_txt], "sistema": SISTEMAS[sistema_txt], "area_ha": area_ha, "tasa_mm_h": tasa_mm_h,
        "potencia_bomba_kw": potencia_kw, "horas_riego_habitual": horas_habituales,
        "latitud": latitud, "longitud": longitud,
    }


def cargar_parcelas() -> list[dict] | None:
    if st.session_state.parcelas is None:
        ok, datos = llamar_api("GET", "/api/riego/parcelas")
        if not ok:
            st.error(datos)
            return None
        st.session_state.parcelas = datos
    return st.session_state.parcelas


def registrar_decision(decision: str, horas: float, motivo: str = "") -> None:
    ok, datos = llamar_api("POST", "/api/riego/decision", json={
        "id_recomendacion": st.session_state.reporte["id_recomendacion"], "decision": decision,
        "horas_aplicadas": horas, "motivo": motivo,
    })
    if not ok:
        st.error(datos)
        return
    st.session_state.ultima_decision = datos
    st.session_state.historial_bd = None  # se vuelve a leer con la decision nueva


# --------------------------------------------------------------------------
# Pagina
# --------------------------------------------------------------------------
st.set_page_config(page_title="B.A.W.Í. Riego", page_icon="💧", layout="wide")
for clave, valor in {"token": None, "usuario": None, "parcelas": None, "id_parcela": None, "reporte": None,
                     "ultima_decision": None, "historial_bd": None, "nueva_parcela": None, "vista_acceso": "entrar",
                     "registro": None, "cultivos": None}.items():
    st.session_state.setdefault(clave, valor)

# Sesion compartida: si se llega desde Comunidad, la sesion viene en el enlace (?sesion=...)
token_enlace = st.query_params.get("sesion")
if token_enlace:
    st.query_params.clear()  # no dejar el token en la barra de direcciones
    if not st.session_state.token:
        st.session_state.token = token_enlace  # se valida abajo con /yo

if not st.session_state.token:
    pantalla_acceso()
    st.stop()

# Datos de la cuenta al dia (tambien confirma que la sesion sigue siendo valida)
ok, datos_yo = llamar_api("GET", "/api/comunidad/yo")
if ok:
    st.session_state.usuario = datos_yo
elif not st.session_state.token:  # la sesion vencio
    st.rerun()
else:
    st.error(datos_yo)
    st.stop()
usuario = st.session_state.usuario

if not st.session_state.cultivos:
    ok, datos = llamar_api("GET", "/api/riego/cultivos")
    if not ok:
        st.error(datos)
        st.stop()
    st.session_state.cultivos = datos
# Nombre que se muestra -> clave en la BD (las etapas son las mismas para todos los cultivos)
CULTIVOS = {c["nombre"]: c["clave"] for c in st.session_state.cultivos}
ETAPAS = {e["nombre"]: e["clave"] for c in st.session_state.cultivos for e in c["etapas"]}

parcelas = cargar_parcelas()
if parcelas is None:
    st.stop()

with st.sidebar:
    st.link_button("🌱 Ir a B.A.W.Í. Comunidad", f"{COMUNIDAD_URL}/?sesion={st.session_state.token}",
                   width="stretch", help="Abre Comunidad con tu misma sesión.")
    st.success(f"👨‍🌾 **{usuario['nombre']}**  \n{usuario['correo'] or usuario['usuario']}")
    if st.button("Cerrar sesión", width="stretch"):
        cerrar_sesion()
        st.rerun()

# --- Alta de parcela (la primera, o una mas) -----------------------------------
if not parcelas or st.session_state.nueva_parcela:
    st.title("💧 B.A.W.Í. Riego")
    st.subheader("Registra tu parcela")
    st.caption("Con estos datos calculamos cada día cuánto y cuánto tiempo regar.")
    municipio = CIUDADES.get(usuario.get("municipio"), usuario.get("municipio"))  # "Cuauhtémoc" -> "Cuauhtemoc"
    nueva = formulario_parcela({"municipio": municipio}, CULTIVOS, ETAPAS, "form_nueva", "Registrar parcela")
    if nueva:
        ok, datos = llamar_api("POST", "/api/riego/parcelas", json=nueva)
        if ok:
            st.session_state.parcelas = None
            st.session_state.id_parcela = datos["id_parcela"]
            st.session_state.nueva_parcela = None
            limpiar_resultado()
            st.rerun()
        st.error(datos)
    if parcelas and st.button("Cancelar"):
        st.session_state.nueva_parcela = None
        st.rerun()
    st.stop()

# --- Parcela elegida y sus datos -----------------------------------------------
ids = [p["id_parcela"] for p in parcelas]
if st.session_state.id_parcela not in ids:
    st.session_state.id_parcela = ids[0]
with st.sidebar:
    if len(parcelas) > 1:
        nombres = {p["id_parcela"]: p["nombre"] for p in parcelas}
        elegida = st.selectbox("Parcela", ids, index=ids.index(st.session_state.id_parcela),
                               format_func=lambda i: nombres[i])
        if elegida != st.session_state.id_parcela:
            st.session_state.id_parcela = elegida
            limpiar_resultado()
            st.rerun()
    if st.button("➕ Registrar otra parcela", width="stretch"):
        st.session_state.nueva_parcela = True
        st.rerun()
parcela = next(p for p in parcelas if p["id_parcela"] == st.session_state.id_parcela)

st.title("💧 B.A.W.Í. Riego")
st.caption("Recomendación de riego explicada, para que decidas tú con información.")

with st.sidebar:
    st.header(f"🌳 {parcela['nombre']}")
    # Formulario: mover un numero no recarga la pagina; todo se aplica al presionar el boton
    cambios = formulario_parcela(parcela, CULTIVOS, ETAPAS, "form_parcela", "Guardar y calcular")

if cambios:
    limpiar_resultado()
    guardados = {k: parcela.get(k) for k in cambios}
    if cambios != guardados:
        ok, datos = llamar_api("PUT", f"/api/riego/parcelas/{parcela['id_parcela']}", json=cambios)
        if not ok:
            st.error(datos)
            st.stop()
        st.session_state.parcelas = None
        parcela = datos
    with st.spinner("Consultando el clima y calculando..."):
        ok, datos = llamar_api("POST", f"/api/riego/parcelas/{parcela['id_parcela']}/diagnostico")
    if not ok:
        st.error(datos)
        st.stop()
    st.session_state.reporte = datos
    if st.session_state.parcelas is None:
        st.rerun()  # vuelve a leer la parcela con los datos guardados

reporte = st.session_state.reporte
if reporte is None:
    st.info("Revisa los datos de tu parcela en el panel izquierdo y presiona **Guardar y calcular**.")
    st.stop()

ciudad_txt = next((k for k, v in CIUDADES.items() if v == parcela["municipio"]), parcela["municipio"])
cultivo_txt = next((k for k, v in CULTIVOS.items() if v == parcela["cultivo"]), parcela["cultivo"])
etapa_txt = next((k for k, v in ETAPAS.items() if v == parcela["etapa"]), parcela["etapa"])
clima = reporte["clima_actual"]
dia = reporte["clima_dia"]
pron = reporte["pronostico_24h"]
calc = reporte["calculos"]
diag = reporte["diagnostico_ia"]
riego = reporte["riego"]
ahorro = reporte["ahorro"]
horas = riego["horas"]

if reporte.get("aviso_bd"):
    st.warning("La recomendación no se guardó en la base de datos; no se podrá registrar tu decisión de hoy.")

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
horas_habituales = parcela["horas_riego_habitual"]
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
st.caption(f"Ahora: {clima['descripcion']}")
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Temperatura", f"{clima['temperatura_c']} °C")
c2.metric("Humedad", f"{clima['humedad_pct']} %")
c3.metric("Viento", f"{clima['viento_ms']} m/s")
c4.metric("Máxima próximas 24 h", f"{pron['temp_max_c']} °C")
c5.metric("Prob. de lluvia 24 h", f"{pron['prob_lluvia_pct']} %")
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Máxima de hoy", f"{dia['temp_max_c']:.1f} °C")
c2.metric("Mínima de hoy", f"{dia['temp_min_c']:.1f} °C")
c3.metric("Humedad mín. / máx.", f"{dia['humedad_min_pct']:.0f} / {dia['humedad_max_pct']:.0f} %")
c4.metric("Radiación solar", f"{dia['radiacion_mj_m2']:.1f} MJ/m²")
c5.metric("Altitud", f"{dia['altitud_m']:,.0f} m")
st.caption("Datos del día para el cálculo FAO-56 · Fuente: Open-Meteo (modelos meteorológicos nacionales).")

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
**1. Cuánta agua se pierde.** Hoy en **{ciudad_txt}** la temperatura va de **{dia['temp_min_c']:.1f}** a
**{dia['temp_max_c']:.1f} °C**, la humedad de **{dia['humedad_min_pct']:.0f} %** a **{dia['humedad_max_pct']:.0f} %**,
el viento promedia **{dia['viento_medio_ms']:.1f} m/s** y el sol aporta **{dia['radiacion_mj_m2']:.1f} MJ/m²**.
Con ese clima, un pasto de referencia pierde **{calc['et0_mm']} mm** de agua al día entre evaporación del suelo
y transpiración de las hojas (**ET₀**).

**2. Cuánto consume tu cultivo.** Tu **{cultivo_txt.lower()}** en etapa **{etapa_txt.lower()}** consume
**{calc['kc_aplicado']} veces** esa cantidad (coeficiente de cultivo **Kc**): **{calc['etc_mm']} mm**
(**ETc = ET₀ × Kc**).

**3. La lluvia.** {texto_lluvia}

**4. Cuánto tiempo regar.** Tu sistema aplica **{riego['tasa_mm_h']:g} mm por hora**, así que reponer
{riego['lamina_mm']} mm toma **{horas:.1f} horas**. Regar más lava nutrientes y gasta energía del pozo;
regar menos deja al cultivo en déficit.
"""
    )
    st.caption("Método: FAO-56 Penman-Monteith, estándar internacional para calcular el consumo de agua "
               "de los cultivos, con lógica difusa para el riesgo y el ajuste por lluvia.")

# --- Decision del agricultor (human-in-the-loop) -----------------------------
if reporte.get("id_recomendacion"):
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
# El historial se pide una vez y se vuelve a pedir solo despues de calcular o decidir
if st.session_state.historial_bd is None:
    ok, datos = llamar_api("GET", f"/api/riego/parcelas/{parcela['id_parcela']}/historial")
    st.session_state.historial_bd = datos if ok else []
filas = [
    {"Fecha": h["fecha"], "Sugeridas (h)": h["horas_sugeridas"], "Decisión": ESTADOS.get(h["estado"], h["estado"]),
     "Aplicadas (h)": h["horas_aplicadas"], "Motivo": h["motivo"] or "", "Agua ahorrada (m³)": h["agua_ahorrada_m3"],
     "Ahorro ($)": h["ahorro_mxn"]}
    for h in st.session_state.historial_bd
]
if filas:
    st.subheader("Historial de decisiones")
    st.dataframe(filas, width="stretch", hide_index=True)
