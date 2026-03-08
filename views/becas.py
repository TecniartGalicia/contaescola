import streamlit as st
import pandas as pd

from db import get_cursos, get_becas_resumen
from utils import fmt, fmtD


def render(ano: int, cur_id: int | None) -> None:
    st.title("🎓 Becas NEAE")
    st.markdown(
        '<div style="background:#dbeafe;border:1px solid #93c5fd;border-radius:8px;'
        'padding:10px 14px;font-size:13px;color:#1e3a5f;margin-bottom:12px">'
        'ℹ️ Móstranse <strong>todos os alumnos NEAE</strong>. '
        'Os importes calcúlanse dos movementos do Diario con ese alumno asignado.</div>',
        unsafe_allow_html=True,
    )

    cursos  = get_cursos()
    cf_opts = ["Todos"] + [c["nome"] for c in cursos]
    cur_f   = st.selectbox("Filtrar por curso do alumno", cf_opts, key="beca_cf")
    cid_f   = next((c["id"] for c in cursos if c["nome"] == cur_f), None)

    becas = get_becas_resumen(ano, cid_f)
    if not becas:
        st.info("Non hai alumnos NEAE. Ve a 👤 Alumnos NEAE para crear fichas.")
        return

    total_haber = sum(d["haber"] for d in becas.values())
    total_debe  = sum(d["debe"]  for d in becas.values())

    c1, c2, c3 = st.columns(3)
    c1.metric("Alumnos NEAE",   len(becas))
    c2.metric("Total recibido", fmt(total_haber))
    c3.metric("Total gastado",  fmt(total_debe))
    st.divider()

    for alumno, data in sorted(becas.items()):
        al   = data["alumno"]; movs = data["movs"]
        debe = data["debe"];   haber = data["haber"]; pend = haber - debe
        ico  = "🟢" if pend >= 0 else "🔴"
        curso_lbl = f" · Curso: {al.get('curso_nome','—')}" if al.get("curso_nome") else ""

        with st.expander(
            f"{ico} **{alumno}**{curso_lbl} — "
            f"Recibido: {fmt(haber)} | Gastado: {fmt(debe)} | "
            f"{'Pendente: '+fmt(pend) if pend>=0 else '⚠️ DÉFICIT: '+fmt(abs(pend))}",
            expanded=False,
        ):
            if movs:
                df = pd.DataFrame([{
                    "Data":    fmtD(m.get("data","")),
                    "Ano":     m.get("ano",""),
                    "Área":    m.get("area",""),
                    "Curso":   m.get("curso_nome",""),
                    "Concepto": m.get("concepto",""),
                    "Período": m.get("periodo",""),
                    "Debe €":  round(m["importe"],2) if m["tipo"]=="G" else None,
                    "Haber €": round(m["importe"],2) if m["tipo"]=="I" else None,
                } for m in movs])
                st.dataframe(df, use_container_width=True, hide_index=True)
                cc1, cc2, cc3 = st.columns(3)
                cc1.metric("Movementos",   len(movs))
                cc2.metric("Total gastado",  fmt(debe))
                cc3.metric("Total recibido", fmt(haber))
            else:
                st.info(
                    f"ℹ️ {alumno} non ten movementos rexistrados para o ano {ano}. "
                    f"Para rexistrar gastos, crea un movemento no Diario e selecciona "
                    f"este alumno no campo 'Alumno NEAE'."
                )
