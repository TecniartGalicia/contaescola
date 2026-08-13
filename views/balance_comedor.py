"""
views/balance_comedor.py
Balance de comedores escolares — o impreso trimestral da Consellería.

O período córtase por número de asento, non por datas: os asentos numéranse por
orde de rexistro e o corte real do centro é "do asento X ao asento Y".
"""
import json
from datetime import date

import streamlit as st
import pandas as pd

from db import get_cursos, get_anos, get_cfg
from db.balance_comedor import (
    TRIMESTRES, PERIODOS_SUXERIDOS, get_rango_dispoñible, calcular_saldo_inicial,
    calcular_balance, get_balances, get_balance, ultimo_asento_declarado,
    save_balance,
)
from utils import fmt, fmtD
from utils.docx_balance import gen_balance_docx, FILAS_GASTO

MESES_GL = ["xaneiro", "febreiro", "marzo", "abril", "maio", "xuño",
            "xullo", "agosto", "setembro", "outubro", "novembro", "decembro"]


def _data_longa(d: date) -> str:
    return f"{d.day} de {MESES_GL[d.month - 1]} de {d.year}"


def render(ano: int, cur_id: int | None) -> None:
    st.title("🍽️ Balance de comedores escolares")
    st.markdown(
        '<div style="background:#dbeafe;border:1px solid #93c5fd;border-radius:8px;'
        'padding:10px 14px;font-size:13px;color:#1e3a5f;margin-bottom:12px">'
        'ℹ️ O período defínese por <strong>número de asento</strong> do Diario de Comedor, '
        'non por datas. Todo o económico calcúlase só; os datos de alumnos complétanse '
        'no Word descargado.</div>',
        unsafe_allow_html=True,
    )

    cursos = get_cursos()
    anos = get_anos()
    if not cursos:
        st.warning("Non hai cursos escolares creados. Ve a ⚙️ Táboas Mestras.")
        return

    # ── Período ──────────────────────────────────────────────────
    c1, c2, c3 = st.columns([2, 1.4, 1.2])
    cur_def = next((i for i, c in enumerate(cursos) if c["id"] == cur_id), len(cursos) - 1)
    curso_sel = c1.selectbox("🎓 Curso escolar", [c["nome"] for c in cursos],
                             index=cur_def, key="bc_curso")
    curso = next(c for c in cursos if c["nome"] == curso_sel)
    trim = c2.selectbox("📆 Trimestre", TRIMESTRES, key="bc_trim")
    ano_sel = c3.selectbox("📅 Exercicio dos asentos", anos,
                           index=anos.index(ano) if ano in anos else len(anos) - 1,
                           key="bc_ano",
                           help="O 1º trimestre do curso adoita saír do exercicio anterior")

    xa_emitido = get_balance(curso["id"], trim)
    snap = (json.loads(xa_emitido["snapshot_json"] or "{}") or {}) if xa_emitido else {}
    if xa_emitido:
        st.info(f"ℹ️ Este trimestre xa se emitiu o "
                f"{fmtD(xa_emitido['creado_en'][:10])} — asentos "
                f"{xa_emitido['num_desde']} a {xa_emitido['num_ata']}, remanente "
                f"{fmt(snap.get('remanente', 0))}. Se o volves gardar, substitúese.")

    dispo_min, dispo_max = get_rango_dispoñible(ano_sel)
    if dispo_max == 0:
        st.warning(f"Non hai asentos de comedor no exercicio {ano_sel}.")
        return

    ultimo = ultimo_asento_declarado(ano_sel)
    desde_def = (xa_emitido["num_desde"] if xa_emitido
                 else (ultimo + 1 if ultimo and ultimo < dispo_max else dispo_min))
    ata_def = xa_emitido["num_ata"] if xa_emitido else dispo_max

    st.markdown(f"**📒 Asentos do Diario de Comedor** — dispoñibles do "
                f"**{dispo_min}** ao **{dispo_max}** no exercicio {ano_sel}")
    c4, c5, c6 = st.columns([1, 1, 2])
    desde = c4.number_input("Do asento nº", min_value=dispo_min, max_value=dispo_max,
                            value=max(dispo_min, min(desde_def, dispo_max)), step=1, key="bc_desde")
    ata = c5.number_input("Ao asento nº", min_value=dispo_min, max_value=dispo_max,
                          value=max(desde_def, min(ata_def, dispo_max)), step=1, key="bc_ata")
    if ata < desde:
        st.error("O asento final ten que ser igual ou maior que o inicial.")
        return

    periodo_txt = c6.text_input("Período (texto do impreso)",
                                value=(xa_emitido["periodo_txt"] if xa_emitido
                                       else PERIODOS_SUXERIDOS.get(trim, "")),
                                key="bc_periodo")

    # ── Cálculo ──────────────────────────────────────────────────
    saldo_auto = calcular_saldo_inicial(ano_sel, desde)
    c7, c8, c9 = st.columns(3)
    saldo_inicial = c7.number_input(
        "💶 Saldo inicial na conta (€)", value=float(saldo_auto), step=0.01, key="bc_saldo",
        help=f"Calculado: saldo de apertura do exercicio máis os asentos anteriores ao {desde}")
    existencias = c8.number_input("📦 Valoración das existencias (€)",
                                  value=float(xa_emitido["existencias"]) if xa_emitido else 0.0,
                                  step=0.01, key="bc_exist")
    dias = c9.number_input("📅 Días de funcionamento",
                           value=int(xa_emitido["dias_funcionamento"]) if xa_emitido else 0,
                           min_value=0, max_value=200, step=1, key="bc_dias")
    if abs(saldo_inicial - saldo_auto) > 0.005:
        st.caption(f"⚠️ Estás usando un saldo distinto do calculado ({fmt(saldo_auto)}).")

    bal = calcular_balance(ano_sel, desde, ata, saldo_inicial, existencias)

    c10, c11 = st.columns(2)
    txt_oi = c10.text_input("Outros ingresos — especificar",
                            value=xa_emitido["outros_ingresos_txt"] if xa_emitido else "",
                            placeholder="Ex: Obras técnicas e causas sobrevidas comedor",
                            key="bc_txt_oi")
    txt_og = c11.text_input("Outros gastos — especificar",
                            value=xa_emitido["outros_gastos_txt"] if xa_emitido else "",
                            placeholder="Ex: UTENSILIOS COCIÑA", key="bc_txt_og")

    st.divider()

    # ── Avisos ───────────────────────────────────────────────────
    if bal["sen_clasificar"]:
        st.warning("⚠️ Hai asentos cunha categoría que non encaixa en ningunha liña do "
                   "impreso; contabilizáronse en OUTROS:\n\n" +
                   "\n".join(f"- nº{m['num']} · {fmtD(m['data'])} · {m['concepto']} · "
                             f"{m.get('categoria') or 'sen categoría'} · {fmt(m['importe'])}"
                             for m in bal["sen_clasificar"][:8]))
    if ata < dispo_max:
        pendentes = len([1 for _ in range(ata + 1, dispo_max + 1)])
        st.info(f"ℹ️ Quedan asentos posteriores ao {ata} sen declarar neste balance "
                f"(ata o {dispo_max}, {pendentes} números).")
    if ultimo and not xa_emitido:
        if ultimo >= dispo_max:
            st.info(f"ℹ️ Todos os asentos do exercicio {ano_sel} (ata o {dispo_max}) "
                    f"xa están declarados noutros balances.")
        elif desde <= ultimo:
            st.warning(f"⚠️ Os asentos ata o {ultimo} xa están declarados noutro "
                       f"balance: este rango solápase con el.")
        elif desde > ultimo + 1:
            st.warning(f"⚠️ O último asento declarado noutro balance foi o {ultimo}; "
                       f"estás empezando no {desde} e quedan {desde - ultimo - 1} sen declarar.")

    # Se o diario cambiou despois de emitir, o papel novo non coincidiría co
    # certificado: avísase comparando coa foto gardada na emisión
    if (xa_emitido and snap and desde == xa_emitido["num_desde"]
            and ata == xa_emitido["num_ata"]):
        difs = []
        for k, lbl in [("saldo_inicial", "saldo inicial"), ("subvencions", "subvencións"),
                       ("outros_ingresos", "outros ingresos"),
                       ("total_gastos", "total gastos"), ("remanente", "remanente")]:
            if k in snap and abs((snap.get(k) or 0) - bal[k]) > 0.005:
                difs.append(f"{lbl}: {fmt(snap[k])} → {fmt(bal[k])}")
        if difs:
            st.error("🚨 O diario cambiou despois de emitir este balance. "
                     "O documento que descargues agora NON coincidirá co papel "
                     "certificado: " + " · ".join(difs))

    # ── Vista previa ─────────────────────────────────────────────
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Saldo inicial", fmt(bal["saldo_inicial"]))
    m2.metric("Total ingresos", fmt(bal["total_ingresos"]))
    m3.metric("Total gastos", fmt(bal["total_gastos"]))
    m4.metric("🏦 Remanente", fmt(bal["remanente"]))

    ce, cg = st.columns(2)
    with ce:
        st.markdown("**INGRESOS**")
        st.dataframe(pd.DataFrame([
            {"Concepto": f"Saldo inicial na conta {get_cfg('comedor_conta','')}",
             "Importe €": bal["saldo_inicial"]},
            {"Concepto": "Subvencións da Administración", "Importe €": bal["subvencions"]},
            {"Concepto": "Outros ingresos", "Importe €": bal["outros_ingresos"]},
            {"Concepto": "Existencias no almacén", "Importe €": bal["existencias"]},
            {"Concepto": "TOTAL INGRESOS", "Importe €": bal["total_ingresos"]},
        ]), use_container_width=True, hide_index=True)
    with cg:
        st.markdown("**GASTOS**")
        filas = [{"Concepto": f, "Importe €": bal["gastos"].get(f, 0.0)} for f in FILAS_GASTO]
        filas.append({"Concepto": "TOTAL GASTOS", "Importe €": bal["total_gastos"]})
        st.dataframe(pd.DataFrame(filas), use_container_width=True, hide_index=True)

    with st.expander(f"📋 Asentos incluídos ({len(bal['movs'])})", expanded=False):
        if bal["movs"]:
            st.dataframe(pd.DataFrame([{
                "Nº": m["num"], "Data": fmtD(m.get("data", "")),
                "Concepto": m.get("concepto", ""), "Provedor": m.get("cliente_nome") or "",
                "Categoría": m.get("categoria", ""),
                "Debe €": m["importe"] if m["tipo"] == "G" else None,
                "Haber €": m["importe"] if m["tipo"] == "I" else None,
            } for m in bal["movs"]]), use_container_width=True, hide_index=True)
        else:
            st.info("Non hai asentos nese rango.")

    # ── Descarga ─────────────────────────────────────────────────
    st.divider()
    cd1, cd2 = st.columns([1, 2])
    # Ao reabrir un balance emitido, propor a data de sinatura gardada
    data_def = date.today()
    if xa_emitido and xa_emitido.get("data_sinatura"):
        try:
            data_def = date.fromisoformat(xa_emitido["data_sinatura"])
        except ValueError:
            pass
    data_sin = cd1.date_input("📅 Data da sinatura", value=data_def, key="bc_data_sin")
    lugar = get_cfg("comedor_lugar", "")
    cd2.caption(f"O documento sairá asinado en **{lugar}**, con data "
                f"**{_data_longa(data_sin)}**. Os datos de alumnos van en branco: "
                f"complétaos no Word.")

    datos = {
        "curso": curso["nome"].replace("-", "/"),
        "periodo_txt": periodo_txt, "trimestre": trim, "dias": dias or "",
        "tipo_comedor": get_cfg("comedor_tipo", "C"), "conta": get_cfg("comedor_conta", ""),
        "saldo_inicial": bal["saldo_inicial"], "subvencions": bal["subvencions"],
        "outros_ingresos": bal["outros_ingresos"], "outros_ingresos_txt": txt_oi,
        "existencias": bal["existencias"], "total_ingresos": bal["total_ingresos"],
        "gastos": bal["gastos"], "outros_gastos_txt": txt_og,
        "total_gastos": bal["total_gastos"], "remanente": bal["remanente"],
        "data_saldo": _data_longa(data_sin), "lugar": lugar,
        "lugar_data": f"{lugar}, a {_data_longa(data_sin)}.",
    }

    try:
        doc = gen_balance_docx(datos)
    except Exception as e:
        st.error(f"❌ Non se puido xerar o documento: {e}")
        return

    nome_arq = (f"Balance_comedor_{trim.replace('º','').replace(' ','')}_"
                f"{curso['nome']}.docx")
    b1, b2 = st.columns([1, 1])
    b1.download_button("⬇️ Descargar balance (Word)", data=doc, file_name=nome_arq,
                       mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                       type="primary", use_container_width=True, key="bc_dl")
    if b2.button("💾 Gardar como emitido", use_container_width=True, key="bc_save",
                 help="Garda as cifras deste balance para que reemitilo dea o mesmo papel"):
        save_balance({
            "curso_id": curso["id"], "trimestre": trim, "periodo_txt": periodo_txt,
            "ano": ano_sel, "num_desde": desde, "num_ata": ata,
            "dias_funcionamento": dias, "saldo_inicial": bal["saldo_inicial"],
            "existencias": bal["existencias"], "outros_ingresos_txt": txt_oi,
            "outros_gastos_txt": txt_og, "data_sinatura": str(data_sin),
        }, {k: v for k, v in bal.items() if k != "movs"})
        st.success(f"✅ Balance do {trim} de {curso['nome']} gardado.")
        st.rerun()

    # ── Histórico ────────────────────────────────────────────────
    emitidos = get_balances()
    if emitidos:
        st.divider()
        st.markdown("**🗂️ Balances emitidos**")
        st.dataframe(pd.DataFrame([{
            "Curso": b["curso_nome"], "Trimestre": b["trimestre"],
            "Período": b["periodo_txt"], "Exercicio": b["ano"],
            "Asentos": f"{b['num_desde']} – {b['num_ata']}",
            "Días": b["dias_funcionamento"] or "",
            "Remanente €": (json.loads(b["snapshot_json"] or "{}") or {}).get("remanente"),
            "Emitido": fmtD(b["creado_en"][:10]),
        } for b in emitidos]), use_container_width=True, hide_index=True)
