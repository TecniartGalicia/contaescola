"""
components/sidebar.py
Sidebar de navegación. Devuelve (ano_activo, curso_id_filtro).
"""
import streamlit as st
from db import get_anos, get_ano_activo, set_ano_activo, get_cursos, add_ano

PAGES = [
    ("📊", "Dashboard",             "dash"),
    ("📒", "Diario Funcionamento",  "func"),
    ("⚖️", "Balance Funcionamento", "funcbal"),
    ("🍽️", "Diario Comedor",        "com"),
    ("⚖️", "Balance Comedor",       "combal"),
    ("📋", "Partidas Finalistas",   "part"),
    ("🎓", "Becas NEAE",            "becas"),
    ("📈", "Informes e Filtros",    "inf"),
    ("🏛️", "Modelo 347",            "m347"),
    ("🏢", "Clientes/Provedores",   "cl"),
    ("👤", "Alumnos NEAE",          "al"),
    ("⚙️", "Tablas Maestras",       "mae"),
    ("🖨️", "Configuración PDF",     "cfgpdf"),
    ("📤", "Exportar",              "exp"),
]


def render_sidebar() -> tuple[int, int | None]:
    with st.sidebar:
        st.markdown("## 📒 ContaEscola")
        st.caption("Contabilidade do Centro v6.0")
        st.divider()

        # Selector de año activo
        anos    = get_anos()
        ano_act = get_ano_activo()
        ano_sel = st.selectbox(
            "📅 Ano natural", anos,
            index=anos.index(ano_act) if ano_act in anos else 0,
            key="sb_ano",
        )
        if ano_sel != ano_act:
            set_ano_activo(ano_sel)
            st.rerun()

        # Filtro de curso
        cursos   = get_cursos()
        cur_opts = ["Todos os cursos"] + [c["nome"] for c in cursos]
        cur_sel  = st.selectbox("🎓 Filtro curso", cur_opts, key="sb_cur")
        cur_id   = next((c["id"] for c in cursos if c["nome"] == cur_sel), None)

        # Añadir nuevo año
        with st.expander("➕ Novo ano natural"):
            nv  = st.number_input("Ano", min_value=2020, max_value=2040,
                                  value=ano_sel+1, step=1, key="new_ano_v")
            c1, c2 = st.columns(2)
            fs  = c1.number_input("Saldo Func €", value=0.0, step=0.01, key="new_fs_v")
            cs  = c2.number_input("Saldo Com €",  value=0.0, step=0.01, key="new_cs_v")
            if st.button("Crear", key="btn_add_ano", use_container_width=True):
                add_ano(int(nv), fs, cs)
                st.success(f"Ano {nv} creado!")
                st.rerun()

        st.divider()
        st.caption("NAVEGACIÓN")

        for icon, label, key in PAGES:
            if st.button(f"{icon} {label}", key=f"nav_{key}", use_container_width=True):
                st.session_state["page"] = key
                st.rerun()

        st.divider()
        st.caption(f"🟢 SQLite · Ano {ano_sel}")

    return ano_sel, cur_id
