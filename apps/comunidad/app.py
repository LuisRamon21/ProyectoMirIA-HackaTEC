"""
B.A.W.I. Comunidad - red de aprendizaje entre productores (Streamlit).

Ejecutar desde la raiz del proyecto (con la API corriendo):
    streamlit run apps/comunidad/app.py --server.port 8503
"""
import os

import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv()
API_URL = os.getenv("API_URL", "http://localhost:8000")
API_COMUNIDAD = f"{API_URL}/api/comunidad"
REGIONES = ["Delicias", "Cuauhtémoc", "Camargo", "Chihuahua", "Otra"]

CATEGORIAS = {
    "riego": "💧 Riego",
    "plagas": "🐛 Plagas",
    "suelo": "🟫 Suelo",
    "cultivo": "🌳 Cultivo",
    "otro": "💬 Otro",
}


# --------------------------------------------------------------------------
# Conexion con la API (la app nunca habla directo con la base de datos)
# --------------------------------------------------------------------------
def llamar_api(metodo: str, ruta: str, **kwargs):
    """Regresa (True, datos) o (False, mensaje de error para mostrar)."""
    headers = kwargs.pop("headers", {})
    if st.session_state.get("token"):
        headers["Authorization"] = f"Bearer {st.session_state.token}"
    try:
        resp = requests.request(metodo, f"{API_COMUNIDAD}{ruta}", headers=headers, timeout=20, **kwargs)
    except requests.exceptions.RequestException:
        return False, f"No se pudo conectar con el servidor ({API_URL}). ¿Está corriendo la API?"
    if resp.status_code == 200:
        return True, resp.json()
    try:
        detalle = resp.json().get("detail", resp.text)
    except ValueError:
        detalle = resp.text
    if isinstance(detalle, list):  # errores de validacion de FastAPI
        detalle = "Revisa los datos: usuario de 3 a 30 letras o números (sin espacios) y contraseña de al menos 6."
    return False, detalle


def iniciar_sesion(datos: dict) -> None:
    st.session_state.token = datos["token"]
    st.session_state.usuario = datos["usuario"]


def cerrar_sesion() -> None:
    st.session_state.token = None
    st.session_state.usuario = None


@st.cache_data(show_spinner=False, max_entries=200)
def descargar_archivo(ruta: str) -> bytes | None:
    """Descarga una foto o audio desde la API. Se manda como bytes a la pagina,
    asi tambien se ve desde el celular (que no puede abrir 'localhost')."""
    try:
        resp = requests.get(f"{API_URL}{ruta}", timeout=20)
        return resp.content if resp.status_code == 200 else None
    except requests.exceptions.RequestException:
        return None


ESTADOS_RIEGO = {"aceptada": "aceptó", "ajustada": "ajustó", "rechazada": "rechazó", "pendiente": "aún no decide"}


def mostrar_dato_riego(dato: dict) -> None:
    """Tarjeta con el calculo real de B.A.W.I. Riego que adjunto el productor."""
    origen = " · clima de ejemplo" if dato["clima_de_ejemplo"] else ""
    aplicado = ""
    if dato["estado"] in ("aceptada", "ajustada") and dato["horas_aplicadas"] is not None:
        aplicado = f" y regó **{dato['horas_aplicadas']} h**"
    ahorro = ""
    if dato["agua_ahorrada_m3"]:
        ahorro = f" Ahorró **{dato['agua_ahorrada_m3']:,.0f} m³** de agua frente a su riego habitual."
    st.info(
        f"📊 **Dato de campo de B.A.W.Í. Riego** ({dato['fecha']}{origen})  \n"
        f"🌳 {dato['cultivo']} · etapa {dato['etapa'].lower()} · {dato['municipio']}  \n"
        f"🌡️ Máxima {dato['temp_max_c']} °C · 🌧️ {dato['prob_lluvia_pct']} % de probabilidad de lluvia  \n"
        f"💧 El cultivo consumía **{dato['etc_mm']} mm/día**; la recomendación fue **{dato['horas_sugeridas']} h** "
        f"de riego (riesgo {dato['riesgo']}). El productor {ESTADOS_RIEGO.get(dato['estado'], dato['estado'])}"
        f"{aplicado}.{ahorro}"
    )


