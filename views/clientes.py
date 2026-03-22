import streamlit as st
import pandas as pd

from db import get_clientes, get_diario_cliente, save_cliente, delete_cliente
from utils import fmtD, fmt


def render() -> None:
    st.title("🏢 Clientes / Provedores")
    clientes = get_clientes()

    tab1, tab2 = st.tabs(["📋 Lista", "➕ Novo / Editar"])

    with tab1:
        tf = st.selectbox("Filtrar por tipo",
                          ["Todos","proveedor","cliente","outro"], key="cl_tf")
        f = clientes if tf == "Todos" else [c for c in clientes if c["tipo"] == tf]
        if f:
            df = pd.DataFrame([{
                "Nome":     c["nome"],  "Tipo": c["tipo"],
                "NIF":      c["nif"],   "Dirección": c.get("direccion",""),
                "Teléfono": c["telefono"], "Email": c["email"],
            } for c in f])
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("Non hai clientes para este filtro")

        # Historial de movimientos de un cliente
        if f:
            st.divider()
            st.subheader("📋 Historial de movementos")
            sel_h = st.selectbox("Ver movementos de",
                                 ["— Seleccionar —"] + [c["nome"] for c in f],
                                 key="cl_hist_sel")
            if sel_h != "— Seleccionar —":
                cl_h  = next(c for c in f if c["nome"] == sel_h)
                movs  = get_diario_cliente(cl_h["id"])
                if movs:
                    total_g = sum(m["importe"] for m in movs if m["tipo"]=="G")
                    total_i = sum(m["importe"] for m in movs if m["tipo"]=="I")
                    c1, c2, c3 = st.columns(3)
                    c1.metric("Nº operacións", len(movs))
                    c2.metric("Total pagado",  fmt(total_g))
                    c3.metric("Total cobrado", fmt(total_i))
                    df_m = pd.DataFrame([{
                        "Data":    fmtD(m.get("data","")),
                        "Ano":     m.get("ano",""),
                        "Área":    m.get("area",""),
                        "Concepto": m.get("concepto",""),
                        "Período": m.get("periodo",""),
                        "Debe €":  m["importe"] if m["tipo"]=="G" else None,
                        "Haber €": m["importe"] if m["tipo"]=="I" else None,
                    } for m in movs])
                    st.dataframe(df_m, use_container_width=True, hide_index=True)
                else:
                    st.info(f"{sel_h} non ten movementos rexistrados")

    with tab2:
        opts = ["— Novo —"] + [f"{c['nome']} ({c['tipo']})" for c in clientes]
        sel  = st.selectbox("Editar ou crear", opts, key="cl_es")
        ce   = None if sel.startswith("—") else clientes[opts.index(sel)-1]

        with st.form("cl_form"):
            c1, c2 = st.columns(2)
            nome = c1.text_input("Nome *", value=ce["nome"] if ce else "")
            tipo = c2.selectbox("Tipo", ["proveedor","cliente","outro"],
                                index=["proveedor","cliente","outro"].index(ce["tipo"])
                                if ce else 0)
            c3, c4 = st.columns(2)
            nif  = c3.text_input("NIF / CIF", value=ce["nif"]      if ce else "")
            tel  = c4.text_input("Teléfono",  value=ce["telefono"] if ce else "")
            direc = st.text_input("Enderezo / Dirección",
                                  value=ce.get("direccion","") if ce else "")
            email = st.text_input("Email", value=ce["email"] if ce else "")
            notas = st.text_area("Notas", value=ce["notas"] if ce else "", height=55)

            cs, cd = st.columns([3, 1])
            sv = cs.form_submit_button("💾 Gardar", type="primary", use_container_width=True)
            dl = cd.form_submit_button("🗑️ Eliminar", use_container_width=True) if ce else False

            if sv:
                if not nome.strip():
                    st.error("Nome obrigatorio")
                else:
                    d = {"nome": nome.strip(), "tipo": tipo, "nif": nif.strip(),
                         "direccion": direc.strip(), "telefono": tel,
                         "email": email, "notas": notas}
                    if ce: d["id"] = ce["id"]
                    save_cliente(d)
                    st.success("Gardado ✓"); st.rerun()
            if dl and ce:
                delete_cliente(ce["id"]); st.success("Eliminado"); st.rerun()
