"""
ContaEscola v6.0 — Streamlit
Executa: streamlit run app.py

Estructura:
  app.py              ← este fichero: solo config + enrutamiento
  db/                 ← base de datos (conexión, esquema, queries, mutations)
  pages/              ← una página = un archivo
  components/         ← sidebar + formulario compartido
  utils/              ← formatters, excel, pdf (sin Streamlit)
"""
import streamlit as st

from db import init_db
from components import render_sidebar

# ── Importar páginas ────────────────────────────────────────────
from views import (dashboard, diario, balance, partidas, becas,
                   informes, modelo_347, clientes, alumnos,
                   maestras, cfg_pdf, exportar)

# ── Configuración global de Streamlit ──────────────────────────
st.set_page_config(
    page_title="ContaEscola",
    page_icon="📒",
    layout="wide",
    initial_sidebar_state="expanded",
)

# CSS global mínimo
st.markdown("""<style>
[data-testid="stSidebar"]{background:#0f172a;}
[data-testid="stSidebar"] *{color:#94a3b8 !important;}
div[data-testid="stMetric"]{background:white;border-radius:10px;padding:14px;
  box-shadow:0 1px 3px rgba(0,0,0,.08);border-left:4px solid #1e40af;}
h1{font-size:1.6rem !important;}h2{font-size:1.3rem !important;}
</style>""", unsafe_allow_html=True)

# ── Inicialización ──────────────────────────────────────────────
init_db()

if "page" not in st.session_state:
    st.session_state["page"] = "dash"

# ── Sidebar (devuelve año activo y filtro de curso) ─────────────
ano, cur_id = render_sidebar()

# ── Enrutamiento ────────────────────────────────────────────────
page = st.session_state["page"]

ROUTES = {
    "dash":    lambda: dashboard.render(ano, cur_id),
    "func":    lambda: diario.render("func", ano, cur_id),
    "funcbal": lambda: balance.render("func", ano, cur_id),
    "com":     lambda: diario.render("com",  ano, cur_id),
    "combal":  lambda: balance.render("com",  ano, cur_id),
    "part":    lambda: partidas.render(ano, cur_id),
    "becas":   lambda: becas.render(ano, cur_id),
    "inf":     lambda: informes.render(ano),
    "m347":    lambda: modelo_347.render(ano),
    "cl":      lambda: clientes.render(),
    "al":      lambda: alumnos.render(),
    "mae":     lambda: maestras.render(),
    "cfgpdf":  lambda: cfg_pdf.render(),
    "exp":     lambda: exportar.render(ano),
}

if page in ROUTES:
    ROUTES[page]()
else:
    dashboard.render(ano, cur_id)
