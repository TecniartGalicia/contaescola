import io
import os
import json
import shutil
import sqlite3
import zipfile
from datetime import datetime, timedelta

import streamlit as st
import pandas as pd

from db import (get_diario, get_clientes, get_alumnos, get_cursos,
                get_partidas, get_partidas_resumen_global, get_becas_resumen,
                get_codigos, get_anos)
from db.connection import q, q1, mut, DB_PATH
from utils import excel_bytes


# ── Rutas de backup ────────────────────────────────────────────
BACKUP_DIR = os.path.join(os.path.dirname(DB_PATH), "backups")


def _ensure_backup_dir():
    os.makedirs(BACKUP_DIR, exist_ok=True)


def _crear_zip_backup() -> bytes:
    """Crea un ZIP con la BD + JSON de todas las tablas."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        # 1. Base de datos SQLite completa
        if os.path.exists(DB_PATH):
            zf.write(DB_PATH, "contaescola.db")

        # 2. JSON de cada tabla como respaldo extra
        tablas = ["configuracion", "anos", "cursos", "codigos", "clientes",
                  "alumnos_neae", "partidas_config", "saldos", "diario", "usuarios",
                  "partidas", "partidas_saldos", "partidas_saldos_curso",
                  "balances_comedor"]
        export_data = {}
        for tabla in tablas:
            try:
                rows = q(f"SELECT * FROM {tabla}")
                export_data[tabla] = rows
            except Exception:
                pass

        # 3. Plantillas (balance de comedor, etc.) — viven fóra do repo,
        #    así que o backup é a única copia ademais do propio volume
        plant_dir = os.path.join(os.path.dirname(DB_PATH), "plantillas")
        if os.path.isdir(plant_dir):
            for fn in os.listdir(plant_dir):
                ruta_p = os.path.join(plant_dir, fn)
                if os.path.isfile(ruta_p):
                    zf.write(ruta_p, f"plantillas/{fn}")

        meta = {
            "version":    "ContaEscola v6",
            "fecha":      datetime.now().isoformat(),
            "total_movs": len(export_data.get("diario", [])),
        }
        export_data["_meta"] = meta
        zf.writestr("datos.json", json.dumps(export_data, ensure_ascii=False, indent=2))

    buf.seek(0)
    return buf.read()


def _nombre_backup(prefijo: str = "backup") -> str:
    return f"{prefijo}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"


def _listar_backups_auto() -> list[str]:
    """Lista los ZIPs en el directorio de backups, ordenados por fecha desc."""
    if not os.path.exists(BACKUP_DIR):
        return []
    archivos = [f for f in os.listdir(BACKUP_DIR) if f.endswith(".zip")]
    return sorted(archivos, reverse=True)


def _guardar_backup_auto():
    """Guarda un backup automático en el servidor."""
    _ensure_backup_dir()
    nombre = _nombre_backup("auto")
    ruta   = os.path.join(BACKUP_DIR, nombre)
    with open(ruta, "wb") as f:
        f.write(_crear_zip_backup())
    # Guardar fecha del último backup automático
    mut("INSERT OR REPLACE INTO configuracion VALUES ('backup_ultimo', ?)",
        (datetime.now().isoformat(),))
    # Limpiar backups antiguos — conservar solo los últimos 10
    archivos = _listar_backups_auto()
    for viejo in archivos[10:]:
        try:
            os.remove(os.path.join(BACKUP_DIR, viejo))
        except Exception:
            pass
    return nombre


def check_backup_automatico():
    """
    Llamar al arranque de la app.
    Si toca hacer backup automático, lo ejecuta y notifica al usuario.
    """
    cfg_dias = q1("SELECT valor FROM configuracion WHERE clave='backup_dias'")
    if not cfg_dias or not cfg_dias["valor"]:
        return  # backup automático no configurado

    try:
        dias = int(cfg_dias["valor"])
    except ValueError:
        return

    cfg_ult = q1("SELECT valor FROM configuracion WHERE clave='backup_ultimo'")
    ultimo  = cfg_ult["valor"] if cfg_ult else None

    if ultimo:
        try:
            dt_ultimo = datetime.fromisoformat(ultimo)
            if datetime.now() - dt_ultimo < timedelta(days=dias):
                return  # no toca todavía
        except Exception:
            pass

    # Toca hacer backup
    try:
        nombre = _guardar_backup_auto()
        st.session_state["backup_auto_pendiente"] = nombre
    except Exception as e:
        st.session_state["backup_auto_error"] = str(e)


def render_backup_notificacion():
    """Mostrar notificación si se hizo un backup automático al arrancar."""
    if "backup_auto_pendiente" in st.session_state:
        nombre = st.session_state.pop("backup_auto_pendiente")
        ruta   = os.path.join(BACKUP_DIR, nombre)
        with st.sidebar:
            with st.expander("💾 Backup automático listo", expanded=True):
                st.success(f"Gardado en servidor: `{nombre}`")
                if os.path.exists(ruta):
                    with open(ruta, "rb") as f:
                        datos = f.read()
                    st.download_button(
                        "⬇️ Descargar agora",
                        data=datos,
                        file_name=nombre,
                        mime="application/zip",
                        key="dl_backup_auto_notif",
                    )

    if "backup_auto_error" in st.session_state:
        err = st.session_state.pop("backup_auto_error")
        with st.sidebar:
            st.warning(f"⚠️ Erro no backup automático: {err}")


# ── Vista principal ────────────────────────────────────────────
def render(ano: int) -> None:
    st.title("📤 Exportar datos")

    tab_exp, tab_bak = st.tabs(["📊 Exportar Excel", "💾 Backup & Restore"])

    # ── TAB 1: Exportar Excel (igual que antes) ────────────────
    with tab_exp:
        fm       = get_diario("func", ano)
        cm       = get_diario("com",  ano)
        clientes = get_clientes()
        becas    = get_becas_resumen(ano)

        c1, c2 = st.columns(2)

        with c1:
            st.subheader("📘 Funcionamento")
            if fm:
                df_f = pd.DataFrame([{
                    "Nº": m.get("num",""), "Data": m.get("data",""),
                    "Concepto": m.get("concepto",""), "Curso": m.get("curso_nome",""),
                    "Cliente": m.get("cliente_nome",""),
                    "Debe €":  m["importe"] if m["tipo"]=="G" else 0,
                    "Haber €": m["importe"] if m["tipo"]=="I" else 0,
                    "Código":  m.get("codigo",""), "Período": m.get("periodo",""),
                    "Partida": m.get("xustifica",""), "NEAE": m.get("alumno_neae",""),
                } for m in fm])
                st.download_button("⬇️ Excel Funcionamento",
                    data=excel_bytes([("FUNCIONAMENTO", df_f)]),
                    file_name=f"Funcionamento_{ano}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            else:
                st.info("Sen datos de Funcionamento")

        with c2:
            st.subheader("🍽️ Comedor")
            if cm:
                df_c = pd.DataFrame([{
                    "Nº": m.get("num",""), "Data": m.get("data",""),
                    "Concepto": m.get("concepto",""), "Curso": m.get("curso_nome",""),
                    "Cliente": m.get("cliente_nome",""),
                    "Debe €":  m["importe"] if m["tipo"]=="G" else 0,
                    "Haber €": m["importe"] if m["tipo"]=="I" else 0,
                    "Categoría": m.get("categoria",""),
                } for m in cm])
                st.download_button("⬇️ Excel Comedor",
                    data=excel_bytes([("COMEDOR", df_c)]),
                    file_name=f"Comedor_{ano}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            else:
                st.info("Sen datos de Comedor")

        c3, c4 = st.columns(2)

        with c3:
            st.subheader("📋 Partidas + Becas")
            # Partidas globais (o modelo vixente), non partidas_config (legado)
            rows_p = []
            for p in get_partidas():
                r = get_partidas_resumen_global(p["nome"])
                rows_p.append({
                    "Partida":       p["nome"],
                    "Saldo inicial": p["saldo_inicial"],
                    "Gastado":       r["debe"],
                    "Ingresado":     r["haber"],
                    "Balance":       round(p["saldo_inicial"] + r["haber"] - r["debe"], 2),
                })
            df_p = pd.DataFrame(rows_p)
            brows = []
            for alumno, d in becas.items():
                for m in d["movs"]:
                    brows.append({
                        "Alumno": alumno, "Data": m.get("data",""),
                        "Concepto": m.get("concepto",""),
                        "Debe €":  m["importe"] if m["tipo"]=="G" else 0,
                        "Haber €": m["importe"] if m["tipo"]=="I" else 0,
                    })
            df_b = (pd.DataFrame(brows) if brows
                    else pd.DataFrame(columns=["Alumno","Data","Concepto","Debe €","Haber €"]))
            st.download_button("⬇️ Excel Partidas + Becas",
                data=excel_bytes([("PARTIDAS", df_p), ("BECAS_NEAE", df_b)]),
                file_name=f"Partidas_{ano}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

        with c4:
            st.subheader("📦 Exportar todo")
            sheets = []
            if fm: sheets.append(("FUNCIONAMENTO", pd.DataFrame([{
                "Nº":m.get("num",""),"Data":m.get("data",""),
                "Concepto":m.get("concepto",""),
                "Debe":m["importe"] if m["tipo"]=="G" else 0,
                "Haber":m["importe"] if m["tipo"]=="I" else 0} for m in fm])))
            if cm: sheets.append(("COMEDOR", pd.DataFrame([{
                "Nº":m.get("num",""),"Data":m.get("data",""),
                "Concepto":m.get("concepto",""),
                "Debe":m["importe"] if m["tipo"]=="G" else 0,
                "Haber":m["importe"] if m["tipo"]=="I" else 0} for m in cm])))
            if clientes: sheets.append(("CLIENTES", pd.DataFrame([{
                "Nome":c["nome"],"Tipo":c["tipo"],"NIF":c["nif"],
                "Dir":c.get("direccion",""),"Tel":c["telefono"],
                "Email":c["email"]} for c in clientes])))
            if sheets:
                st.download_button("⬇️ Excel completo",
                    data=excel_bytes(sheets),
                    file_name=f"ContaEscola_{ano}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            else:
                st.info("Sen datos para exportar")

    # ── TAB 2: Backup & Restore ────────────────────────────────
    with tab_bak:

        sec1, sec2, sec3 = st.tabs([
            "💾 Backup manual",
            "🔁 Backup automático",
            "📥 Restaurar",
        ])

        # ── Backup manual ──────────────────────────────────────
        with sec1:
            st.markdown("""
            **Descarga un ZIP completo** con todos los datos de la aplicación.
            Contiene la base de datos SQLite y un JSON de todas las tablas.
            Guárdalo en un lugar seguro en tu ordenador.
            """)

            cfg_ult = q1("SELECT valor FROM configuracion WHERE clave='backup_ultimo'")
            if cfg_ult and cfg_ult["valor"]:
                try:
                    dt = datetime.fromisoformat(cfg_ult["valor"])
                    st.caption(f"Último backup automático: {dt.strftime('%d/%m/%Y %H:%M')}")
                except Exception:
                    pass

            n_movs = q1("SELECT COUNT(*) as n FROM diario")
            n_cl   = q1("SELECT COUNT(*) as n FROM clientes")
            c1m, c2m, c3m = st.columns(3)
            c1m.metric("Movementos", n_movs["n"] if n_movs else 0)
            c2m.metric("Clientes",   n_cl["n"]   if n_cl   else 0)
            c3m.metric("Tamaño BD",
                f"{os.path.getsize(DB_PATH)/1024:.0f} KB"
                if os.path.exists(DB_PATH) else "—")

            st.divider()

            if st.button("💾 Crear backup agora", type="primary",
                         use_container_width=True, key="btn_backup_manual"):
                with st.spinner("Creando backup..."):
                    datos  = _crear_zip_backup()
                    nombre = _nombre_backup("manual")
                st.success("✅ Backup creado — descárgao agora:")
                st.download_button(
                    f"⬇️ Descargar {nombre}",
                    data=datos,
                    file_name=nombre,
                    mime="application/zip",
                    key="dl_backup_manual",
                )

        # ── Backup automático ──────────────────────────────────
        with sec2:
            st.markdown("""
            **Configura backups automáticos** en el servidor.
            Al arrancar la app se comprueba si toca hacer backup y se guarda
            en el servidor. Recibirás una notificación con botón para descargarlo.
            """)

            cfg_dias = q1("SELECT valor FROM configuracion WHERE clave='backup_dias'")
            dias_act = int(cfg_dias["valor"]) if cfg_dias and cfg_dias["valor"] else 0

            with st.form("backup_auto_form"):
                dias = st.number_input(
                    "Frecuencia (días entre backups)",
                    min_value=0, max_value=30, value=dias_act, step=1,
                    help="0 = desactivado. 1 = diario. 7 = semanal."
                )
                sv = st.form_submit_button("💾 Gardar configuración",
                                            type="primary", use_container_width=True)
                if sv:
                    mut("INSERT OR REPLACE INTO configuracion VALUES ('backup_dias', ?)",
                        (str(int(dias)),))
                    if dias == 0:
                        st.success("✅ Backup automático desactivado")
                    else:
                        st.success(f"✅ Backup automático cada {dias} día(s)")
                    st.rerun()

            if dias_act > 0:
                st.info(f"🟢 Backup automático activado — cada **{dias_act} día(s)**")

                # Listar backups automáticos guardados en servidor
                backups = _listar_backups_auto()
                if backups:
                    st.markdown(f"**{len(backups)} backup(s) no servidor** (máx. 10):")
                    for b in backups[:5]:
                        ruta_b = os.path.join(BACKUP_DIR, b)
                        size   = os.path.getsize(ruta_b) // 1024
                        col_n, col_d = st.columns([3, 1])
                        col_n.caption(f"📦 {b} ({size} KB)")
                        with open(ruta_b, "rb") as f:
                            col_d.download_button("⬇️", data=f.read(),
                                file_name=b, mime="application/zip",
                                key=f"dl_auto_{b}")
                else:
                    st.caption("Aínda non hai backups automáticos gardados")
            else:
                st.warning("⚠️ Backup automático desactivado. Ponle un valor > 0 para activarlo.")

        # ── Restaurar ──────────────────────────────────────────
        with sec3:
            st.markdown("""
            **Restaura un backup** subiendo un ZIP manual o eligiendo uno
            de los backups automáticos guardados en el servidor.
            ⚠️ **Esto sobreescribirá TODOS los datos actuales.**
            """)

            rest_modo = st.radio(
                "Orixe do backup",
                ["📤 Subir arquivo ZIP", "📦 Backup automático do servidor"],
                key="rest_modo",
            )

            if rest_modo.startswith("📤"):
                # Restaurar desde ZIP subido
                uploaded = st.file_uploader(
                    "Sube o arquivo ZIP de backup",
                    type=["zip"], key="restore_upload",
                )
                if uploaded:
                    st.warning(f"⚠️ Vas a restaurar desde: **{uploaded.name}**")
                    st.error("Todos os datos actuais serán substituídos polo backup.")
                    confirmar = st.checkbox("Entendo que se perderán os datos actuais",
                                            key="rest_confirm1")
                    if confirmar and st.button("🔁 Restaurar agora",
                                               type="primary", key="btn_rest_upload"):
                        _restaurar_zip(io.BytesIO(uploaded.read()))

            else:
                # Restaurar desde backup automático del servidor
                backups = _listar_backups_auto()
                if not backups:
                    st.info("Non hai backups automáticos no servidor.")
                else:
                    sel_bak = st.selectbox(
                        "Selecciona o backup a restaurar",
                        backups, key="rest_sel_auto",
                    )
                    if sel_bak:
                        ruta_sel = os.path.join(BACKUP_DIR, sel_bak)
                        size     = os.path.getsize(ruta_sel) // 1024
                        st.caption(f"📦 {sel_bak} — {size} KB")
                        st.warning("⚠️ Todos os datos actuais serán substituídos.")
                        confirmar = st.checkbox("Entendo que se perderán os datos actuais",
                                                key="rest_confirm2")
                        if confirmar and st.button("🔁 Restaurar agora",
                                                   type="primary", key="btn_rest_auto"):
                            with open(ruta_sel, "rb") as f:
                                _restaurar_zip(io.BytesIO(f.read()))


def _validar_db(ruta: str) -> str | None:
    """Comproba que o ficheiro é unha BD SQLite íntegra co esquema de ContaEscola.
    Devolve None se é válida, ou o motivo do rexeitamento."""
    try:
        con = sqlite3.connect(f"file:{ruta}?mode=ro", uri=True)
        integridade = con.execute("PRAGMA integrity_check").fetchone()[0]
        ten_diario = con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='diario'"
        ).fetchone()
        con.close()
    except Exception as e:
        return f"non é unha base de datos SQLite lexible ({e})"
    if integridade != "ok":
        return f"a base de datos está corrupta (integrity_check: {integridade})"
    if not ten_diario:
        return "non contén a táboa 'diario' — non parece un backup de ContaEscola"
    return None


def _restaurar_zip(zip_buf: io.BytesIO):
    """Extrae el ZIP, VALIDA la BD y solo entonces la restaura."""
    tmp = DB_PATH + ".restore_tmp"
    restaurado = False
    try:
        with st.spinner("Restaurando backup..."):
            with zipfile.ZipFile(zip_buf, "r") as zf:
                nombres = zf.namelist()

                if "contaescola.db" not in nombres:
                    st.error("❌ Arquivo ZIP inválido: non contén contaescola.db")
                    return

                # 1. Extraer a un temporal e validar ANTES de tocar nada:
                #    escribir un ficheiro corrupto enriba do bo non lanza
                #    ningunha excepción, así que hai que comprobalo á man
                with open(tmp, "wb") as f:
                    f.write(zf.read("contaescola.db"))
                motivo = _validar_db(tmp)
                if motivo:
                    os.remove(tmp)
                    st.error(f"❌ Backup rexeitado: {motivo}. Non se cambiou nada.")
                    return

                # 2. Copia de seguridade da BD actual
                if os.path.exists(DB_PATH):
                    shutil.copy2(DB_PATH, DB_PATH + ".pre_restore")

                # 3. Substituír
                shutil.move(tmp, DB_PATH)

                # 4. Restaurar tamén as plantillas se veñen no ZIP
                for n in nombres:
                    if n.startswith("plantillas/") and not n.endswith("/"):
                        dest = os.path.join(os.path.dirname(DB_PATH), n)
                        os.makedirs(os.path.dirname(dest), exist_ok=True)
                        with open(dest, "wb") as f:
                            f.write(zf.read(n))
                restaurado = True

    except Exception as e:
        if os.path.exists(tmp):
            os.remove(tmp)
        st.error(f"❌ Erro ao restaurar: {e}")
        backup_prev = DB_PATH + ".pre_restore"
        if os.path.exists(backup_prev):
            shutil.copy2(backup_prev, DB_PATH)
            st.warning("BD anterior recuperada automáticamente")

    # Fóra do try: st.rerun() lanza unha excepción interna de Streamlit que o
    # except Exception atraparía — e desfaría a restauración co .pre_restore
    if restaurado:
        st.success("✅ Backup restaurado correctamente. A app reiniciarase.")
        st.session_state.clear()
        st.rerun()
