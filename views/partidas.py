import streamlit as st
import pandas as pd

from db import get_cursos, get_partidas_config, get_partidas_resumen
from db.queries import get_diario_partida
from utils import fmt, fmtD


def render(ano: int, cur_id: int | None) -> None:
    st.title("📋 Partidas Finalistas")
    st.markdown(
        '<div style="background:#dbeafe;border:1px solid #93c5fd;border-radius:8px;'
        'padding:10px 14px;font-size:13px;color:#1e3a5f;margin-bottom:12px">'
        'ℹ️ Os importes calcúlanse por <strong>curso escolar</strong>, non por ano natural. '
        'Selecciona un curso para ver os totais reais da partida.</div>',
        unsafe_allow_html=True,
    )

    cursos  = get_cursos()
    cf_opts = ["— Selecciona un curso —"] + [c["nome"] for c in cursos]

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
    pcs   = get_partidas_config(cid_f)
    res   = get_partidas_resumen(ano, cid_f)

    if not pcs:
        st.info("Non hai partidas configuradas para este curso. Ve a ⚙️ Tablas Maestras.")
        return

    # ── Totais globais ─────────────────────────────────────────────
    total_asig = sum(p["importe_asignado"] for p in pcs)
    total_gast = sum(res.get(p["nome"], {}).get("debe",  0.0) for p in pcs)
    # ★ Si importe_asignado=0, usar el total de ingresos (haber) como asignado
    total_ing  = sum(res.get(p["nome"], {}).get("haber", 0.0) for p in pcs)
    total_real = total_asig if total_asig > 0 else total_ing
    total_pend = total_real - total_gast

    c1, c2, c3 = st.columns(3)
    c1.metric("Total asignado",  fmt(total_real))
    c2.metric("Total gastado",   fmt(total_gast))
    c3.metric("Total pendente" if total_pend >= 0 else "⚠️ EXCESO TOTAL",
              fmt(abs(total_pend)))
    st.divider()

    # ── Detalle por partida ────────────────────────────────────────
    for p in pcs:
        r      = res.get(p["nome"], {"debe": 0.0, "haber": 0.0})
        debe   = r["debe"]
        haber  = r["haber"]

        # ★ Si importe_asignado=0 y hay ingresos, usar ingresos como asignado
        asig   = p["importe_asignado"] if p["importe_asignado"] > 0 else haber
        pend   = asig - debe
        pct    = min(100, debe / asig * 100) if asig > 0 else 0
        ico    = "🔴" if pct > 90 else "🟡" if pct > 70 else "🟢"

        # Cabecera del expander con todos los datos visibles
        header = (
            f"{ico} **{p['nome']}** — "
            f"Asignado: {fmt(asig)} | "
            f"Gastado: {fmt(debe)} | "
            f"Ingresado: {fmt(haber)} | "
            f"{'Pendente: '+fmt(pend) if pend >= 0 else '⚠️ EXCESO: '+fmt(abs(pend))}"
        )

        with st.expander(header, expanded=False):
            # Métricas
            cc1, cc2, cc3, cc4 = st.columns(4)
            cc1.metric("💶 Asignado",  fmt(asig))
            cc2.metric("📤 Gastado",   fmt(debe))
            cc3.metric("📥 Ingresado", fmt(haber))
            cc4.metric("✅ Pendente" if pend >= 0 else "⚠️ EXCESO", fmt(abs(pend)))

            if asig > 0:
                st.progress(pct / 100)
                st.caption(f"{pct:.1f}% executado")

            # Movementos asociados a esta partida
            movs = get_diario_partida(p["nome"], cid_f) if cid_f else []
            if movs:
                st.markdown("**📋 Movementos desta partida:**")
                df = pd.DataFrame([{
                    "Data":     fmtD(m.get("data", "")),
                    "Ano":      m.get("ano", ""),
                    "Área":     m.get("area", ""),
                    "Concepto": m.get("concepto", ""),
                    "Cliente":  m.get("cliente_nome", ""),
                    "Período":  m.get("periodo", ""),
                    "Debe €":   round(m["importe"], 2) if m["tipo"] == "G" else None,
                    "Haber €":  round(m["importe"], 2) if m["tipo"] == "I" else None,
                } for m in movs])
                st.dataframe(df, use_container_width=True, hide_index=True)

                # Mini totales
                t_debe  = sum(m["importe"] for m in movs if m["tipo"] == "G")
                t_haber = sum(m["importe"] for m in movs if m["tipo"] == "I")
                st.caption(f"Total gastos: **{fmt(t_debe)}** · Total ingresos: **{fmt(t_haber)}**")
            else:
                st.info("Non hai movementos asociados a esta partida neste curso.")
