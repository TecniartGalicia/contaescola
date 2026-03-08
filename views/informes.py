import streamlit as st
import pandas as pd

from db import get_anos, get_cursos, get_codigos, get_clientes, get_partidas_config, get_informes
from db.schema import PERIODOS
from utils import fmt, fmtD, excel_bytes, gen_pdf


def render(ano: int) -> None:
    st.title("📈 Informes e Filtros Cruzados")

    cursos  = get_cursos()
    codigos = get_codigos()
    clientes = get_clientes()
    pcs     = get_partidas_config()
    pnames  = sorted(set(p["nome"] for p in pcs))
    anos    = get_anos()

    with st.form("inf_form"):
        c1, c2, c3, c4 = st.columns(4)
        area_f = c1.selectbox("Área", ["Func + Comedor","Funcionamento","Comedor"])
        ano_f  = c2.selectbox("Ano", ["Todos"] + [str(a) for a in anos],
                              index=next((i+1 for i,a in enumerate(anos) if a==ano), 0))
        cur_f  = c3.selectbox("Curso", ["Todos"] + [c["nome"] for c in cursos])
        tip_f  = c4.selectbox("Tipo", ["Todos","Gastos","Ingresos"])

        c5, c6, c7, c8 = st.columns(4)
        per_f  = c5.selectbox("Período", ["Todos"] + PERIODOS)
        cod_f  = c6.selectbox("Código", ["Todos"] + [
                              f"{c['codigo']} — {c['descripcion']}" for c in codigos])
        part_f = c7.selectbox("Partida", ["Todas"] + pnames)
        cl_f   = c8.selectbox("Cliente", ["Todos"] + [c["nome"] for c in clientes])

        c9, c10 = st.columns(2)
        desde  = c9.date_input("Data desde", value=None, key="inf_desde")
        ata    = c10.date_input("Data ata",  value=None, key="inf_ata")

        submitted = st.form_submit_button("🔍 Xerar informe",
                                          type="primary", use_container_width=True)

    if submitted:
        params: dict = {}
        if area_f == "Funcionamento": params["area"] = "func"
        elif area_f == "Comedor":     params["area"] = "com"
        if ano_f  != "Todos":    params["ano"]        = int(ano_f)
        if cur_f  != "Todos":    params["curso_id"]   = next((c["id"] for c in cursos if c["nome"]==cur_f), None)
        if tip_f  == "Gastos":   params["tipo"]       = "G"
        elif tip_f == "Ingresos": params["tipo"]      = "I"
        if per_f  != "Todos":    params["periodo"]    = per_f
        if cod_f  != "Todos":    params["codigo"]     = cod_f.split(" — ")[0]
        if part_f != "Todas":    params["xustifica"]  = part_f
        if cl_f   != "Todos":    params["cliente_id"] = next((c["id"] for c in clientes if c["nome"]==cl_f), None)
        if desde:                params["fecha_desde"] = str(desde)
        if ata:                  params["fecha_hasta"] = str(ata)

        movs  = get_informes(params)
        debe  = sum(m["importe"] for m in movs if m["tipo"]=="G")
        haber = sum(m["importe"] for m in movs if m["tipo"]=="I")
        st.session_state["inf_result"] = {"movs":movs, "debe":debe, "haber":haber}

    if "inf_result" not in st.session_state:
        return

    data  = st.session_state["inf_result"]
    movs  = data["movs"]; debe = data["debe"]; haber = data["haber"]
    st.divider()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Rexistros", len(movs)); c2.metric("Total Debe",  fmt(debe))
    c3.metric("Total Haber", fmt(haber));  c4.metric("Neto", fmt(haber-debe))

    if not movs:
        st.info("Non se atoparon rexistros cos filtros seleccionados")
        return

    df = pd.DataFrame([{
        "Data":    fmtD(m.get("data","")), "Ano": m.get("ano",""),
        "Área":    m.get("area",""),       "Curso": m.get("curso_nome",""),
        "Concepto": m.get("concepto",""), "Cliente": m.get("cliente_nome",""),
        "NIF":     m.get("cliente_nif",""), "Código": m.get("codigo",""),
        "Período": m.get("periodo",""),   "Partida": m.get("xustifica",""),
        "Debe €":  m["importe"] if m["tipo"]=="G" else None,
        "Haber €": m["importe"] if m["tipo"]=="I" else None,
    } for m in movs])
    st.dataframe(df, use_container_width=True, hide_index=True)

    col_x, col_p, _ = st.columns([1, 1, 4])
    with col_x:
        st.download_button("📊 Excel", data=excel_bytes([("INFORME", df)]),
            file_name=f"Informe_{ano}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    with col_p:
        if st.button("🖨️ PDF", key="inf_pdf_btn"):
            cols_p = ["Data","Ano","Área","Curso","Concepto","Cliente",
                      "NIF","Código","Período","Partida","Debe €","Haber €"]
            filas  = [[fmtD(m.get("data","")), m.get("ano",""), m.get("area",""),
                       m.get("curso_nome",""), m.get("concepto",""),
                       m.get("cliente_nome",""), m.get("cliente_nif",""),
                       m.get("codigo",""), m.get("periodo",""), m.get("xustifica",""),
                       m["importe"] if m["tipo"]=="G" else 0.0,
                       m["importe"] if m["tipo"]=="I" else 0.0] for m in movs]
            pdf, err = gen_pdf(f"Informe — Ano {ano}", f"{len(movs)} rexistros",
                               cols_p, filas, ["","","","","TOTAL","","","","","",debe,haber])
            if err: st.error(f"PDF: {err}")
            else:   st.download_button("⬇️ PDF", data=pdf, file_name=f"Informe_{ano}.pdf",
                        mime="application/pdf", key="inf_pdf_dl")
