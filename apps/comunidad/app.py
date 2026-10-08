"""
B.A.W.I. Comunidad - red de aprendizaje entre productores (Streamlit).

- Entrada: iniciar sesion con correo, crear cuenta o continuar sin cuenta (solo lectura)
- Menu: Inicio (recientes), Tendencias (mas likes), Capacitacion y Mi perfil
- Rangos y puntos: solo Especialista Agronomo y Maestro de la Tierra responden;
  "Le funciono al autor" da +10 a quien respondio; +5 a quien pregunta (max. 20)
- Respuestas de productores de B.A.W.I. Riego con su dato de campo real

Ejecutar desde la raiz del proyecto (con la API corriendo):
    streamlit run apps/comunidad/app.py --server.port 8503
"""
import html
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
SECCIONES = {
    "inicio": "🏠  Inicio",
    "tendencias": "🔥  Tendencias",
    "capacitacion": "🎓  Capacitación",
    "perfil": "👤  Mi perfil",
}
NOTA_ZONA = ("Nota: Los resultados pueden variar según la zona, el clima, el suelo y las condiciones "
             "donde cultives.")
ESTADOS_RIEGO = {"aceptada": "aceptó", "ajustada": "ajustó", "rechazada": "rechazó", "pendiente": "aún no decide"}

# --------------------------------------------------------------------------
# Identidad visual (paleta de la maqueta de Irving)
# --------------------------------------------------------------------------
LOGO_SVG = """
<svg viewBox="0 0 64 64" xmlns="http://www.w3.org/2000/svg" width="{t}" height="{t}" aria-label="B.A.W.Í.">
  <rect width="64" height="64" rx="16" fill="#A3D977"/>
  <path d="M32 9 C32 9 15 31 15 41 a17 17 0 0 0 34 0 C49 31 32 9 32 9 Z" fill="#143D2C"/>
  <rect x="26" y="40" width="3" height="7" rx="1.5" fill="#EEF3EF"/>
  <rect x="35" y="40" width="3" height="7" rx="1.5" fill="#EEF3EF"/>
</svg>
"""

