import io
import streamlit as st
import pandas as pd
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT

from db import (get_cursos, get_anos, get_partidas, get_movs_partida,
                get_partidas_resumen_global,
                get_partida_saldo, get_partida_saldos,
                get_partida_saldo_curso, get_partida_saldos_curso,
                get_saldo_arrastrado, calcular_saldo_auto, calcular_saldo_auto_curso,
                save_partida_saldo, delete_partida_saldo,
                save_partida_saldo_curso, delete_partida_saldo_curso,
                save_partida, delete_partida, get_cfg)
from db.connection import q
from utils import fmt, fmtD
from utils.pdf import gen_pdf


# ── Colores para balance ──────────────────────────────────────────
def _color_balance(val: float) -> str:
    """HTML color para mostrar balance: verde positivo, rojo negativo."""
    color = "#166534" if val >= 0 else "#991b1b"
    signo = "+" if val > 0 else ""
    return f"<span style='color:{color};font-weight:600'>{signo}{fmt(val)} €</span>"


# ── PDF de una partida ────────────────────────────────────────────
def _pdf_partida(p, movs, filtro_label, remanente, ing, gast):
    balance     = remanente + ing - gast
    subtitulo   = (
        f"Remanente anterior: {fmt(remanente)} € | "
        f"Ingresos: {fmt(ing)} € | Gastos: {fmt(gast)} € | "
        f"Balance: {fmt(balance)} €"
        + (f" | Filtro: {filtro_label}" if filtro_label != "Todos" else "")
    )
    cols  = ["Data","Ano","Curso","Área","Concepto","Cliente","Período","Debe €","Haber €"]
    filas = [[fmtD(m.get("data","")), m.get("ano",""), m.get("curso_nome",""),
              "Func" if m.get("area")=="func" else "Com",
              m.get("concepto",""), m.get("cliente_nome","") or "",
              m.get("periodo",""),
              round(m["importe"],2) if m["tipo"]=="G" else None,
              round(m["importe"],2) if m["tipo"]=="I" else None] for m in movs]
    totales = ["","","","","TOTAL","","", fmt(gast), fmt(ing)]
    pdf_bytes, _ = gen_pdf(
        title    = f"Partida: {p['nome']}",
        subtitulo= subtitulo,
        columnas = cols,
        filas    = filas,
        totales  = totales,
    )
    return pdf_bytes


