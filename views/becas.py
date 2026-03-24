import streamlit as st
import pandas as pd

from db import get_cursos, get_becas_resumen, get_alumnos
from utils import fmt, fmtD


def render(ano: int, cur_id: int | None) -> None:
    st.title("🎓 Becas NEAE")
    st.markdown(
        '<div style="background:#dbeafe;border:1px solid #93c5fd;border-radius:8px;'
        'padding:10px 14px;font-size:13px;color:#1e3a5f;margin-bottom:12px">'
        'ℹ️ Os importes calcúlanse por <strong>curso escolar</strong>, non por ano natural. '
        'Selecciona un curso para ver os totais correctos de cada alumno.</div>',
        unsafe_allow_html=True,
    )

    cursos  = get_cursos()
    cf_opts = ["— Selecciona un curso —"] + [c["nome"] for c in cursos]

    # Preseleccionar cur_id del sidebar si viene
    cur_def = 0
    if cur_id:
        idx = next((i+1 for i, c in enumerate(cursos) if c["id"] == cur_id), 0)
        cur_def = idx

    cur_f = st.selectbox(
        "📅 Curso escolar",
        cf_opts,
        index=cur_def,
        key="beca_cf",
        help="Filtra os alumnos e movementos polo curso escolar, non polo ano natural",
    )

    if cur_f.startswith("—"):
        st.info("Selecciona un curso escolar para ver as becas.")
        return

    cid_f   = next((c["id"] for c in cursos if c["nome"] == cur_f), None)
    becas   = get_becas_resumen(ano, cid_f)
    alumnos = {a["nome"]: a for a in get_alumnos()}

    if not becas:
        st.info("Non hai alumnos NEAE para este curso. Ve a 👤 Alumnos NEAE para crear fichas.")
        return

    # ── Totais globais ────────────────────────────────────────────
    total_asignado = sum(
        float(alumnos.get(n, {}).get("importe_beca", 0) or 0)
        for n in becas
    )
    total_gastado  = sum(d["debe"]  for d in becas.values())
    total_cobrado  = sum(d["haber"] for d in becas.values())
    total_pendente = total_asignado - total_gastado

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Alumnos NEAE",     len(becas))
    c2.metric("Total asignado",   fmt(total_asignado))
    c3.metric("Total gastado",    fmt(total_gastado))
    c4.metric(
        "Total pendente" if total_pendente >= 0 else "⚠️ DÉFICIT TOTAL",
        fmt(abs(total_pendente)),
        delta=fmt(total_pendente) if total_pendente != 0 else None,
        delta_color="normal" if total_pendente >= 0 else "inverse",
    )
    st.divider()

    # ── Detalle por alumno ────────────────────────────────────────
    for alumno_nome, data in sorted(becas.items()):
        al      = data["alumno"]
        movs    = data["movs"]
        gastado = data["debe"]
        cobrado = data["haber"]

        asignado = float(alumnos.get(alumno_nome, {}).get("importe_beca", 0) or 0)
        pendente = asignado - gastado
        pct      = min(100, gastado / asignado * 100) if asignado > 0 else 0
        ico      = "🔴" if pct > 90 else "🟡" if pct > 70 else "🟢"
        curso_lbl = f" · {al.get('curso_nome','—')}" if al.get("curso_nome") else ""

        header = (
            f"{ico} **{alumno_nome}**{curso_lbl} — "
            f"Asignado: {fmt(asignado)} | "
            f"Gastado: {fmt(gastado)} | "
            f"Cobrado: {fmt(cobrado)} | "
            f"{'Pendente: '+fmt(pendente) if pendente >= 0 else '⚠️ EXCESO: '+fmt(abs(pendente))}"
        )

        with st.expander(header, expanded=False):
            cc1, cc2, cc3, cc4 = st.columns(4)
            cc1.metric("💶 Asignado",  fmt(asignado))
            cc2.metric("📤 Gastado",   fmt(gastado))
            cc3.metric("📥 Cobrado",   fmt(cobrado))
            cc4.metric(
                "✅ Pendente" if pendente >= 0 else "⚠️ EXCESO",
                fmt(abs(pendente)),
            )

            if asignado > 0:
                st.progress(pct / 100)
                st.caption(f"{pct:.1f}% da beca executada")

            if movs:
                st.markdown("**📋 Movementos rexistrados:**")
                df = pd.DataFrame([{
                    "Data":     fmtD(m.get("data", "")),
                    "Ano":      m.get("ano", ""),
                    "Área":     m.get("area", ""),
                    "Curso":    m.get("curso_nome", ""),
                    "Concepto": m.get("concepto", ""),
                    "Período":  m.get("periodo", ""),
                    "Debe €":   round(m["importe"], 2) if m["tipo"] == "G" else None,
                    "Haber €":  round(m["importe"], 2) if m["tipo"] == "I" else None,
                } for m in movs])
                st.dataframe(df, use_container_width=True, hide_index=True)
            else:
                st.info(
                    f"ℹ️ {alumno_nome} non ten movementos neste curso. "
                    f"Para rexistrar un gasto, crea un movemento no Diario e "
                    f"selecciona este alumno no campo 'Alumno NEAE'."
                )

            if asignado == 0:
                st.warning(
                    "⚠️ Este alumno non ten importe de beca configurado. "
                    "Ve a 👤 Alumnos NEAE para asignarllo."
                )
