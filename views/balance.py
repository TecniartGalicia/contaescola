import streamlit as st
import pandas as pd

from db import get_diario, get_saldo, save_saldo
from db.schema import PERIODOS
from utils import fmt, sum_tipo


def render(area: str, ano: int, cur_id: int | None) -> None:
    label = "Funcionamento" if area == "func" else "Comedor"
    st.title(f"⚖️ Balance {label} — {ano}")

    movs = get_diario(area, ano, cur_id)
    sa   = get_saldo(ano, area)
    d_t  = sum_tipo(movs,"G"); h_t = sum_tipo(movs,"I"); bal = sa + h_t - d_t

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Saldo anterior", fmt(sa))
    c2.metric("Total Debe",     fmt(d_t))
    c3.metric("Total Haber",    fmt(h_t))
    c4.metric("Saldo actual",   fmt(bal), delta=fmt(h_t-d_t))

    with st.expander("✏️ Editar saldo anterior"):
        new_sa = st.number_input("Saldo €", value=float(sa), step=0.01,
                                 key=f"sa_{area}_{ano}")
        if st.button("Gardar saldo", key=f"save_sa_{area}"):
            save_saldo(ano, area, new_sa)
            st.success("Saldo actualizado!")
            st.rerun()

    st.divider()
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Por categoría")
        cats = {}
        for m in movs:
            if m["tipo"] == "G":
                k = ((m.get("cod_desc") or m.get("codigo") or "Outros")
                     if area == "func" else (m.get("categoria") or "Outros"))
                cats[k] = cats.get(k, 0) + m["importe"]
        if cats:
            df_c = (pd.DataFrame(list(cats.items()), columns=["Categoría","Importe €"])
                    .sort_values("Importe €", ascending=False))
            st.dataframe(df_c, use_container_width=True, hide_index=True)
        else:
            st.info("Sen datos de gastos")

    with col2:
        st.subheader("Por trimestre")
        rows = []
        for p in PERIODOS:
            pd_v = sum(m["importe"] for m in movs if m["tipo"]=="G" and m.get("periodo")==p)
            ph_v = sum(m["importe"] for m in movs if m["tipo"]=="I" and m.get("periodo")==p)
            rows.append({"Período":p, "Debe €":pd_v, "Haber €":ph_v, "Saldo €":ph_v-pd_v})
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
