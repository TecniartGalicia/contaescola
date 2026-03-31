import streamlit as st
import pandas as pd

from db import (get_cursos, get_anos, get_partidas,
                get_movs_partida, get_partidas_resumen_global)
from db.connection import q
from utils import fmt, fmtD
from utils.pdf import gen_pdf


def _calcular_saldo_arrastrado(nome: str, saldo_inicial: float, hasta_ano: int) -> float:
    """
    Calcula el saldo acumulado hasta el año anterior al seleccionado.
    saldo_inicial + sum(ingresos años < hasta_ano) - sum(gastos años < hasta_ano)
    """
    rows = q("""
        SELECT tipo, SUM(importe) as t
        FROM diario
        WHERE xustifica = ? AND ano < ?
        GROUP BY tipo
    """, (nome, hasta_ano))
    ing_prev  = sum(r["t"] for r in rows if r["tipo"] == "I")
    gast_prev = sum(r["t"] for r in rows if r["tipo"] == "G")
    return saldo_inicial + ing_prev - gast_prev


def _pdf_partida(p: dict, movs: list, filtro_label: str,
                 saldo_arrastrado: float) -> bytes | None:
    total_ing  = sum(m["importe"] for m in movs if m["tipo"] == "I")
    total_gast = sum(m["importe"] for m in movs if m["tipo"] == "G")
    saldo_final = saldo_arrastrado + total_ing - total_gast

    subtitulo = (
        f"Saldo anterior: {fmt(saldo_arrastrado)} € | "
        f"Ingresos: {fmt(total_ing)} € | "
        f"Gastos: {fmt(total_gast)} € | "
        f"Saldo actual: {fmt(saldo_final)} €"
        + (f" | Filtro: {filtro_label}" if filtro_label != "Todos" else "")
    )

    cols  = ["Data", "Ano", "Curso", "Área", "Concepto", "Cliente",
             "Período", "Debe €", "Haber €"]
    filas = []
    for m in movs:
        filas.append([
            fmtD(m.get("data", "")),
            m.get("ano", ""),
            m.get("curso_nome", ""),
            "Func" if m.get("area") == "func" else "Com",
            m.get("concepto", ""),
            m.get("cliente_nome", "") or "",
            m.get("periodo", ""),
            round(m["importe"], 2) if m["tipo"] == "G" else None,
            round(m["importe"], 2) if m["tipo"] == "I" else None,
        ])
    totales = ["", "", "", "", "TOTAL", "", "",
               fmt(total_gast), fmt(total_ing)]

    pdf_bytes, _ = gen_pdf(
        title     = f"📋 Partida: {p['nome']}",
        subtitulo = subtitulo,
        columnas  = cols,
        filas     = filas,
        totales   = totales,
    )
    return pdf_bytes