CSS = """
<style>
:root {
  --verde-bosque: #143D2C;
  --verde-claro: #A3D977;
  --verde-texto: #8CCB63;
  --amarillo: #F2C94C;
  --fondo: #0B0F0D;
  --tarjeta: #141916;
  --borde: #26302A;
  --texto: #EEF3EF;
  --tenue: #A9B5AD;
}
.stApp { background: radial-gradient(ellipse at top left, #10251B 0%, var(--fondo) 55%); }
[data-testid="stSidebar"] { background: var(--verde-bosque); border-right: 1px solid #1E4A36; }
[data-testid="stSidebar"] * { color: var(--texto); }
[data-testid="stHeader"] { background: transparent; }

/* Botones: amarillo con texto oscuro (primario) y contorno verde (secundario) */
button[kind="primary"], [data-testid="stBaseButton-primary"],
[data-testid="stFormSubmitButton"] button[kind="primaryFormSubmit"],
[data-testid="stBaseButton-primaryFormSubmit"] {
  background: var(--amarillo) !important; color: #10140F !important;
  border: none !important; border-radius: 999px !important; font-weight: 700 !important;
}
button[kind="secondary"], [data-testid="stBaseButton-secondary"] {
  border-radius: 999px !important; border-color: var(--borde) !important;
}

/* Tarjetas */
[class*="st-key-tarjeta"] {
  background: var(--tarjeta); border: 1px solid var(--borde) !important; border-radius: 18px;
  padding: 0.4rem 0.6rem;
}
[class*="st-key-tarjeta_pub"] [data-testid="stImage"] img { max-height: 420px; object-fit: cover; border-radius: 12px; }
[class*="st-key-tarjeta_login"] { border-top: 3px solid var(--verde-claro) !important; padding: 1rem 1.2rem; }

.bawi-marca { display: flex; align-items: center; gap: 12px; }
.bawi-marca .titulo { font-weight: 800; font-size: 1.45rem; letter-spacing: .06em; line-height: 1.1; }
.bawi-marca .lema { font-size: .66rem; letter-spacing: .22em; color: var(--verde-texto); text-transform: uppercase; }
.bawi-etiqueta { font-size: .72rem; letter-spacing: .2em; color: var(--verde-texto); text-transform: uppercase;
  font-weight: 700; margin: .2rem 0 .3rem; }
.bawi-hero { font-size: 2.6rem; font-weight: 800; line-height: 1.1; margin: .4rem 0 1rem; }
.bawi-tenue { color: var(--tenue); }

.bawi-autor { display: flex; align-items: center; gap: 12px; }
.bawi-avatar { width: 42px; height: 42px; border-radius: 50%; background: #1E3A2B; color: var(--verde-claro);
  display: flex; align-items: center; justify-content: center; font-weight: 800; flex-shrink: 0; }
.bawi-autor .nombre { font-weight: 700; }
.bawi-autor .detalle { color: var(--tenue); font-size: .85rem; }
.bawi-tema { margin-left: auto; background: #1E3A2B; color: var(--verde-texto); border-radius: 8px;
  padding: 4px 10px; font-size: .8rem; font-weight: 700; white-space: nowrap; }
.bawi-pub-titulo { font-size: 1.25rem; font-weight: 800; margin: .7rem 0 .3rem; }
.bawi-pub-texto { color: #D5DDD7; white-space: pre-wrap; }
/* Menu lateral como lista de secciones (sin circulos de radio) */
[data-testid="stSidebar"] [role="radiogroup"] { gap: 6px; width: 100%; }
[data-testid="stSidebar"] [role="radiogroup"] label {
  padding: 12px 14px; border-radius: 12px; width: 100%; box-sizing: border-box; margin: 0; cursor: pointer;
}
[data-testid="stSidebar"] [role="radiogroup"] label[data-baseweb="radio"] > div:first-child,
[data-testid="stSidebar"] [data-testid="stRadioOption"] > div > div:first-child { display: none; }
[data-testid="stSidebar"] [role="radiogroup"] p { font-size: 1.02rem; }
[data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) {
  background: #2C6B4C; border-left: 4px solid var(--verde-claro); font-weight: 700;
}
[data-testid="stSidebar"] [role="radiogroup"] label:hover { background: #1D5139; }

/* Celular: menos espacio en la portada y sin boton + duplicado */
@media (max-width: 640px) {
  .bawi-logo-grande { display: none; }
  .bawi-hero { font-size: 1.8rem; }
  .st-key-btn_mas { display: none; }
}

.bawi-funciono { display: inline-block; background: #1F4D2E; color: #B9F08F; border-radius: 8px;
  padding: 2px 10px; font-size: .8rem; font-weight: 700; margin: 4px 0; }
</style>
"""


def marca(tamano: int = 44, lema: str = "Agua · Talento · Comunidad") -> str:
    return (f'<div class="bawi-marca">{LOGO_SVG.format(t=tamano)}'
            f'<div><div class="titulo">B.A.W.Í.</div><div class="lema">{lema}</div></div></div>')


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
        detalle = "Revisa los datos: correo válido, nombre y contraseña de al menos 6 caracteres."
    return False, detalle


def iniciar_sesion(datos: dict) -> None:
    st.session_state.token = datos["token"]
    st.session_state.usuario = datos["usuario"]
    st.session_state.invitado = False
    st.session_state.menu = "inicio"


def ir_a(seccion: str) -> None:
    """Cambia de seccion del menu (se usa como on_click de los botones)."""
    st.session_state.menu = seccion


def cerrar_sesion() -> None:
    st.session_state.token = None
    st.session_state.usuario = None
    st.session_state.invitado = False