# ── PDF multi-partida ─────────────────────────────────────────────
def _pdf_multi_partidas(partidas_data: list[dict]) -> bytes:
    """
    Genera un PDF con todas las partidas seleccionadas.
    partidas_data: [{p, movs, filtro_label, remanente, ing, gast}, ...]
    """
    BLUE   = colors.HexColor("#1e40af")
    BLUE_L = colors.HexColor("#dbeafe")
    PAPER  = colors.HexColor("#f8f7f4")
    GRAY   = colors.HexColor("#94a3b8")
    GREEN  = colors.HexColor("#166534")
    RED    = colors.HexColor("#991b1b")

    cfg = {k: get_cfg(k) for k in ["centro_nome","footer1","footer2"]}

    styles = getSampleStyleSheet()
    sT  = ParagraphStyle("T",  parent=styles["Title"],  fontSize=13, spaceAfter=2)
    sSu = ParagraphStyle("Su", parent=styles["Normal"], fontSize=8,
                         textColor=colors.HexColor("#64748b"), spaceAfter=6)
    sH  = ParagraphStyle("TH", parent=styles["Normal"], fontSize=7, fontName="Helvetica-Bold",
                         textColor=colors.white, alignment=TA_CENTER)
    sC  = ParagraphStyle("TC", parent=styles["Normal"], fontSize=7, alignment=TA_LEFT)
    sCR = ParagraphStyle("TR", parent=styles["Normal"], fontSize=7, alignment=TA_RIGHT)
    sF  = ParagraphStyle("FO", parent=styles["Normal"], fontSize=7,
                         textColor=GRAY, alignment=TA_CENTER)
    sRes= ParagraphStyle("RES",parent=styles["Normal"], fontSize=8, fontName="Helvetica-Bold")

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4),
                            leftMargin=1.5*cm, rightMargin=1.5*cm,
                            topMargin=2*cm, bottomMargin=2*cm)
    elements = []

    # Cabecera global
    elements.append(Paragraph(
        f"<b>{cfg['centro_nome']}</b> — Informe de Partidas Finalistas", sT))
    elements.append(HRFlowable(width="100%", thickness=1.5, color=BLUE, spaceAfter=6))

    avail_w = landscape(A4)[0] - 3*cm
    col_ws  = [1.8*cm, 1*cm, 2.2*cm, 1*cm, 4*cm, 3*cm, 2.2*cm, 1.8*cm, 1.8*cm]

    for item in partidas_data:
        p, movs, filtro_label = item["p"], item["movs"], item["filtro_label"]
        remanente = item["remanente"]
        ing       = item["ing"]
        gast      = item["gast"]
        balance   = remanente + ing - gast

        # Resumen de la partida
        bal_color = GREEN if balance >= 0 else RED
        elements.append(Spacer(1, 0.3*cm))
        elements.append(Paragraph(f"<b>📋 {p['nome']}</b>"
            + (f"  <font size='7' color='#64748b'>— {filtro_label}</font>"
               if filtro_label != "Todos" else ""), sRes))

        # Mini tabla de resumen
        res_data = [[
            Paragraph("Remanente anterior", sC),
            Paragraph("Ingresos", sC),
            Paragraph("Gastos", sC),
            Paragraph("Balance", sC),
        ],[
            Paragraph(f"<b>{fmt(remanente)} €</b>", sCR),
            Paragraph(f"<b>{fmt(ing)} €</b>", sCR),
            Paragraph(f"<b>{fmt(gast)} €</b>", sCR),
            Paragraph(f"<b>{fmt(balance)} €</b>",
                      ParagraphStyle("B", parent=sCR,
                                     textColor=GREEN if balance>=0 else RED)),
        ]]
        rt = Table(res_data, colWidths=[avail_w/4]*4)
        rt.setStyle(TableStyle([
            ("BACKGROUND",    (0,0), (-1,0), BLUE_L),
            ("FONTSIZE",      (0,0), (-1,-1), 7),
            ("GRID",          (0,0), (-1,-1), 0.3, GRAY),
            ("TOPPADDING",    (0,0), (-1,-1), 3),
            ("BOTTOMPADDING", (0,0), (-1,-1), 3),
        ]))
        elements.append(rt)
        elements.append(Spacer(1, 0.15*cm))

        if movs:
            # Tabla de movimientos
            thead = [Paragraph(c, sH) for c in
                     ["Data","Ano","Curso","Área","Concepto","Cliente","Período","Debe €","Haber €"]]
            data  = [thead]
            for m in movs:
                data.append([
                    Paragraph(fmtD(m.get("data","")), sC),
                    Paragraph(str(m.get("ano","")), sC),
                    Paragraph(m.get("curso_nome","") or "", sC),
                    Paragraph("F" if m.get("area")=="func" else "C", sC),
                    Paragraph(m.get("concepto",""), sC),
                    Paragraph(m.get("cliente_nome","") or "", sC),
                    Paragraph(m.get("periodo",""), sC),
                    Paragraph(fmt(m["importe"]) if m["tipo"]=="G" else "", sCR),
                    Paragraph(fmt(m["importe"]) if m["tipo"]=="I" else "", sCR),
                ])
            # Fila totales
            data.append([
                Paragraph("<b>TOTAL</b>", sC), "", "", "", "", "", "",
                Paragraph(f"<b>{fmt(gast)}</b>", sCR),
                Paragraph(f"<b>{fmt(ing)}</b>", sCR),
            ])
            t = Table(data, colWidths=col_ws, repeatRows=1)
            t.setStyle(TableStyle([
                ("BACKGROUND",    (0,0),  (-1,0),  BLUE),
                ("TEXTCOLOR",     (0,0),  (-1,0),  colors.white),
                ("ROWBACKGROUNDS",(0,1),  (-1,-2), [colors.white, PAPER]),
                ("BACKGROUND",    (0,-1), (-1,-1), BLUE_L),
                ("FONTNAME",      (0,-1), (-1,-1), "Helvetica-Bold"),
                ("GRID",          (0,0),  (-1,-1), 0.3, GRAY),
                ("FONTSIZE",      (0,0),  (-1,-1), 7),
                ("TOPPADDING",    (0,0),  (-1,-1), 3),
                ("BOTTOMPADDING", (0,0),  (-1,-1), 3),
            ]))
            elements.append(t)
        else:
            elements.append(Paragraph("Sen movementos para este filtro.", sC))

        elements.append(HRFlowable(width="100%", thickness=0.5, color=GRAY, spaceAfter=4))

    # Footer
    footers = [x for x in [cfg["footer1"], cfg["footer2"]] if x]
    if footers:
        elements.append(Spacer(1, 0.3*cm))
        elements.append(Paragraph(" · ".join(footers), sF))

    doc.build(elements)
    return buf.getvalue()