def mostrar_respuestas(pub: dict) -> None:
    """Respuestas de una publicacion y, con sesion, el formulario para responder."""
    ok, detalle = llamar_api("GET", f"/publicaciones/{pub['id_publicacion']}")
    if not ok:
        st.error(detalle)
        return
    for resp in detalle["respuestas"]:
        autor = resp["autor"]
        insignia = " · 💧 usa B.A.W.Í. Riego" if autor["usa_riego"] else ""
        st.markdown(f"**{autor['nombre']}** · {autor['municipio']}{insignia}")
        st.caption(resp["creada_en"])
        st.write(resp["texto"])
        if resp["audio"]:
            audio = descargar_archivo(resp["audio"])
            if audio:
                st.audio(audio)
        if resp["dato_riego"]:
            mostrar_dato_riego(resp["dato_riego"])
        st.divider()

    if not yo:
        st.caption("Para responder, entra o crea tu cuenta en **👤 Mi cuenta**.")
        return
    with st.form(f"form_responder_{pub['id_publicacion']}", clear_on_submit=True):
        texto = st.text_area("Tu respuesta", height=90)
        voz = st.audio_input("🎤 Nota de voz (opcional)")
        adjuntar = False
        if yo["usa_riego"]:
            adjuntar = st.checkbox("📊 Adjuntar mi dato de campo de B.A.W.Í. Riego (mi última recomendación)")
        enviar = st.form_submit_button("Responder", type="primary")
    if enviar:
        if len(texto.strip()) < 2:
            st.error("Escribe tu respuesta.")
            return
        archivos = {"audio": ("nota_de_voz.wav", voz.getvalue(), "audio/wav")} if voz else None
        with st.spinner("Enviando respuesta..."):
            ok, datos = llamar_api("POST", f"/publicaciones/{pub['id_publicacion']}/respuestas",
                                   data={"texto": texto, "adjuntar_riego": str(adjuntar).lower()},
                                   files=archivos)
        if ok:
            st.session_state.aviso = "¡Gracias por ayudar! Tu respuesta ya está publicada."
            st.rerun()
        st.error(datos)


def mostrar_publicacion(pub: dict) -> None:
    """Dibuja una publicacion como tarjeta del feed."""
    autor = pub["autor"]
    with st.container(border=True):
        insignia = " · 💧 usa B.A.W.Í. Riego" if autor["usa_riego"] else ""
        st.markdown(f"**{autor['nombre']}** · {autor['municipio']}{insignia}")
        st.caption(f"{CATEGORIAS.get(pub['categoria'], pub['categoria'])} · {pub['creada_en']}")
        st.subheader(pub["titulo"])
        st.write(pub["texto"])
        if pub["imagen"]:
            foto = descargar_archivo(pub["imagen"])
            if foto:
                st.image(foto, width=420)
            else:
                st.caption("🖼️ No se pudo cargar la foto.")
        if pub["audio"]:
            audio = descargar_archivo(pub["audio"])
            if audio:
                st.audio(audio)
        n = pub["num_respuestas"]
        titulo = f"💬 {n} respuesta(s)" if n else "💬 Sé el primero en responder"
        with st.expander(titulo, expanded=n > 0):
            mostrar_respuestas(pub)

st.set_page_config(page_title="B.A.W.Í. Comunidad", page_icon="🌾", layout="wide")
st.session_state.setdefault("token", None)
st.session_state.setdefault("usuario", None)
st.session_state.setdefault("aviso", None)
yo = st.session_state.usuario

st.title("🌾 B.A.W.Í. Comunidad")
st.caption("El Instagram del campo que capacita, explica y certifica el talento agrícola de Chihuahua.")

if yo:
    st.caption(f"👤 Sesión iniciada como **{yo['nombre']}** ({yo['municipio']})")
if st.session_state.aviso:
    st.success(st.session_state.aviso)
    st.session_state.aviso = None

tab_feed, tab_preguntar, tab_cuenta = st.tabs(["📰 Feed", "✍️ Preguntar", "👤 Mi cuenta"])

