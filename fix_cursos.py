"""
fix_cursos.py — Corrige el curso escolar en contaescola.db

Regla:
  - Movimientos año 2025 con fecha 01/01 - 30/06 → curso 2024-2025  (ya correcto)
  - Movimientos año 2025 con fecha 01/07 - 31/12 → curso 2025-2026  (a corregir)
  - Movimientos año 2025 con fecha 2026 (nums 220-225) → curso 2025-2026 (a corregir)

Aplica a AMBAS áreas: func y com.

Ejecutar DENTRO de la carpeta contaescola_v6:
    python fix_cursos.py
"""
import sqlite3, os, sys

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'contaescola.db')

def main():
    if not os.path.exists(DB_PATH):
        print(f"❌ BD non atopada: {DB_PATH}"); sys.exit(1)

    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")

    print("=" * 55)
    print("  FIX CURSOS ESCOLARES — ContaEscola")
    print("=" * 55)

    # Obtener IDs de los cursos
    cur_2425 = con.execute("SELECT id FROM cursos WHERE nome='2024-2025'").fetchone()
    cur_2526 = con.execute("SELECT id FROM cursos WHERE nome='2025-2026'").fetchone()

    if not cur_2425:
        print("❌ Curso '2024-2025' non atopado na BD"); sys.exit(1)
    if not cur_2526:
        print("❌ Curso '2025-2026' non atopado na BD"); sys.exit(1)

    id_2425 = cur_2425['id']
    id_2526 = cur_2526['id']
    print(f"\n  Curso 2024-2025 → id={id_2425}")
    print(f"  Curso 2025-2026 → id={id_2526}")

    # ── Situación actual ───────────────────────────────────────
    print("\n  Estado ANTES da corrección:")
    for area in ('func', 'com'):
        tots = con.execute("""
            SELECT c.nome, COUNT(*) as n
            FROM diario d LEFT JOIN cursos c ON d.curso_id = c.id
            WHERE d.ano = 2025 AND d.area = ?
            GROUP BY c.nome ORDER BY c.nome
        """, (area,)).fetchall()
        for t in tots:
            print(f"    {area} | curso='{t['nome'] or 'SEN CURSO'}' → {t['n']} movs")

    # ── CORRECCIÓN 1: año 2025, fecha >= 01/07/2025 ────────────
    # Incluye también los nums 220-225 que tienen fecha 2026
    # pero pertenecen al ejercicio contable 2025 (ano=2025 en la BD)
    print("\n  Aplicando corrección...")

    r1 = con.execute("""
        UPDATE diario
        SET curso_id = ?
        WHERE ano = 2025
          AND data >= '2025-07-01'
          AND (curso_id = ? OR curso_id IS NULL)
    """, (id_2526, id_2425))
    print(f"  ✅ Movementos 01/07-31/12/2025 → 2025-2026: {r1.rowcount} actualizados")

    # ── CORRECCIÓN 2: año 2025, fecha en 2026 (nums 220-225) ───
    # Estos movimientos tienen ano=2025 (ejercicio contable 2025)
    # pero su fecha real es enero/febrero 2026
    r2 = con.execute("""
        UPDATE diario
        SET curso_id = ?
        WHERE ano = 2025
          AND data >= '2026-01-01'
          AND (curso_id = ? OR curso_id IS NULL)
    """, (id_2526, id_2425))
    print(f"  ✅ Movementos xan-feb 2026 (exercicio 2025) → 2025-2026: {r2.rowcount} actualizados")

    # ── CORRECCIÓN 3: por si hay alguno de año 2026 con curso 2024-2025 ──
    r3 = con.execute("""
        UPDATE diario
        SET curso_id = ?
        WHERE ano = 2026
          AND (curso_id = ? OR curso_id IS NULL)
    """, (id_2526, id_2425))
    if r3.rowcount > 0:
        print(f"  ✅ Movementos ano=2026 con curso erróneo → 2025-2026: {r3.rowcount} actualizados")

    con.commit()

    # ── Verificación final ─────────────────────────────────────
    print("\n  Estado DESPOIS da corrección:")
    for area in ('func', 'com'):
        tots = con.execute("""
            SELECT c.nome, COUNT(*) as n,
                   SUM(CASE WHEN d.tipo='G' THEN d.importe ELSE 0 END) as debe,
                   SUM(CASE WHEN d.tipo='I' THEN d.importe ELSE 0 END) as haber
            FROM diario d LEFT JOIN cursos c ON d.curso_id = c.id
            WHERE d.ano = 2025 AND d.area = ?
            GROUP BY c.nome ORDER BY c.nome
        """, (area,)).fetchall()
        for t in tots:
            d = f"{t['debe']:,.2f}".replace(',','X').replace('.',',').replace('X','.')
            h = f"{t['haber']:,.2f}".replace(',','X').replace('.',',').replace('X','.')
            print(f"    {area} | '{t['nome'] or 'SEN CURSO'}' → {t['n']} movs | D:{d} H:{h}")

    total_corr = r1.rowcount + r2.rowcount + r3.rowcount
    con.close()

    print()
    print("=" * 55)
    print(f"  ✅  CORRECCIÓN COMPLETADA")
    print("=" * 55)
    print(f"  Total movementos corrixidos: {total_corr}")
    print()
    print("  Regra aplicada (func + com):")
    print("  01/01 - 30/06/2025 → curso 2024-2025  (sen cambio)")
    print("  01/07/2025 en diante → curso 2025-2026 (corrixido)")
    print("=" * 55)

if __name__ == '__main__':
    main()
