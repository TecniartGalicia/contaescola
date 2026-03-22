"""
db/connection.py
Punto único de conexión a la base de datos.
Para cambiar a PostgreSQL en el futuro: solo modificar get_con().
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "contaescola.db")


def get_con() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    con.execute("PRAGMA journal_mode = WAL")   # mejor concurrencia
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
