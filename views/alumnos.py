import streamlit as st
import pandas as pd

from db import get_alumnos, get_cursos, save_alumno, delete_alumno


def render() -> None:
    st.title("👤 Alumnos NEAE")
    st.markdown(
        '<div style="background:#ffedd5;border:1px solid #fed7aa;border-radius:8px;'
        'padding:10px 14px;font-size:13px;color:#7c2d12;margin-bottom:12px">'
        'Asigna o <strong>curso escolar</strong> ao alumno para filtrar correctamente as becas. '
        'Os gastos vincúlanse no Diario seleccionando o alumno no campo correspondente.</div>',
        unsafe_allow_html=True,
    )

    alumnos = get_alumnos()
    cursos  = get_cursos()
    tab1, tab2 = st.tabs(["📋 Lista", "➕ Novo / Editar"])

    with tab1:
        if alumnos:
            df = pd.DataFrame([{
                "Nome":          a["nome"],
                "Curso":         a.get("curso_nome","—"),
                "Curso ingreso": a["curso_ingreso"],
                "Notas":         a["notas"],
            } for a in alumnos])
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("Non hai alumnos NEAE rexistrados")

    with tab2:
        opts = ["— Novo —"] + [a["nome"] for a in alumnos]
        sel  = st.selectbox("Editar ou crear", opts, key="al_es")
        ae   = None if sel.startswith("—") else alumnos[opts.index(sel)-1]

        with st.form("al_form"):
            nome = st.text_input("Nome *", value=ae["nome"] if ae else "")

            c1, c2 = st.columns(2)
            cur_opts = ["— Sen curso asignado —"] + [c["nome"] for c in cursos]
            cur_def  = 0
            if ae and ae.get("curso_id"):
                idx = next((i+1 for i, c in enumerate(cursos)
                             if c["id"] == ae["curso_id"]), 0)
                cur_def = idx
            cur_al = c1.selectbox(
                "Curso escolar do alumno", cur_opts, index=cur_def,
                help="Úsase para filtrar o alumno na páxina de Becas NEAE",
            )
            ci = c2.text_input(
                "Curso de ingreso (opcional)",
                value=ae["curso_ingreso"] if ae else "",
                placeholder="Ex: 2023-2024",
            )
            notas = st.text_area("Notas / Tipo de necesidade",
                                 value=ae["notas"] if ae else "", height=70)

            cs, cd = st.columns([3, 1])
            sv = cs.form_submit_button("💾 Gardar", type="primary", use_container_width=True)
            dl = cd.form_submit_button("🗑️ Eliminar", use_container_width=True) if ae else False

            if sv:
                if not nome.strip():
                    st.error("Nome obrigatorio")
                else:
                    cid_al = (None if cur_al.startswith("—")
                              else next((c["id"] for c in cursos if c["nome"]==cur_al), None))
                    d = {"nome": nome.strip().upper(), "curso_id": cid_al,
                         "curso_ingreso": ci, "notas": notas}
                    if ae: d["id"] = ae["id"]
                    save_alumno(d); st.success("Gardado ✓"); st.rerun()
            if dl and ae:
                delete_alumno(ae["id"]); st.success("Eliminado"); st.rerun()
