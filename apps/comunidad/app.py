"""
B.A.W.I. Comunidad - red de aprendizaje entre productores (Streamlit).

- Entrada: iniciar sesion con correo, crear cuenta o continuar sin cuenta (solo lectura)
- Menu: Inicio (recientes), Tendencias (mas likes), Capacitacion y Mi perfil
- Rangos y puntos: solo Especialista Agronomo y Maestro de la Tierra responden;
  "Le funciono al autor" da +10 a quien respondio; +5 a quien pregunta (max. 20)
- Respuestas de productores de B.A.W.I. Riego con su dato de campo real
- Capacitacion: "Conoce una palabra" y "Verdadero o falso" (una dinamica con puntos al dia)

Ejecutar desde la raiz del proyecto (con la API corriendo):
    streamlit run apps/comunidad/app.py --server.port 8503
"""
import html
import os
from datetime import datetime

import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv()
API_URL = os.getenv("API_URL", "http://localhost:8000")
API_COMUNIDAD = f"{API_URL}/api/comunidad"
API_CAPACITACION = f"{API_URL}/api/capacitacion"
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
  --agua: #4FB3BF;
  --tierra: #9A6B45;
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

/* Tarjetas (login, perfil, capacitacion) */
[class*="st-key-tarjeta"] {
  background: var(--tarjeta); border: 1px solid var(--borde) !important; border-radius: 18px;
  padding: 0.4rem 0.6rem;
}
[class*="st-key-tarjeta_login"] { border-top: 3px solid var(--verde-claro) !important; padding: 1rem 1.2rem; }

.bawi-marca { display: flex; align-items: center; gap: 12px; }
.bawi-marca .titulo { font-weight: 800; font-size: 1.45rem; letter-spacing: .06em; line-height: 1.1; }
.bawi-marca .lema { font-size: .66rem; letter-spacing: .22em; color: var(--verde-texto); text-transform: uppercase; }
.bawi-etiqueta { font-size: .72rem; letter-spacing: .2em; color: var(--verde-texto); text-transform: uppercase;
  font-weight: 700; margin: .2rem 0 .3rem; }
.bawi-hero { font-size: 2.6rem; font-weight: 800; line-height: 1.1; margin: .4rem 0 1rem; }
.bawi-tenue { color: var(--tenue); }

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

/* ======================= FEED ESTILO INSTAGRAM ======================= */
/* Columna central angosta, como el feed de Instagram */
.st-key-feed { max-width: 600px; width: 100%; margin: 0 auto; }

/* Encabezado: la gota cae una sola vez al abrir la pagina y deja una onda */
.bawi-gota { position: relative; display: inline-flex; animation: gota-cae .7s cubic-bezier(.3,1.4,.5,1) both; }
.bawi-gota::after { content: ""; position: absolute; left: 50%; bottom: -6px; width: 44px; height: 10px;
  margin-left: -22px; border: 2px solid var(--agua); border-radius: 50%; opacity: 0;
  animation: onda 1s ease-out .55s 1; }
@keyframes gota-cae { from { transform: translateY(-26px); opacity: 0; } to { transform: none; opacity: 1; } }
@keyframes onda { 0% { transform: scale(.3); opacity: .9; } 100% { transform: scale(1.6); opacity: 0; } }

/* Historias = temas. Circulos con anillo; en el celular se deslizan de lado */
.st-key-historias [role="radiogroup"], .st-key-historias [data-baseweb="button-group"] {
  flex-wrap: nowrap; overflow-x: auto; gap: 8px; padding: 6px 4px 8px; scrollbar-width: none; }
.st-key-historias [role="radiogroup"]::-webkit-scrollbar { display: none; }
.st-key-historias button { flex: 0 0 auto; width: 76px; height: auto; min-height: 0; overflow: visible;
  padding: 0 !important; background: transparent !important; border: none !important; box-shadow: none !important; }
.st-key-historias button p { margin: 0; font-size: .78rem; color: var(--tenue); white-space: nowrap; text-align: center; }
.st-key-historias button p:first-child { width: 58px; height: 58px; margin: 4px auto 6px; border-radius: 50%;
  font-size: 1.6rem; display: flex; align-items: center; justify-content: center; background: #17241D;
  box-shadow: 0 0 0 2px var(--fondo), 0 0 0 4px var(--borde); transition: transform .15s; }
.st-key-historias button:hover p:first-child { transform: scale(1.06); }
.st-key-historias button[aria-checked="true"] p:first-child,
.st-key-historias [data-testid="stBaseButton-segmented_controlActive"] p:first-child {
  box-shadow: 0 0 0 2px var(--fondo), 0 0 0 4px var(--amarillo); }
.st-key-historias button[aria-checked="true"] p,
.st-key-historias [data-testid="stBaseButton-segmented_controlActive"] p { color: var(--texto); font-weight: 700; }

/* Caja para publicar (en lugar del boton amarillo) */
.st-key-btn_crear_feed button { justify-content: flex-start; border-radius: 14px !important;
  background: var(--tarjeta) !important; border: 1px solid var(--borde) !important; padding: .8rem 1rem; }
.st-key-btn_crear_feed button > div { justify-content: flex-start; }
.st-key-btn_crear_feed button p { color: var(--tenue); }

/* Publicacion: sin caja, separadas por una linea (como Instagram) */
[class*="st-key-tarjeta_pub"] { background: transparent; border: none !important; border-radius: 0;
  padding: .9rem 0 .6rem; border-bottom: 1px solid var(--borde) !important; }
[class*="st-key-tarjeta_pub"] [data-testid="stImage"] img { width: 100%; aspect-ratio: 4 / 3.4; object-fit: cover;
  border-radius: 10px; }
[class*="st-key-tarjeta_pub"] [data-testid="stElementToolbar"] { display: none; }

/* Avatar con anillo segun el rango */
.bawi-autor { display: flex; align-items: center; gap: 11px; }
.bawi-avatar { position: relative; width: 44px; height: 44px; flex-shrink: 0; }
.bawi-avatar::before { content: ""; position: absolute; inset: 0; border-radius: 50%; background: var(--borde); }
.bawi-avatar span { position: absolute; inset: 3px; border-radius: 50%; background: #1E3A2B; color: var(--verde-claro);
  display: flex; align-items: center; justify-content: center; font-weight: 800; font-size: .9rem;
  box-shadow: 0 0 0 2px var(--fondo); }
