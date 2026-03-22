"""
utils/excel.py
Generación de archivos Excel con xlsxwriter.
"""
import io
import pandas as pd


def excel_bytes(sheets: list[tuple[str, pd.DataFrame]]) -> bytes:
    """
    Recibe una lista de (nombre_hoja, DataFrame) y devuelve bytes de Excel.
    Uso: st.download_button(..., data=excel_bytes([("HOJA1", df)]))
    """
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="xlsxwriter") as writer:
        for sheet_name, df in sheets:
            df.to_excel(writer, sheet_name=sheet_name[:31], index=False)
    return buf.getvalue()