def render(ano: int, cur_id: int | None) -> None:
    st.title("📋 Partidas Finalistas")

    partidas = get_partidas()
    if not partidas:
        st.info("Non hai partidas creadas. Ve a ⚙️ Tablas Maestras → Partidas para crealas.")
        return

    cursos = get_cursos()
    anos   = get_anos()

    # ── Selector de partida ────────────────────────────────────────
    p_names = [p["nome"] for p in partidas]
    p_sel   = st.selectbox("📋 Selecciona a partida", p_names, key="part_sel")
    p       = next((x for x in partidas if x["nome"] == p_sel), None)
    if not p:
        return

    st.divider()

    # ── Filtros ────────────────────────────────────────────────────
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
        cur_opts    = [c["nome"] for c in cursos]
        cur_def     = next((i for i,c in enumerate(cursos) if c["id"]==cur_id), 0)
        cur_sel     = col_f2.selectbox("Curso", cur_opts, index=cur_def, key="part_filtro_cur")
        filtro_curso_id = next((c["id"] for c in cursos if c["nome"]==cur_sel), None)
        filtro_label    = cur_sel

    elif modo_filtro == "Ano natural":
        ano_sel     = col_f2.selectbox(
            "Ano", anos,
            index=anos.index(ano) if ano in anos else len(anos)-1,
            key="part_filtro_ano",
        )
        filtro_ano   = ano_sel
        filtro_label = str(ano_sel)

    # ── Cargar movimientos ─────────────────────────────────────────
    movs = get_movs_partida(p["nome"], filtro_curso_id, filtro_ano)

    # ── Calcular saldo de partida según modo ───────────────────────
    if modo_filtro == "Ano natural" and filtro_ano is not None:
        # ★ Saldo arrastrado: saldo_inicial + movimientos de años anteriores
        saldo_anterior = _calcular_saldo_arrastrado(p["nome"], p["saldo_inicial"], filtro_ano)
        ing_periodo    = sum(m["importe"] for m in movs if m["tipo"] == "I")
        gast_periodo   = sum(m["importe"] for m in movs if m["tipo"] == "G")
        saldo_final    = saldo_anterior + ing_periodo - gast_periodo
        label_saldo_ant = f"Saldo anterior ({filtro_ano-1} e antes)"

    elif modo_filtro == "Curso escolar":
        # Saldo inicial de la partida tal cual
        saldo_anterior = p["saldo_inicial"]
        ing_periodo    = sum(m["importe"] for m in movs if m["tipo"] == "I")
        gast_periodo   = sum(m["importe"] for m in movs if m["tipo"] == "G")
        saldo_final    = saldo_anterior + ing_periodo - gast_periodo
        label_saldo_ant = "Saldo inicial"

    else:
        # Todos — saldo global de toda la vida de la partida
        res_global  = get_partidas_resumen_global(p["nome"])
        saldo_anterior = p["saldo_inicial"]
        ing_periodo    = res_global["haber"]
        gast_periodo   = res_global["debe"]
        saldo_final    = saldo_anterior + ing_periodo - gast_periodo
        label_saldo_ant = "Saldo inicial"

    # ── Cabecera con métricas ──────────────────────────────────────
    st.subheader(f"📋 {p['nome']}")
    if p.get("notas"):
        st.caption(p["notas"])

    c1, c2, c3, c4 = st.columns(4)
    c1.metric(label_saldo_ant,  fmt(saldo_anterior))
    c2.metric("📥 Ingresos",    fmt(ing_periodo))
    c3.metric("📤 Gastos",      fmt(gast_periodo))
    c4.metric("🏦 Saldo actual", fmt(saldo_final),
              delta=fmt(saldo_final - saldo_anterior) if saldo_anterior else None)

    # Barra de progreso: gastos vs (saldo_anterior + ingresos)
    base = saldo_anterior + ing_periodo
    if base > 0:
        pct = min(100, gast_periodo / base * 100)
        ico = "🔴" if pct > 90 else "🟡" if pct > 70 else "🟢"
        st.progress(pct / 100)
        st.caption(f"{ico} {pct:.1f}% dos recursos gastados")

    # Aviso informativo para modo año natural
    if modo_filtro == "Ano natural":
        st.markdown(
            f"<div style='background:#f0fdf4;border:1px solid #86efac;"
            f"border-radius:6px;padding:6px 10px;font-size:11px;color:#166534;"
            f"margin-bottom:8px;'>"
            f"ℹ️ <strong>Saldo arrastrado:</strong> O saldo anterior inclúe o saldo inicial "
            f"da partida máis todos os movementos de anos anteriores a {filtro_ano}.</div>",
            unsafe_allow_html=True,
        )

    st.divider()

    # ── Tabla de movimientos ───────────────────────────────────────
    col_tit, col_pdf = st.columns([4, 1])
    col_tit.markdown(
        f"**📋 Movementos** "
        f"{'— ' + filtro_label if modo_filtro != 'Todos' else ''} "
        f"({len(movs)})"
    )

    pdf_bytes = _pdf_partida(p, movs, filtro_label, saldo_anterior)
    if pdf_bytes:
        fname = f"Partida_{p['nome'].replace(' ','_')}_{filtro_label}.pdf"
        col_pdf.download_button(
            "📄 PDF", data=pdf_bytes, file_name=fname,
            mime="application/pdf", key="btn_pdf_partida",
        )

    if movs:
        df = pd.DataFrame([{
            "Data":     fmtD(m.get("data", "")),
            "Ano":      m.get("ano", ""),
            "Curso":    m.get("curso_nome", ""),
            "Área":     "📘 Func" if m.get("area") == "func" else "🍽️ Com",
            "Concepto": m.get("concepto", ""),
            "Cliente":  m.get("cliente_nome", "") or "",
            "Período":  m.get("periodo", ""),
            "Debe €":   round(m["importe"], 2) if m["tipo"] == "G" else None,
            "Haber €":  round(m["importe"], 2) if m["tipo"] == "I" else None,
        } for m in movs])
        st.dataframe(df, use_container_width=True, hide_index=True)
        st.caption(
            f"Ingresos: **{fmt(ing_periodo)}** · "
            f"Gastos: **{fmt(gast_periodo)}** · "
            f"Balance período: **{fmt(ing_periodo - gast_periodo)}**"
        )
    else:
        st.info(
            f"Non hai movementos para esta partida"
            + (f" co filtro '{filtro_label}'" if modo_filtro != "Todos" else "") + "."
        )
