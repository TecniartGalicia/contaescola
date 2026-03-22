"""
utils/formatters.py
Funciones puras de formato y cálculo. Sin dependencias de Streamlit.
"""
from datetime import datetime


def fmt(n: float | None) -> str:
    """Formatea número como moneda: 1.234,56 €"""
    if n is None:
        return "—"
    return f"{n:,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")


def fmt_num(n: float | None) -> str:
    """Formatea número sin símbolo de moneda."""
    if n is None:
        return "—"
    return f"{n:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def fmtD(d: str | None) -> str:
    """Convierte fecha ISO (2026-03-01) a formato legible (01/03/2026)."""
    if not d:
        return ""
    try:
        return datetime.strptime(str(d), "%Y-%m-%d").strftime("%d/%m/%Y")
    except ValueError:
        return str(d)


def fecha_to_trimestre(fecha: str) -> str:
    """Calcula el trimestre automáticamente a partir de la fecha ISO."""
    try:
        mes = datetime.strptime(str(fecha), "%Y-%m-%d").month
        if mes <= 3:  return "1º TRIMESTRE"
        if mes <= 6:  return "2º TRIMESTRE"
        if mes <= 9:  return "3º TRIMESTRE"
        return "4º TRIMESTRE"
    except ValueError:
        return "1º TRIMESTRE"


def sum_tipo(movs: list[dict], tipo: str) -> float:
    """Suma los importes de un tipo ('G' o 'I') de una lista de movimientos."""
    return sum(m["importe"] for m in movs if m["tipo"] == tipo)
