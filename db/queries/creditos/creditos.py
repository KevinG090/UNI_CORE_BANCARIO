"""
Queries para banking.creditos, banking.cuotas_credito,
banking.movimientos_cupo y banking.pagos.

Lógica financiera:
  cuota = P * i / (1 - (1+i)^-n)
  donde i = tasa_nominal_mes / 100
"""

import math
from datetime import date
from typing import Any, Dict, List, Optional

from psycopg2.extras import RealDictCursor

from db.connection import get_conn
from schemas.creditos import CompraCreate, PagoCreate


# ─── helpers ──────────────────────────────────────────────────────────────────

def _calcular_cuota(capital: float, tasa_mes: float, n: int) -> float:
    """Cuota fija mensual (sistema francés)."""
    i = tasa_mes / 100
    if i == 0:
        return round(capital / n, 2)
    cuota = capital * i / (1 - math.pow(1 + i, -n))
    return round(cuota, 2)


# ─── generar crédito / compra ─────────────────────────────────────────────────

def crear_credito_desde_compra(data: CompraCreate) -> Dict[str, Any]:
    """
    Flujo completo de una compra:
    1. Verifica que el cupo tenga saldo disponible.
    2. Obtiene producto, tasa y configuración.
    3. Inserta el crédito.
    4. Genera el plan de cuotas.
    5. Registra el movimiento de débito al cupo.
    6. Actualiza cupo_utilizado / cupo_disponible.
    Todo en una sola transacción.
    """
    query_cupo = """
        SELECT
            cu.id, cu.cupo_disponible, cu.cupo_utilizado,
            cu.parametro_interes_id, cu.configuracion_id,
            pi.tasa_interes_nominal_mes, pi.tasa_mora_mes
        FROM banking.cupos cu
        JOIN banking.parametros_interes pi ON pi.id = cu.parametro_interes_id
        WHERE cu.id = %(cupo_id)s AND cu.estado = 'ACTIVO'
        FOR UPDATE;
    """
    query_producto = """
        SELECT id, plazo_minimo_cuotas, plazo_maximo_cuotas,
               monto_minimo, monto_maximo
        FROM banking.productos_credito
        WHERE codigo = %(codigo)s AND activo = TRUE
        LIMIT 1;
    """
    query_credito = """
        INSERT INTO banking.creditos (
            cupo_id, producto_id, parametro_interes_id, configuracion_id,
            valor_credito, numero_cuotas_pactadas, numero_cuotas_pagadas,
            numero_cuotas_mora, tasa_interes_nominal_mes, tasa_mora_mes,
            valor_seguro_cuota, valor_cuota,
            saldo_capital, saldo_intereses, saldo_mora,
            fecha_desembolso, fecha_primer_pago, fecha_ultimo_pago_esperado,
            estado, dias_mora_actuales, dias_mora_acumulados,
            created_by, updated_by
        ) VALUES (
            %(cupo_id)s, %(producto_id)s, %(param_id)s, %(cfg_id)s,
            %(valor)s, %(n)s, 0,
            0, %(tasa)s, %(tasa_mora)s,
            0, %(cuota)s,
            %(valor)s, 0, 0,
            now(),
            %(fecha_primer_pago)s,
            %(fecha_ultimo_pago)s,
            'ACTIVO', 0, 0,
            %(created_by)s, %(created_by)s
        )
        RETURNING id, valor_credito, numero_cuotas_pactadas, valor_cuota,
                  fecha_primer_pago, fecha_ultimo_pago_esperado, estado;
    """
    query_cuota = """
        INSERT INTO banking.cuotas_credito (
            credito_id, numero_cuota, fecha_vencimiento,
            valor_capital, valor_interes, valor_seguro,
            valor_total_esperado, valor_pagado, estado, dias_mora
        ) VALUES (
            %(credito_id)s, %(n)s, %(fecha_venc)s,
            %(v_capital)s, %(v_interes)s, 0,
            %(cuota)s, 0, 'PENDIENTE', 0
        );
    """
    query_mov = """
        INSERT INTO banking.movimientos_cupo (
            cupo_id, credito_id, tipo_movimiento,
            valor, saldo_cupo_antes, saldo_cupo_despues,
            descripcion, usuario
        ) VALUES (
            %(cupo_id)s, %(credito_id)s, 'DEBITO_NUEVO_CREDITO',
            %(valor)s, %(antes)s, %(despues)s,
            %(descripcion)s, %(usuario)s
        );
    """
    query_upd_cupo = """
        UPDATE banking.cupos
        SET cupo_disponible = cupo_disponible - %(valor)s,
            cupo_utilizado  = cupo_utilizado  + %(valor)s,
            fecha_ultima_utilizacion = now(),
            updated_at = now()
        WHERE id = %(cupo_id)s;
    """

    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:

            # 1. Cupo
            cur.execute(query_cupo, {"cupo_id": data.cupo_id})
            cupo = cur.fetchone()
            if not cupo:
                raise ValueError("Cupo no encontrado o inactivo.")
            if cupo["cupo_disponible"] < data.valor_compra:
                raise ValueError(
                    f"Cupo insuficiente. Disponible: {cupo['cupo_disponible']:.2f}, "
                    f"solicitado: {data.valor_compra:.2f}"
                )

            # 2. Producto (por defecto rotativo)
            cur.execute(query_producto, {"codigo": "CRE-ROT-001"})
            producto = cur.fetchone()
            if not producto:
                raise ValueError("Producto CRE-ROT-001 no encontrado.")

            # Validar plazo
            n = data.numero_cuotas
            if not (producto["plazo_minimo_cuotas"] <= n <= producto["plazo_maximo_cuotas"]):
                raise ValueError(
                    f"Plazo {n} fuera del rango "
                    f"[{producto['plazo_minimo_cuotas']}, {producto['plazo_maximo_cuotas']}]."
                )

            # 3. Calcular cuota
            tasa = float(cupo["tasa_interes_nominal_mes"])
            tasa_mora = float(cupo["tasa_mora_mes"])
            cuota = _calcular_cuota(data.valor_compra, tasa, n)

            from datetime import timedelta
            hoy = date.today()
            fecha_primer_pago = date(hoy.year, hoy.month + 1 if hoy.month < 12 else 1,
                                     hoy.day if hoy.day <= 28 else 28)
            # Para meses largos calculamos correctamente
            import calendar
            primer_mes = hoy.month + 1 if hoy.month < 12 else 1
            primer_anio = hoy.year if hoy.month < 12 else hoy.year + 1
            ultimo_dia = calendar.monthrange(primer_anio, primer_mes)[1]
            dia = min(hoy.day, ultimo_dia)
            fecha_primer_pago = date(primer_anio, primer_mes, dia)

            # fecha último pago = n meses después del primer pago
            mes_final = (fecha_primer_pago.month + n - 1) % 12 or 12
            anio_final = fecha_primer_pago.year + (fecha_primer_pago.month + n - 1) // 12
            ultimo_dia_final = calendar.monthrange(anio_final, mes_final)[1]
            fecha_ultimo_pago = date(anio_final, mes_final, min(fecha_primer_pago.day, ultimo_dia_final))

            params_cred = {
                "cupo_id": data.cupo_id,
                "producto_id": str(producto["id"]),
                "param_id": str(cupo["parametro_interes_id"]),
                "cfg_id": str(cupo["configuracion_id"]),
                "valor": data.valor_compra,
                "n": n,
                "tasa": tasa,
                "tasa_mora": tasa_mora,
                "cuota": cuota,
                "fecha_primer_pago": fecha_primer_pago,
                "fecha_ultimo_pago": fecha_ultimo_pago,
                "created_by": data.created_by,
            }
            cur.execute(query_credito, params_cred)
            credito = dict(cur.fetchone())
            credito_id = credito["id"]

            # 4. Plan de cuotas
            capital_cuota = round(data.valor_compra / n, 2)
            for i in range(1, n + 1):
                mes = (fecha_primer_pago.month + i - 1) % 12 or 12
                anio = fecha_primer_pago.year + (fecha_primer_pago.month + i - 1) // 12
                ultimo_dia_cuota = calendar.monthrange(anio, mes)[1]
                fecha_venc = date(anio, mes, min(fecha_primer_pago.day, ultimo_dia_cuota))

                v_interes = round(cuota - capital_cuota, 2)
                cur.execute(query_cuota, {
                    "credito_id": str(credito_id),
                    "n": i,
                    "fecha_venc": fecha_venc,
                    "v_capital": capital_cuota,
                    "v_interes": v_interes,
                    "cuota": cuota,
                })

            # 5. Movimiento débito cupo
            saldo_antes = float(cupo["cupo_disponible"])
            saldo_despues = round(saldo_antes - data.valor_compra, 2)
            cur.execute(query_mov, {
                "cupo_id": data.cupo_id,
                "credito_id": str(credito_id),
                "valor": data.valor_compra,
                "antes": saldo_antes,
                "despues": saldo_despues,
                "descripcion": data.descripcion,
                "usuario": data.created_by,
            })

            # 6. Actualizar cupo
            cur.execute(query_upd_cupo, {
                "valor": data.valor_compra,
                "cupo_id": data.cupo_id,
            })

            credito["cuota_mensual"] = cuota
            credito["tasa_nominal_mes"] = tasa
            credito["saldo_cupo_restante"] = saldo_despues
            return credito


