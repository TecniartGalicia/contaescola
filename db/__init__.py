"""
db/__init__.py
Exports públicos del paquete de base de datos.
El resto de la app solo importa desde aquí.
"""
from .schema import init_db, PERIODOS, CATEGORIAS_COM, UMBRAL_347
from .queries import (
    get_cfg, get_ano_activo, get_anos, get_cursos, get_codigos,
    get_clientes, get_cliente, get_alumnos, get_partidas_config,
    get_saldo, get_diario, get_diario_cliente, get_diario_partida,
    get_partidas_resumen, get_becas_resumen,
    get_informes, get_347,
)
from .mutations import (
    set_cfg, set_ano_activo, add_ano, save_saldo,
    save_diario, delete_diario,
    save_cliente, delete_cliente,
    save_alumno, delete_alumno,
    save_curso, delete_curso,
    save_codigo, delete_codigo,
    save_partida, delete_partida,
)
