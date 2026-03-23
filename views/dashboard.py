import streamlit as st
import pandas as pd
import plotly.express as px

from db import get_diario, get_saldo, get_partidas_config
from utils import fmt, fmtD, sum_tipo


def render(ano: int, cur_id: int | None) -> None:
    st.title(f"🏠 Resumo — Ano {ano}")
    st.caption("Visión xeral da contabilidade do centro")

    fm = get_diario("func", ano, cur_id)
    cm = get_diario("com",  ano, cur_id)
    sa_f = get_saldo(ano, "func"); sa_c = get_saldo(ano, "com")
    fd = sum_tipo(fm,"G"); fh = sum_tipo(fm,"I"); fs = sa_f + fh - fd
    cd = sum_tipo(cm,"G"); ch = sum_tipo(cm,"I"); cs = sa_c + ch - cd

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("📘 Saldo Funcionamento", fmt(fs),  delta=fmt(fh-fd))
    c2.metric("🍽️ Saldo Comedor",       fmt(cs),  delta=fmt(ch-cd))
    c3.metric("📝 Movementos", len(fm)+len(cm),   delta=f"F:{len(fm)} C:{len(cm)}")
    c4.metric("📋 Partidas configuradas", len(get_partidas_config()))

    st.divider()
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("📘 Funcionamento — gastos por código")
        cats = {}
        for m in fm:
            if m["tipo"] == "G":
                k = m.get("cod_desc") or m.get("codigo") or "Outros"
                cats[k] = cats.get(k, 0) + m["importe"]
        if cats:
            df_c = (pd.DataFrame(list(cats.items()), columns=["Cat","Val"])
                    .sort_values("Val", ascending=False).head(8))
            fig = px.bar(df_c, x="Val", y="Cat", orientation="h",
                         color_discrete_sequence=["#1e40af"])
            fig.update_layout(height=280, margin=dict(l=0,r=0,t=0,b=0),
                              showlegend=False, xaxis_title="", yaxis_title="")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Sen datos de gastos")

    with col2:
        st.subheader("🍽️ Comedor — por categoría")
        cats = {}
        for m in cm:
            if m["tipo"] == "G":
                k = m.get("categoria") or "Outros"
                cats[k] = cats.get(k, 0) + m["importe"]
        if cats:
            df_c = pd.DataFrame(list(cats.items()), columns=["Cat","Val"])
            fig = px.pie(df_c, values="Val", names="Cat",
                         color_discrete_sequence=px.colors.qualitative.Set2)
            fig.update_layout(height=280, margin=dict(l=0,r=0,t=0,b=0))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Sen datos de gastos")

    st.subheader("🕐 Últimos movementos")
    all_m = sorted(
        [{**m, "_a":"func"} for m in fm] + [{**m, "_a":"com"} for m in cm],
        key=lambda x: x.get("data",""), reverse=True
    )[:10]
    if all_m:
        df = pd.DataFrame([{
            "Área":    "📘 Func" if m["_a"]=="func" else "🍽️ Com",
            "Data":    fmtD(m.get("data","")),
            "Concepto": m.get("concepto",""),
            "Curso":   m.get("curso_nome",""),
            "Período": m.get("periodo",""),
            "Partida": m.get("xustifica",""),
            "Debe €":  m["importe"] if m["tipo"]=="G" else None,
            "Haber €": m["importe"] if m["tipo"]=="I" else None,
        } for m in all_m])
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("Rexistra o primeiro movemento en 📒 Diario Funcionamento ou 🍽️ Diario Comedor")