.anillo-tecnico::before { background: var(--agua); }
.anillo-especialista::before { background: var(--verde-claro); }
.anillo-maestro::before { background: var(--amarillo); }
/* Quien usa B.A.W.I. Riego: anillo de goteros que fluye (unica animacion continua) */
.anillo-riego::before { background: repeating-conic-gradient(var(--agua) 0 16deg, transparent 16deg 26deg);
  animation: fluye 9s linear infinite; }
@keyframes fluye { to { transform: rotate(360deg); } }
.bawi-autor .nombre { font-weight: 700; font-size: .95rem; }
.bawi-autor .detalle { color: var(--tenue); font-size: .8rem; }
.bawi-tema { margin-left: auto; color: var(--tenue); font-size: .8rem; white-space: nowrap; }

/* Lienzo de surcos: publicaciones sin foto */
.bawi-surco { position: relative; aspect-ratio: 4 / 3; border-radius: 10px; overflow: hidden; margin-top: .7rem;
  display: flex; flex-direction: column; justify-content: flex-end; padding: 1.4rem 1.3rem;
  background: repeating-linear-gradient(100deg, rgba(0,0,0,.20) 0 12px, transparent 12px 30px),
              linear-gradient(160deg, var(--c1), var(--c2)); }
.bawi-surco .icono { position: absolute; top: 1rem; left: 1.2rem; font-size: 2rem; }
.bawi-surco .texto-grande { font-size: clamp(1.4rem, 5vw, 2rem); font-weight: 800; line-height: 1.15;
  color: #fff; text-shadow: 0 2px 12px rgba(0,0,0,.45); max-width: 18ch; }
.surco-riego { --c1: #1F5F66; --c2: #0E2E33; }
.surco-plagas { --c1: #8A6A1C; --c2: #3A2C0B; }
.surco-suelo { --c1: #7A5136; --c2: #2E1D12; }
.surco-cultivo { --c1: #2C6B4C; --c2: #0F2A1D; }
.surco-otro { --c1: #3B4A42; --c2: #161D19; }

/* Pie de la publicacion */
.bawi-pie { margin: .1rem 0 .2rem; color: #D5DDD7; line-height: 1.45; white-space: pre-wrap; }
.bawi-pie b { color: var(--texto); }
.bawi-pie .titulo-pub { font-weight: 700; color: var(--texto); }
.bawi-chip-campo { display: inline-block; margin-top: .35rem; font-size: .78rem; color: var(--agua);
  border: 1px solid #285F66; border-radius: 999px; padding: 1px 10px; }

/* Brote (like): gris si no lo has dado; brota al darlo */
[class*="st-key-brote_"] button, [class*="st-key-util_"] button { border: none !important;
  background: transparent !important; padding: 2px 4px !important; min-height: 0; }
[class*="st-key-brote_"] button p { font-size: 1.15rem; font-weight: 700; }
[class*="st-key-brote_off_"] button p { filter: grayscale(1); opacity: .7; }
[class*="st-key-brote_on_"] button p, [class*="st-key-util_on_"] button p {
  display: inline-block; animation: brotar .45s cubic-bezier(.3,1.6,.5,1) both; }
[class*="st-key-util_"] { margin-left: 55px; }
[class*="st-key-util_"] button p { font-size: .85rem; color: var(--tenue); }
[class*="st-key-util_on_"] button p { color: var(--verde-claro); font-weight: 700; }
@keyframes brotar { 0% { transform: scale(.4) translateY(8px); } 60% { transform: scale(1.3) translateY(-3px); }
  100% { transform: none; } }

/* "Ver las N respuestas" como texto, sin caja */
[class*="st-key-tarjeta_pub"] [data-testid="stExpander"] details { border: none; background: transparent; }
[class*="st-key-tarjeta_pub"] [data-testid="stExpander"] summary { padding: .2rem 0; color: var(--tenue); }
[class*="st-key-tarjeta_pub"] [data-testid="stExpander"] summary:hover { color: var(--texto); }
.bawi-respuesta { color: #D5DDD7; margin: .35rem 0 .1rem 55px; white-space: pre-wrap; }
.bawi-funciono { display: inline-block; background: #1F4D2E; color: #B9F08F; border-radius: 8px;
  padding: 2px 10px; font-size: .78rem; font-weight: 700; margin: 4px 0 0 55px; }

/* Dato de campo de Riego: tarjeta con la barra de agua aplicada */
.bawi-campo { margin: .5rem 0 .3rem 55px; border: 1px solid #285F66; border-radius: 12px; padding: .7rem .9rem;
  background: linear-gradient(180deg, #10262A, #0E1714); font-size: .86rem; color: #CFE3E1; }
.bawi-campo .cab { display: flex; justify-content: space-between; color: var(--agua); font-weight: 700; }
.bawi-campo .cab span { color: var(--tenue); font-weight: 400; }
.bawi-campo .numeros { display: grid; grid-template-columns: repeat(3, 1fr); gap: 6px; margin: .55rem 0; }
.bawi-campo .numeros b { display: block; font-size: 1.15rem; color: var(--texto); }
.bawi-campo .numeros small { color: var(--tenue); }
.bawi-barra { height: 8px; border-radius: 99px; background: #1C2B2A; overflow: hidden; }
.bawi-barra i { display: block; height: 100%; width: var(--nivel); border-radius: 99px;
  background: linear-gradient(90deg, #2F8F9B, var(--agua)); transform-origin: left;
  animation: llenar .9s ease-out both; }
@keyframes llenar { from { transform: scaleX(0); } }
.bawi-campo .nota { color: var(--tenue); margin-top: .45rem; }

/* Celular: menos espacio en la portada y sin boton + duplicado */
@media (max-width: 640px) {
  .bawi-logo-grande { display: none; }
  .bawi-hero { font-size: 1.8rem; }
  .st-key-btn_mas { display: none; }
  .bawi-respuesta, .bawi-campo, .bawi-funciono, [class*="st-key-util_"] { margin-left: 0; }
}

/* Capacitacion */
.bawi-palabra { font-size: 2.3rem; font-weight: 800; color: var(--verde-claro); line-height: 1.15; margin: .2rem 0 .5rem; }
.bawi-definicion { font-size: 1.12rem; color: var(--texto); margin-bottom: .8rem; }
.bawi-ejemplo { background: #1A2C22; border-left: 4px solid var(--amarillo); border-radius: 10px;
  padding: .7rem .9rem; color: #D5DDD7; margin-bottom: .8rem; }
.bawi-afirmacion { font-size: 1.35rem; font-weight: 700; line-height: 1.35; margin: .3rem 0 .9rem; }
.bawi-racha { color: var(--amarillo); font-weight: 700; }

/* Arreglo: la foto no se encima en el nombre y no crece de mas en computadora */
[data-testid="stMarkdownContainer"]:has(> .bawi-autor, > .bawi-pie, > .bawi-surco, > .bawi-campo, > .bawi-respuesta, > .bawi-caso) {
  margin-bottom: 0 !important; }
.bawi-autor { padding-bottom: .2rem; }
[class*="st-key-tarjeta_pub"] [data-testid="stImage"] img { max-height: 520px; }

/* Menu "⋯ Opciones" de tus publicaciones: discreto */
[class*="st-key-tarjeta_pub"] [data-testid="stPopover"] button { border: none !important;
  background: transparent !important; padding: 0 4px !important; min-height: 0; }
[class*="st-key-tarjeta_pub"] [data-testid="stPopover"] button p { color: var(--tenue); font-size: .85rem; }

/* Formularios */
.bawi-caso { background: #12221C; border: 1px solid var(--borde); border-left: 4px solid var(--agua);
  border-radius: 10px; padding: .75rem .95rem; color: #D5DDD7; font-size: .93rem; line-height: 1.5; margin: .3rem 0 .6rem; }
.bawi-caso small { display: block; margin-top: .4rem; color: var(--tenue); font-size: .78rem; }
[class*="st-key-fo_"] button, [class*="st-key-lista_form_"] button { justify-content: flex-start;
  border-radius: 12px !important; text-align: left; }
[class*="st-key-fo_"] button > div, [class*="st-key-lista_form_"] button > div { justify-content: flex-start; }

/* Quien prefiere menos movimiento (ajuste del sistema) no ve animaciones */
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after { animation: none !important; transition: none !important; }
}
</style>
"""


def marca(tamano: int = 44, lema: str = "Agua · Talento · Comunidad") -> str:
    return (f'<div class="bawi-marca">{LOGO_SVG.format(t=tamano)}'
            f'<div><div class="titulo">B.A.W.Í.</div><div class="lema">{lema}</div></div></div>')


# --------------------------------------------------------------------------
# Conexion con la API (la app nunca habla directo con la base de datos)
# --------------------------------------------------------------------------
@st.cache_resource
def sesion_http() -> requests.Session:
    """Una sola conexion reutilizable hacia la API (keep-alive): cada clic es mas rapido."""
    return requests.Session()


def llamar_api(metodo: str, ruta: str, base: str = API_COMUNIDAD, **kwargs):
    """Regresa (True, datos) o (False, mensaje de error para mostrar)."""
    headers = kwargs.pop("headers", {})
    if st.session_state.get("token"):
        headers["Authorization"] = f"Bearer {st.session_state.token}"
    try:
        resp = sesion_http().request(metodo, f"{base}{ruta}", headers=headers, timeout=20, **kwargs)
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


def llamar_capacitacion(metodo: str, ruta: str, **kwargs):
    return llamar_api(metodo, ruta, base=API_CAPACITACION, **kwargs)


def iniciar_sesion(datos: dict) -> None:
    st.session_state.vf = None
    st.session_state.token = datos["token"]
    st.session_state.usuario = datos["usuario"]
    st.session_state.invitado = False
    st.session_state.menu = "inicio"


def ir_a(seccion: str) -> None:
    """Cambia de seccion del menu (se usa como on_click de los botones)."""
    st.session_state.menu = seccion


def cerrar_sesion() -> None:
    st.session_state.vf = None
    st.session_state.token = None
    st.session_state.usuario = None
    st.session_state.invitado = False


def avisar(mensaje: str, tipo: str = "success") -> None:
    st.session_state.aviso = (tipo, mensaje)


def avisar_puntos(datos: dict) -> None:
    """Aviso despues de una dinamica: puntos ganados y, si aplica, el nuevo rango (con globos)."""
    mensaje = datos["mensaje"]
    if datos.get("subio_de_rango") and datos.get("rango_nuevo"):
        rango = datos["rango_nuevo"]
        mensaje += f" 🎉 ¡Subiste de rango! Ahora eres {rango['insignia']} **{rango['nombre']}**."
        st.session_state.globos = True
    avisar(mensaje, "success" if datos.get("puntos_ganados") else "info")


@st.cache_data(show_spinner=False, max_entries=200)
def descargar_archivo(ruta: str) -> bytes | None:
    """Descarga una foto o audio desde la API. Se manda como bytes a la pagina,
    asi tambien se ve desde el celular (que no puede abrir 'localhost')."""
    try:
        resp = sesion_http().get(f"{API_URL}{ruta}", timeout=20)
        return resp.content if resp.status_code == 200 else None
    except requests.exceptions.RequestException:
        return None


def iniciales(nombre: str) -> str:
    partes = [p for p in nombre.split() if p]
    return "".join(p[0] for p in partes[:2]).upper() or "?"


def hace(fecha: str) -> str:
    """'2026-10-08 08:12' -> 'hace 2 h' (como Instagram)."""
    try:
        momento = datetime.strptime(fecha, "%Y-%m-%d %H:%M")
    except ValueError:
        return fecha
    segundos = (datetime.now() - momento).total_seconds()
    if segundos < 60:
        return "ahora"
    if segundos < 3600:
        return f"hace {int(segundos // 60)} min"
    if segundos < 86400:
        return f"hace {int(segundos // 3600)} h"
    dias = int(segundos // 86400)
    if dias == 1:
        return "ayer"
    return f"hace {dias} días" if dias < 7 else momento.strftime("%d/%m/%Y")


# Color del anillo del avatar segun el rango; quien usa Riego tiene el anillo de goteros
ANILLOS = {"🌱": "aprendiz", "💧": "tecnico", "🌾": "especialista", "👑": "maestro"}


def cabecera_autor(autor: dict, detalle: str, tema: str | None = None) -> None:
    """Avatar con anillo de rango, nombre con insignia y detalle (zona, fecha)."""
    rango = autor["rango"]
    anillo = "riego" if autor["usa_riego"] else ANILLOS.get(rango["insignia"], "aprendiz")
    riego = " · 💧 riega con B.A.W.Í." if autor["usa_riego"] else ""
    tema_html = f'<span class="bawi-tema">{html.escape(tema)}</span>' if tema else ""
    st.markdown(
        f'<div class="bawi-autor">'
        f'<div class="bawi-avatar anillo-{anillo}" title="{html.escape(rango["nombre"])}">'
        f'<span>{html.escape(iniciales(autor["nombre"]))}</span></div>'
        f'<div><div class="nombre">{html.escape(autor["nombre"])} '
        f'<span title="{html.escape(rango["nombre"])}">{rango["insignia"]}</span></div>'
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
    """Tarjeta con el calculo real de B.A.W.I. Riego que adjunto el productor.
    La barra muestra cuanto rego frente a lo recomendado."""
    estado = ESTADOS_RIEGO.get(dato["estado"], dato["estado"])
    aplicadas = dato["horas_aplicadas"] if dato["estado"] in ("aceptada", "ajustada") else None
    if aplicadas is not None and dato["horas_sugeridas"]:
        nivel = min(aplicadas / dato["horas_sugeridas"], 1.0) * 100
        regado = f"{aplicadas:g} h"
    else:
        nivel, regado = 0, "—"
    ahorro = f" · ahorró {dato['agua_ahorrada_m3']:,.0f} m³" if dato["agua_ahorrada_m3"] else ""
    st.markdown(
        f'<div class="bawi-campo">'
        f'<div class="cab">📊 Dato de campo de B.A.W.Í. Riego<span>{html.escape(dato["fecha"])}</span></div>'
        f'<div>🌳 {html.escape(dato["cultivo"])}, etapa {html.escape(dato["etapa"].lower())} · '
        f'{html.escape(dato["municipio"])}</div>'
        f'<div class="numeros">'
        f'<div><b>{dato["etc_mm"]:g} mm</b><small>consumo del día</small></div>'
        f'<div><b>{dato["horas_sugeridas"]:g} h</b><small>recomendadas</small></div>'
        f'<div><b>{regado}</b><small>el productor {estado}</small></div>'
        f'</div>'
        f'<div class="bawi-barra"><i style="--nivel:{nivel:.0f}%"></i></div>'
        f'<div class="nota">🌡️ {dato["temp_max_c"]:g} °C máx · 🌧️ {dato["prob_lluvia_pct"]} % lluvia · '
        f'riesgo {html.escape(str(dato["riesgo"]).lower())}{ahorro}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )


def mostrar_respuestas(pub: dict) -> None:
    """Respuestas (ya vienen con el feed) y, si el rango lo permite, el formulario para responder."""
    soy_autor = bool(yo) and yo["id_usuario"] == pub["autor"]["id_usuario"]
    for resp in pub.get("respuestas", []):
        cabecera_autor(resp["autor"], hace(resp["creada_en"]))
        st.markdown(f'<div class="bawi-respuesta">{html.escape(resp["texto"])}</div>', unsafe_allow_html=True)
        if resp["le_funciono_al_autor"]:
            st.markdown('<span class="bawi-funciono">✅ Le funcionó al autor</span>', unsafe_allow_html=True)
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
            texto_boton = ("👍 Útil" if resp["yo_di_like"] else "👍 ¿Te sirvió?") + f" · {resp['likes']}"
        ayuda = None
        if not yo:
            ayuda = "Inicia sesión para dar like."
        elif es_mia:
            ayuda = "No puedes dar like a tu propia respuesta."
        elif soy_autor:
            ayuda = "Márcala solo si pusiste en práctica la recomendación y te funcionó."
        # La clave cambia con el estado: asi la animacion solo corre al darle like
        clave = f"util_{'on' if resp['yo_di_like'] else 'off'}_{resp['id_respuesta']}"
        if st.button(texto_boton, key=clave, disabled=not yo or es_mia, help=ayuda):
            dar_like(f"/respuestas/{resp['id_respuesta']}/like")
            st.rerun()

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
    """Publicacion estilo Instagram: autor, foto (o lienzo de surcos), brotes, pie y respuestas."""
    tema = CATEGORIAS.get(pub["categoria"], pub["categoria"])
    with st.container(key=f"tarjeta_pub_{pub['id_publicacion']}"):
        detalle = hace(pub["creada_en"]) + (" · editada" if pub.get("editada") else "")
        cabecera_autor(pub["autor"], detalle, tema)

        foto = descargar_archivo(pub["imagen"]) if pub["imagen"] else None
        if foto:
            st.image(foto, width="stretch")
        else:
            # Sin foto: el titulo se muestra grande sobre surcos del color del tema
            icono = tema.split()[0]
            st.markdown(
                f'<div class="bawi-surco surco-{html.escape(pub["categoria"])}"><span class="icono">{icono}</span>'
                f'<div class="texto-grande">{html.escape(pub["titulo"])}</div></div>',
                unsafe_allow_html=True,
            )
        if pub["audio"]:
            audio = descargar_archivo(pub["audio"])
            if audio:
                st.audio(audio)

        # Brote = like. La clave cambia con el estado para que la animacion corra solo al darlo
        clave = f"brote_{'on' if pub['yo_di_like'] else 'off'}_{pub['id_publicacion']}"
        if st.button(f"🌱 {pub['likes']}", key=clave, disabled=not yo,
                     help="Dale un brote si esta publicación te sirvió." if yo else "Inicia sesión para dar like."):
            dar_like(f"/publicaciones/{pub['id_publicacion']}/like")
            st.rerun()

        respuestas = pub.get("respuestas", [])
        con_dato = any(r["dato_riego"] for r in respuestas)
        chip = '<br><span class="bawi-chip-campo">📊 Respondida con dato de campo real</span>' if con_dato else ""
        titulo = (f'<span class="titulo-pub">{html.escape(pub["titulo"])}</span><br>' if foto else "")
        st.markdown(
            f'<div class="bawi-pie"><b>{html.escape(pub["autor"]["nombre"])}</b> {titulo}'
            f'{html.escape(pub["texto"])}{chip}</div>',
            unsafe_allow_html=True,
        )
        if yo and yo["id_usuario"] == pub["autor"]["id_usuario"]:
            opciones_de_autor(pub)

        n = pub["num_respuestas"]
        etiqueta = f"Ver {'la respuesta' if n == 1 else f'las {n} respuestas'}" if n else "Aún sin respuestas"
        with st.expander(etiqueta):
            mostrar_respuestas(pub)


def opciones_de_autor(pub: dict) -> None:
    """Menu ⋯ que solo ve quien publico: editar o eliminar."""
    id_pub = pub["id_publicacion"]
    with st.popover("⋯ Opciones"):
        if st.button("✏️ Editar publicación", key=f"editar_{id_pub}", width="stretch"):
            dialogo_editar(pub)
        st.divider()
        seguro = st.checkbox("Sí, quiero eliminarla (también se borran sus respuestas)", key=f"seguro_{id_pub}")
        if st.button("🗑️ Eliminar publicación", key=f"borrar_{id_pub}", disabled=not seguro, width="stretch"):
            ok, datos = llamar_api("DELETE", f"/publicaciones/{id_pub}")
            if ok:
                avisar("Publicación eliminada.")
                st.rerun()
            st.error(datos)


@st.dialog("Editar publicación", width="large")
def dialogo_editar(pub: dict) -> None:
    temas = list(CATEGORIAS)
    with st.form(f"form_editar_{pub['id_publicacion']}", border=False):
        titulo = st.text_input("Título", value=pub["titulo"])
        categoria = st.selectbox("Tema", temas, format_func=lambda c: CATEGORIAS[c],
                                 index=temas.index(pub["categoria"]) if pub["categoria"] in temas else 0)
        texto = st.text_area("Contenido", value=pub["texto"], height=140)
        st.caption("La foto y la nota de voz se quedan como están.")
        guardar = st.form_submit_button("Guardar cambios", type="primary", width="stretch")
    if guardar:
        if len(titulo.strip()) < 3 or len(texto.strip()) < 3:
            st.error("Escribe un título y un contenido de al menos 3 letras.")
            return
        ok, datos = llamar_api("PUT", f"/publicaciones/{pub['id_publicacion']}",
                               json={"titulo": titulo, "texto": texto, "categoria": categoria})
        if ok:
            avisar("Publicación actualizada.")
            st.rerun()
        st.error(datos)


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


HISTORIAS = {"todas": "🌄\n\nTodo", **{c: e.replace(" ", "\n\n", 1) for c, e in CATEGORIAS.items()}}


def mostrar_feed(orden: str) -> None:
    with st.container(key="feed"):
        if st.button("📷  ¿Qué observaste hoy en tu parcela?", key="btn_crear_feed", width="stretch"):
            dialogo_publicar()
        # Historias = temas: tocar un circulo filtra el feed
        with st.container(key="historias"):
            filtro = st.segmented_control(
                "Tema", list(HISTORIAS), default="todas", label_visibility="collapsed",
                format_func=lambda c: HISTORIAS[c], key=f"filtro_{orden}",
            )
        parametros = {"orden": orden, "con_respuestas": "true"}
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
        elif st.session_state.registro:
            pantalla_codigo()
        else:
            st.markdown('<div class="bawi-etiqueta">Únete a Comunidad</div>', unsafe_allow_html=True)
            st.subheader("Crear cuenta")
            st.caption("Paso 1 de 2 · Te enviaremos un código a tu correo para confirmar que es tuyo.")
            with st.form("form_crear", border=False):
                nombre = st.text_input("Nombre que aparecerá en tu perfil")
                correo = st.text_input("Correo electrónico", placeholder="tu@correo.com")
                municipio = st.selectbox("Zona de tu cultivo", REGIONES)
                password = st.text_input("Contraseña (mínimo 6)", type="password")
                confirmacion = st.text_input("Confirma tu contraseña", type="password")
                crear = st.form_submit_button("Enviarme el código", type="primary", width="stretch")
            if crear:
                if password != confirmacion:
                    st.error("Las contraseñas no coinciden.")
                else:
                    with st.spinner("Enviando el código a tu correo..."):
                        ok, datos = llamar_api("POST", "/registro/solicitar", json={
                            "nombre": nombre, "correo": correo, "municipio": municipio,
                            "password": password, "confirmacion": confirmacion,
                        })
                    if ok:
                        st.session_state.registro = datos
                        st.rerun()
                    st.error(datos)
            st.divider()
            if st.button("Ya tengo cuenta", width="stretch"):
                st.session_state.vista_acceso = "entrar"
                st.rerun()


def pantalla_codigo() -> None:
    """Paso 2 de crear cuenta: escribir el codigo que llego al correo."""
    registro = st.session_state.registro
    st.markdown('<div class="bawi-etiqueta">Verifica tu correo</div>', unsafe_allow_html=True)
    st.subheader("Escribe tu código")
    st.caption(f"Paso 2 de 2 · Enviamos un código de 6 números a **{registro['correo']}**. "
               f"Vence en {registro['minutos']} minutos. Si no lo ves, revisa la carpeta de spam.")
    with st.form("form_codigo", border=False):
        codigo = st.text_input("Código de verificación", max_chars=6, placeholder="000000")
        verificar = st.form_submit_button("Verificar y crear cuenta", type="primary", width="stretch")
    if verificar:
        ok, datos = llamar_api("POST", "/registro/verificar", json={"correo": registro["correo"], "codigo": codigo.strip()})
        if ok:
            st.session_state.registro = None
            st.session_state.vista_acceso = "entrar"  # al cerrar sesion vuelve a "Iniciar sesion"
            iniciar_sesion(datos)
            avisar(f"¡Correo verificado! Bienvenido a la comunidad, {datos['usuario']['nombre']}.")
            st.rerun()
        st.error(datos)
    if st.button("Reenviar código", width="stretch"):
        with st.spinner("Enviando un código nuevo..."):
            ok, datos = llamar_api("POST", "/registro/reenviar", json={"correo": registro["correo"]})
        if ok:
            st.session_state.registro = datos
            st.success("Te enviamos un código nuevo. El anterior ya no sirve.")
        else:
            st.warning(datos)
    if st.button("Usar otro correo", width="stretch"):
        st.session_state.registro = None
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
                "- **+5** por palabra aprendida o por acierto en Verdadero o falso (una dinámica al día).\n"
                "- Quien contrata **B.A.W.Í. Riego** es Maestro de la Tierra.")
    if st.button("Cerrar sesión"):
        cerrar_sesion()
        st.rerun()


DINAMICAS = {"palabra": "📖 Conoce una palabra", "verdadero_falso": "✅ Verdadero o falso",
             "formulario": "📝 Formularios"}


def aprender_palabra(id_quiz: int) -> None:
    ok, datos = llamar_capacitacion("POST", f"/palabras/{id_quiz}/aprender")
    if ok:
        avisar_puntos(datos)
    else:
        avisar(datos, "warning")


def mostrar_palabra(palabra: dict | None, con_sesion: bool) -> None:
    """Dinamica 1: tarjeta con la palabra del dia, su explicacion sencilla y un ejemplo de campo."""
    if not palabra:
        st.info("Aún no hay palabras cargadas. Corre: python -m backend.seed_capacitacion")
        return
    with st.container(key="tarjeta_palabra"):
        st.markdown('<div class="bawi-etiqueta">Palabra del día</div>'
                    f'<div class="bawi-palabra">{html.escape(palabra["palabra"])}</div>'
                    f'<div class="bawi-definicion">{html.escape(palabra["explicacion"])}</div>',
                    unsafe_allow_html=True)
        if palabra["ejemplo"]:
            st.markdown(f'<div class="bawi-ejemplo">🌾 <b>En el campo:</b> {html.escape(palabra["ejemplo"])}</div>',
                        unsafe_allow_html=True)
        if not con_sesion:
            st.caption("🔒 Inicia sesión para ganar +5 puntos con la palabra del día.")
        elif palabra["con_puntos"]:
            st.button("✅ ¡La aprendí! · +5 puntos", type="primary", width="stretch", key="btn_aprender",
                      on_click=aprender_palabra, args=(palabra["id_quiz"],))
        elif palabra["ya_aprendida"]:
            st.success("Ya aprendiste esta palabra. ¡Mañana habrá otra!")
        else:
            st.caption("Hoy ya ganaste tus puntos de Capacitación. Léela para aprender; mañana podrás sumar.")


# --- Dinamica 3: Verdadero o falso -------------------------------------------------
def empezar_cuestionario(info: dict) -> None:
    ok, quiz = llamar_capacitacion("GET", f"/cuestionarios/{info['id_quiz']}")
    if not ok:
        avisar(quiz, "error")
        return
    st.session_state.vf = {
        "quiz": quiz, "con_puntos": info["con_puntos"], "indice": 0, "primeros": {},
        "aciertos": 0, "racha": 0, "bono": False, "feedback": None, "resuelta": False, "resultado": None,
    }


def responder_afirmacion(id_pregunta: int, id_opcion: int) -> None:
    vf = st.session_state.vf
    ok, revision = llamar_capacitacion("POST", f"/preguntas/{id_pregunta}/revisar", json={"id_opcion": id_opcion})
    if not ok:
        vf["feedback"] = {"tipo": "error", "titulo": revision, "texto": ""}
        return
    primer_intento = str(id_pregunta) not in vf["primeros"]
    if primer_intento:
        vf["primeros"][str(id_pregunta)] = id_opcion
    puntos = vf["quiz"]["puntos_por_acierto"]
    if revision["correcta"]:
        if primer_intento:
            vf["aciertos"] += 1
            vf["racha"] += 1
            titulo = f"¡Correcto! +{puntos} puntos" if vf["con_puntos"] else "¡Correcto!"
            if vf["racha"] >= 3 and not vf["bono"]:
                vf["bono"] = True
                titulo += f" · 🔥 ¡3 seguidas! +{vf['quiz']['bono_racha']} extra" if vf["con_puntos"] else \
                    " · 🔥 ¡3 seguidas!"
        else:
            titulo = "¡Correcto! Aprendizaje completado (sin puntos, porque recibiste una pista)."
        vf["feedback"] = {"tipo": "success", "titulo": titulo, "texto": revision["explicacion"]}
        vf["resuelta"] = True
    else:
        vf["racha"] = 0
        vf["feedback"] = {"tipo": "warning", "titulo": "No es correcto. Tu racha vuelve a cero.",
                          "texto": f"💡 Pista: {revision['pista']} Intenta de nuevo."}


def siguiente_afirmacion() -> None:
    vf = st.session_state.vf
    preguntas = vf["quiz"]["preguntas"]
    if vf["indice"] + 1 < len(preguntas):
        vf["indice"] += 1
        vf["feedback"] = None
        vf["resuelta"] = False
        return
    total = len(preguntas)
    if not st.session_state.token:  # sin cuenta: solo practica
        vf["resultado"] = {"aciertos": vf["aciertos"], "total": total, "puntos_ganados": 0, "bono_racha": 0,
                           "mensaje": "Practicaste sin cuenta. Inicia sesión para ganar puntos y subir de rango."}
        return
    respuestas = [{"id_pregunta": int(p), "id_opcion": o} for p, o in vf["primeros"].items()]
    ruta = vf.get("ruta_terminar") or f"/cuestionarios/{vf['quiz']['id_quiz']}/terminar"
    ok, resultado = llamar_capacitacion("POST", ruta, json={"respuestas": respuestas})
    if not ok:
        vf["feedback"] = {"tipo": "error", "titulo": resultado, "texto": ""}
        return
    vf["resultado"] = resultado
    if resultado.get("subio_de_rango"):
        avisar_puntos(resultado)


def salir_cuestionario() -> None:
    st.session_state.vf = None


def mostrar_verdadero_falso(info: dict | None, con_sesion: bool) -> None:
    vf = st.session_state.vf
    if vf and vf.get("tipo") == "formulario":  # hay un formulario a medias: aqui no se mezcla
        vf = None
    if vf and vf["resultado"]:
        r = vf["resultado"]
        with st.container(key="tarjeta_resultado"):
            st.markdown('<div class="bawi-etiqueta">Cuestionario terminado</div>', unsafe_allow_html=True)
            st.subheader(f"🏁 {vf['quiz']['titulo']}")
            c1, c2, c3 = st.columns(3)
            c1.metric("Aciertos al primer intento", f"{r['aciertos']} de {r['total']}")
            c2.metric("Bono por racha", f"+{r['bono_racha']}")
            c3.metric("Puntos ganados", f"+{r['puntos_ganados']}")
            (st.success if r["puntos_ganados"] else st.info)(r["mensaje"])
            st.button("Volver a Capacitación", width="stretch", on_click=salir_cuestionario, key="btn_volver_vf")
        return

    if not info:
        st.info("Aún no hay cuestionarios cargados. Corre: python -m backend.seed_capacitacion")
        return

    if not vf or vf["quiz"]["id_quiz"] != info["id_quiz"]:
        with st.container(key="tarjeta_vf_inicio"):
            st.markdown('<div class="bawi-etiqueta">Verdadero o falso</div>', unsafe_allow_html=True)
            st.subheader(info["titulo"])
            st.caption(info["descripcion"])
            st.markdown(f"- {info['total']} afirmaciones sobre riego y cuidado del agua.\n"
                        "- **+5** por cada acierto al primer intento y **+5 extra** si aciertas 3 seguidas.\n"
                        "- Si te equivocas, recibes una pista y puedes volver a intentar (sin puntos).")
            if con_sesion and not info["con_puntos"]:
                st.caption("Esta vez es práctica: hoy ya ganaste tus puntos de Capacitación o ya lo completaste.")
            st.button("Comenzar", type="primary", width="stretch", key="btn_empezar_vf",
                      on_click=empezar_cuestionario, args=(info,))
        return

    preguntas = vf["quiz"]["preguntas"]
    pregunta = preguntas[vf["indice"]]
    with st.container(key="tarjeta_vf"):
        st.progress(vf["indice"] / len(preguntas),
                    text=f"Afirmación {vf['indice'] + 1} de {len(preguntas)}"
                         + ("" if vf["con_puntos"] else " · práctica sin puntos"))
        st.markdown(f'<div class="bawi-racha">🔥 Racha: {vf["racha"]}</div>'
                    f'<div class="bawi-afirmacion">“{html.escape(pregunta["enunciado"])}”</div>',
                    unsafe_allow_html=True)
        columnas = st.columns(len(pregunta["opciones"]))
        for columna, opcion in zip(columnas, pregunta["opciones"]):
            icono = "✅" if opcion["texto"].lower().startswith("v") else "❌"
            columna.button(f"{icono} {opcion['texto']}", width="stretch", disabled=vf["resuelta"],
                           key=f"vf_{pregunta['id_pregunta']}_{opcion['id_opcion']}",
                           on_click=responder_afirmacion, args=(pregunta["id_pregunta"], opcion["id_opcion"]))
        feedback = vf["feedback"]
        if feedback:
            getattr(st, feedback["tipo"])(f"**{feedback['titulo']}**  \n{feedback['texto']}")
        if vf["resuelta"]:
            ultima = vf["indice"] + 1 == len(preguntas)
            st.button("Ver resultado 🏁" if ultima else "Siguiente →", type="primary", width="stretch",
                      key="btn_siguiente_vf", on_click=siguiente_afirmacion)
    st.button("Salir del cuestionario", key="btn_salir_vf", on_click=salir_cuestionario)


# --- Formularios: 10 por rango, 5 preguntas de opcion multiple -----------------------
NIVELES = {1: "🌱 Aprendiz", 2: "💧 Técnico", 3: "🌾 Especialista", 4: "👑 Maestro"}
NOMBRE_NIVEL = {1: "Aprendiz del Campo", 2: "Técnico de Riego", 3: "Especialista Agrónomo", 4: "Maestro de la Tierra"}
TEMA_NIVEL = {1: "vocabulario y fundamentos", 2: "lectura y aplicación de datos",
              3: "cálculos encadenados", 4: "revisión crítica y trazabilidad"}
FUENTES = {"M": "Contexto Maestro B.A.W.Í.", "F": "FAO-56", "L": "FAO, Irrigation Water Management",
           "G": "FAO, Drip Irrigation", "U": "Conversión de unidades y aritmética"}


def empezar_formulario(info: dict) -> None:
    ok, quiz = llamar_capacitacion("GET", f"/formularios/{info['id_quiz']}")
    if not ok:
        avisar(quiz, "error")
        return
    st.session_state.vf = {
        "tipo": "formulario", "ruta_terminar": f"/formularios/{info['id_quiz']}/terminar",
        "quiz": quiz, "con_puntos": info["con_puntos"], "indice": 0, "primeros": {},
        "aciertos": 0, "racha": 0, "bono": False, "feedback": None, "resuelta": False, "resultado": None,
    }


def mostrar_formulario_en_curso(vf: dict) -> None:
    quiz = vf["quiz"]
    preguntas = quiz["preguntas"]
    pregunta = preguntas[vf["indice"]]
    with st.container(key="tarjeta_form"):
        st.progress(vf["indice"] / len(preguntas),
                    text=f"{quiz['codigo']} · Pregunta {vf['indice'] + 1} de {len(preguntas)}"
                         + ("" if vf["con_puntos"] else " · práctica sin puntos"))
        st.markdown(f'<div class="bawi-racha">🔥 Racha: {vf["racha"]}</div>', unsafe_allow_html=True)
        if quiz["contexto"]:
            st.markdown(f'<div class="bawi-caso"><b>📋 Caso</b><br>{html.escape(quiz["contexto"])}'
                        f'<small>Valores simulados para practicar; no son recomendaciones para tu cultivo.</small></div>',
                        unsafe_allow_html=True)
        st.markdown(f'<div class="bawi-afirmacion">{html.escape(pregunta["enunciado"])}</div>', unsafe_allow_html=True)
        for letra, opcion in zip("ABCD", pregunta["opciones"]):
            st.button(f"{letra})  {opcion['texto']}", width="stretch", disabled=vf["resuelta"],
                      key=f"fo_{pregunta['id_pregunta']}_{opcion['id_opcion']}",
                      on_click=responder_afirmacion, args=(pregunta["id_pregunta"], opcion["id_opcion"]))
        feedback = vf["feedback"]
        if feedback:
            getattr(st, feedback["tipo"])(f"**{feedback['titulo']}**  \n{feedback['texto']}")
        if vf["resuelta"]:
            fuentes = [FUENTES.get(f, f) for f in (pregunta.get("fuentes") or "").split(",") if f]
            if fuentes:
                st.caption("📚 Fuentes: " + " · ".join(fuentes))
            ultima = vf["indice"] + 1 == len(preguntas)
            st.button("Ver resultado 🏁" if ultima else "Siguiente →", type="primary", width="stretch",
                      key="btn_siguiente_form", on_click=siguiente_afirmacion)
    st.button("Salir del formulario", key="btn_salir_form", on_click=salir_cuestionario)


def mostrar_formularios() -> None:
    vf = st.session_state.vf
    if vf and vf.get("tipo") == "formulario":
        if vf["resultado"]:
            r = vf["resultado"]
            with st.container(key="tarjeta_resultado_form"):
                st.subheader(f"🏁 {vf['quiz']['codigo']} · {vf['quiz']['titulo']}")
                c1, c2, c3 = st.columns(3)
                c1.metric("Aciertos al primer intento", f"{r['aciertos']} de {r['total']}")
                c2.metric("Bono por racha", f"+{r['bono_racha']}")
                c3.metric("Puntos ganados", f"+{r['puntos_ganados']}")
                (st.success if r["puntos_ganados"] else st.info)(r["mensaje"])
                st.button("Volver a Formularios", width="stretch", on_click=salir_cuestionario, key="btn_volver_form")
        else:
            mostrar_formulario_en_curso(vf)
        return

    ok, datos = llamar_capacitacion("GET", "/formularios")
    if not ok:
        st.error(datos)
        return
    if not datos["formularios"]:
        if datos["en_revision"]:
            st.info(f"📝 Hay {datos['en_revision']} formularios en revisión técnica. Aparecerán aquí al aprobarlos.")
        else:
            st.info("Aún no hay formularios cargados. Corre: python -m backend.seed_formularios")
        return

    mi_nivel = datos["nivel_usuario"]
    st.caption("Cada rango tiene 10 formularios de 5 preguntas. Los de **tu rango** dan puntos "
               "(+5 por acierto al primer intento y +5 por 3 seguidas, máximo 30); los de rangos anteriores "
               "son práctica. Si fallas, ves la explicación y puedes volver a intentar.")
    nivel = st.segmented_control("Nivel", list(NIVELES), default=mi_nivel, key="nivel_form",
                                 format_func=lambda n: NIVELES[n] + (" · tú" if n == mi_nivel else ""),
                                 label_visibility="collapsed") or mi_nivel
    st.markdown(f"**{NOMBRE_NIVEL[nivel]}** · {TEMA_NIVEL[nivel]}")
    if nivel > mi_nivel:
        st.caption(f"🔒 Se desbloquean al llegar a {NOMBRE_NIVEL[nivel]}.")
    for f in [f for f in datos["formularios"] if f["nivel"] == nivel]:
        if f["completado"]:
            estado = "✅ completado"
        elif f["con_puntos"]:
            estado = "⭐ da puntos"
        elif f["bloqueado"]:
            estado = "🔒"
        else:
            estado = "práctica"
        st.button(f"{f['codigo']} · {f['titulo']}  —  {estado}", key=f"lista_form_{f['id_quiz']}",
                  width="stretch", disabled=f["bloqueado"], on_click=empezar_formulario, args=(f,))


def pantalla_capacitacion() -> None:
    st.markdown('<div class="bawi-etiqueta">Talento y capacitación</div>', unsafe_allow_html=True)
    st.subheader("🎓 Capacitación")
    ok, hoy = llamar_capacitacion("GET", "/hoy")
    if not ok:
        st.error(hoy)
        return
    if not hoy["con_sesion"]:
        st.info("📖 Estás practicando sin cuenta. Inicia sesión para ganar puntos y subir de rango.")
    elif hoy["hecha_hoy"]:
        d = hoy["dinamica_de_hoy"]
        st.success(f"✅ Ya hiciste tu dinámica de hoy: **{d['tipo']} · {d['titulo']}** (+{d['puntos']} puntos). "
                   "Vuelve mañana por más puntos; mientras, puedes practicar.")
    else:
        st.info("🎯 Elige **una** dinámica para hoy: solo la primera que completes da puntos.")
    with st.expander("¿Cómo gano puntos en Capacitación?"):
        st.table([
            {"Situación": "Palabra del día aprendida", "Regla": "+5 puntos"},
            {"Situación": "Acierto en el primer intento", "Regla": "+5 puntos"},
            {"Situación": "Tres aciertos seguidos al primer intento", "Regla": "+5 extra, una vez por cuestionario"},
            {"Situación": "Respuesta incorrecta", "Regla": "Pista breve; la racha vuelve a cero"},
            {"Situación": "Acierto después de recibir ayuda", "Regla": "Aprendizaje completado, sin puntos"},
            {"Situación": "Repetir una dinámica", "Regla": "Puedes practicar, sin volver a ganar puntos"},
        ])
        st.caption("Máximo una dinámica con puntos al día.")

    dinamica = st.segmented_control("Dinámica", list(DINAMICAS), format_func=lambda d: DINAMICAS[d],
                                    default="palabra", key="dinamica", label_visibility="collapsed")
    if dinamica == "verdadero_falso":
        mostrar_verdadero_falso(hoy["cuestionario"], hoy["con_sesion"])
    elif dinamica == "formulario":
        mostrar_formularios()
    else:
        mostrar_palabra(hoy["palabra"], hoy["con_sesion"])


# --------------------------------------------------------------------------
# Pagina
# --------------------------------------------------------------------------
st.set_page_config(page_title="B.A.W.Í. Comunidad", page_icon="💧", layout="wide")
st.markdown(CSS, unsafe_allow_html=True)
for clave, valor in {"token": None, "usuario": None, "aviso": None, "invitado": False,
                     "vista_acceso": "entrar", "menu": "inicio", "vf": None, "globos": False,
                     "registro": None}.items():
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
    if st.session_state.globos:
        st.balloons()
        st.session_state.globos = False


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
    f'<div class="bawi-marca" style="margin:.8rem 0 .2rem"><span class="bawi-gota">{LOGO_SVG.format(t=52)}</span><div>'
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