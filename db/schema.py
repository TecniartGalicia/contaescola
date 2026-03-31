"""
db/schema.py
Definición completa del esquema y migraciones seguras.
"""
from .connection import get_con

PERIODOS = ["1º TRIMESTRE", "2º TRIMESTRE", "3º TRIMESTRE", "4º TRIMESTRE"]
CATEGORIAS_COM = ["ALIMENTACION", "LIMPEZA", "COMBUSTIBLE", "MANTEMENTO", "OUTROS"]
UMBRAL_347 = 3005.06

DDL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS configuracion (
    clave TEXT PRIMARY KEY,
    valor TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS anos (ano INTEGER PRIMARY KEY);
CREATE TABLE IF NOT EXISTS cursos (
    id   INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT    NOT NULL UNIQUE
);
CREATE TABLE IF NOT EXISTS codigos (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo      TEXT    NOT NULL UNIQUE,
    descripcion TEXT    NOT NULL,
    activo      INTEGER NOT NULL DEFAULT 1,
    orden       INTEGER NOT NULL DEFAULT 99
);
CREATE TABLE IF NOT EXISTS clientes (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    nome      TEXT    NOT NULL,
    tipo      TEXT    NOT NULL DEFAULT 'proveedor'
                      CHECK(tipo IN ('proveedor','cliente','outro')),
    nif       TEXT    NOT NULL DEFAULT '',
    direccion TEXT    NOT NULL DEFAULT '',
    telefono  TEXT    NOT NULL DEFAULT '',
    email     TEXT    NOT NULL DEFAULT '',
    notas     TEXT    NOT NULL DEFAULT '',
    creado_en TEXT    NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS alumnos_neae (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    nome          TEXT    NOT NULL UNIQUE,
    curso_id      INTEGER REFERENCES cursos(id) ON DELETE SET NULL,
    curso_ingreso TEXT    NOT NULL DEFAULT '',
    importe_beca  REAL    NOT NULL DEFAULT 0,
    notas         TEXT    NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS partidas_config (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    curso_id         INTEGER NOT NULL REFERENCES cursos(id) ON DELETE CASCADE,
    nome             TEXT    NOT NULL,
    importe_asignado REAL    NOT NULL DEFAULT 0,
    notas            TEXT    NOT NULL DEFAULT '',
    UNIQUE(curso_id, nome)
);
CREATE TABLE IF NOT EXISTS partidas (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    nome          TEXT    NOT NULL UNIQUE,
    saldo_inicial REAL    NOT NULL DEFAULT 0,
    notas         TEXT    NOT NULL DEFAULT '',
    activa        INTEGER NOT NULL DEFAULT 1,
    creado_en     TEXT    NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS saldos (
    ano  INTEGER NOT NULL,
    area TEXT    NOT NULL CHECK(area IN ('func','com')),
    saldo_anterior REAL NOT NULL DEFAULT 0,
    PRIMARY KEY (ano, area)
);
CREATE TABLE IF NOT EXISTS usuarios (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    username   TEXT    NOT NULL UNIQUE,
    nome       TEXT    NOT NULL DEFAULT '',
    password   TEXT    NOT NULL,
    activo     INTEGER NOT NULL DEFAULT 1,
    creado_en  TEXT    NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS diario (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    area             TEXT    NOT NULL CHECK(area IN ('func','com')),
    ano              INTEGER NOT NULL REFERENCES anos(ano),
    curso_id         INTEGER REFERENCES cursos(id),
    partida_curso_id INTEGER REFERENCES cursos(id),
    num              INTEGER NOT NULL DEFAULT 0,
    data             TEXT    NOT NULL,
    tipo             TEXT    NOT NULL CHECK(tipo IN ('G','I')),
    importe          REAL    NOT NULL CHECK(importe > 0),
    concepto         TEXT    NOT NULL,
    codigo           TEXT    NOT NULL DEFAULT '',
    cod_desc         TEXT    NOT NULL DEFAULT '',
    periodo          TEXT    NOT NULL DEFAULT '',
    notas            TEXT    NOT NULL DEFAULT '',
    categoria        TEXT    NOT NULL DEFAULT '',
    xustifica        TEXT    NOT NULL DEFAULT '',
    alumno_neae      TEXT    NOT NULL DEFAULT '',
    cliente_id       INTEGER REFERENCES clientes(id),
    creado_en        TEXT    NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_diario_ano_area ON diario(ano, area);
CREATE INDEX IF NOT EXISTS idx_diario_curso    ON diario(curso_id);
CREATE INDEX IF NOT EXISTS idx_diario_cliente  ON diario(cliente_id);
CREATE INDEX IF NOT EXISTS idx_diario_data     ON diario(data);
CREATE INDEX IF NOT EXISTS idx_diario_xustifica ON diario(xustifica);
"""

DATOS_INICIALES = {
    "configuracion": [
        ("ano_activo",       "2026"),
        ("centro_nome",      "Centro Educativo"),
        ("centro_direccion", ""),
        ("centro_nif",       ""),
        ("footer1",          "Documento xerado por ContaEscola"),
        ("footer2",          ""),
        ("logo_base64",      ""),
    ],
    "anos": [2025, 2026],
    "saldos": [
        (2025, "func", 64080.83), (2025, "com", 57479.82),
        (2026, "func", 47028.32), (2026, "com", 50608.14),
    ],
    "cursos": ["2024-2025", "2025-2026"],
    "codigos": [
        ("01","Arrendamentos",1),("02","Reparacións e conservación",2),
        ("03","Material de oficina",3),("04","Suministracións",4),
        ("04.1","Gasoleo",5),("04.2","Electricidade",6),("04.3","Auga",7),
        ("04.4","Gas",8),("04.5","Teléfono/Internet",9),
        ("04.6","Outras suministracións",10),("05","Transportes",11),
        ("06","Comunicacións",12),("07","Publicidade",13),
        ("08","Prima de seguro",14),("09","Gastos bancarios",15),
        ("10","Gastos de viaxe",16),("11","Gastos diversos",17),
        ("12","Reprografía",18),
    ],
}

MIGRATIONS = [
    ("clientes",     "direccion",        "TEXT NOT NULL DEFAULT ''"),
    ("alumnos_neae", "curso_id",         "INTEGER REFERENCES cursos(id)"),
    ("alumnos_neae", "importe_beca",     "REAL NOT NULL DEFAULT 0"),
    ("diario",       "ano",              "INTEGER NOT NULL DEFAULT 2026"),
    ("diario",       "curso_id",         "INTEGER REFERENCES cursos(id)"),
    ("diario",       "partida_curso_id", "INTEGER REFERENCES cursos(id)"),
]


def init_db():
    con = get_con()
    con.executescript(DDL)
    _run_migrations(con)
    _seed_data(con)
    _backfill_partida_curso_id(con)
    _migrate_partidas_to_global(con)
    con.commit()
    con.close()


def _run_migrations(con):
    for tbl, col, dfn in MIGRATIONS:
        try:
            con.execute(f"ALTER TABLE {tbl} ADD COLUMN {col} {dfn}")
        except Exception:
            pass


def _backfill_partida_curso_id(con):
    try:
        con.execute("""
            UPDATE diario SET partida_curso_id = curso_id
            WHERE partida_curso_id IS NULL AND xustifica != ''
              AND curso_id IS NOT NULL
        """)
    except Exception:
        pass


def _migrate_partidas_to_global(con):
    """
    Migración única: copia partidas de partidas_config al nuevo modelo global.
    Solo si la tabla partidas está vacía.
    Prioridad: partidas del curso 25/26, luego el resto.
    """
    n = con.execute("SELECT COUNT(*) FROM partidas").fetchone()[0]
    if n > 0:
        return  # ya migrado

    # Obtener partidas únicas priorizando las del curso más reciente
    rows = con.execute("""
        SELECT pc.nome, pc.importe_asignado, pc.notas, c.nome as curso_nome
        FROM partidas_config pc
        JOIN cursos c ON pc.curso_id = c.id
        ORDER BY c.nome DESC, pc.nome
    """).fetchall()

    vistas = set()
    for r in rows:
        nome = r[0]
        if nome in vistas:
            continue
        vistas.add(nome)
        con.execute(
            "INSERT OR IGNORE INTO partidas (nome, saldo_inicial, notas) VALUES (?,?,?)",
            (nome, r[1] or 0.0, r[2] or ""),
        )


def _seed_data(con):
    for k, v in DATOS_INICIALES["configuracion"]:
        con.execute("INSERT OR IGNORE INTO configuracion VALUES (?,?)", (k, v))
    for a in DATOS_INICIALES["anos"]:
        con.execute("INSERT OR IGNORE INTO anos VALUES (?)", (a,))
    for ano, area, saldo in DATOS_INICIALES["saldos"]:
        con.execute("INSERT OR IGNORE INTO saldos VALUES (?,?,?)", (ano, area, saldo))
    for nome in DATOS_INICIALES["cursos"]:
        con.execute("INSERT OR IGNORE INTO cursos (nome) VALUES (?)", (nome,))
    for codigo, desc, orden in DATOS_INICIALES["codigos"]:
        con.execute(
            "INSERT OR IGNORE INTO codigos (codigo,descripcion,orden) VALUES (?,?,?)",
            (codigo, desc, orden),
        )
    n = con.execute("SELECT COUNT(*) FROM usuarios").fetchone()[0]
    if n == 0:
        import bcrypt
        pwd_hash = bcrypt.hashpw(b"mateo", bcrypt.gensalt(12)).decode()
        con.execute(
            "INSERT OR IGNORE INTO usuarios (username,nome,password,activo) VALUES (?,?,?,1)",
            ("raquel", "Raquel", pwd_hash),
        )
