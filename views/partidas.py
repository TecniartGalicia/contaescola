import streamlit as st
import pandas as pd

from db import get_cursos, get_partidas_config, get_partidas_resumen
from utils import fmt


def render(ano: int, cur_id: int | None) -> None:
    st.title("📋 Partidas Finalistas")
    st.markdown(
        '<div style="background:#dbeafe;border:1px solid #93c5fd;border-radius:8px;'
        'padding:10px 14px;font-size:13px;color:#1e3a5f;margin-bottom:12px">'
        'ℹ️ Os gastos calcúlanse por <strong>curso escolar</strong>, non por ano natural. '
        'Selecciona un curso para ver o total real da partida (abarca dous anos naturais).</div>',
        unsafe_allow_html=True,
    )

    cursos  = get_cursos()

    # ★ CORRECCIÓN: el filtro por curso es OBLIGATORIO aquí.
    # Las partidas son por curso escolar — si no se selecciona uno
    # los totales serían incorrectos al cambiar el año en el sidebar.
    cf_opts = ["— Selecciona un curso —"] + [c["nome"] for c in cursos]

    # Si viene cur_id del sidebar, preseleccionarlo
    cur_def = 0
    if cur_id:
        idx = next((i+1 for i, c in enumerate(cursos) if c["id"] == cur_id), 0)
        cur_def = idx

    cur_f = st.selectbox(
        "📅 Curso escolar",
        cf_opts,
        index=cur_def,
        key="part_cf",
        help="Os importes suman TODOS os gastos do curso, independentemente do ano natural",
    )

    if cur_f.startswith("—"):
        st.info("Selecciona un curso escolar para ver as partidas.")
        return

    cid_f = next((c["id"] for c in cursos if c["nome"] == cur_f), None)

    pcs = get_partidas_config(cid_f)
    # ★ Pasamos ano como fallback pero cid_f tiene prioridad en la query
    res = get_partidas_resumen(ano, cid_f)

    if not pcs:
        st.info("Non hai partidas configuradas para este curso. Ve a ⚙️ Tablas Maestras para crealas.")
        return

    # Totales globales del curso
    total_asig  = sum(p["importe_asignado"] for p in pcs)
    total_gast  = sum(res.get(p["nome"], {}).get("debe",  0.0) for p in pcs)
    total_pend  = total_asig - total_gast

    c1, c2, c3 = st.columns(3)
    c1.metric("Total asignado",  fmt(total_asig))
    c2.metric("Total gastado",   fmt(total_gast))
    c3.metric("Total pendente" if total_pend >= 0 else "⚠️ EXCESO TOTAL",
              fmt(abs(total_pend)))
    st.divider()

    cols = st.columns(3)
    for i, p in enumerate(pcs):
        r    = res.get(p["nome"], {"debe": 0.0, "haber": 0.0})
        pct  = min(100, r["debe"] / p["importe_asignado"] * 100) if p["importe_asignado"] > 0 else 0
        pend = p["importe_asignado"] - r["debe"]
        ico  = "🔴" if pct > 90 else "🟡" if pct > 70 else "🟢"

        with cols[i % 3]:
            st.markdown(f"**{ico} {p['nome']}**")
            st.caption(f"Curso: {p.get('curso_nome', '—')}")
            a, b, c = st.columns(3)
            a.metric("Asignado",  fmt(p["importe_asignado"]))
            b.metric("Gastado",   fmt(r["debe"]))
            c.metric("Pendente" if pend >= 0 else "EXCESO", fmt(abs(pend)))
            st.progress(pct / 100)
            st.caption(f"{pct:.1f}% executado")
            st.divider()
