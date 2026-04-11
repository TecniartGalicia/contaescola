import io
import base64
from datetime import datetime

import streamlit as st
import pandas as pd

from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm, mm
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle,
    Paragraph, Spacer, HRFlowable, Image, KeepTogether,
)

from db import (get_anos, get_cursos, get_codigos, get_clientes,
                get_partidas_config, get_informes, get_saldo, get_cfg)
from db.schema import PERIODOS
from utils import fmt, fmtD, excel_bytes, gen_pdf


# ── Colores corporativos ──────────────────────────────────────────
BLUE   = colors.HexColor("#1e40af")
BLUE_L = colors.HexColor("#dbeafe")
PAPER  = colors.HexColor("#f8f7f4")
GRAY   = colors.HexColor("#94a3b8")
GREEN  = colors.HexColor("#166534")
RED    = colors.HexColor("#991b1b")
DARK   = colors.HexColor("#0f172a")


# ── Generador PDF Cuadro Presentación ────────────────────────────
def _gen_cuadro_presentacion(ano: int, trimestre: str | None,
                              movs_func: list, movs_com: list) -> bytes:
    """
    PDF díptico A4 landscape, doble cara = 4 hojas A5.
    - Auto-sizing con medición real + retry hasta que cabe en 2 páginas
    - FrameBreaks calculados dinámicamente según contenido real
    """
    import math
    from reportlab.platypus import (
        BaseDocTemplate, PageTemplate, Frame,
        FrameBreak, NextPageTemplate,
    )
    from reportlab.platypus.flowables import UseUpSpace
    from reportlab.lib.utils import ImageReader

    cfg = {k: get_cfg(k) for k in [
        "centro_nome","centro_direccion","centro_nif",
        "footer1","footer2","logo_base64",
    ]}
    codigos_db = {c["codigo"]: c["descripcion"]
                  for c in __import__('db').get_codigos(solo_activos=False)}

    styles  = getSampleStyleSheet()
    PAGE_W, PAGE_H = landscape(A4)

    ML = MR = 0.35*cm
    MT      = 1.45*cm
    MB      = 0.4*cm
    A5_GAP  = 0.4*cm
    COL_GAP = 0.18*cm

    A5_W    = (PAGE_W - ML - MR - A5_GAP) / 2
    COL_W   = (A5_W   - COL_GAP) / 2
    FRAME_H = PAGE_H - MT - MB
    FRAME_Y = MB
    GRAY_L  = colors.HexColor("#e2e8f0")

    FX = [ML, ML+COL_W+COL_GAP,
          ML+A5_W+A5_GAP, ML+A5_W+A5_GAP+COL_W+COL_GAP]

    periodo_label = trimestre if trimestre else "Anual"
    fecha_gen     = datetime.now().strftime("%d/%m/%Y %H:%M")

    IW = 1.85*cm
    NW = 1.05*cm

    # ── Medición real de flowables ─────────────────────────────────
    def _medir(flowables):
        """Mide altura real de una lista de flowables."""
        total = 0.0
        avail_w = COL_W - 4  # padding L+R del frame
        for f in flowables:
            try:
                _, h = f.wrap(avail_w, 9999*cm)
                total += h
                # spaceBefore/After del estilo del párrafo
                if hasattr(f, 'style'):
                    total += getattr(f.style, 'spaceBefore', 0) or 0
                    total += getattr(f.style, 'spaceAfter',  0) or 0
                # spaceBefore/After directos (HRFlowable, Spacer…)
                else:
                    total += getattr(f, 'spaceBefore', 0) or 0
                    total += getattr(f, 'spaceAfter',  0) or 0
            except Exception:
                total += 15
        # Factor de seguridad: tabla split añade filas de cabecera extra
        return total * 1.35

    # ── Estilos ────────────────────────────────────────────────────
    def make_st(fs):
        fsh = min(fs + 0.5, 8.0)
        pad = max(1, int(fs * 0.18))
        N   = styles["Normal"]
        uid = f"_{fs:.1f}"
        def p(nm, bold=False, al=TA_LEFT, col=None, sb=0, sa=0, sz=None):
            s = ParagraphStyle(nm+uid, parent=N,
                               fontSize=sz or fs, leading=(sz or fs)+1.5,
                               fontName="Helvetica-Bold" if bold else "Helvetica",
                               alignment=al, spaceBefore=sb, spaceAfter=sa)
            if col: s.textColor = col
            return s
        return dict(
            fs=fs, fsh=fsh, pad=pad,
            sC   = p("sC"),
            sCR  = p("sCR",  al=TA_RIGHT),
            sCB  = p("sCB",  bold=True),
            sCRB = p("sCRB", bold=True, al=TA_RIGHT),
            sH   = p("sH",   bold=True, al=TA_CENTER,
                     col=colors.white, sz=fsh),
            sCod = p("sCod", bold=True,
                     sb=max(2, int(fs*0.35)), sz=fsh),
            sTit = p("sTit", bold=True, sa=1, sz=fsh+0.5),
        )

    # ── Builders de contenido ──────────────────────────────────────
    def _build_gastos(movs, st):
        cw = [NW, COL_W - NW - IW, IW]
        max_c = max(16, int((COL_W - NW - IW) / (st["fs"] * 0.53)))
        elems = [
            Paragraph("<b>GASTOS</b>", st["sTit"]),
            HRFlowable(width="100%", thickness=0.8,
                       color=DARK, spaceAfter=1),
        ]
        grupos: dict = {}
        for m in movs:
            if m["tipo"] != "G": continue
            grupos.setdefault(m.get("codigo","") or "—", []).append(m)

        total = 0.0
        for cod in sorted(grupos):
            desc = codigos_db.get(cod, cod)
            ms   = grupos[cod]
            sub  = sum(m["importe"] for m in ms)
            total += sub
            elems.append(Paragraph(f"<b>Código {cod}</b>  {desc}", st["sCod"]))
            data = [[Paragraph("Nº",st["sH"]),
                     Paragraph("CONCEPTO",st["sH"]),
                     Paragraph("DEBE",st["sH"])]]
            for m in ms:
                cli = (m.get("cliente_nome","") or
                       m.get("concepto","") or "")[:max_c]
                data.append([
                    Paragraph(str(m.get("num","")), st["sC"]),
                    Paragraph(cli, st["sC"]),
                    Paragraph(fmt(m["importe"]), st["sCR"]),
                ])
            t = Table(data, colWidths=cw, repeatRows=1, splitByRow=1)
            t.setStyle(TableStyle([
                ("BACKGROUND",    (0,0),(-1,0), DARK),
                ("FONTSIZE",      (0,0),(-1,-1), st["fs"]),
                ("TOPPADDING",    (0,0),(-1,-1), st["pad"]),
                ("BOTTOMPADDING", (0,0),(-1,-1), st["pad"]),
                ("ROWBACKGROUNDS",(0,1),(-1,-1), [colors.white, PAPER]),
                ("GRID",          (0,0),(-1,-1), 0.2, GRAY_L),
            ]))
            elems.append(t)
            sub_t = Table([[
                Paragraph(f"<b>Total código {cod}</b>", st["sCB"]),
                Paragraph(f"<b>{fmt(sub)}</b>", st["sCRB"]),
            ]], colWidths=[COL_W-IW, IW])
            sub_t.setStyle(TableStyle([
                ("FONTSIZE",      (0,0),(-1,-1), st["fs"]),
                ("TOPPADDING",    (0,0),(-1,-1), st["pad"]),
                ("BOTTOMPADDING", (0,0),(-1,-1), st["pad"]),
                ("LINEABOVE",     (0,0),(-1,-1), 0.4, DARK),
            ]))
            elems.append(sub_t)
            elems.append(Spacer(1, 0.04*cm))
        tot = Table([[
            Paragraph("<b>TOTAL GASTOS</b>", st["sCB"]),
            Paragraph(f"<b>{fmt(total)}</b>", st["sCRB"]),
        ]], colWidths=[COL_W-IW, IW])
        tot.setStyle(TableStyle([
            ("BACKGROUND",    (0,0),(-1,-1), BLUE),
            ("TEXTCOLOR",     (0,0),(-1,-1), colors.white),
            ("FONTSIZE",      (0,0),(-1,-1), st["fsh"]),
            ("TOPPADDING",    (0,0),(-1,-1), 2),
            ("BOTTOMPADDING", (0,0),(-1,-1), 2),
        ]))
        elems.append(tot)
        return elems, total

    def _build_ingresos_resumo(movs, st, total_g, sal_ant):
        cw    = [NW, COL_W - NW - IW, IW]
        max_c = max(16, int((COL_W - NW - IW) / (st["fs"] * 0.53)))
        elems = [
            Paragraph("<b>INGRESOS</b>", st["sTit"]),
            HRFlowable(width="100%", thickness=0.8,
                       color=DARK, spaceAfter=1),
        ]
        movs_i  = [m for m in movs if m["tipo"]=="I"]
        total_i = 0.0
        if movs_i:
            data = [[Paragraph("Nº",st["sH"]),
                     Paragraph("CONCEPTO",st["sH"]),
                     Paragraph("HABER",st["sH"])]]
            for m in movs_i:
                total_i += m["importe"]
                cli = (m.get("cliente_nome","") or
                       m.get("concepto","") or "")[:max_c]
                data.append([
                    Paragraph(str(m.get("num","")), st["sC"]),
                    Paragraph(cli, st["sC"]),
                    Paragraph(fmt(m["importe"]), st["sCR"]),
                ])
            t = Table(data, colWidths=cw, repeatRows=1, splitByRow=1)
            t.setStyle(TableStyle([
                ("BACKGROUND",    (0,0),(-1,0), DARK),
                ("FONTSIZE",      (0,0),(-1,-1), st["fs"]),
                ("TOPPADDING",    (0,0),(-1,-1), st["pad"]),
                ("BOTTOMPADDING", (0,0),(-1,-1), st["pad"]),
                ("ROWBACKGROUNDS",(0,1),(-1,-1), [colors.white, PAPER]),
                ("GRID",          (0,0),(-1,-1), 0.2, GRAY_L),
            ]))
            elems.append(t)
        else:
            elems.append(Paragraph("Sen ingresos no período.", st["sC"]))
        tot = Table([[
            Paragraph("<b>TOTAL INGRESOS</b>", st["sCB"]),
            Paragraph(f"<b>{fmt(total_i)}</b>", st["sCRB"]),
        ]], colWidths=[COL_W-IW, IW])
        tot.setStyle(TableStyle([
            ("BACKGROUND",    (0,0),(-1,-1), BLUE),
            ("TEXTCOLOR",     (0,0),(-1,-1), colors.white),
            ("FONTSIZE",      (0,0),(-1,-1), st["fsh"]),
            ("TOPPADDING",    (0,0),(-1,-1), 2),
            ("BOTTOMPADDING", (0,0),(-1,-1), 2),
        ]))
        elems.append(tot)
        # Resumo
        dif = total_i - total_g
        sf  = sal_ant + total_i - total_g
        dc  = GREEN if dif >= 0 else RED
        sc  = GREEN if sf  >= 0 else RED
        N   = styles["Normal"]
        uid = f"_r{st['fs']:.1f}"
        def rp(nm, bold=False, al=TA_LEFT, col=None):
            s = ParagraphStyle(nm+uid, parent=N,
                               fontSize=st["fsh"], leading=st["fsh"]+2,
                               fontName="Helvetica-Bold" if bold else "Helvetica",
                               alignment=al)
            if col: s.textColor = col
            return s
        elems.append(Spacer(1, 0.15*cm))
        elems.append(HRFlowable(width="100%", thickness=1,
                                color=BLUE, spaceAfter=2))
        elems.append(Paragraph("<b>RESUMO BALANCE</b>", st["sTit"]))
        res_t = Table([
            [Paragraph("Saldo anterior",    rp("a")),
             Paragraph(fmt(sal_ant),        rp("ar",al=TA_RIGHT))],
            [Paragraph("Total ingresos",    rp("b")),
             Paragraph(fmt(total_i),        rp("br",al=TA_RIGHT))],
            [Paragraph("Total gastos",      rp("c")),
             Paragraph(fmt(total_g),        rp("cr",al=TA_RIGHT))],
            [Paragraph("<b>Diferenza</b>",  rp("d",bold=True)),
             Paragraph(f"<b>{fmt(dif)}</b>",rp("dr",bold=True,al=TA_RIGHT,col=dc))],
            [Paragraph("<b>Saldo final</b>",rp("e",bold=True)),
             Paragraph(f"<b>{fmt(sf)}</b>", rp("er",bold=True,al=TA_RIGHT,col=sc))],
        ], colWidths=[COL_W-IW, IW])
        res_t.setStyle(TableStyle([
            ("FONTSIZE",      (0,0),(-1,-1), st["fsh"]),
            ("TOPPADDING",    (0,0),(-1,-1), 2),
            ("BOTTOMPADDING", (0,0),(-1,-1), 2),
            ("LINEBELOW",     (0,0),(-1,0),  0.3, GRAY_L),
            ("LINEBELOW",     (0,2),(-1,2),  0.3, GRAY_L),
            ("BACKGROUND",    (0,3),(-1,3),  colors.HexColor("#f0fdf4")),
            ("BACKGROUND",    (0,4),(-1,4),  BLUE_L),
            ("LINEABOVE",     (0,4),(-1,4),  1.2, BLUE),
        ]))
        elems.append(res_t)
        return elems

    # ── Cabecera canvas ────────────────────────────────────────────
    def _make_on_page(lbl_izq, lbl_dcha):
        def _on_page(canvas, doc):
            canvas.saveState()
            canvas.setFillColor(BLUE)
            canvas.rect(ML, PAGE_H-MT, PAGE_W-ML-MR, MT, fill=1, stroke=0)
            if cfg.get("logo_base64"):
                try:
                    import base64 as _b64
                    img = ImageReader(
                        io.BytesIO(_b64.b64decode(cfg["logo_base64"])))
                    canvas.drawImage(img, ML+0.1*cm, PAGE_H-MT+0.1*cm,
                                     width=1.0*cm, height=1.2*cm,
                                     preserveAspectRatio=True, mask="auto")
                except Exception:
                    pass
            cx_l = ML + A5_W/2
            cx_r = ML + A5_W + A5_GAP + A5_W/2
            canvas.setFillColor(colors.white)
            canvas.setFont("Helvetica-Bold", 8)
            canvas.drawCentredString(cx_l, PAGE_H-MT+0.68*cm, lbl_izq)
            canvas.drawCentredString(cx_r, PAGE_H-MT+0.68*cm, lbl_dcha)
            canvas.setFont("Helvetica", 6)
            canvas.setFillColor(colors.HexColor("#dbeafe"))
            centro = cfg.get("centro_nome","")
            canvas.drawCentredString(cx_l,  PAGE_H-MT+0.22*cm, centro)
            canvas.drawCentredString(cx_r,  PAGE_H-MT+0.22*cm, centro)
            canvas.drawRightString(PAGE_W-MR-0.1*cm,
                                   PAGE_H-MT+0.22*cm, fecha_gen)
            canvas.setStrokeColor(GRAY)
            canvas.setLineWidth(0.8)
            canvas.line(ML+A5_W+A5_GAP/2, MB, ML+A5_W+A5_GAP/2, PAGE_H-MT)
            canvas.setStrokeColor(GRAY_L)
            canvas.setLineWidth(0.3)
            canvas.line(FX[1]-COL_GAP/2, MB, FX[1]-COL_GAP/2, PAGE_H-MT)
            canvas.line(FX[3]-COL_GAP/2, MB, FX[3]-COL_GAP/2, PAGE_H-MT)
            footers = [x for x in [cfg.get("footer1",""),
                                    cfg.get("footer2","")] if x]
            if footers:
                canvas.setFont("Helvetica", 5)
                canvas.setFillColor(GRAY)
                canvas.drawCentredString(PAGE_W/2, MB/3, " · ".join(footers))
            canvas.restoreState()
        return _on_page

    # ── Construir con un fs dado ───────────────────────────────────
    def _build(fs):
        st_f = make_st(fs)
        st_c = make_st(fs)

        sal_f = get_saldo(ano, "func")
        sal_c = get_saldo(ano, "com")

        fg, tgf = _build_gastos(movs_func, st_f)
        fi      = _build_ingresos_resumo(movs_func, st_f, tgf, sal_f)
        cg, tgc = _build_gastos(movs_com,  st_c)
        ci      = _build_ingresos_resumo(movs_com,  st_c, tgc, sal_c)

        # ── Calcular FrameBreaks necesarios ────────────────────────
        # COM_ING ocupa frames 0,1 (H4). FUNC ocupa frames 2-5 (H1+H2).
        # COM_GAS ocupa frames 6,7 (H3).
        # Frames por área calculados con medición + factor seguridad.

        ci_h  = _medir(ci)
        ci_fr = min(2, max(1, math.ceil(ci_h / FRAME_H)))
        # Pares UseUpSpace+FrameBreak para llegar a frame 2 desde frame ci_fr-1:
        fb_after_ci = 3 - ci_fr   # ci_fr=1→2 pares, ci_fr=2→1 par

        func_h  = _medir(fg + fi)
        func_fr = min(4, max(1, math.ceil(func_h / FRAME_H)))
        # FUNC empieza en frame 2, termina en 2+func_fr-1
        # Necesitamos llegar al frame 6 (inicio H3)
        func_end = 2 + func_fr - 1
        fb_after_func = max(1, 6 - func_end)

        # ── Construir documento ─────────────────────────────────────
        fl = f"FUNCIONAMENTO · {ano} · {periodo_label}"
        cl = f"COMEDOR · {ano} · {periodo_label}"

        def mk_frame(x, fid):
            return Frame(x, FRAME_Y, COL_W, FRAME_H,
                         leftPadding=2, rightPadding=2,
                         topPadding=0, bottomPadding=0, id=fid)

        p1_frames = [mk_frame(FX[0],"p1f0"), mk_frame(FX[1],"p1f1"),
                     mk_frame(FX[2],"p1f2"), mk_frame(FX[3],"p1f3")]
        p2_frames = [mk_frame(FX[0],"p2f0"), mk_frame(FX[1],"p2f1"),
                     mk_frame(FX[2],"p2f2"), mk_frame(FX[3],"p2f3")]

        pt1 = PageTemplate(id="p1", frames=p1_frames,
                           onPage=_make_on_page(f"COM — {cl}", f"FUNC — {fl}"))
        pt2 = PageTemplate(id="p2", frames=p2_frames,
                           onPage=_make_on_page(f"FUNC — {fl}", f"COM — {cl}"))

        buf = io.BytesIO()
        doc = BaseDocTemplate(buf, pagesize=landscape(A4),
                              leftMargin=ML, rightMargin=MR,
                              topMargin=MT, bottomMargin=MB,
                              pageTemplates=[pt1, pt2])

        flowables = [NextPageTemplate("p1")]

        # H4: COM ingresos+resumo (frames 0,1)
        flowables.extend(ci)
        for _ in range(fb_after_ci):
            flowables.append(UseUpSpace())
            flowables.append(FrameBreak())

        # H1+H2: FUNC gastos+ingresos (frames 2,3,4,5)
        flowables.extend(fg)
        flowables.extend(fi)
        for _ in range(fb_after_func):
            flowables.append(UseUpSpace())
            flowables.append(FrameBreak())

        # H3: COM gastos (frames 6,7)
        flowables.extend(cg)

        doc.build(flowables)
        n_pages = doc.page   # páginas reales generadas
        return buf.getvalue(), n_pages

    # ── Retry hasta que cabe en 2 páginas ─────────────────────────
    last_pdf = None
    for fs in [7.5, 7.0, 6.5, 6.0, 5.5, 5.0, 4.5, 4.0, 3.5, 3.0]:
        try:
            pdf_bytes, n_pages = _build(fs)
            last_pdf = pdf_bytes
            if n_pages <= 2:
                return pdf_bytes
        except Exception:
            continue

    return last_pdf or b""



