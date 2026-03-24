"""
db/mutations.py
Todas las operaciones de escritura sobre la base de datos.
"""
from .connection import get_con, mut


def set_cfg(clave: str, valor: str) -> None:
    mut("INSERT OR REPLACE INTO configuracion VALUES (?,?)", (clave, valor))

def set_ano_activo(ano: int) -> None:
    set_cfg("ano_activo", str(ano))

def add_ano(ano: int, saldo_func: float, saldo_com: float) -> None:
    con = get_con()
    con.execute("INSERT OR IGNORE INTO anos VALUES (?)", (ano,))
    con.execute("INSERT OR REPLACE INTO saldos VALUES (?,?,?)", (ano, "func", saldo_func))
    con.execute("INSERT OR REPLACE INTO saldos VALUES (?,?,?)", (ano, "com",  saldo_com))
    con.execute("INSERT OR REPLACE INTO configuracion VALUES ('ano_activo',?)", (str(ano),))
    con.commit()
    con.close()

def save_saldo(ano: int, area: str, saldo: float) -> None:
    mut("INSERT OR REPLACE INTO saldos VALUES (?,?,?)", (ano, area, saldo))

def save_diario(d: dict) -> int:
    con = get_con()
    if d.get("id"):
        con.execute(
            """UPDATE diario SET ano=?, curso_id=?, partida_curso_id=?, data=?,
               tipo=?, importe=?, concepto=?, codigo=?, cod_desc=?, periodo=?,
               notas=?, categoria=?, xustifica=?, alumno_neae=?, cliente_id=?
               WHERE id=?""",
            (
                d["ano"], d.get("curso_id"), d.get("partida_curso_id"),
                d["data"], d["tipo"], d["importe"], d["concepto"],
                d.get("codigo",""), d.get("cod_desc",""), d.get("periodo",""),
                d.get("notas",""), d.get("categoria",""), d.get("xustifica",""),
                d.get("alumno_neae",""), d.get("cliente_id"), d["id"],
            ),
        )
        rowid = d["id"]
    else:
        cur = con.execute(
            "SELECT COALESCE(MAX(num),0) FROM diario WHERE area=? AND ano=?",
            (d["area"], d["ano"]),
        )
        next_num = cur.fetchone()[0] + 1
        cur = con.execute(
            """INSERT INTO diario
               (area, ano, curso_id, partida_curso_id, num, data, tipo, importe,
                concepto, codigo, cod_desc, periodo, notas, categoria,
                xustifica, alumno_neae, cliente_id)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                d["area"], d["ano"], d.get("curso_id"), d.get("partida_curso_id"),
                next_num, d["data"], d["tipo"], d["importe"], d["concepto"],
                d.get("codigo",""), d.get("cod_desc",""), d.get("periodo",""),
                d.get("notas",""), d.get("categoria",""), d.get("xustifica",""),
                d.get("alumno_neae",""), d.get("cliente_id"),
            ),
        )
        rowid = cur.lastrowid
    con.commit()
    con.close()
    return rowid

def delete_diario(id: int) -> None:
    mut("DELETE FROM diario WHERE id=?", (id,))

def save_cliente(d: dict) -> int:
    if d.get("id"):
        mut(
            """UPDATE clientes SET nome=?, tipo=?, nif=?, direccion=?,
               telefono=?, email=?, notas=? WHERE id=?""",
            (d["nome"], d["tipo"], d["nif"], d["direccion"],
             d["telefono"], d["email"], d["notas"], d["id"]),
        )
        return d["id"]
    return mut(
        "INSERT INTO clientes (nome,tipo,nif,direccion,telefono,email,notas) VALUES (?,?,?,?,?,?,?)",
        (d["nome"], d["tipo"], d["nif"], d["direccion"],
         d["telefono"], d["email"], d["notas"]),
    )

def delete_cliente(id: int) -> None:
    mut("DELETE FROM clientes WHERE id=?", (id,))

def save_alumno(d: dict) -> int:
    if d.get("id"):
        mut(
            "UPDATE alumnos_neae SET nome=?, curso_id=?, curso_ingreso=?, importe_beca=?, notas=? WHERE id=?",
            (d["nome"], d.get("curso_id"), d["curso_ingreso"], d.get("importe_beca", 0), d["notas"], d["id"]),
        )
        return d["id"]
    return mut(
        "INSERT OR IGNORE INTO alumnos_neae (nome,curso_id,curso_ingreso,importe_beca,notas) VALUES (?,?,?,?,?)",
        (d["nome"], d.get("curso_id"), d["curso_ingreso"], d.get("importe_beca", 0), d["notas"]),
    )

def delete_alumno(id: int) -> None:
    mut("DELETE FROM alumnos_neae WHERE id=?", (id,))

def save_curso(nome: str) -> int:
    return mut("INSERT OR IGNORE INTO cursos (nome) VALUES (?)", (nome,))

def delete_curso(id: int) -> None:
    mut("DELETE FROM cursos WHERE id=?", (id,))

def save_codigo(d: dict) -> int:
    if d.get("id"):
        mut(
            "UPDATE codigos SET codigo=?, descripcion=?, activo=?, orden=? WHERE id=?",
            (d["codigo"], d["descripcion"], d["activo"], d["orden"], d["id"]),
        )
        return d["id"]
    return mut(
        "INSERT INTO codigos (codigo,descripcion,activo,orden) VALUES (?,?,?,?)",
        (d["codigo"], d["descripcion"], d["activo"], d["orden"]),
    )

def delete_codigo(id: int) -> None:
    mut("DELETE FROM codigos WHERE id=?", (id,))

def save_partida(d: dict) -> int:
    if d.get("id"):
        mut(
            "UPDATE partidas_config SET nome=?, importe_asignado=?, notas=? WHERE id=?",
            (d["nome"], d["importe_asignado"], d["notas"], d["id"]),
        )
        return d["id"]
    return mut(
        "INSERT OR REPLACE INTO partidas_config (curso_id,nome,importe_asignado,notas) VALUES (?,?,?,?)",
        (d["curso_id"], d["nome"], d["importe_asignado"], d["notas"]),
    )

def delete_partida(id: int) -> None:
    mut("DELETE FROM partidas_config WHERE id=?", (id,))
