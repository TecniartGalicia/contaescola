import streamlit as st
import pandas as pd

from db import get_cursos, get_partidas_config, get_partidas_resumen
from utils import fmt


def render(ano: int, cur_id: int | None) -> None:
    st.title("📋 Partidas Finalistas")
    st.markdown(
        '<div style="background:#dbeafe;border:1px solid #93c5fd;border-radius:8px;'
        'padding:10px 14px;font-size:13px;color:#1e3a5f;margin-bottom:12px">'
        'ℹ️ Os gastos calcúlanse automaticamente desde os rexistros do Diario.</div>',
        unsafe_allow_html=True,
    )

    cursos  = get_cursos()
    cf_opts = ["Todos os cursos"] + [c["nome"] for c in cursos]
    cur_f   = st.selectbox("Filtrar por curso", cf_opts, key="part_cf")
    cid_f   = next((c["id"] for c in cursos if c["nome"] == cur_f), None)

    pcs = get_partidas_config(cid_f)
    res = get_partidas_resumen(ano, cid_f)

    if not pcs:
        st.info("Non hai partidas configuradas. Ve a ⚙️ Tablas Maestras para crealas.")
        return

    cols = st.columns(3)
    for i, p in enumerate(pcs):
        r    = res.get(p["nome"], {"debe": 0.0, "haber": 0.0})
        pct  = min(100, r["debe"] / p["importe_asignado"] * 100) if p["importe_asignado"] > 0 else 0
        pend = p["importe_asignado"] - r["debe"]
        ico  = "🔴" if pct > 90 else "🟡" if pct > 70 else "🟢"

        with cols[i % 3]:
            st.markdown(f"**{ico} {p['nome']}**")
            st.caption(f"Curso: {p.get('curso_nome','—')}")
            a, b, c = st.columns(3)
            a.metric("Asignado",  fmt(p["importe_asignado"]))
            b.metric("Gastado",   fmt(r["debe"]))
            c.metric("Pendente" if pend >= 0 else "EXCESO", fmt(abs(pend)))
            st.progress(pct / 100)
            st.caption(f"{pct:.1f}% executado")
            st.divider()
