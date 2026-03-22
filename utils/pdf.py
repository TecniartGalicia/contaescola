"""
utils/pdf.py
Generación de PDFs con reportlab.
Recibe datos genéricos (título, columnas, filas) y aplica el estilo corporativo
usando la configuración guardada en la BD (logo, centro, pies de página).
"""
import io
import base64
from datetime import datetime

from db import get_cfg
from utils.formatters import fmt


def gen_pdf(
    title: str,
    subtitulo: str,
    columnas: list[str],
    filas: list[list],
    totales: list | None = None,
) -> tuple[bytes | None, str | None]:
    """
    Genera un PDF con cabecera corporativa, tabla de datos y pies de página.

    Returns:
        (bytes_pdf, None)         si todo fue bien
        (None, mensaje_de_error)  si reportlab no está instalado
    """
    try:
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
        from reportlab.platypus import (
            SimpleDocTemplate, Table, TableStyle,
            Paragraph, Spacer, HRFlowable, Image,
        )
    except ImportError:
        return None, "reportlab non instalado. Executa: pip install reportlab"

    # Configuración del centro
    cfg = {k: get_cfg(k) for k in [
        "centro_nome", "centro_direccion", "centro_nif",
        "footer1", "footer2", "logo_base64",
    ]}

    buf = io.BytesIO()
    use_landscape = len(columnas) > 7
    pagesize = landscape(A4) if use_landscape else A4
    doc = SimpleDocTemplate(
        buf, pagesize=pagesize,
        leftMargin=1.5*cm, rightMargin=1.5*cm,
        topMargin=2*cm, bottomMargin=2*cm,
    )

    styles = getSampleStyleSheet()
    BLUE   = colors.HexColor("#1e40af")
    BLUE_L = colors.HexColor("#dbeafe")
    PAPER  = colors.HexColor("#f8f7f4")
    GRAY   = colors.HexColor("#94a3b8")

    sT  = ParagraphStyle("T2", parent=styles["Title"], fontSize=14, spaceAfter=4)
    sSu = ParagraphStyle("Su", parent=styles["Normal"], fontSize=9,
                         textColor=colors.HexColor("#64748b"), spaceAfter=2)
    sH  = ParagraphStyle("TH", parent=styles["Normal"], fontSize=7.5,
                         textColor=colors.white, fontName="Helvetica-Bold",
                         alignment=TA_CENTER)
    sC  = ParagraphStyle("TC", parent=styles["Normal"], fontSize=7.5, alignment=TA_LEFT)
    sCR = ParagraphStyle("TR", parent=styles["Normal"], fontSize=7.5, alignment=TA_RIGHT)
    sF  = ParagraphStyle("FO", parent=styles["Normal"], fontSize=7,
                         textColor=GRAY, alignment=TA_CENTER, spaceBefore=3)

    elements = []

    # ── Cabecera ──────────────────────────────────────────────────
    hrow = []
    if cfg["logo_base64"]:
        try:
            img_buf = io.BytesIO(base64.b64decode(cfg["logo_base64"]))
            hrow.append(Image(img_buf, width=3*cm, height=2*cm))
        except Exception:
            hrow.append("")
    else:
        hrow.append("")

    centro_txt = f"<b>{cfg['centro_nome']}</b>"
    if cfg["centro_direccion"]:
        centro_txt += f"<br/><font size='8'>{cfg['centro_direccion']}</font>"
    if cfg["centro_nif"]:
        centro_txt += f"<font size='8'> · NIF: {cfg['centro_nif']}</font>"
    hrow.append(Paragraph(centro_txt, styles["Normal"]))
    hrow.append(Paragraph(
        f"<font size='8'>{datetime.now().strftime('%d/%m/%Y %H:%M')}</font>",
        ParagraphStyle("R", parent=styles["Normal"], alignment=TA_RIGHT),
    ))

    header_table = Table([hrow], colWidths=[3.2*cm, None, 3.5*cm])
    header_table.setStyle(TableStyle([
        ("VALIGN",       (0,0), (-1,-1), "MIDDLE"),
        ("BOTTOMPADDING",(0,0), (-1,-1), 6),
    ]))
    elements.append(header_table)
    elements.append(HRFlowable(width="100%", thickness=1.5, color=BLUE, spaceAfter=6))
    elements.append(Paragraph(title, sT))
    if subtitulo:
        elements.append(Paragraph(subtitulo, sSu))
    elements.append(Spacer(1, 0.3*cm))

    # ── Tabla de datos ────────────────────────────────────────────
    thead = [Paragraph(c, sH) for c in columnas]
    data  = [thead]

    for row in filas:
        trow = []
        for cell in row:
            if cell is None or cell == "":
                trow.append("")
            elif isinstance(cell, float) and cell != 0:
                trow.append(Paragraph(fmt(cell), sCR))
            elif isinstance(cell, (int, float)) and cell == 0:
                trow.append("")
            else:
                trow.append(Paragraph(str(cell), sC))
        data.append(trow)

    if totales:
        data.append([
            Paragraph(f"<b>{c}</b>" if c else "", sCR if i > 0 else sC)
            for i, c in enumerate(totales)
        ])

    avail_w = (landscape(A4)[0] if use_landscape else A4[0]) - 3*cm
    col_w   = avail_w / len(columnas)
    t = Table(data, colWidths=[col_w]*len(columnas), repeatRows=1)
    ts = TableStyle([
        ("BACKGROUND",      (0,0),  (-1,0),  BLUE),
        ("TEXTCOLOR",       (0,0),  (-1,0),  colors.white),
        ("FONTNAME",        (0,0),  (-1,0),  "Helvetica-Bold"),
        ("FONTSIZE",        (0,0),  (-1,0),  7.5),
        ("ROWBACKGROUNDS",  (0,1),  (-1,-1), [colors.white, PAPER]),
        ("FONTSIZE",        (0,1),  (-1,-1), 7.5),
        ("FONTNAME",        (0,1),  (-1,-1), "Helvetica"),
        ("GRID",            (0,0),  (-1,-1), 0.3, colors.HexColor("#e8e6e0")),
        ("LINEBELOW",       (0,0),  (-1,0),  1.5, BLUE),
        ("VALIGN",          (0,0),  (-1,-1), "MIDDLE"),
        ("TOPPADDING",      (0,0),  (-1,-1), 4),
        ("BOTTOMPADDING",   (0,0),  (-1,-1), 4),
    ])
    if totales:
        ts.add("BACKGROUND", (0,-1), (-1,-1), BLUE_L)
        ts.add("FONTNAME",   (0,-1), (-1,-1), "Helvetica-Bold")
        ts.add("LINEABOVE",  (0,-1), (-1,-1), 1, BLUE)
    t.setStyle(ts)
    elements.append(t)

    # ── Pies de página ────────────────────────────────────────────
    elements.append(Spacer(1, 0.4*cm))
    elements.append(HRFlowable(width="100%", thickness=0.5, color=GRAY))
    footers = [x for x in [cfg["footer1"], cfg["footer2"]] if x]
    if footers:
        elements.append(Paragraph(" · ".join(footers), sF))

    doc.build(elements)
    return buf.getvalue(), None
