"""
db/connection.py
Punto único de conexión a la base de datos.

Ruta de la BD:
  - En producción (Coolify): variable de entorno DB_PATH → /data/contaescola.db
  - En local: directorio raíz del proyecto
"""
import sqlite3
import os

_DEFAULT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "contaescola.db"
)
# ★ Usa DB_PATH del entorno si existe, si no la ruta local
DB_PATH = os.environ.get("DB_PATH", _DEFAULT_PATH)

# Asegurar que el directorio existe (crítico para /data en Coolify)
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)


def get_con() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    con.execute("PRAGMA journal_mode = WAL")
    return con


def q(sql: str, params: tuple = ()) -> list[dict]:
    """SELECT → lista de dicts"""
    con = get_con()
    rows = [dict(r) for r in con.execute(sql, params).fetchall()]
    con.close()
    return rows


def q1(sql: str, params: tuple = ()) -> dict | None:
    """SELECT → primer resultado o None"""
    con = get_con()
    r = con.execute(sql, params).fetchone()
    con.close()
    return dict(r) if r else None


def mut(sql: str, params: tuple = ()) -> int:
    """INSERT / UPDATE / DELETE → lastrowid"""
    con = get_con()
    cur = con.execute(sql, params)
    con.commit()
    lastrowid = cur.lastrowid
    con.close()
    return lastrowid
