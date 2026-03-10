"""
Pool de conexiones con psycopg2.pool.ThreadedConnectionPool.
Una sola instancia global inicializada al arrancar la app.
"""

from contextlib import contextmanager
from typing import Generator

import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2.pool import ThreadedConnectionPool

from core.config import get_settings

_pool: ThreadedConnectionPool | None = None


def init_pool() -> None:
    """Inicializar el pool. Llamar una sola vez al arrancar."""
    global _pool
    if _pool is not None:
        return

    s = get_settings()
    _pool = ThreadedConnectionPool(
        minconn=s.POOL_MIN_CONN,
        maxconn=s.POOL_MAX_CONN,
        host=s.POSTGRES_SERVER,
        port=s.POSTGRES_PORT,
        user=s.POSTGRES_USER,
        password=s.POSTGRES_PASSWORD,
        dbname=s.POSTGRES_DB,
        sslmode="require",
        options="-c search_path=banking,public",
    )


def get_pool() -> ThreadedConnectionPool:
    if _pool is None:
        init_pool()
    return _pool  # type: ignore


@contextmanager
def get_conn() -> Generator:
    """
    Context manager que obtiene una conexión del pool,
    hace commit/rollback automático y la devuelve al pool.

    Uso:
        with get_conn() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(...)
    """
    pool = get_pool()
    conn = pool.getconn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        pool.putconn(conn)