# ── Gestión saldos ────────────────────────────────────────────────
def _render_gestion_saldos(p, anos, cursos):
    st.markdown(
        '<div style="background:#fef9c3;border:1px solid #fde047;border-radius:6px;'
        'padding:8px 12px;font-size:12px;color:#713f12;margin-bottom:12px">'
        '⚠️ O remanente anterior é o punto de partida dos cálculos. '
        'Consolídao manualmente ou usa o botón <strong>🔢 Auto</strong>.</div>',
        unsafe_allow_html=True,
    )
    sub1, sub2 = st.tabs(["📅 Por ano natural", "🎓 Por curso escolar"])

    with sub1:
        saldos_ano = {s["ano"]: s for s in get_partida_saldos(p["id"])}
        for ano in sorted(anos):
            cons       = saldos_ano.get(ano)
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
                    f"Remanente anterior {ano} €", value=float(saldo_actual), step=0.01,
                    key=f"ps_a_{p['id']}_{ano}",
                    help=f"Cálculo automático: {fmt(saldo_auto)} €",
                )
                with col_btn:
                    st.markdown("<div style='margin-top:22px'></div>", unsafe_allow_html=True)
                    c1, c2 = st.columns(2)
                    if c1.button("🔢 Auto", key=f"auto_a_{p['id']}_{ano}"):
                        save_partida_saldo(p["id"], ano, saldo_auto, 1)
                        st.success(f"✅ {fmt(saldo_auto)} € consolidado"); st.rerun()
                    if c2.button("💾 Consolidar", key=f"cons_a_{p['id']}_{ano}", type="primary"):
                        save_partida_saldo(p["id"], ano, novo, 1)
                        st.success(f"✅ {fmt(novo)} € consolidado"); st.rerun()
                if cons and cons["consolidado"]:
                    diff = abs(cons["saldo"] - saldo_auto)
                    st.caption(f"Consolidado: **{fmt(cons['saldo'])} €** · Auto: **{fmt(saldo_auto)} €**")
                    if diff > 0.01:
                        st.warning(f"⚠️ Diferenza: {fmt(diff)} €")

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
                    f"Remanente anterior {cur['nome']} €", value=float(saldo_actual), step=0.01,
                    key=f"ps_c_{p['id']}_{cur['id']}",
                )
                with col_btn:
                    st.markdown("<div style='margin-top:22px'></div>", unsafe_allow_html=True)
                    c1, c2 = st.columns(2)
                    if c1.button("🔢 Auto", key=f"auto_c_{p['id']}_{cur['id']}"):
                        save_partida_saldo_curso(p["id"], cur["id"], saldo_auto, 1)
                        st.success(f"✅ {fmt(saldo_auto)} € consolidado"); st.rerun()
                    if c2.button("💾 Consolidar", key=f"cons_c_{p['id']}_{cur['id']}", type="primary"):
                        save_partida_saldo_curso(p["id"], cur["id"], novo, 1)
                        st.success(f"✅ {fmt(novo)} € consolidado"); st.rerun()