def avisar(mensaje: str, tipo: str = "success") -> None:
    st.session_state.aviso = (tipo, mensaje)


@st.cache_data(show_spinner=False, max_entries=200)
def descargar_archivo(ruta: str) -> bytes | None:
    """Descarga una foto o audio desde la API. Se manda como bytes a la pagina,
    asi tambien se ve desde el celular (que no puede abrir 'localhost')."""
    try:
        resp = requests.get(f"{API_URL}{ruta}", timeout=20)
        return resp.content if resp.status_code == 200 else None
    except requests.exceptions.RequestException:
        return None


def iniciales(nombre: str) -> str:
    partes = [p for p in nombre.split() if p]
    return "".join(p[0] for p in partes[:2]).upper() or "?"


def cabecera_autor(autor: dict, detalle: str, tema: str | None = None) -> None:
    """Avatar con iniciales, nombre, rango y detalle (fecha, region)."""
    rango = autor["rango"]
    riego = " · 💧 usa B.A.W.Í. Riego" if autor["usa_riego"] else ""
    tema_html = f'<span class="bawi-tema">{html.escape(tema)}</span>' if tema else ""
    st.markdown(
        f'<div class="bawi-autor"><div class="bawi-avatar">{html.escape(iniciales(autor["nombre"]))}</div>'
        f'<div><div class="nombre">{html.escape(autor["nombre"])} · {rango["insignia"]} {html.escape(rango["nombre"])}</div>'
        f'<div class="detalle">{html.escape(autor["municipio"])}{riego} · {html.escape(detalle)}</div></div>'
        f'{tema_html}</div>',
        unsafe_allow_html=True,
    )


def dar_like(ruta: str) -> None:
    """Pone o quita un like (publicacion o respuesta) y guarda el aviso de puntos si hubo."""
    ok, datos = llamar_api("POST", ruta)
    if not ok:
        avisar(datos, "warning")
    elif datos.get("puntos_a_quien_respondio"):
        avisar(f"✅ Marcaste que te funcionó. Quien te respondió ganó +{datos['puntos_a_quien_respondio']} "
               f"puntos por ayudarte.")


# --------------------------------------------------------------------------
# Publicaciones y respuestas
# --------------------------------------------------------------------------
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
    """Respuestas de una publicacion y, si el rango lo permite, el formulario para responder."""
    ok, detalle = llamar_api("GET", f"/publicaciones/{pub['id_publicacion']}")
    if not ok:
        st.error(detalle)
        return
    soy_autor = bool(yo) and yo["id_usuario"] == pub["autor"]["id_usuario"]
    for resp in detalle["respuestas"]:
        cabecera_autor(resp["autor"], resp["creada_en"])
        if resp["le_funciono_al_autor"]:
            st.markdown('<span class="bawi-funciono">✅ Le funcionó al autor</span>', unsafe_allow_html=True)
        st.markdown(f'<div class="bawi-pub-texto">{html.escape(resp["texto"])}</div>', unsafe_allow_html=True)
        if resp["audio"]:
            audio = descargar_archivo(resp["audio"])
            if audio:
                st.audio(audio)
        if resp["dato_riego"]:
            mostrar_dato_riego(resp["dato_riego"])

        # Like: el autor de la duda marca "Me funcionó"; los demas solo suman al contador
        es_mia = bool(yo) and yo["id_usuario"] == resp["autor"]["id_usuario"]
        if soy_autor:
            texto_boton = ("✅ Me funcionó" if resp["yo_di_like"] else "☑️ ¿Te funcionó? Márcalo") + f" · {resp['likes']}"
        else:
            texto_boton = ("👍 Útil" if resp["yo_di_like"] else "👍") + f" · {resp['likes']}"
        ayuda = None
        if not yo:
            ayuda = "Inicia sesión para dar like."
        elif es_mia:
            ayuda = "No puedes dar like a tu propia respuesta."
        elif soy_autor:
            ayuda = "Márcala solo si pusiste en práctica la recomendación y te funcionó."
        if st.button(texto_boton, key=f"like_resp_{resp['id_respuesta']}", disabled=not yo or es_mia, help=ayuda):
            dar_like(f"/respuestas/{resp['id_respuesta']}/like")
            st.rerun()
        st.divider()

    st.caption(f"ℹ️ {NOTA_ZONA}")
    if not yo:
        st.caption("🔒 Inicia sesión para dar like o responder.")
        return
    if not yo["puede_responder"]:
        st.caption(f"🔒 Solo **Especialista Agrónomo** y **Maestro de la Tierra** pueden responder. "
                   f"Tu rango es {yo['rango']['insignia']} {yo['rango']['nombre']}: sigue preguntando y "
                   f"capacitándote para subir.")
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
            extra = ""
            if datos.get("puntos_al_autor"):
                extra = (f" {pub['autor']['nombre']} ganó +{datos['puntos_al_autor']} puntos por recibir una "
                         f"respuesta experta.")
            avisar("¡Gracias por ayudar! Tu respuesta ya está publicada." + extra)
            st.rerun()
        st.error(datos)


