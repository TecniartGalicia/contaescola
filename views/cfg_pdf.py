import base64
import streamlit as st

from db import get_cfg, set_cfg


def render() -> None:
    st.title("🖨️ Configuración PDF e Informes")
    st.markdown(
        '<div style="background:#dbeafe;border:1px solid #93c5fd;border-radius:8px;'
        'padding:10px 14px;font-size:13px;color:#1e3a5f;margin-bottom:12px">'
        'ℹ️ Esta configuración aplícase a <strong>todos</strong> os PDFs xerados.</div>',
        unsafe_allow_html=True,
    )

    col1, col2 = st.columns([3, 2])

    with col1:
        with st.form("cfg_form"):
            st.subheader("🏫 Datos do centro")
            nome  = st.text_input("Nome do centro",    value=get_cfg("centro_nome"),
                                  placeholder="C.E.I.P. ...")
            direc = st.text_input("Enderezo completo", value=get_cfg("centro_direccion"),
                                  placeholder="Rúa ..., Nº, CP Localidade")
            nif   = st.text_input("NIF / CIF",         value=get_cfg("centro_nif"),
                                  placeholder="Q1234567A")
            st.subheader("📄 Pés de páxina")
            f1 = st.text_input("Pé 1", value=get_cfg("footer1"),
                               placeholder="Texto principal do pé")
            f2 = st.text_input("Pé 2 (opcional)", value=get_cfg("footer2"),
                               placeholder="Texto secundario")
            if st.form_submit_button("💾 Gardar configuración",
                                     type="primary", use_container_width=True):
                for k, v in [("centro_nome", nome), ("centro_direccion", direc),
                              ("centro_nif", nif), ("footer1", f1), ("footer2", f2)]:
                    set_cfg(k, v)
                st.success("✅ Configuración gardada!")
                st.rerun()

    with col2:
        st.subheader("🖼️ Logo do centro")
        logo_b64 = get_cfg("logo_base64", "")
        if logo_b64:
            try:
                st.image(base64.b64decode(logo_b64), width=200, caption="Logo actual")
                if st.button("🗑️ Eliminar logo"):
                    set_cfg("logo_base64", ""); st.rerun()
            except Exception:
                st.warning("Logo corrupto — sube un novo")
        else:
            st.info("Sen logo configurado")

        up = st.file_uploader("Subir logo PNG/JPG (máx 2MB)",
                              type=["png","jpg","jpeg"])
        if up:
            if up.size > 2 * 1024 * 1024:
                st.error("O arquivo é demasiado grande (máx 2MB)")
            else:
                set_cfg("logo_base64", base64.b64encode(up.read()).decode())
                st.success("✅ Logo gardado!"); st.rerun()

        st.divider()
        st.subheader("🔍 Vista previa")
        for k, label in [("centro_nome","Nome"), ("centro_direccion","Dirección"),
                          ("centro_nif","NIF"), ("footer1","Pé 1"), ("footer2","Pé 2")]:
            st.caption(f"**{label}:** {get_cfg(k) or '—'}")

        st.divider()
        st.subheader("📦 Estado reportlab")
        try:
            import reportlab
            st.success(f"✅ reportlab {reportlab.Version} instalado")
        except ImportError:
            st.error("❌ reportlab non instalado")
            st.code("pip install reportlab")
