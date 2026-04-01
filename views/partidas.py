import streamlit as st
import pandas as pd

from db import (get_cursos, get_anos, get_partidas, get_movs_partida,
                get_partidas_resumen_global, get_partida_saldo, get_partida_saldos,
                get_saldo_arrastrado, calcular_saldo_auto,
                save_partida_saldo, delete_partida_saldo)
from utils import fmt, fmtD
from utils.pdf import gen_pdf


def _pdf_partida(p, movs, filtro_label, saldo_anterior):
    total_ing  = sum(m["importe"] for m in movs if m["tipo"]=="I")
    total_gast = sum(m["importe"] for m in movs if m["tipo"]=="G")
    saldo_final = saldo_anterior + total_ing - total_gast
    subtitulo = (
        f"Saldo anterior: {fmt(saldo_anterior)} € | "
        f"Ingresos: {fmt(total_ing)} € | Gastos: {fmt(total_gast)} € | "
        f"Saldo actual: {fmt(saldo_final)} €"
        + (f" | Filtro: {filtro_label}" if filtro_label != "Todos" else "")
    )
    cols  = ["Data","Ano","Curso","Área","Concepto","Cliente","Período","Debe €","Haber €"]
    filas = [[fmtD(m.get("data","")), m.get("ano",""), m.get("curso_nome",""),
              "Func" if m.get("area")=="func" else "Com",
              m.get("concepto",""), m.get("cliente_nome","") or "",
              m.get("periodo",""),
              round(m["importe"],2) if m["tipo"]=="G" else None,
              round(m["importe"],2) if m["tipo"]=="I" else None] for m in movs]
    totales = ["","","","","TOTAL","","",fmt(total_gast),fmt(total_ing)]
    pdf_bytes, _ = gen_pdf(title=f"📋 Partida: {p['nome']}", subtitulo=subtitulo,
                            columnas=cols, filas=filas, totales=totales)
    return pdf_bytes


def _render_gestion_saldos(p, anos):
    """
    Panel de gestión de saldos iniciales por año.
    Para cada año: saldo consolidado (manual o auto) + botón consolidar.
    """
    st.subheader("💰 Saldos iniciais por ano natural")
    st.markdown(
        '<div style="background:#fef9c3;border:1px solid #fde047;border-radius:6px;'
        'padding:8px 12px;font-size:12px;color:#713f12;margin-bottom:12px">'
        '⚠️ O saldo inicial de cada ano é o punto de partida para os cálculos. '
        'Podes introducilo manualmente ou calculalo de forma automática a partir '
        'dos movementos anteriores.</div>',
        unsafe_allow_html=True,
    )

    saldos_consolidados = {s["ano"]: s for s in get_partida_saldos(p["id"])}

    for ano in sorted(anos):
        consolidado = saldos_consolidados.get(ano)
        saldo_auto  = calcular_saldo_auto(p["id"], p["nome"], p["saldo_inicial"], ano)

        with st.expander(
            f"Ano **{ano}** — "
            + (f"✅ Consolidado: **{fmt(consolidado['saldo'])} €**"
               if consolidado and consolidado["consolidado"]
               else f"⚪ Non consolidado (auto: {fmt(saldo_auto)} €)"),
            expanded=False,
        ):
            col_val, col_btn = st.columns([3, 2])

            saldo_actual = consolidado["saldo"] if consolidado else saldo_auto
            novo_saldo   = col_val.number_input(
                f"Saldo inicial {ano} €",
                value=float(saldo_actual),
                step=0.01,
                key=f"ps_{p['id']}_{ano}",
                help=f"Cálculo automático: {fmt(saldo_auto)} €",
            )

            with col_btn:
                st.markdown("<div style='margin-top:22px'></div>", unsafe_allow_html=True)
                c1, c2 = st.columns(2)
                if c1.button("🔢 Auto", key=f"auto_{p['id']}_{ano}",
                              help="Calcular automáticamente desde movementos anteriores"):
                    save_partida_saldo(p["id"], ano, saldo_auto, 1)
                    st.success(f"✅ {fmt(saldo_auto)} € consolidado (auto)")
                    st.rerun()
                if c2.button("💾 Consolidar", key=f"cons_{p['id']}_{ano}", type="primary"):
                    save_partida_saldo(p["id"], ano, novo_saldo, 1)
                    st.success(f"✅ {fmt(novo_saldo)} € consolidado")
                    st.rerun()

            if consolidado and consolidado["consolidado"]:
                st.caption(f"Último consolidado: **{fmt(consolidado['saldo'])} €** · "
                           f"Cálculo auto: **{fmt(saldo_auto)} €**")
                if abs(consolidado["saldo"] - saldo_auto) > 0.01:
                    st.warning(
                        f"⚠️ Diferenza entre consolidado ({fmt(consolidado['saldo'])} €) "
                        f"e cálculo automático ({fmt(saldo_auto)} €): "
                        f"{fmt(abs(consolidado['saldo']-saldo_auto))} €"
                    )