def mostrar_publicacion(pub: dict) -> None:
    """Tarjeta del feed: autor, tema, titulo, texto, foto, audio, likes y respuestas."""
    with st.container(key=f"tarjeta_pub_{pub['id_publicacion']}"):
        cabecera_autor(pub["autor"], pub["creada_en"], CATEGORIAS.get(pub["categoria"], pub["categoria"]))
        st.markdown(f'<div class="bawi-pub-titulo">{html.escape(pub["titulo"])}</div>'
                    f'<div class="bawi-pub-texto">{html.escape(pub["texto"])}</div>', unsafe_allow_html=True)
        if pub["imagen"]:
            foto = descargar_archivo(pub["imagen"])
            if foto:
                st.image(foto, width="stretch")
            else:
                st.caption("🖼️ No se pudo cargar la foto.")
        if pub["audio"]:
            audio = descargar_archivo(pub["audio"])
            if audio:
                st.audio(audio)
        corazon = "❤️" if pub["yo_di_like"] else "🤍"
        if st.button(f"{corazon} {pub['likes']}", key=f"like_pub_{pub['id_publicacion']}", disabled=not yo,
                     help=None if yo else "Inicia sesión para dar like."):
            dar_like(f"/publicaciones/{pub['id_publicacion']}/like")
            st.rerun()
        n = pub["num_respuestas"]
        with st.expander(f"💬 {n} respuesta(s)" if n else "💬 Aún sin respuestas", expanded=n > 0):
            mostrar_respuestas(pub)


@st.dialog("Crear publicación", width="large")
def dialogo_publicar() -> None:
    if not yo:
        st.info("Para publicar una duda necesitas una cuenta. Es gratis y puedes leer sin ella.")
        if st.button("Iniciar sesión o crear cuenta", type="primary", width="stretch"):
            st.session_state.invitado = False
            st.rerun()
        return
    st.caption(f"Publicando como **{yo['nombre']}** · zona: {yo['municipio']} (no se muestra tu dirección)")
    with st.form("form_publicar", clear_on_submit=True, border=False):
        titulo = st.text_input("Título", placeholder="Resume tu pregunta o experiencia")
        categoria = st.selectbox("Tema", list(CATEGORIAS), format_func=lambda c: CATEGORIAS[c])
        texto = st.text_area("Contenido", height=120, placeholder="Describe tu duda o lo que observas en tu parcela")
        foto = st.file_uploader("📷 Fotografía (opcional)", type=["jpg", "jpeg", "png", "webp"])
        voz = st.audio_input("🎤 Nota de voz (opcional)")
        enviar = st.form_submit_button("Publicar", type="primary", width="stretch")
    if enviar:
        if len(titulo.strip()) < 3 or len(texto.strip()) < 3:
            st.error("Escribe un título y un contenido de al menos 3 letras.")
            return
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
            avisar("¡Publicación creada! Ya aparece en el feed.")
            st.rerun()
        st.error(datos)


