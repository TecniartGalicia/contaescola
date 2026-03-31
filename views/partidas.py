import io
import streamlit as st
import pandas as pd

from db import (get_cursos, get_anos, get_partidas, get_movs_partida,
                get_partidas_resumen_global)
from utils import fmt, fmtD
from utils.pdf import gen_pdf


def _pdf_partida(p: dict, movs: list, filtro_label: str) -> bytes | None:
    """Genera PDF de una partida con sus movimientos."""
    total_ing  = sum(m["importe"] for m in movs if m["tipo"]=="I")
    total_gast = sum(m["importe"] for m in movs if m["tipo"]=="G")
    saldo_act  = p["saldo_inicial"] + total_ing - total_gast

    subtitulo = (
        f"Saldo inicial: {fmt(p['saldo_inicial'])} € | "
        f"Ingresos: {fmt(total_ing)} € | "
        f"Gastos: {fmt(total_gast)} € | "
        f"Saldo actual: {fmt(saldo_act)} €"
        + (f" | Filtro: {filtro_label}" if filtro_label != "Todos" else "")
    )

    cols = ["Data", "Ano", "Curso", "Área", "Concepto", "Cliente",
            "Período", "Debe €", "Haber €"]
    filas = []
    for m in movs:
        filas.append([
            fmtD(m.get("data","")),
            m.get("ano",""),
            m.get("curso_nome",""),
            "Func" if m.get("area")=="func" else "Com",
            m.get("concepto",""),
            m.get("cliente_nome","") or "",
            m.get("periodo",""),
            round(m["importe"],2) if m["tipo"]=="G" else None,
            round(m["importe"],2) if m["tipo"]=="I" else None,
        ])

    totales = ["", "", "", "", "TOTAL", "",
               "", fmt(total_gast), fmt(total_ing)]

    pdf_bytes, err = gen_pdf(
        title    = f"📋 Partida: {p['nome']}",
        subtitulo= subtitulo,
        columnas = cols,
        filas    = filas,
        totales  = totales,
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
        cur_opts = [c["nome"] for c in cursos]
        # Preseleccionar cur_id del sidebar si viene
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

    # ── Cargar movimientos ─────────────────────────────────────────
    movs = get_movs_partida(p["nome"], filtro_curso_id, filtro_ano)

    # ── Totales globales de la partida (sin filtro) ────────────────
    res_global = get_partidas_resumen_global(p["nome"])
    ing_global  = res_global["haber"]
    gast_global = res_global["debe"]
    saldo_act   = p["saldo_inicial"] + ing_global - gast_global

    # ── Totales del filtro actual ──────────────────────────────────
    ing_filtro  = sum(m["importe"] for m in movs if m["tipo"]=="I")
    gast_filtro = sum(m["importe"] for m in movs if m["tipo"]=="G")

    # ── Cabecera con métricas ──────────────────────────────────────
    st.subheader(f"📋 {p['nome']}")
    if p.get("notas"):
        st.caption(p["notas"])

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("💰 Saldo inicial",  fmt(p["saldo_inicial"]))
    c2.metric("📥 Total ingresos", fmt(ing_global))
    c3.metric("📤 Total gastos",   fmt(gast_global))
    c4.metric("🏦 Saldo actual",   fmt(saldo_act),
              delta=fmt(saldo_act - p["saldo_inicial"]) if p["saldo_inicial"] else None)

    # Barra de progreso si hay saldo inicial
    if p["saldo_inicial"] > 0:
        pct = min(100, gast_global / p["saldo_inicial"] * 100)
        ico = "🔴" if pct > 90 else "🟡" if pct > 70 else "🟢"
        st.progress(pct / 100)
        st.caption(f"{ico} {pct:.1f}% do saldo inicial gastado")

    st.divider()

    # ── Totales del filtro (si hay filtro activo) ──────────────────
    if modo_filtro != "Todos":
        st.markdown(f"**Resultados para: {filtro_label}**")
        cf1, cf2, cf3 = st.columns(3)
        cf1.metric("📥 Ingresos", fmt(ing_filtro))
        cf2.metric("📤 Gastos",   fmt(gast_filtro))
        cf3.metric("Balance",     fmt(ing_filtro - gast_filtro))

    # ── Tabla de movimientos ───────────────────────────────────────
    col_tit, col_pdf = st.columns([4, 1])
    col_tit.markdown(f"**📋 Movementos** {'— ' + filtro_label if modo_filtro != 'Todos' else ''} ({len(movs)})")

    # Botón PDF
    pdf_bytes = _pdf_partida(p, movs, filtro_label)
    if pdf_bytes:
        fname = f"Partida_{p['nome'].replace(' ','_')}_{filtro_label}.pdf"
        col_pdf.download_button(
            "📄 PDF", data=pdf_bytes, file_name=fname,
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
            f"Total gastos: **{fmt(gast_filtro)}** · "
            f"Total ingresos: **{fmt(ing_filtro)}** · "
            f"Balance filtro: **{fmt(ing_filtro - gast_filtro)}**"
        )
    else:
        st.info(f"Non hai movementos para esta partida"
                + (f" co filtro '{filtro_label}'" if modo_filtro != "Todos" else "") + ".")