with tab_feed:
    filtro = st.segmented_control(
        "Categoría",
        ["todas"] + list(CATEGORIAS),
        format_func=lambda c: "Todas" if c == "todas" else CATEGORIAS[c],
        default="todas",
    )
    parametros = {} if filtro in (None, "todas") else {"categoria": filtro}
    ok, publicaciones = llamar_api("GET", "/publicaciones", params=parametros)
    if not ok:
        st.error(publicaciones)
    elif not publicaciones:
        st.info("Todavía no hay publicaciones en esta categoría. ¡Haz la primera pregunta!")
    else:
        for pub in publicaciones:  # la API ya las manda de la mas reciente a la mas antigua
            mostrar_publicacion(pub)

with tab_preguntar:
    if not yo:
        st.info("Para hacer una pregunta, entra o crea tu cuenta en la pestaña **👤 Mi cuenta**.")
    else:
        st.caption(f"Publicando como **{yo['nombre']}**.")
        with st.form("form_preguntar", clear_on_submit=True):
            titulo = st.text_input("Título de tu pregunta")
            categoria = st.selectbox("Categoría", list(CATEGORIAS), format_func=lambda c: CATEGORIAS[c])
            texto = st.text_area("Cuéntanos qué pasa en tu parcela", height=120)
            foto = st.file_uploader("📷 Foto (opcional)", type=["jpg", "jpeg", "png", "webp"])
            voz = st.audio_input("🎤 Nota de voz (opcional)")
            enviar = st.form_submit_button("Publicar pregunta", type="primary")

        if enviar:
            if len(titulo.strip()) < 3 or len(texto.strip()) < 3:
                st.error("Escribe un título y una descripción de al menos 3 letras.")
            else:
                archivos = {}
                if foto:
                    archivos["foto"] = (foto.name, foto.getvalue(), foto.type or "image/jpeg")
                if voz:
                    archivos["audio"] = ("nota_de_voz.wav", voz.getvalue(), "audio/wav")
                with st.spinner("Publicando..."):
                    ok, datos = llamar_api("POST", "/publicaciones",
                                           data={"titulo": titulo, "texto": texto, "categoria": categoria},
                                           files=archivos or None)
                if ok:
                    st.session_state.aviso = "¡Pregunta publicada! Ya aparece en el Feed."
                    st.rerun()
                st.error(datos)

with tab_cuenta:
    if yo:
        st.subheader(f"👋 Hola, {yo['nombre']}")
        st.write(f"**Usuario:** {yo['usuario']}  \n**Región:** {yo['municipio']}")
        if yo["usa_riego"]:
            st.info("💧 Usas B.A.W.Í. Riego: al responder dudas puedes compartir tu dato de campo real.")
        if st.button("Cerrar sesión"):
            cerrar_sesion()
            st.rerun()
    else:
        st.caption("Puedes leer el feed sin cuenta. Para preguntar o responder, entra o crea tu cuenta.")
        col_entrar, col_crear = st.columns(2)

        with col_entrar, st.form("form_entrar"):
            st.subheader("Entrar")
            usuario = st.text_input("Usuario")
            password = st.text_input("Contraseña", type="password")
            if st.form_submit_button("Entrar", type="primary"):
                ok, datos = llamar_api("POST", "/login", json={"usuario": usuario, "password": password})
                if ok:
                    iniciar_sesion(datos)
                    st.session_state.aviso = f"¡Bienvenido de nuevo, {datos['usuario']['nombre']}!"
                    st.rerun()
                st.error(datos)

        with col_crear, st.form("form_crear"):
            st.subheader("Crear cuenta")
            nombre = st.text_input("Tu nombre")
            nuevo_usuario = st.text_input("Usuario (sin espacios)")
            region = st.selectbox("Región", REGIONES)
            nueva_password = st.text_input("Contraseña (mínimo 6)", type="password")
            if st.form_submit_button("Crear cuenta", type="primary"):
                ok, datos = llamar_api("POST", "/registro", json={
                    "usuario": nuevo_usuario, "nombre": nombre, "municipio": region, "password": nueva_password,
                })
                if ok:
                    iniciar_sesion(datos)
                    st.session_state.aviso = f"¡Bienvenido a la comunidad, {datos['usuario']['nombre']}!"
                    st.rerun()
                st.error(datos)