def mostrar_feed(orden: str) -> None:
    col_crear, col_tema = st.columns([1, 3], vertical_alignment="center")
    if col_crear.button("＋ Crear publicación", type="primary", width="stretch"):
        dialogo_publicar()
    filtro = col_tema.segmented_control(
        "Tema", ["todas"] + list(CATEGORIAS), default="todas", label_visibility="collapsed",
        format_func=lambda c: "Todo" if c == "todas" else CATEGORIAS[c], key=f"filtro_{orden}",
    )
    parametros = {"orden": orden}
    if filtro not in (None, "todas"):
        parametros["categoria"] = filtro
    buscar = st.session_state.get("buscar", "").strip()
    if buscar:
        parametros["buscar"] = buscar
    ok, publicaciones = llamar_api("GET", "/publicaciones", params=parametros)
    if not ok:
        st.error(publicaciones)
    elif not publicaciones:
        st.info("No hay publicaciones con esos filtros. ¡Haz la primera pregunta!")
    else:
        for pub in publicaciones:
            mostrar_publicacion(pub)


# --------------------------------------------------------------------------
# Pantallas
# --------------------------------------------------------------------------
def pantalla_acceso() -> None:
    """Iniciar sesion / Crear cuenta / Continuar sin cuenta (maqueta login_MMM)."""
    st.markdown(marca(46), unsafe_allow_html=True)
    st.write("")
    izquierda, derecha = st.columns([1.1, 1], gap="large")
    with izquierda:
        st.write("")
        st.markdown(f'<div class="bawi-logo-grande">{LOGO_SVG.format(t=120)}</div>', unsafe_allow_html=True)
        st.markdown('<div class="bawi-etiqueta">B.A.W.Í. Comunidad</div>'
                    '<div class="bawi-hero">El conocimiento del campo se comparte.</div>'
                    '<p class="bawi-tenue">Entra para publicar tus dudas, aprender y compartir experiencias '
                    'con la comunidad agrícola.</p><p>📖 También puedes leer sin iniciar sesión.</p>',
                    unsafe_allow_html=True)
    with derecha, st.container(key="tarjeta_login"):
        if st.session_state.vista_acceso == "entrar":
            st.markdown('<div class="bawi-etiqueta">Bienvenido a Comunidad</div>', unsafe_allow_html=True)
            st.subheader("Iniciar sesión")
            st.caption("Accede a tu cuenta para participar.")
            with st.form("form_entrar", border=False):
                correo = st.text_input("Correo electrónico", placeholder="tu@correo.com")
                password = st.text_input("Contraseña", type="password", placeholder="Escribe tu contraseña")
                entrar = st.form_submit_button("Iniciar sesión", type="primary", width="stretch")
            if entrar:
                ok, datos = llamar_api("POST", "/login", json={"correo": correo, "password": password})
                if ok:
                    iniciar_sesion(datos)
                    avisar(f"¡Bienvenido de nuevo, {datos['usuario']['nombre']}!")
                    st.rerun()
                st.error(datos)
            if st.button("Continuar sin cuenta", width="stretch"):
                st.session_state.invitado = True
                st.rerun()
            st.divider()
            st.caption("¿No tienes una cuenta?")
            if st.button("Crear cuenta", width="stretch", key="ir_crear"):
                st.session_state.vista_acceso = "crear"
                st.rerun()
        else:
            st.markdown('<div class="bawi-etiqueta">Únete a Comunidad</div>', unsafe_allow_html=True)
            st.subheader("Crear cuenta")
            st.caption("Empiezas como 🌱 Aprendiz del Campo y subes de rango participando.")
            with st.form("form_crear", border=False):
                nombre = st.text_input("Nombre que aparecerá en tu perfil")
                correo = st.text_input("Correo electrónico", placeholder="tu@correo.com")
                municipio = st.selectbox("Zona de tu cultivo", REGIONES)
                password = st.text_input("Contraseña (mínimo 6)", type="password")
                confirmacion = st.text_input("Confirma tu contraseña", type="password")
                crear = st.form_submit_button("Crear cuenta", type="primary", width="stretch")
            if crear:
                if password != confirmacion:
                    st.error("Las contraseñas no coinciden.")
                else:
                    ok, datos = llamar_api("POST", "/registro", json={
                        "nombre": nombre, "correo": correo, "municipio": municipio,
                        "password": password, "confirmacion": confirmacion,
                    })
                    if ok:
                        iniciar_sesion(datos)
                        avisar(f"¡Bienvenido a la comunidad, {datos['usuario']['nombre']}!")
                        st.rerun()
                    st.error(datos)
            st.divider()
            if st.button("Ya tengo cuenta", width="stretch"):
                st.session_state.vista_acceso = "entrar"
                st.rerun()