def render(ano: int, cur_id: int | None) -> None:
    st.title("📋 Partidas Finalistas")

    partidas = get_partidas()
    if not partidas:
        st.info("Non hai partidas creadas. Ve a ⚙️ Tablas Maestras → Partidas.")
        return

    cursos = get_cursos()
    anos   = get_anos()

    # ── Selector de partida ────────────────────────────────────────
    p_names = [p["nome"] for p in partidas]
    p_sel   = st.selectbox("📋 Selecciona a partida", p_names, key="part_sel")
    p       = next((x for x in partidas if x["nome"]==p_sel), None)
    if not p:
        return

    # ── Tabs: Vista / Saldos ───────────────────────────────────────
    tab_vista, tab_saldos = st.tabs(["📊 Vista e movementos", "💰 Saldos iniciais por ano"])

    with tab_saldos:
        _render_gestion_saldos(p, anos)

    with tab_vista:
        st.divider()

        # ── Filtros ────────────────────────────────────────────────
        col_f1, col_f2 = st.columns(2)
        modo_filtro = col_f1.radio(
            "Filtrar por",
            ["Todos", "Curso escolar", "Ano natural"],
            horizontal=True, key="part_filtro_modo",
        )

        filtro_curso_id = None
        filtro_ano      = None
        filtro_label    = "Todos"

        if modo_filtro == "Curso escolar":
            cur_opts = [c["nome"] for c in cursos]
            cur_def  = next((i for i,c in enumerate(cursos) if c["id"]==cur_id), 0)
            cur_sel  = col_f2.selectbox("Curso", cur_opts, index=cur_def, key="part_filtro_cur")
            filtro_curso_id = next((c["id"] for c in cursos if c["nome"]==cur_sel), None)
            filtro_label    = cur_sel
        elif modo_filtro == "Ano natural":
            ano_sel      = col_f2.selectbox("Ano", anos,
                               index=anos.index(ano) if ano in anos else len(anos)-1,
                               key="part_filtro_ano")
            filtro_ano   = ano_sel
            filtro_label = str(ano_sel)

        # ── Cargar movimientos ─────────────────────────────────────
        movs = get_movs_partida(p["nome"], filtro_curso_id, filtro_ano)

        # ── Calcular saldo según modo ──────────────────────────────
        if modo_filtro == "Ano natural" and filtro_ano is not None:
            # ★ Usa saldo consolidado si existe, si no calcula automático
            consolidado = get_partida_saldo(p["id"], filtro_ano)
            if consolidado and consolidado["consolidado"]:
                saldo_anterior    = consolidado["saldo"]
                label_saldo_ant   = f"Saldo consolidado {filtro_ano}"
                es_consolidado    = True
            else:
                saldo_anterior    = get_saldo_arrastrado(
                    p["id"], p["nome"], p["saldo_inicial"], filtro_ano)
                label_saldo_ant   = f"Saldo anterior ({filtro_ano-1} e antes)"
                es_consolidado    = False

            ing_periodo  = sum(m["importe"] for m in movs if m["tipo"]=="I")
            gast_periodo = sum(m["importe"] for m in movs if m["tipo"]=="G")
            saldo_final  = saldo_anterior + ing_periodo - gast_periodo

        elif modo_filtro == "Curso escolar":
            saldo_anterior  = p["saldo_inicial"]
            label_saldo_ant = "Saldo inicial"
            es_consolidado  = False
            ing_periodo     = sum(m["importe"] for m in movs if m["tipo"]=="I")
            gast_periodo    = sum(m["importe"] for m in movs if m["tipo"]=="G")
            saldo_final     = saldo_anterior + ing_periodo - gast_periodo
        else:
            res_global      = get_partidas_resumen_global(p["nome"])
            saldo_anterior  = p["saldo_inicial"]
            label_saldo_ant = "Saldo inicial"
            es_consolidado  = False
            ing_periodo     = res_global["haber"]
            gast_periodo    = res_global["debe"]
            saldo_final     = saldo_anterior + ing_periodo - gast_periodo

        # ── Métricas ───────────────────────────────────────────────
        st.subheader(f"📋 {p['nome']}")
        if p.get("notas"):
            st.caption(p["notas"])

        c1, c2, c3, c4 = st.columns(4)
        c1.metric(label_saldo_ant, fmt(saldo_anterior),
                  help="✅ Consolidado manualmente" if es_consolidado else
                       "⚪ Calculado automáticamente")
        c2.metric("📥 Ingresos",    fmt(ing_periodo))
        c3.metric("📤 Gastos",      fmt(gast_periodo))
        c4.metric("🏦 Saldo actual", fmt(saldo_final),
                  delta=fmt(saldo_final-saldo_anterior) if saldo_anterior else None)

        base = saldo_anterior + ing_periodo
        if base > 0:
            pct = min(100, gast_periodo / base * 100)
            ico = "🔴" if pct > 90 else "🟡" if pct > 70 else "🟢"
            st.progress(pct / 100)
            st.caption(f"{ico} {pct:.1f}% dos recursos gastados")

        if modo_filtro == "Ano natural" and not es_consolidado:
            st.markdown(
                f"<div style='background:#f0fdf4;border:1px solid #86efac;"
                f"border-radius:6px;padding:6px 10px;font-size:11px;color:#166534;"
                f"margin-bottom:8px;'>ℹ️ Saldo calculado automaticamente. "
                f"Ve á pestaña <strong>💰 Saldos iniciais</strong> para consolidalo.</div>",
                unsafe_allow_html=True,
            )

        st.divider()

        # ── Tabla movimientos ──────────────────────────────────────
        col_tit, col_pdf = st.columns([4, 1])
        col_tit.markdown(
            f"**📋 Movementos** "
            f"{'— '+filtro_label if modo_filtro!='Todos' else ''} ({len(movs)})"
        )
        pdf_bytes = _pdf_partida(p, movs, filtro_label, saldo_anterior)
        if pdf_bytes:
            col_pdf.download_button(
                "📄 PDF", data=pdf_bytes,
                file_name=f"Partida_{p['nome'].replace(' ','_')}_{filtro_label}.pdf",
                mime="application/pdf", key="btn_pdf_partida",
            )

        if movs:
            df = pd.DataFrame([{
                "Data":     fmtD(m.get("data","")),
                "Ano":      m.get("ano",""),
                "Curso":    m.get("curso_nome",""),
                "Área":     "📘 Func" if m.get("area")=="func" else "🍽️ Com",
                "Concepto": m.get("concepto",""),
                "Cliente":  m.get("cliente_nome","") or "",
                "Período":  m.get("periodo",""),
                "Debe €":   round(m["importe"],2) if m["tipo"]=="G" else None,
                "Haber €":  round(m["importe"],2) if m["tipo"]=="I" else None,
            } for m in movs])
            st.dataframe(df, use_container_width=True, hide_index=True)
            st.caption(
                f"Ingresos: **{fmt(ing_periodo)}** · "
                f"Gastos: **{fmt(gast_periodo)}** · "
                f"Balance período: **{fmt(ing_periodo-gast_periodo)}**"
            )
        else:
            st.info(f"Non hai movementos para esta partida"
                    + (f" co filtro '{filtro_label}'" if modo_filtro!="Todos" else "") + ".")
