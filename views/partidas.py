import streamlit as st
import pandas as pd

from db import get_cursos, get_partidas_config, get_partidas_resumen
from db.connection import q
from utils import fmt, fmtD


def _get_movimentos_partida(nome_partida: str, curso_id: int) -> list[dict]:
    """Devuelve todos los movimientos asociados a una partida y curso."""
    return q("""
        SELECT d.num, d.data, d.tipo, d.importe, d.concepto,
               d.codigo, d.cod_desc, d.periodo, d.alumno_neae,
               cl.nome as cliente_nome
        FROM diario d
        LEFT JOIN clientes cl ON d.cliente_id = cl.id
        WHERE d.xustifica = ? AND d.curso_id = ?
        ORDER BY d.data ASC, d.num ASC
    """, (nome_partida, curso_id))


def render(ano: int, cur_id: int | None) -> None:
    st.title("📋 Partidas Finalistas")
    st.markdown(
        '<div style="background:#dbeafe;border:1px solid #93c5fd;border-radius:8px;'
        'padding:10px 14px;font-size:13px;color:#1e3a5f;margin-bottom:12px">'
        'ℹ️ Os gastos calcúlanse por <strong>curso escolar</strong>. '
        'Se a partida non ten importe asignado, úsanse os <strong>ingresos rexistrados</strong> '
        'como referencia. Fai clic en cada partida para ver os movementos.</div>',
        unsafe_allow_html=True,
    )

    cursos  = get_cursos()
    cf_opts = ["— Selecciona un curso —"] + [c["nome"] for c in cursos]

    cur_def = 0
    if cur_id:
        idx = next((i+1 for i, c in enumerate(cursos) if c["id"] == cur_id), 0)
        cur_def = idx

    cur_f = st.selectbox(
        "📅 Curso escolar",
        cf_opts,
        index=cur_def,
        key="part_cf",
        help="Os importes suman TODOS os gastos do curso, independentemente do ano natural",
    )

    if cur_f.startswith("—"):
        st.info("Selecciona un curso escolar para ver as partidas.")
        return

    cid_f = next((c["id"] for c in cursos if c["nome"] == cur_f), None)
    pcs   = get_partidas_config(cid_f)
    res   = get_partidas_resumen(ano, cid_f)

    if not pcs:
        st.info("Non hai partidas configuradas para este curso. Ve a ⚙️ Tablas Maestras.")
        return

    # ── Totales globales ──────────────────────────────────────────
    total_asig  = sum(p["importe_asignado"] for p in pcs)
    total_gast  = sum(res.get(p["nome"], {}).get("debe",  0.0) for p in pcs)
    total_ingr  = sum(res.get(p["nome"], {}).get("haber", 0.0) for p in pcs)
    total_pend  = total_asig - total_gast if total_asig > 0 else total_ingr - total_gast

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total asignado",  fmt(total_asig))
    c2.metric("Total ingresos",  fmt(total_ingr))
    c3.metric("Total gastado",   fmt(total_gast))
    c4.metric(
        "Total pendente" if total_pend >= 0 else "⚠️ EXCESO TOTAL",
        fmt(abs(total_pend)),
        delta=fmt(total_pend) if total_pend != 0 else None,
        delta_color="normal" if total_pend >= 0 else "inverse",
    )
    st.divider()

    # ── Detalle por partida ───────────────────────────────────────
    for p in pcs:
        r       = res.get(p["nome"], {"debe": 0.0, "haber": 0.0})
        gastado = r["debe"]
        ingreso = r["haber"]

        # ★ Si importe_asignado = 0 usar ingresos como referencia
        if p["importe_asignado"] > 0:
            asignado = p["importe_asignado"]
            ref_label = "Asignado"
        else:
            asignado  = ingreso
            ref_label = "Ingresado"

        pendente = asignado - gastado
        pct      = min(100, gastado / asignado * 100) if asignado > 0 else 0
        ico      = "🔴" if pct > 90 else "🟡" if pct > 70 else "🟢"

        # Cabecera del expander con todos los números visibles
        header = (
            f"{ico} **{p['nome']}**  —  "
            f"{ref_label}: {fmt(asignado)}  |  "
            f"Gastado: {fmt(gastado)}  |  "
            f"{'Pendente' if pendente >= 0 else '⚠️ EXCESO'}: {fmt(abs(pendente))}"
        )

        with st.expander(header, expanded=False):

            # Métricas internas
            cc1, cc2, cc3, cc4 = st.columns(4)
            cc1.metric(ref_label,   fmt(asignado))
            cc2.metric("Ingresos",  fmt(ingreso))
            cc3.metric("Gastado",   fmt(gastado))
            cc4.metric(
                "Pendente" if pendente >= 0 else "⚠️ EXCESO",
                fmt(abs(pendente)),
            )

            if asignado > 0:
                st.progress(pct / 100)
                st.caption(f"{pct:.1f}% executado")

            if p["importe_asignado"] == 0 and ingreso > 0:
                st.info(
                    f"ℹ️ Esta partida non ten importe asignado. "
                    f"Úsanse os ingresos rexistrados ({fmt(ingreso)}) como referencia."
                )

            # Movementos asociados
            movs = _get_movimentos_partida(p["nome"], cid_f) if cid_f else []

            if movs:
                st.markdown("**📋 Movementos:**")
                df = pd.DataFrame([{
                    "Nº":       m["num"],
                    "Data":     fmtD(m["data"]),
                    "Tipo":     "📤 Gasto" if m["tipo"] == "G" else "📥 Ingreso",
                    "Concepto": m["concepto"],
                    "Cliente":  m.get("cliente_nome") or "",
                    "NEAE":     m.get("alumno_neae") or "",
                    "Período":  m.get("periodo") or "",
                    "Debe €":   round(m["importe"], 2) if m["tipo"] == "G" else None,
                    "Haber €":  round(m["importe"], 2) if m["tipo"] == "I" else None,
                } for m in movs])
                st.dataframe(df, use_container_width=True, hide_index=True)

                # Mini resumen al pie
                tot_g = sum(m["importe"] for m in movs if m["tipo"] == "G")
                tot_i = sum(m["importe"] for m in movs if m["tipo"] == "I")
                st.caption(
                    f"Total: {len(movs)} movementos  —  "
                    f"Gastos: {fmt(tot_g)}  |  Ingresos: {fmt(tot_i)}"
                )
            else:
                st.info("Esta partida non ten movementos rexistrados aínda.")
