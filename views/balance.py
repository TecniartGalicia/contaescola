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
        st.subheader("Gastos por código" if area == "func" else "Gastos por categoría")
        _tabla_desglose(movs, area, "G")

    with col2:
        # Os ingresos de funcionamento levan os seus propios códigos (serie A/B/C,
        # ningún compartido cos de gasto); os de comedor clasifícanse por categoría.
        st.subheader("Ingresos por código" if area == "func" else "Ingresos por categoría")
        _tabla_desglose(movs, area, "I")

    st.subheader("Por trimestre")
    rows = []
    for p in PERIODOS:
        pd_v = sum(m["importe"] for m in movs if m["tipo"]=="G" and m.get("periodo")==p)
        ph_v = sum(m["importe"] for m in movs if m["tipo"]=="I" and m.get("periodo")==p)
        rows.append({"Período":p, "Debe €":pd_v, "Haber €":ph_v, "Saldo €":ph_v-pd_v})
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def _tabla_desglose(movs: list[dict], area: str, tipo: str) -> None:
    """Desglose dos movementos dun tipo ('G' ou 'I'), coa clave propia de cada área."""
    grupos: dict = {}
    for m in movs:
        if m["tipo"] != tipo:
            continue
        if area == "func":
            clave = (m.get("codigo") or "—", m.get("cod_desc") or m.get("codigo") or "Outros")
        else:
            clave = ("", m.get("categoria") or "Outros")
        g = grupos.setdefault(clave, {"n": 0, "total": 0.0})
        g["n"] += 1
        g["total"] += m["importe"]

    if not grupos:
        st.info(f"Sen datos de {'gastos' if tipo == 'G' else 'ingresos'}")
        return

    filas = [{**({"Código": cod} if area == "func" else {}),
              "Descrición" if area == "func" else "Categoría": desc,
              "Nº": v["n"], "Importe €": round(v["total"], 2)}
             for (cod, desc), v in grupos.items()]
    df = pd.DataFrame(filas).sort_values("Importe €", ascending=False)
    st.dataframe(df, use_container_width=True, hide_index=True)
    st.caption(f"**Total: {fmt(sum(v['total'] for v in grupos.values()))}** · "
               f"{sum(v['n'] for v in grupos.values())} asentos")
