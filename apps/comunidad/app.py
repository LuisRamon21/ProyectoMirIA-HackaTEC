"""
B.A.W.I. Comunidad - red de aprendizaje entre productores (Streamlit).

Ejecutar desde la raiz del proyecto:
    streamlit run apps/comunidad/app.py --server.port 8503
"""
import streamlit as st

from datos_ejemplo import PUBLICACIONES, USUARIOS

CATEGORIAS = {
    "riego": "💧 Riego",
    "plagas": "🐛 Plagas",
    "suelo": "🟫 Suelo",
    "cultivo": "🌳 Cultivo",
    "otro": "💬 Otro",
}


def mostrar_publicacion(pub: dict) -> None:
    """Dibuja una publicacion como tarjeta del feed."""
    autor = USUARIOS[pub["autor_id"]]
    with st.container(border=True):
        insignia = " · 💧 usa B.A.W.Í. Riego" if autor["es_riego"] else ""
        st.markdown(f"**{autor['nombre']}** · {autor['region']}{insignia}")
        st.caption(f"{CATEGORIAS[pub['categoria']]} · {pub['fecha']}")
        st.subheader(pub["titulo"])
        st.write(pub["texto"])
        if pub["foto"]:
            st.image(pub["foto"], width=420)
        if pub["audio"]:
            st.audio(pub["audio"])
        st.caption(f"💬 {len(pub['respuestas'])} respuesta(s)")

st.set_page_config(page_title="B.A.W.Í. Comunidad", page_icon="🌾", layout="wide")

st.title("🌾 B.A.W.Í. Comunidad")
st.caption("El Instagram del campo que capacita, explica y certifica el talento agrícola de Chihuahua.")

tab_feed, tab_preguntar, tab_cuenta = st.tabs(["📰 Feed", "✍️ Preguntar", "👤 Mi cuenta"])

with tab_feed:
    filtro = st.segmented_control(
        "Categoría",
        ["todas"] + list(CATEGORIAS),
        format_func=lambda c: "Todas" if c == "todas" else CATEGORIAS[c],
        default="todas",
    )
    if filtro in (None, "todas"):
        visibles = PUBLICACIONES
    else:
        visibles = [p for p in PUBLICACIONES if p["categoria"] == filtro]

    if not visibles:
        st.info("Todavía no hay publicaciones en esta categoría. ¡Haz la primera pregunta!")
    for pub in sorted(visibles, key=lambda p: p["fecha"], reverse=True):
        mostrar_publicacion(pub)

with tab_preguntar:
    st.info("Aquí irá el formulario para hacer una pregunta (paso C).")

with tab_cuenta:
    st.info("Aquí irán las pantallas de entrar y crear cuenta (paso E).")