def pantalla_perfil() -> None:
    if not yo:
        st.info("Inicia sesión para ver tu perfil, tus puntos y tu rango.")
        if st.button("Iniciar sesión", type="primary"):
            st.session_state.invitado = False
            st.rerun()
        return
    rango = yo["rango"]
    with st.container(key="tarjeta_perfil"):
        cabecera_autor({"nombre": yo["nombre"], "municipio": yo["municipio"], "usa_riego": yo["usa_riego"],
                        "rango": rango}, yo.get("correo") or yo["usuario"])
        c1, c2, c3 = st.columns(3)
        c1.metric("Rango", f"{rango['insignia']} {rango['nombre']}")
        c2.metric("Puntaje", yo["puntos"])
        c3.metric("Puede responder dudas", "Sí" if yo["puede_responder"] else "Aún no")
        if yo["usa_riego"]:
            st.info("👑 Eres **Maestro de la Tierra** por usar B.A.W.Í. Riego: al responder dudas puedes "
                    "compartir tu dato de campo real.")
        elif rango["siguiente"]:
            avance = min(yo["puntos"] / rango["puntos_siguiente"], 1.0)
            st.progress(avance, text=f"Te faltan {rango['faltan']} puntos para {rango['siguiente']}")

    ok_act, actividad = llamar_api("GET", "/yo/actividad")
    if ok_act:
        st.subheader("Tu actividad")
        a1, a2 = st.columns(2)
        a1.metric("Publicaciones compartidas", actividad["publicaciones"])
        a2.metric("Respuestas", actividad["respuestas"])
        motivos = {"publicacion": "Recibiste una respuesta experta",
                   "comentario_util": "Tu respuesta le funcionó a alguien", "quiz": "Capacitación"}
        if actividad["movimientos"]:
            st.dataframe([{"Fecha": m["fecha"], "Puntos": f"+{m['puntos']}",
                           "Motivo": motivos.get(m["motivo"], m["motivo"])} for m in actividad["movimientos"]],
                         hide_index=True, width="stretch")

    st.subheader("Rangos de Comunidad")
    ok_r, rangos = llamar_api("GET", "/rangos")
    if ok_r:
        st.table([{"Rango": f"{r['insignia']} {r['nombre']}",
                   "Puntos": f"{r['puntos_min']}+" if r["puntos_max"] is None else f"{r['puntos_min']} – {r['puntos_max']}",
                   "Responde dudas": "Sí" if r["puede_responder"] else "No"} for r in rangos])
    st.markdown("- **+5** cuando un Especialista o Maestro responde tu duda (una vez por publicación, máximo 20).\n"
                "- **+10** cuando el autor marca que tu respuesta **le funcionó** (una vez por publicación).\n"
                "- Quien contrata **B.A.W.Í. Riego** es Maestro de la Tierra.")
    if st.button("Cerrar sesión"):
        cerrar_sesion()
        st.rerun()