# ── Gestión de partidas ───────────────────────────────────────────
def _render_xestion_partidas(partidas):
    st.markdown(
        '<div style="background:#dbeafe;border:1px solid #93c5fd;border-radius:8px;'
        'padding:8px 12px;font-size:12px;color:#1e3a5f;margin-bottom:12px">'
        'ℹ️ As partidas son <strong>globais</strong> — non están ligadas a un curso.</div>',
        unsafe_allow_html=True,
    )
    if partidas:
        st.dataframe(pd.DataFrame([{
            "Partida": p["nome"], "Activa": "✅" if p["activa"] else "❌", "Notas": p["notas"],
        } for p in partidas]), use_container_width=True, hide_index=True)
    st.divider()
    opts_p = ["— Nova partida —"] + [p["nome"] for p in partidas]
    sel_p  = st.selectbox("Editar ou crear partida", opts_p, key="part_xest_sel")
    pe     = None if sel_p.startswith("—") else next(
        (p for p in partidas if p["nome"] == sel_p), None)
    with st.form("part_xest_form"):
        if pe: st.caption(f"Editando: **{pe['nome']}**")
        else:  st.caption("Nova partida global")
        c1, c2 = st.columns(2)
        nome_val  = c1.text_input("Nome *", value=pe["nome"] if pe else "", placeholder="Ex: PLAMBE")
        notas_val = c2.text_input("Notas", value=pe["notas"] if pe else "")
        activa_val = st.checkbox("Activa", value=bool(pe["activa"]) if pe else True)
        cs_b, cd_b = st.columns([3, 1])
        sv = cs_b.form_submit_button("💾 Gardar", type="primary", use_container_width=True)
        dl = cd_b.form_submit_button("🗑️ Eliminar", use_container_width=True) if pe else False
        if sv:
            if not nome_val.strip(): st.error("Nome obrigatorio")
            else:
                d = {"nome": nome_val.strip().upper(), "notas": notas_val, "activa": activa_val}
                if pe: d["id"] = pe["id"]
                save_partida(d); st.success(f"✅ '{nome_val}' gardada!"); st.rerun()
        if dl and pe:
            n = q("SELECT COUNT(*) as n FROM diario WHERE xustifica=?", (pe["nome"],))
            if n and n[0]["n"] > 0:
                st.warning(f"⚠️ Esta partida ten {n[0]['n']} movementos asignados.")
            delete_partida(pe["id"]); st.success("🗑️ Eliminada"); st.rerun()


