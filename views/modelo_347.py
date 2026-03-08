import streamlit as st
import pandas as pd

from db import get_anos, get_347
from db.schema import PERIODOS, UMBRAL_347
from utils import fmt, excel_bytes, gen_pdf


def render(ano: int) -> None:
    st.title("🏛️ Modelo 347")
    st.markdown(
        '<div style="background:#ffedd5;border:1px solid #fed7aa;border-radius:8px;'
        'padding:10px 14px;font-size:13px;color:#7c2d12;margin-bottom:12px">'
        '⚠️ Provedores/clientes con operacións ≥ limiar por <strong>ano natural</strong>. '
        'Desglose por trimestre diferenciando GASTOS e INGRESOS.</div>',
        unsafe_allow_html=True,
    )

    anos = get_anos()
    c1, c2, c3 = st.columns([2, 2, 2])
    ano_w = c1.selectbox("Ano natural", anos,
                         index=anos.index(ano) if ano in anos else 0,
                         key="w347_ano")
    umb_w = c2.number_input("Limiar (€)", value=UMBRAL_347, step=0.01, key="w347_umb")
    if c3.button("🏛️ Calcular", type="primary", use_container_width=True, key="btn_347"):
        st.session_state["r347"] = {
            "data": get_347(ano_w, umb_w), "ano": ano_w, "umbral": umb_w,
        }

    if "r347" not in st.session_state:
        return

    res    = st.session_state["r347"]
    data   = res["data"]; ano_r = res["ano"]; umb_r = res["umbral"]
    st.divider()

    if not data:
        st.success(f"✅ Non hai entidades que superen {fmt(umb_r)} no ano {ano_r}")
        return

    total_g = sum(r["total_pagado"]  for r in data)
    total_i = sum(r["total_cobrado"] for r in data)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Entidades declaradas",      len(data))
    c2.metric("📤 Total GASTOS declarados",  fmt(total_g))
    c3.metric("📥 Total INGRESOS declarados", fmt(total_i))
    c4.metric("Limiar aplicado",           fmt(umb_r))
    st.divider()

    # Detalle por entidad
    for pr in data:
        with st.expander(
            f"🏢 **{pr['nome']}** · NIF: {pr['nif'] or '⚠️SEN NIF'} · "
            f"📤 GASTOS: {fmt(pr['total_pagado'])} · 📥 INGRESOS: {fmt(pr['total_cobrado'])}",
            expanded=False,
        ):
            ci1, ci2 = st.columns(2)
            ci1.markdown(f"**Nome:** {pr['nome']}")
            ci1.markdown(f"**NIF:** {pr['nif'] or '⚠️ Sen NIF'}")
            if pr.get("direccion"): ci1.markdown(f"**Dirección:** {pr['direccion']}")
            if pr.get("email"):     ci1.markdown(f"**Email:** {pr['email']}")
            if pr.get("telefono"):  ci1.markdown(f"**Teléfono:** {pr['telefono']}")
            ci2.metric("Nº operacións",        pr["num_ops"])
            ci2.metric("📤 Total GASTOS",       fmt(pr["total_pagado"]))
            ci2.metric("📥 Total INGRESOS",     fmt(pr["total_cobrado"]))

            st.markdown("**📊 Desglose trimestral:**")
            trim_rows = []
            for per in PERIODOS:
                t = pr["trimestres"][per]
                trim_rows.append({
                    "Trimestre":        per,
                    "📤 Gastos (Debe) €": round(t["gastos"],   2) if t["gastos"]   else None,
                    "📥 Ingresos (Haber) €": round(t["ingresos"],2) if t["ingresos"] else None,
                    "Neto €":           round(t["ingresos"] - t["gastos"], 2),
                })
            st.dataframe(pd.DataFrame(trim_rows), use_container_width=True, hide_index=True)
            tot_g = pr["total_pagado"]; tot_i = pr["total_cobrado"]
            st.markdown(
                f"**Total anual → 📤 Gastos: {fmt(tot_g)} · "
                f"📥 Ingresos: {fmt(tot_i)} · Neto: {fmt(tot_i-tot_g)}**"
            )

    # Tabla resumen + exportar
    st.subheader("📋 Resumo para declaración")
    df_sum = pd.DataFrame([{
        "Nome":                   r["nome"],
        "NIF":                    r["nif"] or "⚠️SEN NIF",
        "Dirección":              r.get("direccion",""),
        "Email":                  r.get("email",""),
        "📤 Total Gastos €":      round(r["total_pagado"],  2),
        "📥 Total Ingresos €":    round(r["total_cobrado"], 2),
        "Nº ops":                 r["num_ops"],
    } for r in data])
    st.dataframe(df_sum, use_container_width=True, hide_index=True)

    # Excel con dos hojas
    rows_trim = []
    for pr in data:
        for per in PERIODOS:
            t = pr["trimestres"][per]
            rows_trim.append({
                "Nome": pr["nome"], "NIF": pr["nif"],
                "Trimestre": per,
                "Gastos €":   t["gastos"],
                "Ingresos €": t["ingresos"],
                "Neto €":     t["ingresos"] - t["gastos"],
            })

    col_x, col_p, _ = st.columns([1, 1, 4])
    with col_x:
        xl = excel_bytes([
            ("RESUMO_347",         df_sum),
            ("DESGLOSE_TRIMESTRAL", pd.DataFrame(rows_trim)),
        ])
        st.download_button("📊 Excel 347", data=xl,
            file_name=f"Modelo347_{ano_r}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    with col_p:
        if st.button("🖨️ PDF 347", key="pdf347_btn"):
            # Tabla plana: por cada empresa → fila resumen + 4 filas de trimestre
            # Columnas: Nome | NIF | Trimestre | 📤 Gastos | 📥 Ingresos | Neto
            cols_p = ["Nome / NIF", "Dirección", "Trimestre",
                      "📤 Gastos €", "📥 Ingresos €", "Neto €"]
            filas = []
            for r in data:
                nif_txt = r["nif"] or "⚠️ SEN NIF"
                # Fila resumen anual de la empresa (sombreada con totales)
                filas.append([
                    f"{r['nome']}  [{nif_txt}]",
                    r.get("direccion", ""),
                    "TOTAL ANUAL",
                    r["total_pagado"],
                    r["total_cobrado"],
                    r["total_cobrado"] - r["total_pagado"],
                ])
                # 4 filas de desglose trimestral
                for per in PERIODOS:
                    t = r["trimestres"][per]
                    filas.append([
                        "",          # nombre vacío → queda agrupado visualmente
                        "",
                        per,
                        t["gastos"]   if t["gastos"]   else 0.0,
                        t["ingresos"] if t["ingresos"] else 0.0,
                        t["ingresos"] - t["gastos"],
                    ])
                # Línea separadora vacía entre empresas
                filas.append(["", "", "", "", "", ""])

            tots = [
                f"TOTAL DECLARADO ({len(data)} entidades)",
                "", "",
                total_g, total_i, total_i - total_g,
            ]
            pdf, err = gen_pdf(
                f"Modelo 347 — Ano {ano_r}",
                f"Limiar: {fmt(umb_r)} · {len(data)} entidades · Desglose trimestral",
                cols_p, filas, tots,
            )
            if err: st.error(f"PDF: {err}")
            else:   st.download_button("⬇️ PDF con desglose", data=pdf,
                        file_name=f"Modelo347_{ano_r}.pdf",
                        mime="application/pdf", key="dl_347_pdf")
