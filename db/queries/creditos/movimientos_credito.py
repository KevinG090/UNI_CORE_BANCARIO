"""Timeline completo de un crédito: apertura, abonos y cierre."""

from typing import Any, Dict, List
from psycopg2.extras import RealDictCursor
from db.connection import get_conn


def obtener_timeline_credito(credito_id: str) -> Dict[str, Any]:
    """
    Retorna:
    - Cabecera del crédito
    - Línea de tiempo: apertura → pagos (con detalle de cuotas abonadas) → cierre
    - Impacto en cupo por cada evento
    """

    query_cabecera = """
        SELECT
            cr.id, cr.valor_credito, cr.numero_cuotas_pactadas,
            cr.numero_cuotas_pagadas, cr.valor_cuota,
            cr.tasa_interes_nominal_mes, cr.saldo_capital,
            cr.saldo_intereses, cr.saldo_mora, cr.estado,
            cr.fecha_desembolso, cr.fecha_primer_pago,
            cr.fecha_ultimo_pago_esperado,
            cu.cupo_aprobado, cu.cupo_disponible
        FROM banking.creditos cr
        JOIN banking.cupos cu ON cu.id = cr.cupo_id
        WHERE cr.id = %(credito_id)s;
    """

    # Todos los movimientos de cupo ligados a este crédito
    # (apertura = DEBITO_NUEVO_CREDITO, pagos = CREDITO_PAGO)
    query_movimientos_cupo = """
        SELECT
            mc.id,
            mc.tipo_movimiento,
            mc.valor,
            mc.saldo_cupo_antes,
            mc.saldo_cupo_despues,
            mc.descripcion,
            mc.created_at
        FROM banking.movimientos_cupo mc
        WHERE mc.credito_id = %(credito_id)s
        ORDER BY mc.created_at ASC;
    """

    # Pagos con el detalle de cuotas que abonó cada uno
    query_pagos = """
        SELECT
            p.id AS pago_id,
            p.valor_pago,
            p.valor_capital_abonado,
            p.valor_interes_abonado,
            p.valor_mora_abonado,
            p.saldo_credito_antes,
            p.saldo_credito_despues,
            p.cupo_liberado,
            p.canal_pago,
            p.fecha_pago,
            -- cuotas que cubre este pago
            json_agg(
                json_build_object(
                    'cuota_id',       dp.cuota_id,
                    'numero_cuota',   cc.numero_cuota,
                    'fecha_vencimiento', cc.fecha_vencimiento,
                    'valor_aplicado', dp.valor_aplicado,
                    'estado_cuota',   cc.estado
                ) ORDER BY cc.numero_cuota
            ) AS cuotas_abonadas
        FROM banking.pagos p
        JOIN banking.detalle_pagos dp ON dp.pago_id = p.id
        JOIN banking.cuotas_credito cc ON cc.id = dp.cuota_id
        WHERE p.credito_id = %(credito_id)s
        GROUP BY p.id
        ORDER BY p.fecha_pago ASC;
    """

    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:

            cur.execute(query_cabecera, {"credito_id": credito_id})
            cabecera = cur.fetchone()
            if not cabecera:
                return None
            cabecera = dict(cabecera)

            cur.execute(query_movimientos_cupo, {"credito_id": credito_id})
            movimientos_cupo = [dict(r) for r in cur.fetchall()]

            cur.execute(query_pagos, {"credito_id": credito_id})
            pagos = [dict(r) for r in cur.fetchall()]

    # ── Construir timeline ──────────────────────────────────────────────────
    # Indexar movimientos de cupo por tipo para cruzarlos con pagos
    mov_apertura = next(
        (m for m in movimientos_cupo if m["tipo_movimiento"] == "DEBITO_NUEVO_CREDITO"),
        None,
    )
    movs_pago = {
        m["created_at"]: m
        for m in movimientos_cupo
        if m["tipo_movimiento"] == "CREDITO_PAGO"
    }

    timeline = []

    # Evento 0: apertura del crédito
    if mov_apertura:
        timeline.append({
            "tipo":            "APERTURA",
            "fecha":           mov_apertura["created_at"],
            "valor":           float(cabecera["valor_credito"]),
            "descripcion":     mov_apertura["descripcion"] or "Apertura de crédito",
            "cupo_antes":      float(mov_apertura["saldo_cupo_antes"]),
            "cupo_despues":    float(mov_apertura["saldo_cupo_despues"]),
            "cupo_impacto":    -float(mov_apertura["valor"]),   # negativo: consume cupo
        })

    # Eventos intermedios: cada pago
    for pago in pagos:
        # Buscar el movimiento de cupo más cercano en tiempo a este pago
        mov_cupo = min(
            movs_pago.values(),
            key=lambda m: abs((m["created_at"] - pago["fecha_pago"]).total_seconds()),
            default=None,
        ) if movs_pago else None

        es_cierre = (
            cabecera["estado"] in ("PAGADO", "CANCELADO")
            and pago == pagos[-1]
        )

        timeline.append({
            "tipo":                  "CIERRE" if es_cierre else "PAGO",
            "fecha":                 pago["fecha_pago"],
            "pago_id":               str(pago["pago_id"]),
            "valor_pago":            float(pago["valor_pago"]),
            "capital_abonado":       float(pago["valor_capital_abonado"]),
            "interes_abonado":       float(pago["valor_interes_abonado"]),
            "mora_abonada":          float(pago["valor_mora_abonado"]),
            "saldo_antes":           float(pago["saldo_credito_antes"]),
            "saldo_despues":         float(pago["saldo_credito_despues"]),
            "cupo_liberado":         float(pago["cupo_liberado"]),
            "cupo_antes":            float(mov_cupo["saldo_cupo_antes"])  if mov_cupo else None,
            "cupo_despues":          float(mov_cupo["saldo_cupo_despues"]) if mov_cupo else None,
            "canal_pago":            pago["canal_pago"],
            "cuotas_abonadas":       pago["cuotas_abonadas"],
        })

    return {
        "credito":  cabecera,
        "timeline": timeline,
    }