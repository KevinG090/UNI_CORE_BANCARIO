"""Queries para banking.cupos"""

from typing import Any, Dict, Optional

from psycopg2.extras import RealDictCursor

from db.connection import get_conn
from schemas.cupos import CupoCreate


def crear_cupo(data: CupoCreate) -> Dict[str, Any]:
    """
    1. Obtiene la configuración VIGENTE y el parámetro de interés según perfil.
    2. Inserta el cupo.
    3. Actualiza el estado del cliente a ACTIVO.
    Todo en una sola transacción.
    """
    query_cfg = """
        SELECT c.id AS cfg_id, pi.id AS param_id, pi.tasa_interes_nominal_mes
        FROM banking.configuracion c
        JOIN banking.parametros_interes pi
          ON pi.configuracion_id = c.id
         AND pi.aplica_a_perfil_riesgo = %(perfil)s
         AND pi.activo = TRUE
        WHERE c.estado = 'VIGENTE'
        LIMIT 1;
    """
    query_insert = """
        INSERT INTO banking.cupos (
            cliente_id, configuracion_id, parametro_interes_id,
            cupo_aprobado, cupo_disponible, cupo_utilizado, cupo_en_mora,
            estado, fecha_aprobacion,
            limite_credito_individual,
            created_by, updated_by
        ) VALUES (
            %(cliente_id)s, %(cfg_id)s, %(param_id)s,
            %(cupo_aprobado)s, %(cupo_aprobado)s, 0, 0,
            'ACTIVO', now(),
            %(limite_credito_individual)s,
            %(created_by)s, %(created_by)s
        )
        RETURNING id, cliente_id, cupo_aprobado, cupo_disponible, estado, fecha_aprobacion;
    """
    query_update_cliente = """
        UPDATE banking.clientes
        SET estado = 'ACTIVO', updated_at = now(), updated_by = %(updated_by)s
        WHERE id = %(cliente_id)s AND estado IN ('EN_ESTUDIO', 'INACTIVO');
    """

    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query_cfg, {"perfil": data.perfil_riesgo})
            cfg = cur.fetchone()
            if not cfg:
                raise ValueError(
                    f"No hay configuración VIGENTE o perfil '{data.perfil_riesgo}' no existe."
                )

            # limite individual = 80% del cupo (porcentaje_cupo_maximo_credito por defecto)
            limite = round(data.cupo_aprobado * 0.80, 2)

            params = {
                "cliente_id": data.cliente_id,
                "cfg_id": str(cfg["cfg_id"]),
                "param_id": str(cfg["param_id"]),
                "cupo_aprobado": data.cupo_aprobado,
                "limite_credito_individual": limite,
                "created_by": data.created_by,
            }
            cur.execute(query_insert, params)
            cupo = dict(cur.fetchone())

            cur.execute(query_update_cliente, {
                "cliente_id": data.cliente_id,
                "updated_by": data.created_by,
            })

            return cupo


def obtener_cupo(cupo_id: str) -> Optional[Dict[str, Any]]:
    query = """
        SELECT
            cu.id, cu.cliente_id,
            cl.primer_nombre || ' ' || cl.primer_apellido AS nombre_cliente,
            cu.cupo_aprobado, cu.cupo_disponible,
            cu.cupo_utilizado, cu.cupo_en_mora,
            cu.estado, cu.fecha_aprobacion, cu.limite_credito_individual,
            pi.aplica_a_perfil_riesgo AS perfil_riesgo,
            pi.tasa_interes_nominal_mes, pi.tasa_mora_mes
        FROM banking.cupos cu
        JOIN banking.clientes cl ON cl.id = cu.cliente_id
        JOIN banking.parametros_interes pi ON pi.id = cu.parametro_interes_id
        WHERE cu.id = %(id)s;
    """
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, {"id": cupo_id})
            row = cur.fetchone()
            return dict(row) if row else None


def obtener_cupo_por_cliente(cliente_id: str) -> Optional[Dict[str, Any]]:
    query = """
        SELECT
            cu.id, cu.cupo_aprobado, cu.cupo_disponible,
            cu.cupo_utilizado, cu.cupo_en_mora, cu.estado,
            pi.aplica_a_perfil_riesgo AS perfil_riesgo,
            pi.tasa_interes_nominal_mes, pi.tasa_mora_mes
        FROM banking.cupos cu
        JOIN banking.parametros_interes pi ON pi.id = cu.parametro_interes_id
        WHERE cu.cliente_id = %(cliente_id)s
          AND cu.estado = 'ACTIVO'
        ORDER BY cu.fecha_aprobacion DESC
        LIMIT 1;
    """
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, {"cliente_id": cliente_id})
            row = cur.fetchone()
            return dict(row) if row else None
