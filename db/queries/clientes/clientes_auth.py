"""
Agrega obtener_cliente_por_identificacion al archivo original de queries.
Pegar al final de db/queries/clientes/clientes.py
"""

from psycopg2.extras import RealDictCursor
from db.connection import get_conn


def obtener_cliente_por_identificacion(tipo: str, numero: str):
    """
    Busca un cliente por tipo + numero de identificacion.
    Usado exclusivamente por el login — no exponer como endpoint publico.
    """
    query = """
        SELECT
            id,
            tipo_identificacion,
            numero_identificacion,
            primer_nombre,
            primer_apellido,
            estado,
            correo_electronico,
            created_at,
            updated_at
        FROM banking.clientes
        WHERE tipo_identificacion = %(tipo)s::banking.tipo_identificacion
          AND numero_identificacion = %(numero)s
        LIMIT 1;
    """

    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, {"tipo": tipo, "numero": numero})
            row = cur.fetchone()
            return dict(row) if row else None
