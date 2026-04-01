import re
import bcrypt
import streamlit as st
import pandas as pd

from db import (get_cursos, get_codigos, get_partidas,
                save_curso, delete_curso, save_codigo, delete_codigo,
                save_partida, delete_partida)
from db.connection import q, mut


def render() -> None:
    st.title("⚙️ Tablas Maestras")
    tab1, tab2, tab3, tab4 = st.tabs([
        "📅 Cursos Escolares",
        "🏷️ Códigos Contables",
        "📋 Partidas Finalistas",
        "👥 Usuarios",
    ])

    # ── Cursos ────────────────────────────────────────────────────
    with tab1:
        cursos = get_cursos()
        if cursos:
            st.dataframe(pd.DataFrame([{"Nome": c["nome"]} for c in cursos]),
                         use_container_width=True, hide_index=True)
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
                "Código": c["codigo"], "Descrición": c["descripcion"],
                "Activo": "✅" if c["activo"] else "❌", "Orde": c["orden"],
            } for c in cods]), use_container_width=True, hide_index=True)
        eo = ["— Novo —"] + [f"{c['codigo']} — {c['descripcion']}" for c in cods]
        es = st.selectbox("Editar ou crear", eo, key="cod_es")
        ce = None if es.startswith("—") else cods[eo.index(es)-1]
        with st.form("cod_form"):
            c1, c2 = st.columns(2)
            codigo = c1.text_input("Código *", value=ce["codigo"] if ce else "")
            orden  = c2.number_input("Orde", value=int(ce["orden"]) if ce else 99, step=1)
            desc   = st.text_input("Descrición *", value=ce["descripcion"] if ce else "")
            act    = st.checkbox("Activo", value=bool(ce["activo"]) if ce else True)
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

    # ── Partidas Finalistas (modelo global) ───────────────────────
    with tab3:
        st.markdown(
            '<div style="background:#dbeafe;border:1px solid #93c5fd;border-radius:8px;'
            'padding:8px 12px;font-size:12px;color:#1e3a5f;margin-bottom:12px">'
            'ℹ️ As partidas son <strong>globais</strong> — non están ligadas a un curso. '
            'Os saldos iniciais por ano xestiónanse en '
            '<strong>Partidas Finalistas → 💰 Saldos iniciais por ano</strong>.</div>',
            unsafe_allow_html=True,
        )

        partidas = get_partidas()
        if partidas:
            st.dataframe(pd.DataFrame([{
                "Partida": p["nome"],
                "Activa":  "✅" if p["activa"] else "❌",
                "Notas":   p["notas"],
            } for p in partidas]), use_container_width=True, hide_index=True)

        st.divider()

        opts_p = ["— Nova partida —"] + [p["nome"] for p in partidas]
        sel_p  = st.selectbox("Editar ou crear partida", opts_p, key="part_glob_sel")
        pe     = None if sel_p.startswith("—") else next(
            (p for p in partidas if p["nome"] == sel_p), None)

        with st.form("part_glob_form"):
            if pe:
                st.caption(f"Editando: **{pe['nome']}**")
            else:
                st.caption("Nova partida global")

            c1, c2 = st.columns(2)
            nome_val  = c1.text_input("Nome da partida *",
                value=pe["nome"] if pe else "", placeholder="Ex: PLAMBE")
            notas_val = c2.text_input("Notas", value=pe["notas"] if pe else "")
            activa_val = st.checkbox("Partida activa (visible no formulario)",
                                     value=bool(pe["activa"]) if pe else True)

            cs_b, cd_b = st.columns([3, 1])
            sv = cs_b.form_submit_button("💾 Gardar", type="primary", use_container_width=True)
            dl = cd_b.form_submit_button("🗑️ Eliminar", use_container_width=True) if pe else False

            if sv:
                if not nome_val.strip():
                    st.error("Nome obrigatorio")
                else:
                    d = {"nome": nome_val.strip().upper(),
                         "notas": notas_val,
                         "activa": activa_val}
                    if pe: d["id"] = pe["id"]
                    save_partida(d)
                    st.success(f"✅ '{nome_val}' gardada!"); st.rerun()
            if dl and pe:
                n = q("SELECT COUNT(*) as n FROM diario WHERE xustifica=?", (pe["nome"],))
                if n and n[0]["n"] > 0:
                    st.warning(f"⚠️ Esta partida ten {n[0]['n']} movementos asignados.")
                delete_partida(pe["id"])
                st.success("🗑️ Eliminada"); st.rerun()

    # ── Usuarios ──────────────────────────────────────────────────
    with tab4:
        usuarios = q("SELECT id, username, nome, activo, creado_en FROM usuarios ORDER BY username")
        if usuarios:
            st.dataframe(pd.DataFrame([{
                "Usuario": u["username"], "Nome": u["nome"],
                "Activo":  "✅" if u["activo"] else "❌",
                "Creado":  u["creado_en"][:10] if u["creado_en"] else "",
            } for u in usuarios]), use_container_width=True, hide_index=True)

        st.divider()
        opts_u = ["— Novo usuario —"] + [u["username"] for u in usuarios]
        sel_u  = st.selectbox("Editar ou crear usuario", opts_u, key="usr_sel")
        ue     = None if sel_u.startswith("—") else next(
            (u for u in usuarios if u["username"] == sel_u), None)

        with st.form("usr_form"):
            if ue: st.caption(f"Editando: **{ue['username']}**")
            else:  st.caption("Novo usuario")
            c1, c2 = st.columns(2)
            uname  = c1.text_input("Usuario *", value=ue["username"] if ue else "",
                                   disabled=bool(ue), placeholder="ex: maria")
            nome_u = c2.text_input("Nome completo", value=ue["nome"] if ue else "",
                                   placeholder="ex: María García")
            c3, c4 = st.columns(2)
            pwd1 = c3.text_input("Contrasinal *" if not ue else
                                  "Nova contrasinal (baleiro = non cambiar)",
                                  type="password", placeholder="••••••••")
            pwd2 = c4.text_input("Repetir contrasinal", type="password",
                                  placeholder="••••••••")
            activo_u = st.checkbox("Usuario activo", value=bool(ue["activo"]) if ue else True)
            cs_u, cd_u = st.columns([3, 1])
            sv_u = cs_u.form_submit_button("💾 Gardar", type="primary", use_container_width=True)
            dl_u = cd_u.form_submit_button("🗑️ Eliminar", use_container_width=True) if ue else False

            if sv_u:
                if not ue and not uname.strip():
                    st.error("Nome obrigatorio"); st.stop()
                if not ue and not pwd1:
                    st.error("Contrasinal obrigatoria"); st.stop()
                if pwd1 and pwd1 != pwd2:
                    st.error("As contrasinais non coinciden"); st.stop()
                if pwd1 and len(pwd1) < 4:
                    st.error("Mínimo 4 caracteres"); st.stop()
                if ue:
                    if pwd1:
                        ph = bcrypt.hashpw(pwd1.encode(), bcrypt.gensalt(12)).decode()
                        mut("UPDATE usuarios SET nome=?,password=?,activo=? WHERE id=?",
                            (nome_u, ph, 1 if activo_u else 0, ue["id"]))
                    else:
                        mut("UPDATE usuarios SET nome=?,activo=? WHERE id=?",
                            (nome_u, 1 if activo_u else 0, ue["id"]))
                    st.success(f"✅ '{ue['username']}' actualizado")
                else:
                    if q("SELECT id FROM usuarios WHERE username=?", (uname.lower().strip(),)):
                        st.error(f"O usuario '{uname}' xa existe")
                    else:
                        ph = bcrypt.hashpw(pwd1.encode(), bcrypt.gensalt(12)).decode()
                        mut("INSERT INTO usuarios (username,nome,password,activo) VALUES (?,?,?,1)",
                            (uname.lower().strip(), nome_u, ph))
                        st.success(f"✅ '{uname}' creado!")
                st.rerun()
            if dl_u and ue:
                if ue["username"] == st.session_state.get("username", ""):
                    st.error("Non podes eliminar o teu propio usuario")
                elif len(usuarios) <= 1:
                    st.error("Debe existir polo menos un usuario")
                else:
                    mut("DELETE FROM usuarios WHERE id=?", (ue["id"],))
                    st.success("🗑️ Eliminado"); st.rerun()