# ─── obtener crédito ──────────────────────────────────────────────────────────

def obtener_credito(credito_id: str) -> Optional[Dict[str, Any]]:
    query = """
        SELECT
            cr.id, cr.valor_credito, cr.numero_cuotas_pactadas,
            cr.numero_cuotas_pagadas, cr.valor_cuota,
            cr.saldo_capital, cr.saldo_intereses, cr.saldo_mora,
            cr.saldo_total,
            cr.tasa_interes_nominal_mes, cr.tasa_mora_mes,
            cr.fecha_desembolso, cr.fecha_primer_pago,
            cr.fecha_ultimo_pago_esperado, cr.estado,
            cr.dias_mora_actuales,
            cl.primer_nombre || ' ' || cl.primer_apellido AS nombre_cliente
        FROM banking.creditos cr
        JOIN banking.cupos cu ON cu.id = cr.cupo_id
        JOIN banking.clientes cl ON cl.id = cu.cliente_id
        WHERE cr.id = %(id)s;
    """
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, {"id": credito_id})
            row = cur.fetchone()
            return dict(row) if row else None


def listar_creditos_por_cupo(cupo_id: str) -> List[Dict[str, Any]]:
    query = """
        SELECT
            id, valor_credito, numero_cuotas_pactadas,
            numero_cuotas_pagadas, valor_cuota,
            saldo_capital, saldo_mora, saldo_total,
            estado, fecha_desembolso, dias_mora_actuales
        FROM banking.creditos
        WHERE cupo_id = %(cupo_id)s
        ORDER BY fecha_desembolso DESC;
    """
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, {"cupo_id": cupo_id})
            return [dict(r) for r in cur.fetchall()]


