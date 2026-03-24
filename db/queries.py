"""
db/queries.py
Todas las consultas SELECT de la aplicación.
"""
from .connection import q, q1
from .schema import PERIODOS


def get_cfg(clave: str, default: str = "") -> str:
    r = q1("SELECT valor FROM configuracion WHERE clave=?", (clave,))
    return r["valor"] if r else default

def get_ano_activo() -> int:
    """Devuelve el año activo guardado en config.
    Si no hay ninguno configurado, devuelve el año más reciente de la BD."""
    val = get_cfg("ano_activo", "")
    if val:
        return int(val)
    # Fallback: año más alto disponible
    r = q1("SELECT MAX(ano) as ano FROM anos")
    return int(r["ano"]) if r and r["ano"] else 2026

def get_anos() -> list[int]:
    return [r["ano"] for r in q("SELECT ano FROM anos ORDER BY ano")]

def get_cursos() -> list[dict]:
    return q("SELECT * FROM cursos ORDER BY nome")

def get_codigos(solo_activos: bool = True) -> list[dict]:
    sql = "SELECT * FROM codigos"
    if solo_activos:
        sql += " WHERE activo=1"
    return q(sql + " ORDER BY orden, codigo")

def get_clientes() -> list[dict]:
    return q("SELECT * FROM clientes ORDER BY nome")

def get_cliente(id: int) -> dict | None:
    return q1("SELECT * FROM clientes WHERE id=?", (id,))

def get_alumnos() -> list[dict]:
    return q(
        """SELECT a.*, c.nome as curso_nome
           FROM alumnos_neae a
           LEFT JOIN cursos c ON a.curso_id = c.id
           ORDER BY a.nome"""
    )

def get_partidas_config(curso_id: int | None = None) -> list[dict]:
    if curso_id:
        return q(
            """SELECT pc.*, c.nome as curso_nome
               FROM partidas_config pc
               LEFT JOIN cursos c ON pc.curso_id = c.id
               WHERE pc.curso_id = ?
               ORDER BY pc.nome""",
            (curso_id,),
        )
    return q(
        """SELECT pc.*, c.nome as curso_nome
           FROM partidas_config pc
           LEFT JOIN cursos c ON pc.curso_id = c.id
           ORDER BY c.nome, pc.nome"""
    )

def get_saldo(ano: int, area: str) -> float:
    r = q1("SELECT saldo_anterior FROM saldos WHERE ano=? AND area=?", (ano, area))
    return r["saldo_anterior"] if r else 0.0

def get_diario(area: str, ano: int, curso_id: int | None = None) -> list[dict]:
    sql = """
        SELECT d.*,
               c.nome  AS curso_nome,
               cl.nome AS cliente_nome,
               cl.nif  AS cliente_nif,
               cl.direccion AS cliente_dir
        FROM diario d
        LEFT JOIN cursos  c  ON d.curso_id  = c.id
        LEFT JOIN clientes cl ON d.cliente_id = cl.id
        WHERE d.area=? AND d.ano=?
    """
    params: list = [area, ano]
    if curso_id:
        sql += " AND d.curso_id=?"
        params.append(curso_id)
    return q(sql + " ORDER BY d.num", tuple(params))

def get_diario_cliente(cliente_id: int) -> list[dict]:
    return q(
        """SELECT d.*, c.nome as curso_nome
           FROM diario d
           LEFT JOIN cursos c ON d.curso_id = c.id
           WHERE d.cliente_id = ?
           ORDER BY d.ano DESC, d.data DESC""",
        (cliente_id,),
    )

def get_diario_partida(xustifica: str, curso_id: int) -> list[dict]:
    """
    Movementos asociados a unha partida dun curso concreto.
    ★ Usa partida_curso_id para identificar correctamente a qué curso
      pertenece la partida, independientemente del curso del movimiento.
    """
    return q(
        """SELECT d.*,
                  c.nome  AS curso_nome,
                  cl.nome AS cliente_nome
           FROM diario d
           LEFT JOIN cursos   c  ON d.curso_id   = c.id
           LEFT JOIN clientes cl ON d.cliente_id  = cl.id
           WHERE d.xustifica = ?
             AND d.partida_curso_id = ?
           ORDER BY d.data, d.num""",
        (xustifica, curso_id),
    )

