import re
import streamlit as st
import pandas as pd

from db import (get_cursos, get_codigos, get_partidas_config,
                save_curso, delete_curso, save_codigo, delete_codigo,
                save_partida, delete_partida)


def render() -> None:
    st.title("⚙️ Tablas Maestras")
    tab1, tab2, tab3 = st.tabs([
        "📅 Cursos Escolares",
        "🏷️ Códigos Contables",
        "📋 Partidas por Curso",
    ])

    # ── Cursos ────────────────────────────────────────────────────
    with tab1:
        cursos = get_cursos()
        if cursos:
            st.dataframe(
                pd.DataFrame([{"Nome": c["nome"]} for c in cursos]),
                use_container_width=True, hide_index=True,
            )
            do = ["— Seleccionar —"] + [c["nome"] for c in cursos]
            ds = st.selectbox("Eliminar curso", do, key="del_cur")
            if ds != "— Seleccionar —" and st.button("🗑️ Confirmar eliminación", key="conf_dc"):
                delete_curso(next(c["id"] for c in cursos if c["nome"] == ds))
                st.success("Eliminado"); st.rerun()
        with st.form("nc_form"):
            st.subheader("➕ Novo curso escolar")
            nome = st.text_input("Nome (ex: 2026-2027)", placeholder="2026-2027")
            if st.form_submit_button("Engadir", type="primary"):
                if not re.match(r"^\d{4}-\d{4}$", nome.strip()):
                    st.error("Formato incorrecto: usa 2026-2027")
                else:
                    save_curso(nome.strip())
                    st.success(f"'{nome}' engadido!"); st.rerun()

    # ── Códigos ───────────────────────────────────────────────────
    with tab2:
        cods = get_codigos(solo_activos=False)
        if cods:
            st.dataframe(pd.DataFrame([{
                "Código":   c["codigo"],    "Descrición": c["descripcion"],
                "Activo":   "✅" if c["activo"] else "❌",
                "Orde":     c["orden"],
            } for c in cods]), use_container_width=True, hide_index=True)

        eo = ["— Novo —"] + [f"{c['codigo']} — {c['descripcion']}" for c in cods]
        es = st.selectbox("Editar ou crear", eo, key="cod_es")
        ce = None if es.startswith("—") else cods[eo.index(es)-1]

        with st.form("cod_form"):
            c1, c2 = st.columns(2)
            codigo = c1.text_input("Código *", value=ce["codigo"] if ce else "")
            orden  = c2.number_input("Orde", value=int(ce["orden"]) if ce else 99, step=1)
            desc   = st.text_input("Descrición *", value=ce["descripcion"] if ce else "")
            act    = st.checkbox("Activo (visible en formularios)",
                                 value=bool(ce["activo"]) if ce else True)
            cs2, cd2 = st.columns([3, 1])
            sv = cs2.form_submit_button("💾 Gardar", type="primary", use_container_width=True)
            dl = cd2.form_submit_button("🗑️ Eliminar", use_container_width=True) if ce else False
            if sv:
                if not codigo.strip() or not desc.strip():
                    st.error("Código e descrición obrigatorios")
                else:
                    d = {"codigo": codigo.strip(), "descripcion": desc.strip(),
                         "activo": 1 if act else 0, "orden": int(orden)}
                    if ce: d["id"] = ce["id"]
                    save_codigo(d); st.success("Gardado ✓"); st.rerun()
            if dl and ce:
                delete_codigo(ce["id"]); st.success("Eliminado"); st.rerun()

    # ── Partidas ──────────────────────────────────────────────────
    with tab3:
        cursos = get_cursos()
        pcs    = get_partidas_config()
        if not cursos:
            st.warning("Primeiro crea un curso escolar na pestaña anterior")
            return

        # Filtro por curso
        cf    = st.selectbox("Filtrar por curso", ["Todos"] + [c["nome"] for c in cursos],
                             key="mp_cf")
        cid_f = next((c["id"] for c in cursos if c["nome"] == cf), None)
        pf    = [p for p in pcs if not cid_f or p["curso_id"] == cid_f]

        # Tabla resumen
        if pf:
            st.dataframe(pd.DataFrame([{
                "Curso":      p["curso_nome"],
                "Partida":    p["nome"],
                "Asignado €": p["importe_asignado"],
                "Notas":      p["notas"],
            } for p in pf]), use_container_width=True, hide_index=True)

        st.divider()

        # ── Editar / Crear partida ─────────────────────────────────
        opts_edit = ["— Nova partida —"] + [
            f"{p['curso_nome']} — {p['nome']}" for p in pf
        ]
        sel_edit = st.selectbox("Editar ou crear partida", opts_edit, key="part_edit_sel")
        pe = None if sel_edit.startswith("—") else pf[opts_edit.index(sel_edit) - 1]

        with st.form("part_form"):
            if pe:
                st.caption(f"Editando: **{pe['nome']}** · Curso: {pe['curso_nome']}")
            else:
                st.caption("Nova partida")

            c1, c2 = st.columns(2)

            # Curso — solo editable al crear, no al editar
            cur_names = [c["nome"] for c in cursos]
            if pe:
                # Al editar mostramos el curso pero no es editable
                c1.text_input("Curso", value=pe["curso_nome"], disabled=True)
                curso_sel = pe["curso_nome"]
            else:
                curso_sel = c1.selectbox("Curso *", cur_names, key="part_form_cur")

            nome_val = c2.text_input(
                "Nome da partida *",
                value=pe["nome"] if pe else "",
                placeholder="Ex: BECAS NEAE",
            )

            c3, c4 = st.columns(2)
            imp_val = c3.number_input(
                "Importe asignado €",
                min_value=0.0, step=0.01,
                value=float(pe["importe_asignado"]) if pe else 0.0,
            )
            notas_val = c4.text_input(
                "Notas",
                value=pe["notas"] if pe else "",
            )

            cs_b, cd_b = st.columns([3, 1])
            sv = cs_b.form_submit_button(
                "💾 Gardar", type="primary", use_container_width=True)
            dl = cd_b.form_submit_button(
                "🗑️ Eliminar", use_container_width=True) if pe else False

            if sv:
                if not nome_val.strip():
                    st.error("Nome obrigatorio")
                else:
                    cid_sel = next(
                        (c["id"] for c in cursos if c["nome"] == curso_sel), None
                    )
                    d = {
                        "curso_id":        cid_sel,
                        "nome":            nome_val.strip().upper(),
                        "importe_asignado": imp_val,
                        "notas":           notas_val,
                    }
                    if pe:
                        d["id"] = pe["id"]
                    save_partida(d)
                    st.success(f"✅ '{nome_val}' gardada!"); st.rerun()

            if dl and pe:
                delete_partida(pe["id"])
                st.success("🗑️ Eliminada"); st.rerun()