def obtener_cuotas(credito_id: str) -> List[Dict[str, Any]]:
    query = """
        SELECT
            id, numero_cuota, fecha_vencimiento,
            valor_capital, valor_interes, valor_total_esperado,
            valor_pagado, saldo_pendiente, estado, dias_mora,
            interes_mora_causado
        FROM banking.cuotas_credito
        WHERE credito_id = %(credito_id)s
        ORDER BY numero_cuota;
    """
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, {"credito_id": credito_id})
            return [dict(r) for r in cur.fetchall()]


# ─── pago ─────────────────────────────────────────────────────────────────────

def registrar_pago(data: PagoCreate) -> Dict[str, Any]:
    """
    Registra un pago parcial o total:
    1. Obtiene las cuotas pendientes ordenadas por vencimiento.
    2. Aplica el valor del pago a las cuotas (primero mora, luego interés, luego capital).
    3. Libera cupo por el capital abonado.
    4. Actualiza saldo del crédito.
    5. Si saldo_total == 0, marca el crédito como PAGADO.
    Todo en una sola transacción.
    """
    query_credito = """
        SELECT
            cr.id, cr.cupo_id,
            cr.saldo_capital, cr.saldo_intereses, cr.saldo_mora,
            cr.saldo_total, cr.estado
        FROM banking.creditos cr
        WHERE cr.id = %(id)s AND cr.estado NOT IN ('PAGADO', 'ANULADO')
        FOR UPDATE;
    """
    query_cuotas = """
        SELECT id, numero_cuota, saldo_pendiente, valor_capital,
               valor_interes, valor_pagado, interes_mora_causado, estado
        FROM banking.cuotas_credito
        WHERE credito_id = %(credito_id)s
          AND estado IN ('PENDIENTE', 'EN_MORA', 'PAGADA_PARCIAL')
          AND saldo_pendiente > 0
        ORDER BY numero_cuota;
    """
    query_upd_cuota_parcial = """
        UPDATE banking.cuotas_credito
        SET valor_pagado = valor_pagado + %(abono)s,
            estado = CASE
                WHEN (valor_pagado + %(abono)s) >= valor_total_esperado THEN 'PAGADA'
                ELSE 'PAGADA_PARCIAL'
            END::banking.estado_cuota,
            fecha_pago_real = CASE
                WHEN (valor_pagado + %(abono)s) >= valor_total_esperado THEN now()
                ELSE NULL
            END,
            updated_at = now()
        WHERE id = %(cuota_id)s;
    """
    query_detalle = """
        INSERT INTO banking.detalle_pagos (pago_id, cuota_id, valor_aplicado)
        VALUES (%(pago_id)s, %(cuota_id)s, %(valor)s);
    """
    query_pago = """
        INSERT INTO banking.pagos (
            credito_id, cupo_id,
            valor_pago, valor_capital_abonado, valor_interes_abonado,
            valor_mora_abonado, valor_seguro_abonado,
            fecha_pago, canal_pago, referencia_externa,
            saldo_credito_antes, saldo_credito_despues,
            cupo_liberado, usuario
        ) VALUES (
            %(credito_id)s, %(cupo_id)s,
            %(valor_pago)s, %(capital)s, %(interes)s,
            %(mora)s, 0,
            now(), %(canal)s, %(ref)s,
            %(saldo_antes)s, %(saldo_despues)s,
            %(cupo_liberado)s, %(usuario)s
        )
        RETURNING id, valor_pago, cupo_liberado, saldo_credito_despues;
    """
    query_upd_credito = """
        UPDATE banking.creditos
        SET 
            saldo_capital   = GREATEST(saldo_capital   - %(capital)s,   0),
            saldo_intereses = GREATEST(saldo_intereses - %(interes)s, 0),
            saldo_mora      = GREATEST(saldo_mora      - %(mora)s,      0),
            numero_cuotas_pagadas = numero_cuotas_pagadas + %(cuotas_completas)s,
            fecha_ultimo_pago_real = now(),
            estado = CASE
                WHEN (saldo_capital - %(capital)s) <= 0 THEN 'PAGADO'
                ELSE estado
            END,
            fecha_pago_total = CASE
                WHEN (saldo_capital - %(capital)s) <= 0 THEN now()
                ELSE NULL
            END,
            updated_at = now()
        WHERE id = %(credito_id)s;
    """
    query_upd_cupo = """
        UPDATE banking.cupos
        SET cupo_disponible = cupo_disponible + %(cupo_liberado)s,
            cupo_utilizado  = GREATEST(0, cupo_utilizado - %(cupo_liberado)s),
            fecha_ultimo_pago = now(),
            updated_at = now()
        WHERE id = %(cupo_id)s;
    """
    query_mov_credito = """
        INSERT INTO banking.movimientos_cupo (
            cupo_id, credito_id, pago_id, tipo_movimiento,
            valor, saldo_cupo_antes, saldo_cupo_despues,
            descripcion, usuario
        )
        SELECT
            cu.id, %(credito_id)s, %(pago_id)s, 'CREDITO_PAGO',
            %(cupo_liberado)s,
            cu.cupo_disponible - %(cupo_liberado)s,
            cu.cupo_disponible,
            'Liberacion cupo por pago', %(usuario)s
        FROM banking.cupos cu
        WHERE cu.id = %(cupo_id)s;
    """

    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:

            # 1. Crédito
            cur.execute(query_credito, {"id": data.credito_id})
            credito = cur.fetchone()
            if not credito:
                raise ValueError("Crédito no encontrado o ya pagado/anulado.")

            saldo_antes = float(credito["saldo_total"])
            restante = data.valor_pago

            # 2. Cuotas pendientes
            cur.execute(query_cuotas, {"credito_id": data.credito_id})
            cuotas = cur.fetchall()

            total_capital = 0.0
            total_interes = 0.0
            total_mora    = 0.0
            cuotas_completas = 0
            distribuciones: list = []  # (cuota_id, abono)

            for cuota in cuotas:
                if restante <= 0:
                    break
                pendiente = float(cuota["saldo_pendiente"])
                abono = min(restante, pendiente)
                restante = round(restante - abono, 2)

                # Desglose proporcional: mora → interés → capital
                mora_c = min(abono, float(cuota["interes_mora_causado"]))
                abono -= mora_c
                if pendiente != float(cuota["valor_interes"]):
                    interes_c = min(abono, float(cuota["valor_interes"]))
                else:  # Si no hay interés pendiente, el abono va directo a capital
                    interes_c = 0.0
                abono -= interes_c
                capital_c = abono

                total_mora    += mora_c
                total_interes += interes_c
                total_capital += capital_c

                abono_total = mora_c + interes_c + capital_c
                if abono_total >= pendiente:
                    cuotas_completas += 1

                distribuciones.append((str(cuota["id"]), round(abono_total, 2)))

                cur.execute(query_upd_cuota_parcial, {
                    "abono": round(abono_total, 2),
                    "cuota_id": str(cuota["id"]),
                })

            total_capital = round(total_capital, 2)
            total_interes = round(total_interes, 2)
            total_mora    = round(total_mora, 2)
            cupo_liberado = total_capital  # Solo el capital libera cupo
            saldo_despues = round(saldo_antes - data.valor_pago + restante, 2)

            # 3. Insertar pago
            cur.execute(query_pago, {
                "credito_id": data.credito_id,
                "cupo_id":    str(credito["cupo_id"]),
                "valor_pago": data.valor_pago,
                "capital":    total_capital,
                "interes":    total_interes,
                "mora":       total_mora,
                "canal":      data.canal_pago,
                "ref":        data.referencia_externa,
                "saldo_antes":   saldo_antes,
                "saldo_despues": max(0.0, saldo_despues),
                "cupo_liberado": cupo_liberado,
                "usuario":    data.usuario,
            })
            pago = dict(cur.fetchone())
            pago_id = str(pago["id"])

            # 4. Detalle pagos
            for cuota_id, valor_apl in distribuciones:
                cur.execute(query_detalle, {
                    "pago_id": pago_id,
                    "cuota_id": cuota_id,
                    "valor": valor_apl,
                })

            # 5. Actualizar crédito
            cur.execute(query_upd_credito, {
                "capital":          total_capital,
                "interes":          total_interes,
                "mora":             total_mora,
                "cuotas_completas": cuotas_completas,
                "credito_id":       data.credito_id,
            })

            # 6. Liberar cupo
            cur.execute(query_upd_cupo, {
                "cupo_liberado": cupo_liberado,
                "cupo_id":       str(credito["cupo_id"]),
            })

            # 7. Movimiento de cupo
            cur.execute(query_mov_credito, {
                "credito_id":    data.credito_id,
                "pago_id":       pago_id,
                "cupo_liberado": cupo_liberado,
                "usuario":       data.usuario,
                "cupo_id":       str(credito["cupo_id"]),
            })

            pago["capital_abonado"]  = total_capital
            pago["interes_abonado"]  = total_interes
            pago["mora_abonada"]     = total_mora
            pago["cuotas_saldadas"]  = cuotas_completas
            return pago
