import streamlit as st
import pandas as pd

from db import get_diario, get_clientes, get_partidas_config, get_partidas_resumen, get_becas_resumen
from utils import excel_bytes


def render(ano: int) -> None:
    st.title("📤 Exportar datos")

    fm       = get_diario("func", ano)
    cm       = get_diario("com",  ano)
    clientes = get_clientes()
    pcs      = get_partidas_config()
    res      = get_partidas_resumen(ano)
    becas    = get_becas_resumen(ano)

    c1, c2 = st.columns(2)

    with c1:
        st.subheader("📘 Funcionamento")
        if fm:
            df_f = pd.DataFrame([{
                "Nº": m.get("num",""), "Data": m.get("data",""),
                "Concepto": m.get("concepto",""), "Curso": m.get("curso_nome",""),
                "Cliente": m.get("cliente_nome",""),
                "Debe €":  m["importe"] if m["tipo"]=="G" else 0,
                "Haber €": m["importe"] if m["tipo"]=="I" else 0,
                "Código":  m.get("codigo",""), "Período": m.get("periodo",""),
                "Partida": m.get("xustifica",""), "NEAE": m.get("alumno_neae",""),
            } for m in fm])
            st.download_button("⬇️ Excel Funcionamento",
                data=excel_bytes([("FUNCIONAMENTO", df_f)]),
                file_name=f"Funcionamento_{ano}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        else:
            st.info("Sen datos de Funcionamento")

    with c2:
        st.subheader("🍽️ Comedor")
        if cm:
            df_c = pd.DataFrame([{
                "Nº": m.get("num",""), "Data": m.get("data",""),
                "Concepto": m.get("concepto",""), "Curso": m.get("curso_nome",""),
                "Cliente": m.get("cliente_nome",""),
                "Debe €":  m["importe"] if m["tipo"]=="G" else 0,
                "Haber €": m["importe"] if m["tipo"]=="I" else 0,
                "Categoría": m.get("categoria",""),
            } for m in cm])
            st.download_button("⬇️ Excel Comedor",
                data=excel_bytes([("COMEDOR", df_c)]),
                file_name=f"Comedor_{ano}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        else:
            st.info("Sen datos de Comedor")

    c3, c4 = st.columns(2)

    with c3:
        st.subheader("📋 Partidas + Becas")
        df_p = pd.DataFrame([{
            "Curso":    p.get("curso_nome",""),
            "Partida":  p["nome"],
            "Asignado": p["importe_asignado"],
            "Gastado":  res.get(p["nome"],{}).get("debe",0),
            "Ingresado": res.get(p["nome"],{}).get("haber",0),
            "Pendente": p["importe_asignado"] - res.get(p["nome"],{}).get("debe",0),
        } for p in pcs])
        brows = []
        for alumno, d in becas.items():
            for m in d["movs"]:
                brows.append({
                    "Alumno": alumno, "Data": m.get("data",""),
                    "Concepto": m.get("concepto",""),
                    "Debe €":  m["importe"] if m["tipo"]=="G" else 0,
                    "Haber €": m["importe"] if m["tipo"]=="I" else 0,
                })
        df_b = (pd.DataFrame(brows) if brows
                else pd.DataFrame(columns=["Alumno","Data","Concepto","Debe €","Haber €"]))
        st.download_button("⬇️ Excel Partidas + Becas",
            data=excel_bytes([("PARTIDAS", df_p), ("BECAS_NEAE", df_b)]),
            file_name=f"Partidas_{ano}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    with c4:
        st.subheader("📦 Exportar todo")
        sheets = []
        if fm:       sheets.append(("FUNCIONAMENTO", pd.DataFrame([
                         {"Nº":m.get("num",""),"Data":m.get("data",""),
                          "Concepto":m.get("concepto",""),
                          "Debe":m["importe"] if m["tipo"]=="G" else 0,
                          "Haber":m["importe"] if m["tipo"]=="I" else 0} for m in fm])))
        if cm:       sheets.append(("COMEDOR", pd.DataFrame([
                         {"Nº":m.get("num",""),"Data":m.get("data",""),
                          "Concepto":m.get("concepto",""),
                          "Debe":m["importe"] if m["tipo"]=="G" else 0,
                          "Haber":m["importe"] if m["tipo"]=="I" else 0} for m in cm])))
        if clientes: sheets.append(("CLIENTES", pd.DataFrame([{
                         "Nome":c["nome"],"Tipo":c["tipo"],"NIF":c["nif"],
                         "Dir":c.get("direccion",""),"Tel":c["telefono"],
                         "Email":c["email"]} for c in clientes])))
        if sheets:
            st.download_button("⬇️ Excel completo",
                data=excel_bytes(sheets),
                file_name=f"ContaEscola_{ano}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        else:
            st.info("Sen datos para exportar")
