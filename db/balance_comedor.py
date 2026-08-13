"""
db/balance_comedor.py
Cálculo do "Balance de comedores escolares" a partir dun rango de asentos.

O período NON se corta por datas senón polo número de asento do diario: os
asentos numéranse por orde de rexistro, non cronoloxicamente, e o corte real
que fai o centro é "do asento X ao asento Y".
"""
import json

from .connection import q, q1, mut
from .queries import get_saldo

TRIMESTRES = ["1º TRIM", "2º TRIM", "3º TRIM", "4º TRIM"]
PERIODOS_SUXERIDOS = {
    "1º TRIM": "outubro/decembro",
    "2º TRIM": "xaneiro/marzo",
    "3º TRIM": "abril/xuño",
    "4º TRIM": "xullo/setembro",
}


def get_movs_rango(ano: int, desde: int, ata: int) -> list[dict]:
    """Asentos de comedor do rango, en orde."""
    return q("""SELECT d.*, cl.nome AS cliente_nome
                FROM diario d
                LEFT JOIN clientes cl ON d.cliente_id = cl.id
                WHERE d.area='com' AND d.ano=? AND d.num BETWEEN ? AND ?
                ORDER BY d.num""", (ano, desde, ata))


def get_rango_dispoñible(ano: int) -> tuple[int, int]:
    r = q1("SELECT MIN(num) mi, MAX(num) ma FROM diario WHERE area='com' AND ano=?", (ano,))
    return (r["mi"] or 0, r["ma"] or 0) if r else (0, 0)


def calcular_saldo_inicial(ano: int, desde: int) -> float:
    """
    Saldo da conta no momento de abrir o período: saldo de apertura do exercicio
    máis todo o movido nos asentos anteriores ao primeiro do rango.

    Comprobado cos tres balances asinados do curso 2025/2026:
      1º trim -> 57.479,82 + asentos 1..131 = 62.153,67
      2º trim -> 50.608,14 + nada           = 50.608,14
      3º trim -> 50.608,14 + asentos 1..52  = 56.728,41
    """
    base = get_saldo(ano, "com")
    r = q1("""SELECT COALESCE(SUM(CASE WHEN tipo='I' THEN importe ELSE 0 END),0) ing,
                     COALESCE(SUM(CASE WHEN tipo='G' THEN importe ELSE 0 END),0) gas
              FROM diario WHERE area='com' AND ano=? AND num < ?""", (ano, desde))
    return round(base + (r["ing"] or 0) - (r["gas"] or 0), 2)


def calcular_balance(ano: int, desde: int, ata: int,
                     saldo_inicial: float | None = None,
                     existencias: float = 0.0) -> dict:
    """Devolve as cifras do impreso para o rango indicado."""
    from utils.docx_balance import CATEGORIA_A_FILA, FILAS_GASTO

    movs = get_movs_rango(ano, desde, ata)
    if saldo_inicial is None:
        saldo_inicial = calcular_saldo_inicial(ano, desde)

    gastos = {f: 0.0 for f in FILAS_GASTO}
    subvencions = 0.0
    outros_ingresos = 0.0
    sen_clasificar: list[dict] = []

    for m in movs:
        cat = (m.get("categoria") or "").strip()
        if m["tipo"] == "I":
            if cat == "CONSELLERÍA":
                subvencions += m["importe"]
            else:
                outros_ingresos += m["importe"]
                if cat not in ("OUTROS", ""):
                    sen_clasificar.append(m)
        else:
            fila = CATEGORIA_A_FILA.get(cat)
            if fila is None:
                fila = "OUTROS"
                sen_clasificar.append(m)
            gastos[fila] = round(gastos.get(fila, 0.0) + m["importe"], 2)

    total_ingresos = round(saldo_inicial + subvencions + outros_ingresos + (existencias or 0), 2)
    total_gastos = round(sum(gastos.values()), 2)
    return {
        "ano": ano, "desde": desde, "ata": ata, "movs": movs,
        "saldo_inicial": round(saldo_inicial, 2),
        "subvencions": round(subvencions, 2),
        "outros_ingresos": round(outros_ingresos, 2),
        "existencias": round(existencias or 0, 2),
        "total_ingresos": total_ingresos,
        "gastos": {k: v for k, v in gastos.items()},
        "total_gastos": total_gastos,
        "remanente": round(total_ingresos - total_gastos, 2),
        "sen_clasificar": sen_clasificar,
    }


# ── Informes emitidos ────────────────────────────────────────────
def get_balances(curso_id: int | None = None) -> list[dict]:
    sql = """SELECT b.*, c.nome AS curso_nome FROM balances_comedor b
             JOIN cursos c ON b.curso_id = c.id"""
    if curso_id:
        return q(sql + " WHERE b.curso_id=? ORDER BY b.trimestre", (curso_id,))
    return q(sql + " ORDER BY c.nome DESC, b.trimestre")


def get_balance(curso_id: int, trimestre: str) -> dict | None:
    return q1("SELECT * FROM balances_comedor WHERE curso_id=? AND trimestre=?",
              (curso_id, trimestre))


def ultimo_asento_declarado(ano: int) -> int | None:
    """
    Último asento dese exercicio xa incluído nun balance emitido.
    A numeración dos asentos é por exercicio (area+ano), non por curso escolar,
    así que aquí non entra o curso.
    """
    r = q1("""SELECT MAX(num_ata) m FROM balances_comedor
              WHERE ano=? AND num_ata IS NOT NULL""", (ano,))
    return r["m"] if r and r["m"] else None


def save_balance(d: dict, snapshot: dict) -> int:
    """Garda o informe emitido cunha foto das cifras, para que reemitilo dea o mesmo papel.

    creado_en consérvase da primeira emisión: o INSERT OR REPLACE reaplicaría o
    default datetime('now') e o histórico mostraría a data da última regeneración.
    """
    return mut("""INSERT OR REPLACE INTO balances_comedor
        (id, curso_id, trimestre, periodo_txt, ano, num_desde, num_ata,
         dias_funcionamento, saldo_inicial, existencias, outros_ingresos_txt,
         outros_gastos_txt, data_sinatura, snapshot_json, creado_en)
        VALUES ((SELECT id FROM balances_comedor WHERE curso_id=? AND trimestre=?),
                ?,?,?,?,?,?,?,?,?,?,?,?,?,
                COALESCE((SELECT creado_en FROM balances_comedor
                          WHERE curso_id=? AND trimestre=?), datetime('now')))""",
        (d["curso_id"], d["trimestre"],
         d["curso_id"], d["trimestre"], d.get("periodo_txt", ""), d["ano"],
         d["num_desde"], d["num_ata"], d.get("dias_funcionamento", 0),
         d.get("saldo_inicial", 0), d.get("existencias", 0),
         d.get("outros_ingresos_txt", ""), d.get("outros_gastos_txt", ""),
         d.get("data_sinatura", ""),
         json.dumps(snapshot, ensure_ascii=False, default=str),
         d["curso_id"], d["trimestre"]))


def delete_balance(id: int) -> None:
    mut("DELETE FROM balances_comedor WHERE id=?", (id,))