def pantalla_capacitacion() -> None:
    st.subheader("🎓 Capacitación")
    st.info("Muy pronto: **Conoce una palabra** y **Verdadero o falso**. Una dinámica al día para sumar puntos "
            "y subir de rango.")


# --------------------------------------------------------------------------
# Pagina
# --------------------------------------------------------------------------
st.set_page_config(page_title="B.A.W.Í. Comunidad", page_icon="💧", layout="wide")
st.markdown(CSS, unsafe_allow_html=True)
for clave, valor in {"token": None, "usuario": None, "aviso": None, "invitado": False,
                     "vista_acceso": "entrar", "menu": "inicio"}.items():
    st.session_state.setdefault(clave, valor)

# Los puntos y el rango cambian al participar: se vuelven a pedir en cada recarga
if st.session_state.token:
    ok_yo, datos_yo = llamar_api("GET", "/yo")
    if ok_yo:
        st.session_state.usuario = datos_yo
    elif "sesión" in str(datos_yo).lower():
        cerrar_sesion()
yo = st.session_state.usuario


def mostrar_aviso() -> None:
    if st.session_state.aviso:
        tipo, mensaje = st.session_state.aviso
        getattr(st, tipo)(mensaje)
        st.session_state.aviso = None


if not yo and not st.session_state.invitado:
    pantalla_acceso()
    st.stop()

# --- Menu lateral ---------------------------------------------------------------
with st.sidebar:
    st.markdown(marca(48), unsafe_allow_html=True)
    st.write("")
    st.markdown('<div class="bawi-etiqueta">Tu espacio</div>', unsafe_allow_html=True)
    st.radio("Menú", list(SECCIONES), format_func=lambda s: SECCIONES[s], key="menu",
             label_visibility="collapsed")
    st.divider()
    if yo:
        st.markdown(f"**{yo['nombre']}**  \n{yo['rango']['insignia']} {yo['rango']['nombre']} · ⭐ {yo['puntos']}")
        if st.button("Cerrar sesión", key="salir_menu", width="stretch"):
            cerrar_sesion()
            st.rerun()
    else:
        st.markdown("**Comunidad abierta**  \nEstás leyendo sin cuenta.")
        if st.button("Iniciar sesión", key="entrar_menu", width="stretch"):
            st.session_state.invitado = False
            st.rerun()

# --- Barra superior -----------------------------------------------------------------
col_buscar, col_mas, col_cuenta = st.columns([5, 1, 2], vertical_alignment="center")
col_buscar.text_input("Buscar", key="buscar", placeholder="🔎 Buscar en Comunidad...",
                      label_visibility="collapsed")
if col_mas.button("＋", type="primary", width="stretch", help="Crear publicación", key="btn_mas"):
    dialogo_publicar()
if yo:
    col_cuenta.button(f"👤 {yo['nombre'].split()[0]}", width="stretch", on_click=ir_a, args=("perfil",))
elif col_cuenta.button("Iniciar sesión", width="stretch"):
    st.session_state.invitado = False
    st.rerun()

st.markdown(
    f'<div class="bawi-marca" style="margin:.8rem 0 .2rem">{LOGO_SVG.format(t=52)}<div>'
    f'<div class="titulo" style="letter-spacing:0;font-size:1.5rem">Comunidad</div>'
    f'<div class="bawi-tenue">Preguntas de campo, experiencias y conocimiento compartido.</div></div></div>',
    unsafe_allow_html=True,
)
mostrar_aviso()

seccion = st.session_state.menu
if seccion == "inicio":
    mostrar_feed("recientes")
elif seccion == "tendencias":
    mostrar_feed("likes")
elif seccion == "capacitacion":
    pantalla_capacitacion()
else:
    pantalla_perfil()