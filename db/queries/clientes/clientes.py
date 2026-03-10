"""Queries para la tabla banking.clientes"""

from typing import Any, Dict, Optional

from psycopg2.extras import RealDictCursor

from db.connection import get_conn
from schemas.clientes import ClienteCreate, ClienteUpdate


def crear_cliente(data: ClienteCreate) -> Dict[str, Any]:
    query = """
        INSERT INTO banking.clientes (
            tipo_identificacion, numero_identificacion,
            primer_nombre, segundo_nombre,
            primer_apellido, segundo_apellido,
            fecha_nacimiento, correo_electronico,
            telefono_movil, telefono_fijo,
            direccion, ciudad, departamento, codigo_postal,
            estado, score_credito,
            created_by, updated_by
        ) VALUES (
            %(tipo_identificacion)s, %(numero_identificacion)s,
            %(primer_nombre)s, %(segundo_nombre)s,
            %(primer_apellido)s, %(segundo_apellido)s,
            %(fecha_nacimiento)s, %(correo_electronico)s,
            %(telefono_movil)s, %(telefono_fijo)s,
            %(direccion)s, %(ciudad)s, %(departamento)s, %(codigo_postal)s,
            'EN_ESTUDIO', %(score_credito)s,
            %(created_by)s, %(created_by)s
        )
        RETURNING
            id, tipo_identificacion, numero_identificacion,
            primer_nombre, primer_apellido,
            correo_electronico, estado, created_at;
    """
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, data.model_dump())
            return dict(cur.fetchone())


def obtener_cliente(cliente_id: str) -> Optional[Dict[str, Any]]:
    query = """
        SELECT
            id, tipo_identificacion, numero_identificacion,
            primer_nombre, segundo_nombre,
            primer_apellido, segundo_apellido,
            fecha_nacimiento, correo_electronico,
            telefono_movil, telefono_fijo,
            direccion, ciudad, departamento,
            estado, score_credito, causal_bloqueo,
            created_at, updated_at
        FROM banking.clientes
        WHERE id = %(id)s;
    """
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, {"id": cliente_id})
            row = cur.fetchone()
            return dict(row) if row else None


def listar_clientes(
    limit: int = 20,
    offset: int = 0,
    estado: Optional[str] = None,
) -> Dict[str, Any]:
    query = """
        SELECT
            id, tipo_identificacion, numero_identificacion,
            primer_nombre, primer_apellido,
            correo_electronico, telefono_movil,
            ciudad, estado, score_credito, created_at
        FROM banking.clientes
        WHERE
            (%(estado)s IS NULL OR estado::TEXT = %(estado)s)
        ORDER BY created_at DESC
        LIMIT %(limit)s OFFSET %(offset)s;
    """
    count_query = """
        SELECT COUNT(*) AS total FROM banking.clientes
        WHERE (%(estado)s IS NULL OR estado::TEXT = %(estado)s);
    """
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(count_query, {"estado": estado})
            total = cur.fetchone()["total"]

            cur.execute(query, {"estado": estado, "limit": limit, "offset": offset})
            rows = [dict(r) for r in cur.fetchall()]

    return {"total": total, "limit": limit, "offset": offset, "results": rows}


def actualizar_cliente(
    cliente_id: str, data: ClienteUpdate
) -> Optional[Dict[str, Any]]:
    # Construir SET dinámico solo con campos que se enviaron
    campos = data.model_dump(exclude_none=True, exclude={"updated_by"})
    if not campos:
        return obtener_cliente(cliente_id)

    set_clause = ", ".join(f"{k} = %({k})s" for k in campos)
    query = f"""
        UPDATE banking.clientes
        SET {set_clause},
            updated_by = %(updated_by)s,
            updated_at  = now()
        WHERE id = %(id)s
        RETURNING
            id, tipo_identificacion, numero_identificacion,
            primer_nombre, primer_apellido,
            correo_electronico, estado, updated_at;
    """
    params = {**campos, "updated_by": data.updated_by, "id": cliente_id}
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, params)
            row = cur.fetchone()
            return dict(row) if row else None
