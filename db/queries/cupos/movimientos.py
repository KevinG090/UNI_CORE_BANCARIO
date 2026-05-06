"""Queries para banking.movimientos_cupo"""

from typing import Any, Dict, List, Optional
from psycopg2.extras import RealDictCursor
from db.connection import get_conn


def obtener_movimientos_cupo(
    cupo_id: str,
    limite: int = 50,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    """
    Retorna los movimientos de un cupo ordenados del más reciente al más antiguo.
    Incluye descripción enriquecida del crédito/pago asociado si existe.
    """
    query = """
        SELECT
            mc.id,
            mc.cupo_id,
            mc.credito_id,
            mc.pago_id,
            mc.tipo_movimiento,
            mc.valor,
            mc.saldo_cupo_antes,
            mc.saldo_cupo_despues,
            mc.descripcion,
            mc.usuario,
            mc.created_at
        FROM banking.movimientos_cupo mc
        WHERE mc.cupo_id = %(cupo_id)s
        ORDER BY mc.created_at DESC
        LIMIT %(limite)s OFFSET %(offset)s;
    """
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, {
                "cupo_id": cupo_id,
                "limite":  limite,
                "offset":  offset,
            })
            return [dict(row) for row in cur.fetchall()]


def contar_movimientos_cupo(cupo_id: str) -> int:
    query = """
        SELECT COUNT(*) AS total
        FROM banking.movimientos_cupo
        WHERE cupo_id = %(cupo_id)s;
    """
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, {"cupo_id": cupo_id})
            return cur.fetchone()["total"]