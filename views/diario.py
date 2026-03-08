import streamlit as st
import pandas as pd

from db import get_diario, get_saldo, get_cursos
from db.schema import PERIODOS, CATEGORIAS_COM
from components.form_movemento import form_movemento
from utils import fmt, fmtD, sum_tipo, excel_bytes, gen_pdf


def render(area: str, ano: int, cur_id: int | None) -> None:
    icon  = "📒" if area == "func" else "🍽️"
    label = "Funcionamento" if area == "func" else "Comedor"
    st.title(f"{icon} {label} — Diario {ano}")

    movs = get_diario(area, ano, cur_id)
    sa   = get_saldo(ano, area)
    d_t  = sum_tipo(movs, "G"); h_t = sum_tipo(movs, "I"); bal = sa + h_t - d_t

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Saldo anterior", fmt(sa))
    c2.metric("Total Debe",     fmt(d_t))
    c3.metric("Total Haber",    fmt(h_t))
    c4.metric("Saldo actual",   fmt(bal))
    st.divider()

    # Filtros
    with st.expander("🔍 Filtros", expanded=False):
        fc1, fc2, fc3, fc4 = st.columns(4)
        busca  = fc1.text_input("Buscar concepto", key=f"{area}_busca")
        tip_f  = fc2.selectbox("Tipo", ["Todos","Gastos","Ingresos"], key=f"{area}_tip")
        curs   = get_cursos()
        cur_f  = fc3.selectbox("Curso", ["Todos"] + [c["nome"] for c in curs], key=f"{area}_curf")
        per_f  = fc4.selectbox("Período", ["Todos"] + PERIODOS, key=f"{area}_perf")

    f = movs
    if busca:
        f = [m for m in f if busca.lower() in
             (m.get("concepto","") + "  " + (m.get("cliente_nome") or "")).lower()]
    if tip_f == "Gastos":   f = [m for m in f if m["tipo"] == "G"]
    elif tip_f == "Ingresos": f = [m for m in f if m["tipo"] == "I"]
    if cur_f != "Todos":
        cid2 = next((c["id"] for c in curs if c["nome"] == cur_f), None)
        if cid2: f = [m for m in f if m["curso_id"] == cid2]
    if per_f != "Todos":
        f = [m for m in f if m.get("periodo") == per_f]

    with st.expander(f"➕ Novo movemento — {label}", expanded=False):
        if form_movemento(area, key_prefix=f"new_{area}"):
            st.rerun()

    st.caption(f"{len(f)} rexistros")
    if not f:
        st.info("Sen movementos para os filtros seleccionados")
        return

    df = pd.DataFrame([{
        "Nº":      m.get("num",""),
        "Data":    fmtD(m.get("data","")),
        "Concepto": m.get("concepto",""),
        "Cliente": m.get("cliente_nome",""),
        "Cód":     m.get("codigo","") if area=="func" else m.get("categoria",""),
        "Período": m.get("periodo",""),
        "Curso":   m.get("curso_nome",""),
        "Partida": m.get("xustifica",""),
        "NEAE":    m.get("alumno_neae",""),
        "Debe €":  round(m["importe"],2) if m["tipo"]=="G" else None,
        "Haber €": round(m["importe"],2) if m["tipo"]=="I" else None,
    } for m in f])
    st.dataframe(df, use_container_width=True, hide_index=True)

    # Exportar
    col_x, col_p, _ = st.columns([1, 1, 4])
    with col_x:
        st.download_button(
            "📊 Excel", data=excel_bytes([(label, df)]),
            file_name=f"{label}_{ano}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    with col_p:
        if st.button("🖨️ PDF", key=f"pdf_{area}"):
            cols_p = ["Nº","Data","Concepto","Cliente","Cód","Período","Curso","Debe €","Haber €"]
            filas  = [[m.get("num",""), fmtD(m.get("data","")), m.get("concepto",""),
                       m.get("cliente_nome",""),
                       m.get("codigo","") if area=="func" else m.get("categoria",""),
                       m.get("periodo",""), m.get("curso_nome",""),
                       m["importe"] if m["tipo"]=="G" else 0.0,
                       m["importe"] if m["tipo"]=="I" else 0.0] for m in f]
            d2 = sum(m["importe"] for m in f if m["tipo"]=="G")
            h2 = sum(m["importe"] for m in f if m["tipo"]=="I")
            pdf, err = gen_pdf(
                f"Diario {label} — Ano {ano}", f"{len(f)} rexistros",
                cols_p, filas, ["","","TOTAL","","","","", d2, h2],
            )
            if err:
                st.error(f"PDF: {err}")
            else:
                st.download_button("⬇️ Descargar PDF", data=pdf,
                    file_name=f"{label}_{ano}.pdf", mime="application/pdf",
                    key=f"dl_pdf_{area}")

    # Editar movimiento
    st.divider()
    st.subheader("✏️ Editar / Eliminar movemento")
    mov_map = {
        f"#{m['num']} — {fmtD(m.get('data',''))} — {m.get('concepto','')}": m
        for m in f
    }
    sel = st.selectbox("Selecciona", ["— Seleccionar —"] + list(mov_map.keys()),
                       key=f"{area}_edit_sel")
    if sel != "— Seleccionar —":
        mov_edit = mov_map[sel]
        if form_movemento(area, mov=mov_edit,
                          key_prefix=f"edit_{area}_{mov_edit['id']}"):
            st.rerun()