# ── RENDER PRINCIPAL ──────────────────────────────────────────────
def render(ano: int) -> None:
    st.title("📈 Informes e Filtros Cruzados")

    cursos   = get_cursos()
    codigos  = get_codigos()
    clientes = get_clientes()
    pcs      = get_partidas_config()
    pnames   = sorted(set(p["nome"] for p in pcs))
    anos     = get_anos()

    tab_inf, tab_cuadro = st.tabs([
        "🔍 Filtros e informes",
        "🖨️ Cuadro Presentación Contas",
    ])

    # ── TAB 1: Filtros cruzados (igual que antes) ─────────────────
    with tab_inf:
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
            if cur_f  != "Todos":    params["curso_id"]   = next(
                (c["id"] for c in cursos if c["nome"]==cur_f), None)
            if tip_f  == "Gastos":   params["tipo"]       = "G"
            elif tip_f == "Ingresos": params["tipo"]      = "I"
            if per_f  != "Todos":    params["periodo"]    = per_f
            if cod_f  != "Todos":    params["codigo"]     = cod_f.split(" — ")[0]
            if part_f != "Todas":    params["xustifica"]  = part_f
            if cl_f   != "Todos":    params["cliente_id"] = next(
                (c["id"] for c in clientes if c["nome"]==cl_f), None)
            if desde:                params["fecha_desde"] = str(desde)
            if ata:                  params["fecha_hasta"] = str(ata)

            movs  = get_informes(params)
            debe  = sum(m["importe"] for m in movs if m["tipo"]=="G")
            haber = sum(m["importe"] for m in movs if m["tipo"]=="I")
            st.session_state["inf_result"] = {"movs":movs,"debe":debe,"haber":haber}

        if "inf_result" not in st.session_state:
            st.info("Configura os filtros e pulsa Xerar informe.")
        else:
            data  = st.session_state["inf_result"]
            movs  = data["movs"]; debe = data["debe"]; haber = data["haber"]
            st.divider()
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Rexistros", len(movs)); c2.metric("Total Debe",  fmt(debe))
            c3.metric("Total Haber", fmt(haber)); c4.metric("Neto", fmt(haber-debe))

            if not movs:
                st.info("Non se atoparon rexistros cos filtros seleccionados")
            else:
                df = pd.DataFrame([{
                    "Data":    fmtD(m.get("data","")), "Ano": m.get("ano",""),
                    "Área":    m.get("area",""), "Curso": m.get("curso_nome",""),
                    "Concepto": m.get("concepto",""), "Cliente": m.get("cliente_nome",""),
                    "NIF":     m.get("cliente_nif",""), "Código": m.get("codigo",""),
                    "Período": m.get("periodo",""), "Partida": m.get("xustifica",""),
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
                        filas  = [[fmtD(m.get("data","")), m.get("ano",""),
                                   m.get("area",""), m.get("curso_nome",""),
                                   m.get("concepto",""), m.get("cliente_nome",""),
                                   m.get("cliente_nif",""), m.get("codigo",""),
                                   m.get("periodo",""), m.get("xustifica",""),
                                   m["importe"] if m["tipo"]=="G" else 0.0,
                                   m["importe"] if m["tipo"]=="I" else 0.0] for m in movs]
                        pdf, err = gen_pdf(
                            f"Informe — Ano {ano}", f"{len(movs)} rexistros",
                            cols_p, filas,
                            ["","","","","TOTAL","","","","","",debe,haber])
                        if err: st.error(f"PDF: {err}")
                        else:   st.download_button(
                            "⬇️ PDF", data=pdf, file_name=f"Informe_{ano}.pdf",
                            mime="application/pdf", key="inf_pdf_dl")

    # ── TAB 2: Cuadro Presentación Contas ─────────────────────────
    with tab_cuadro:
        st.subheader("🖨️ Cuadro de Presentación de Contas")
        st.markdown(
            '<div style="background:#dbeafe;border:1px solid #93c5fd;border-radius:8px;'
            'padding:8px 12px;font-size:12px;color:#1e3a5f;margin-bottom:12px">'
            'Xera un PDF díptico A4 horizontal con os balances de '
            '<strong>Funcionamento e Comedor</strong>: gastos por código, '
            'ingresos e resumo balance. Listo para imprimir e presentar.</div>',
            unsafe_allow_html=True,
        )

        c1, c2 = st.columns(2)
        ano_sel  = c1.selectbox("📅 Ano natural", anos,
                                index=anos.index(ano) if ano in anos else len(anos)-1,
                                key="cuadro_ano")
        trim_opts = ["Anual (todo o ano)"] + PERIODOS
        trim_sel  = c2.selectbox("📆 Trimestre", trim_opts, key="cuadro_trim")
        trimestre = None if trim_sel.startswith("Anual") else trim_sel

        # Preview de saldos
        sal_f = get_saldo(ano_sel, "func")
        sal_c = get_saldo(ano_sel, "com")
        cc1, cc2 = st.columns(2)
        cc1.metric("Saldo anterior Funcionamento", fmt(sal_f))
        cc2.metric("Saldo anterior Comedor",       fmt(sal_c))

        st.divider()

        if st.button("📄 Xerar PDF Cuadro Presentación",
                     type="primary", use_container_width=True, key="btn_cuadro"):
            with st.spinner("Xerando PDF díptico..."):
                # Cargar movimientos filtrados
                params_f: dict = {"area": "func", "ano": ano_sel}
                params_c: dict = {"area": "com",  "ano": ano_sel}
                if trimestre:
                    params_f["periodo"] = trimestre
                    params_c["periodo"] = trimestre

                movs_func = get_informes(params_f)
                movs_com  = get_informes(params_c)

                pdf_bytes = _gen_cuadro_presentacion(
                    ano_sel, trimestre, movs_func, movs_com)

                trim_label = trimestre.replace("º TRIMESTRE","T").replace(" ","") if trimestre else "Anual"
                fname = f"Cuadro_Contas_{ano_sel}_{trim_label}.pdf"

            st.success("✅ PDF xerado!")
            st.download_button(
                "⬇️ Descargar Cuadro Presentación",
                data=pdf_bytes,
                file_name=fname,
                mime="application/pdf",
                key="dl_cuadro",
            )

            # Preview de movimientos incluidos
            with st.expander("Ver movementos incluídos", expanded=False):
                col_f, col_c = st.columns(2)
                with col_f:
                    st.caption(f"Funcionamento: {len(movs_func)} movementos")
                    gf = sum(m["importe"] for m in movs_func if m["tipo"]=="G")
                    hf = sum(m["importe"] for m in movs_func if m["tipo"]=="I")
                    st.caption(f"Gastos: {fmt(gf)} · Ingresos: {fmt(hf)}")
                with col_c:
                    st.caption(f"Comedor: {len(movs_com)} movementos")
                    gc = sum(m["importe"] for m in movs_com if m["tipo"]=="G")
                    hc = sum(m["importe"] for m in movs_com if m["tipo"]=="I")
                    st.caption(f"Gastos: {fmt(gc)} · Ingresos: {fmt(hc)}")