def get_partidas_resumen(ano: int, curso_id: int | None = None) -> dict:
    """
    Devuelve {nombre_partida: {debe, haber}} para un curso escolar.
    ★ Filtra por partida_curso_id — el curso al que pertenece la PARTIDA,
      no el curso del movimiento. Así un movimiento del curso 25/26
      asignado a una partida del 24/25 aparece correctamente en el 24/25.
    """
    if curso_id:
        rows = q(
            """SELECT xustifica, tipo, SUM(importe) as t
               FROM diario
               WHERE partida_curso_id = ? AND xustifica != ''
               GROUP BY xustifica, tipo""",
            (curso_id,),
        )
    else:
        rows = q(
            """SELECT xustifica, tipo, SUM(importe) as t
               FROM diario WHERE ano=? AND xustifica!=''
               GROUP BY xustifica, tipo""",
            (ano,),
        )

    res: dict = {}
    for r in rows:
        res.setdefault(r["xustifica"], {"debe": 0.0, "haber": 0.0})
        key = "haber" if r["tipo"] == "I" else "debe"
        res[r["xustifica"]][key] += r["t"]
    return res

def get_becas_resumen(ano: int, curso_id: int | None = None) -> dict:
    alumnos = get_alumnos()
    result: dict = {}
    for al in alumnos:
        if curso_id and al.get("curso_id") and al["curso_id"] != curso_id:
            continue
        if curso_id:
            sql = """
                SELECT d.*, c.nome as curso_nome
                FROM diario d
                LEFT JOIN cursos c ON d.curso_id = c.id
                WHERE d.curso_id=? AND d.alumno_neae=?
            """
            params: list = [curso_id, al["nome"]]
        else:
            sql = """
                SELECT d.*, c.nome as curso_nome
                FROM diario d
                LEFT JOIN cursos c ON d.curso_id = c.id
                WHERE d.ano=? AND d.alumno_neae=?
            """
            params = [ano, al["nome"]]
        movs = q(sql + " ORDER BY d.data", tuple(params))
        result[al["nome"]] = {
            "alumno": al,
            "movs":   movs,
            "debe":   sum(m["importe"] for m in movs if m["tipo"] == "G"),
            "haber":  sum(m["importe"] for m in movs if m["tipo"] == "I"),
        }
    return result

def get_informes(params: dict) -> list[dict]:
    sql = """
        SELECT d.*,
               c.nome  AS curso_nome,
               cl.nome AS cliente_nome,
               cl.nif  AS cliente_nif,
               cl.direccion AS cliente_dir
        FROM diario d
        LEFT JOIN cursos   c  ON d.curso_id   = c.id
        LEFT JOIN clientes cl ON d.cliente_id  = cl.id
        WHERE 1=1
    """
    p: list = []
    if params.get("area"):        sql += " AND d.area=?";        p.append(params["area"])
    if params.get("ano"):         sql += " AND d.ano=?";         p.append(int(params["ano"]))
    if params.get("curso_id"):    sql += " AND d.curso_id=?";    p.append(int(params["curso_id"]))
    if params.get("tipo"):        sql += " AND d.tipo=?";        p.append(params["tipo"])
    if params.get("periodo"):     sql += " AND d.periodo=?";     p.append(params["periodo"])
    if params.get("codigo"):      sql += " AND d.codigo=?";      p.append(params["codigo"])
    if params.get("xustifica"):   sql += " AND d.xustifica=?";   p.append(params["xustifica"])
    if params.get("cliente_id"):  sql += " AND d.cliente_id=?";  p.append(int(params["cliente_id"]))
    if params.get("fecha_desde"): sql += " AND d.data>=?";       p.append(params["fecha_desde"])
    if params.get("fecha_hasta"): sql += " AND d.data<=?";       p.append(params["fecha_hasta"])
    return q(sql + " ORDER BY d.ano, d.data, d.num", tuple(p))

def get_347(ano: int, umbral: float) -> list[dict]:
    provs = q(
        """SELECT cl.id, cl.nome, cl.nif, cl.email, cl.telefono, cl.direccion,
                  SUM(CASE WHEN d.tipo='G' THEN d.importe ELSE 0 END) AS total_pagado,
                  SUM(CASE WHEN d.tipo='I' THEN d.importe ELSE 0 END) AS total_cobrado,
                  COUNT(*) AS num_ops
           FROM diario d
           JOIN clientes cl ON d.cliente_id = cl.id
           WHERE d.ano=?
           GROUP BY cl.id
           HAVING total_pagado >= ?
           ORDER BY total_pagado DESC""",
        (ano, umbral),
    )
    for pr in provs:
        trim: dict = {}
        for per in PERIODOS:
            rows = q(
                """SELECT tipo, SUM(importe) as t
                   FROM diario
                   WHERE ano=? AND cliente_id=? AND periodo=?
                   GROUP BY tipo""",
                (ano, pr["id"], per),
            )
            trim[per] = {
                "gastos":   next((r["t"] for r in rows if r["tipo"] == "G"), 0.0),
                "ingresos": next((r["t"] for r in rows if r["tipo"] == "I"), 0.0),
            }
        pr["trimestres"] = trim
    return provs