# ── Exportación múltiple ──────────────────────────────────────────
def _render_exportacion_multiple(partidas, cursos, anos):
    st.markdown("Selecciona as partidas e o filtro para xerar un PDF conxunto.")

    # Filtro
    col_f1, col_f2 = st.columns(2)
    modo = col_f1.radio("Filtrar por", ["Todos", "Ano natural", "Curso escolar"],
                        horizontal=True, key="exp_multi_modo")
    filtro_ano_id = None; filtro_cur_id = None; filtro_label = "Todos"

    if modo == "Ano natural":
        ano_sel       = col_f2.selectbox("Ano", anos, key="exp_multi_ano")
        filtro_ano_id = ano_sel
        filtro_label  = str(ano_sel)
    elif modo == "Curso escolar":
        cur_opts      = [c["nome"] for c in cursos]
        cur_sel       = col_f2.selectbox("Curso", cur_opts, key="exp_multi_cur")
        filtro_cur_id = next((c["id"] for c in cursos if c["nome"]==cur_sel), None)
        filtro_label  = cur_sel

    st.divider()

    # Checkboxes de partidas
    st.markdown("**Selecciona as partidas a incluír:**")
    c1, c2 = st.columns(2)
    seleccionadas = []
    for i, p in enumerate(partidas):
        col = c1 if i % 2 == 0 else c2
        if col.checkbox(p["nome"], value=True, key=f"chk_exp_{p['id']}"):
            seleccionadas.append(p)

    st.divider()

    if not seleccionadas:
        st.info("Selecciona polo menos unha partida.")
        return

    st.caption(f"{len(seleccionadas)} partida(s) seleccionada(s) · Filtro: {filtro_label}")

    if st.button("📄 Xerar PDF conxunto", type="primary", use_container_width=True,
                 key="btn_exp_multi"):
        with st.spinner("Xerando PDF..."):
            partidas_data = []
            for p in seleccionadas:
                movs = get_movs_partida(p["nome"], filtro_cur_id, filtro_ano_id)

                if modo == "Ano natural" and filtro_ano_id:
                    cons = get_partida_saldo(p["id"], filtro_ano_id)
                    remanente = cons["saldo"] if cons and cons["consolidado"] else \
                                get_saldo_arrastrado(p["id"], p["nome"],
                                                     p["saldo_inicial"], filtro_ano_id)
                elif modo == "Curso escolar" and filtro_cur_id:
                    cons = get_partida_saldo_curso(p["id"], filtro_cur_id)
                    remanente = cons["saldo"] if cons and cons["consolidado"] else p["saldo_inicial"]
                else:
                    remanente = p["saldo_inicial"]

                ing  = sum(m["importe"] for m in movs if m["tipo"]=="I")
                gast = sum(m["importe"] for m in movs if m["tipo"]=="G")
                partidas_data.append({
                    "p": p, "movs": movs, "filtro_label": filtro_label,
                    "remanente": remanente, "ing": ing, "gast": gast,
                })

            pdf_bytes = _pdf_multi_partidas(partidas_data)
            fname     = f"Partidas_{filtro_label.replace(' ','_')}.pdf"

        st.download_button("⬇️ Descargar PDF", data=pdf_bytes,
                           file_name=fname, mime="application/pdf",
                           key="dl_exp_multi")


