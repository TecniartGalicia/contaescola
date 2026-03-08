"""
components/form_movemento.py
Formulario de alta/edición de movimientos del Diario.
Compartido por Diario Funcionamento y Diario Comedor.
"""
from datetime import date, datetime

import streamlit as st

from db import (
    get_cursos, get_codigos, get_clientes, get_alumnos,
    get_partidas_config, get_ano_activo,
    save_diario, delete_diario,
)
from db.schema import PERIODOS, CATEGORIAS_COM
from utils import fecha_to_trimestre


def form_movemento(
    area: str,
    mov: dict | None = None,
    key_prefix: str = "mov",
) -> bool:
    """
    Renderiza el formulario de movimiento.

    Args:
        area:       'func' o 'com'
        mov:        dict con el movimiento a editar (None = nuevo)
        key_prefix: prefijo para las keys de Streamlit

    Returns:
        True si se guardó o eliminó (señal para st.rerun())
    """
    cursos   = get_cursos()
    codigos  = get_codigos()
    clientes = get_clientes()
    alumnos  = get_alumnos()
    ano_act  = get_ano_activo()

    if not cursos:
        st.warning("⚠️ Non hai cursos creados. Ve a ⚙️ Tablas Maestras.")
        return False

    cur_names = [c["nome"] for c in cursos]

    # ── Paso 1: Curso (fuera del form → reactivo) ─────────────────
    st.markdown("**🎓 Paso 1 — Curso Escolar** *(actualiza as partidas dispoñibles)*")
    cur_def = next(
        (i for i, c in enumerate(cursos) if mov and c["id"] == mov.get("curso_id")), 0
    )
    cur_pre = st.selectbox(
        "Curso escolar *", cur_names,
        index=cur_def, key=f"{key_prefix}_pre_cur",
    )
    cur_id_v = next((c["id"] for c in cursos if c["nome"] == cur_pre), None)

    pcs = get_partidas_config(cur_id_v) if cur_id_v else []
    if pcs:
        st.caption(f"✅ {len(pcs)} partidas dispoñibles para '{cur_pre}'")
    else:
        st.caption(f"ℹ️ Sen partidas en '{cur_pre}' — engádeas en ⚙️ Tablas Maestras")

    # ── Paso 2: Datos del movimiento (dentro del form) ────────────
    st.markdown("**📝 Paso 2 — Datos do movemento**")
    with st.form(key=f"{key_prefix}_form"):
        tipo = st.radio(
            "Tipo *",
            ["G — Gasto / Debe", "I — Ingreso / Haber"],
            index=0 if (mov is None or mov.get("tipo", "G") == "G") else 1,
            horizontal=True, key=f"{key_prefix}_tipo",
        )
        tipo_v = "G" if tipo.startswith("G") else "I"

        c1, c2 = st.columns(2)
        data_v = c1.date_input(
            "📅 Data *",
            value=datetime.strptime(mov["data"], "%Y-%m-%d").date()
                  if mov and mov.get("data") else date.today(),
            key=f"{key_prefix}_data",
        )
        imp_v = c2.number_input(
            "💶 Importe (€) *", min_value=0.01, step=0.01,
            value=float(mov["importe"]) if mov and mov.get("importe") else 0.01,
            key=f"{key_prefix}_imp",
        )

        con_v = st.text_input(
            "📝 Concepto *",
            value=mov.get("concepto", "") if mov else "",
            key=f"{key_prefix}_con",
        )

        # Partidas filtradas por curso (cargadas arriba, fuera del form)
        p_opts = ["— Sen partida —"] + [p["nome"] for p in pcs]
        p_def  = 0
        if mov and mov.get("xustifica") and mov["xustifica"] in p_opts:
            p_def = p_opts.index(mov["xustifica"])
        xust_sel = st.selectbox(
            f"📋 Partida Finalista ({len(pcs)} dispoñibles para '{cur_pre}')",
            p_opts, index=p_def, key=f"{key_prefix}_xust",
        )
        xust_v = "" if xust_sel.startswith("—") else xust_sel

        c3, c4 = st.columns(2)

        if area == "func":
            cod_opts = ["— Sen código —"] + [
                f"{c['codigo']} — {c['descripcion']}" for c in codigos
            ]
            cod_def = 0
            if mov and mov.get("codigo"):
                m = [i+1 for i, c in enumerate(codigos) if c["codigo"] == mov["codigo"]]
                if m: cod_def = m[0]
            cod_sel = c3.selectbox("🏷️ Código contable", cod_opts,
                                   index=cod_def, key=f"{key_prefix}_cod")
            cod_v = "" if cod_sel.startswith("—") else cod_sel.split(" — ")[0]
            cod_d = "" if cod_sel.startswith("—") else " — ".join(cod_sel.split(" — ")[1:])
            cat_v = ""
        else:
            cat_def = (CATEGORIAS_COM.index(mov["categoria"])
                       if mov and mov.get("categoria") in CATEGORIAS_COM else 0)
            cat_v = c3.selectbox("🗂️ Categoría", CATEGORIAS_COM,
                                  index=cat_def, key=f"{key_prefix}_cat")
            cod_v = ""; cod_d = ""

        cl_opts = ["— Sen vincular —"] + [
            f"{c['nome']}" + (f" ({c['nif']})" if c["nif"] else "")
            for c in clientes
        ]
        cl_def = 0
        if mov and mov.get("cliente_id"):
            idx = next((i+1 for i, c in enumerate(clientes)
                        if c["id"] == mov["cliente_id"]), 0)
            cl_def = idx
        cl_sel = c4.selectbox("🏢 Cliente/Proveedor", cl_opts,
                               index=cl_def, key=f"{key_prefix}_cl")
        cl_id_v = (None if cl_sel.startswith("—")
                   else clientes[cl_opts.index(cl_sel)-1]["id"])

        al_opts = ["— Sen alumno NEAE —"] + [a["nome"] for a in alumnos]
        al_def  = 0
        if mov and mov.get("alumno_neae") and mov["alumno_neae"] in al_opts:
            al_def = al_opts.index(mov["alumno_neae"])
        al_sel = st.selectbox("👤 Alumno NEAE", al_opts,
                               index=al_def, key=f"{key_prefix}_al")
        al_v = "" if al_sel.startswith("—") else al_sel

        not_v = st.text_area("📌 Notas",
                             value=mov.get("notas", "") if mov else "",
                             key=f"{key_prefix}_not", height=55)

        cs, cd = st.columns([3, 1])
        submitted = cs.form_submit_button(
            "💾 Gardar", use_container_width=True, type="primary")
        del_btn = (cd.form_submit_button("🗑️ Eliminar", use_container_width=True)
                   if mov else False)

        if submitted:
            if not con_v.strip():
                st.error("Concepto obrigatorio"); return False
            periodo_auto = fecha_to_trimestre(str(data_v))
            payload = {
                "area": area, "ano": ano_act, "curso_id": cur_id_v,
                "tipo": tipo_v, "data": str(data_v), "importe": imp_v,
                "concepto": con_v.strip().upper(), "codigo": cod_v,
                "cod_desc": cod_d, "periodo": periodo_auto,
                "notas": not_v, "categoria": cat_v,
                "xustifica": xust_v, "alumno_neae": al_v,
                "cliente_id": cl_id_v,
            }
            if mov and mov.get("id"):
                payload["id"] = mov["id"]
            save_diario(payload)
            st.success(f"✅ Gardado! Período: **{periodo_auto}**")
            return True

        if del_btn and mov and mov.get("id"):
            delete_diario(mov["id"])
            st.success("🗑️ Eliminado")
            return True

    return False
