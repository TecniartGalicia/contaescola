"""
ContaEscola v6.0 — Streamlit
Executa: streamlit run app.py
"""
import streamlit as st
import bcrypt

from db import init_db
from db.connection import q, mut
from components import render_sidebar
from components.sidebar import render_loader, LOGO_B64

from views import (dashboard, diario, balance, partidas, becas,
                   informes, modelo_347, clientes, alumnos,
                   maestras, cfg_pdf, exportar)

st.set_page_config(
    page_title="ContaEscola",
    page_icon="📒",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""<style>
[data-testid="stSidebar"]{background:#0f172a;}
[data-testid="stSidebar"] *{color:#94a3b8 !important;}
div[data-testid="stMetric"]{background:white;border-radius:10px;padding:14px;
  box-shadow:0 1px 3px rgba(0,0,0,.08);border-left:4px solid #1e40af;}
h1{font-size:1.6rem !important;}h2{font-size:1.3rem !important;}
</style>""", unsafe_allow_html=True)

# ── Inicialización BD ───────────────────────────────────────────
if "app_loaded" not in st.session_state:
    render_loader()
    st.session_state["app_loaded"] = True
    init_db()
    st.rerun()
else:
    init_db()


# ── LOGIN ───────────────────────────────────────────────────────
def check_login(username: str, password: str) -> bool:
    rows = q("SELECT password FROM usuarios WHERE username=? AND activo=1",
             (username.lower().strip(),))
    if not rows:
        return False
    stored = rows[0]["password"].encode()
    return bcrypt.checkpw(password.encode(), stored)


def render_login():
    st.markdown(f"""
        <div style="display:flex;flex-direction:column;align-items:center;
                    justify-content:center;padding:60px 0 20px;">
            <img src="data:image/png;base64,{LOGO_B64}"
                 style="width:110px;margin-bottom:16px;" />
            <div style="font-size:24px;font-weight:600;color:#0f172a;
                        letter-spacing:-0.02em;margin-bottom:4px;">
                ContaEscola
            </div>
            <div style="font-size:13px;color:#64748b;margin-bottom:32px;">
                Acceso á aplicación
            </div>
        </div>
    """, unsafe_allow_html=True)

    col = st.columns([1, 2, 1])[1]
    with col:
        with st.form("login_form"):
            username = st.text_input("👤 Usuario", placeholder="usuario")
            password = st.text_input("🔑 Contrasinal", type="password",
                                     placeholder="••••••••")
            submitted = st.form_submit_button("Entrar", use_container_width=True,
                                              type="primary")
            if submitted:
                if check_login(username, password):
                    st.session_state["logged_in"] = True
                    st.session_state["username"]  = username.lower().strip()
                    st.rerun()
                else:
                    st.error("Usuario ou contrasinal incorrectos")


# ── Control de acceso ───────────────────────────────────────────
if not st.session_state.get("logged_in"):
    render_login()
    st.stop()

# ── App principal (solo si está autenticado) ────────────────────
if "page" not in st.session_state:
    st.session_state["page"] = "dash"

ano, cur_id = render_sidebar()

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