# ── RENDER PRINCIPAL ──────────────────────────────────────────────
def render(ano: int, cur_id: int | None) -> None:
    st.title("📋 Partidas Finalistas")

    partidas = get_partidas()
    cursos   = get_cursos()
    anos     = get_anos()

    if not partidas:
        tab_xest, = st.tabs(["⚙️ Xestión de partidas"])
        with tab_xest:
            _render_xestion_partidas(partidas)
        return

    # Selector de partida
    p_names = [p["nome"] for p in partidas]
    p_sel   = st.selectbox("📋 Selecciona a partida", p_names, key="part_sel")
    p       = next((x for x in partidas if x["nome"]==p_sel), None)
    if not p:
        return

    tab_vista, tab_saldos, tab_exp, tab_xest = st.tabs([
        "📊 Vista e movementos",
        "💰 Saldos e remanentes",
        "📄 Exportar partidas",
        "⚙️ Xestión de partidas",
    ])

    with tab_xest:
        _render_xestion_partidas(partidas)

    with tab_exp:
        _render_exportacion_multiple(partidas, cursos, anos)

    with tab_saldos:
        st.subheader(f"💰 Saldos e remanentes — {p['nome']}")
        _render_gestion_saldos(p, anos, cursos)

    with tab_vista:
        st.divider()

        col_f1, col_f2 = st.columns(2)
        modo_filtro = col_f1.radio("Filtrar por",
                                   ["Todos", "Curso escolar", "Ano natural"],
                                   horizontal=True, key="part_filtro_modo")
        filtro_curso_id = None; filtro_ano = None; filtro_label = "Todos"

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

        if modo_filtro == "Ano natural" and filtro_ano is not None:
            cons = get_partida_saldo(p["id"], filtro_ano)
            if cons and cons["consolidado"]:
                remanente = cons["saldo"]; label_rem = f"Remanente consolidado {filtro_ano}"
                es_cons   = True
            else:
                remanente = get_saldo_arrastrado(p["id"], p["nome"], p["saldo_inicial"], filtro_ano)
                label_rem = f"Remanente anterior ({filtro_ano-1} e antes)"; es_cons = False
            ing  = sum(m["importe"] for m in movs if m["tipo"]=="I")
            gast = sum(m["importe"] for m in movs if m["tipo"]=="G")

        elif modo_filtro == "Curso escolar" and filtro_curso_id is not None:
            cons = get_partida_saldo_curso(p["id"], filtro_curso_id)
            if cons and cons["consolidado"]:
                remanente = cons["saldo"]; label_rem = f"Remanente consolidado {filtro_label}"
                es_cons   = True
            else:
                remanente = p["saldo_inicial"]; label_rem = "Remanente anterior"; es_cons = False
            ing  = sum(m["importe"] for m in movs if m["tipo"]=="I")
            gast = sum(m["importe"] for m in movs if m["tipo"]=="G")

        else:
            res_global = get_partidas_resumen_global(p["nome"])
            remanente  = p["saldo_inicial"]; label_rem = "Remanente anterior"; es_cons = False
            ing  = res_global["haber"]; gast = res_global["debe"]

        balance = remanente + ing - gast

        # ── Métricas ─────────────────────────────────────────────
        st.subheader(f"📋 {p['nome']}")
        if p.get("notas"): st.caption(p["notas"])

        c1, c2, c3, c4 = st.columns(4)
        c1.metric(label_rem, fmt(remanente),
                  help="✅ Consolidado" if es_cons else "⚪ Calculado auto")
        c2.metric("📥 Ingresos", fmt(ing))
        c3.metric("📤 Gastos",   fmt(gast))

        # Balance en verde/rojo
        bal_color = "normal" if balance >= 0 else "inverse"
        c4.metric("🏦 Balance", fmt(balance),
                  delta=fmt(balance - remanente) if remanente else None,
                  delta_color=bal_color)

        # Color adicional con HTML
        color_hex = "#166534" if balance >= 0 else "#991b1b"
        st.markdown(
            f"<div style='text-align:right;font-size:13px;font-weight:600;"
            f"color:{color_hex};margin-top:-8px;margin-bottom:8px'>"
            f"{'▲' if balance >= 0 else '▼'} Balance: {fmt(balance)} €</div>",
            unsafe_allow_html=True,
        )

        base = remanente + ing
        if base > 0:
            pct = min(100, gast / base * 100)
            ico = "🔴" if pct > 90 else "🟡" if pct > 70 else "🟢"
            st.progress(pct / 100)
            st.caption(f"{ico} {pct:.1f}% dos recursos gastados")

        if not es_cons and modo_filtro != "Todos":
            st.markdown(
                "<div style='background:#f0fdf4;border:1px solid #86efac;"
                "border-radius:6px;padding:6px 10px;font-size:11px;color:#166534;"
                "margin-bottom:8px;'>ℹ️ Remanente calculado automaticamente. "
                "Ve á pestaña <strong>💰 Saldos e remanentes</strong> para consolidalo.</div>",
                unsafe_allow_html=True,
            )

        st.divider()

        col_tit, col_pdf = st.columns([4, 1])
        col_tit.markdown(
            f"**📋 Movementos** "
            f"{'— '+filtro_label if modo_filtro!='Todos' else ''} ({len(movs)})"
        )
        pdf_bytes = _pdf_partida(p, movs, filtro_label, remanente, ing, gast)
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
            st.markdown(
                f"Ingresos: **{fmt(ing)}** · Gastos: **{fmt(gast)}** · "
                f"Balance: {_color_balance(ing - gast)}",
                unsafe_allow_html=True,
            )
        else:
            st.info(f"Non hai movementos"
                    + (f" co filtro '{filtro_label}'" if modo_filtro!="Todos" else "") + ".")
