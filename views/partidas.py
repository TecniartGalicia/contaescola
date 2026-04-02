import streamlit as st
import pandas as pd

from db import (get_cursos, get_anos, get_partidas, get_movs_partida,
                get_partidas_resumen_global,
                get_partida_saldo, get_partida_saldos,
                get_partida_saldo_curso, get_partida_saldos_curso,
                get_saldo_arrastrado, calcular_saldo_auto, calcular_saldo_auto_curso,
                save_partida_saldo, delete_partida_saldo,
                save_partida_saldo_curso, delete_partida_saldo_curso)
from utils import fmt, fmtD
from utils.pdf import gen_pdf


def _pdf_partida(p, movs, filtro_label, saldo_anterior):
    total_ing   = sum(m["importe"] for m in movs if m["tipo"]=="I")
    total_gast  = sum(m["importe"] for m in movs if m["tipo"]=="G")
    saldo_final = saldo_anterior + total_ing - total_gast
    subtitulo   = (
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
    totales = ["","","","","TOTAL","","", fmt(total_gast), fmt(total_ing)]
    pdf_bytes, _ = gen_pdf(title=f"📋 Partida: {p['nome']}", subtitulo=subtitulo,
                            columnas=cols, filas=filas, totales=totales)
    return pdf_bytes


def _render_gestion_saldos(p, anos, cursos):
    st.subheader("💰 Saldos iniciais")
    st.markdown(
        '<div style="background:#fef9c3;border:1px solid #fde047;border-radius:6px;'
        'padding:8px 12px;font-size:12px;color:#713f12;margin-bottom:12px">'
        '⚠️ O saldo inicial é o punto de partida dos cálculos. '
        'Consolídao manualmente ou usa o botón <strong>🔢 Auto</strong> '
        'para calculalo desde os movementos anteriores.</div>',
        unsafe_allow_html=True,
    )

    sub1, sub2 = st.tabs(["📅 Por ano natural", "🎓 Por curso escolar"])

    # ── Saldos por AÑO ────────────────────────────────────────────
    with sub1:
        saldos_ano = {s["ano"]: s for s in get_partida_saldos(p["id"])}
        for ano in sorted(anos):
            cons       = saldos_ano.get(ano)
            # ★ Auto siempre desde saldo_inicial real (p["saldo_inicial"]) sin consolidaciones
            saldo_auto = calcular_saldo_auto(p["id"], p["nome"], p["saldo_inicial"], ano)

            with st.expander(
                f"Ano **{ano}** — " + (
                    f"✅ Consolidado: **{fmt(cons['saldo'])} €**"
                    if cons and cons["consolidado"]
                    else f"⚪ Non consolidado (auto: {fmt(saldo_auto)} €)"
                ), expanded=False,
            ):
                col_val, col_btn = st.columns([3, 2])
                saldo_actual = cons["saldo"] if cons else saldo_auto
                novo = col_val.number_input(
                    f"Saldo inicial {ano} €", value=float(saldo_actual), step=0.01,
                    key=f"ps_a_{p['id']}_{ano}",
                    help=f"Cálculo automático puro: {fmt(saldo_auto)} €",
                )
                with col_btn:
                    st.markdown("<div style='margin-top:22px'></div>", unsafe_allow_html=True)
                    c1, c2 = st.columns(2)
                    if c1.button("🔢 Auto", key=f"auto_a_{p['id']}_{ano}",
                                  help="Calcular desde movementos anteriores"):
                        save_partida_saldo(p["id"], ano, saldo_auto, 1)
                        st.success(f"✅ {fmt(saldo_auto)} € consolidado")
                        st.rerun()
                    if c2.button("💾 Consolidar", key=f"cons_a_{p['id']}_{ano}",
                                  type="primary"):
                        save_partida_saldo(p["id"], ano, novo, 1)
                        st.success(f"✅ {fmt(novo)} € consolidado")
                        st.rerun()

                if cons and cons["consolidado"]:
                    diff = abs(cons["saldo"] - saldo_auto)
                    st.caption(f"Consolidado: **{fmt(cons['saldo'])} €** · "
                               f"Auto puro: **{fmt(saldo_auto)} €**")
                    if diff > 0.01:
                        st.warning(f"⚠️ Diferenza: {fmt(diff)} €")

    # ── Saldos por CURSO ──────────────────────────────────────────
    with sub2:
        saldos_curso = {s["curso_id"]: s for s in get_partida_saldos_curso(p["id"])}
        for cur in cursos:
            cons       = saldos_curso.get(cur["id"])
            saldo_auto = calcular_saldo_auto_curso(p["nome"], p["saldo_inicial"], cur["id"])

            with st.expander(
                f"Curso **{cur['nome']}** — " + (
                    f"✅ Consolidado: **{fmt(cons['saldo'])} €**"
                    if cons and cons["consolidado"]
                    else f"⚪ Non consolidado (auto: {fmt(saldo_auto)} €)"
                ), expanded=False,
            ):
                col_val, col_btn = st.columns([3, 2])
                saldo_actual = cons["saldo"] if cons else saldo_auto
                novo = col_val.number_input(
                    f"Saldo inicial {cur['nome']} €", value=float(saldo_actual), step=0.01,
                    key=f"ps_c_{p['id']}_{cur['id']}",
                    help=f"Cálculo automático: {fmt(saldo_auto)} €",
                )
                with col_btn:
                    st.markdown("<div style='margin-top:22px'></div>", unsafe_allow_html=True)
                    c1, c2 = st.columns(2)
                    if c1.button("🔢 Auto", key=f"auto_c_{p['id']}_{cur['id']}"):
                        save_partida_saldo_curso(p["id"], cur["id"], saldo_auto, 1)
                        st.success(f"✅ {fmt(saldo_auto)} € consolidado")
                        st.rerun()
                    if c2.button("💾 Consolidar", key=f"cons_c_{p['id']}_{cur['id']}",
                                  type="primary"):
                        save_partida_saldo_curso(p["id"], cur["id"], novo, 1)
                        st.success(f"✅ {fmt(novo)} € consolidado")
                        st.rerun()


def render(ano: int, cur_id: int | None) -> None:
    st.title("📋 Partidas Finalistas")

    partidas = get_partidas()
    if not partidas:
        st.info("Non hai partidas creadas. Ve a ⚙️ Tablas Maestras → Partidas.")
        return

    cursos = get_cursos()
    anos   = get_anos()

    p_names = [p["nome"] for p in partidas]
    p_sel   = st.selectbox("📋 Selecciona a partida", p_names, key="part_sel")
    p       = next((x for x in partidas if x["nome"]==p_sel), None)
    if not p:
        return

    tab_vista, tab_saldos = st.tabs(["📊 Vista e movementos", "💰 Saldos iniciais"])

    with tab_saldos:
        _render_gestion_saldos(p, anos, cursos)

    with tab_vista:
        st.divider()

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

        movs = get_movs_partida(p["nome"], filtro_curso_id, filtro_ano)

        # ── Calcular saldo según modo ──────────────────────────────
        if modo_filtro == "Ano natural" and filtro_ano is not None:
            cons = get_partida_saldo(p["id"], filtro_ano)
            if cons and cons["consolidado"]:
                saldo_anterior  = cons["saldo"]
                label_ant       = f"Saldo consolidado {filtro_ano}"
                es_consolidado  = True
            else:
                saldo_anterior  = get_saldo_arrastrado(
                    p["id"], p["nome"], p["saldo_inicial"], filtro_ano)
                label_ant       = f"Saldo anterior ({filtro_ano-1} e antes)"
                es_consolidado  = False
            ing_periodo  = sum(m["importe"] for m in movs if m["tipo"]=="I")
            gast_periodo = sum(m["importe"] for m in movs if m["tipo"]=="G")
            saldo_final  = saldo_anterior + ing_periodo - gast_periodo

        elif modo_filtro == "Curso escolar" and filtro_curso_id is not None:
            cons = get_partida_saldo_curso(p["id"], filtro_curso_id)
            if cons and cons["consolidado"]:
                saldo_anterior  = cons["saldo"]
                label_ant       = f"Saldo consolidado {filtro_label}"
                es_consolidado  = True
            else:
                saldo_anterior  = p["saldo_inicial"]
                label_ant       = "Saldo inicial"
                es_consolidado  = False
            ing_periodo  = sum(m["importe"] for m in movs if m["tipo"]=="I")
            gast_periodo = sum(m["importe"] for m in movs if m["tipo"]=="G")
            saldo_final  = saldo_anterior + ing_periodo - gast_periodo

        else:
            res_global     = get_partidas_resumen_global(p["nome"])
            saldo_anterior = p["saldo_inicial"]
            label_ant      = "Saldo inicial"
            es_consolidado = False
            ing_periodo    = res_global["haber"]
            gast_periodo   = res_global["debe"]
            saldo_final    = saldo_anterior + ing_periodo - gast_periodo

        # ── Métricas ───────────────────────────────────────────────
        st.subheader(f"📋 {p['nome']}")
        if p.get("notas"):
            st.caption(p["notas"])

        c1, c2, c3, c4 = st.columns(4)
        c1.metric(label_ant, fmt(saldo_anterior),
                  help="✅ Consolidado" if es_consolidado else "⚪ Calculado auto")
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

        if not es_consolidado and modo_filtro != "Todos":
            st.markdown(
                "<div style='background:#f0fdf4;border:1px solid #86efac;"
                "border-radius:6px;padding:6px 10px;font-size:11px;color:#166534;"
                "margin-bottom:8px;'>ℹ️ Saldo calculado automaticamente. "
                "Ve á pestaña <strong>💰 Saldos iniciais</strong> para consolidalo.</div>",
                unsafe_allow_html=True,
            )

        st.divider()

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
                f"Balance: **{fmt(ing_periodo-gast_periodo)}**"
            )
        else:
            st.info(f"Non hai movementos"
                    + (f" co filtro '{filtro_label}'" if modo_filtro!="Todos" else "") + ".")
