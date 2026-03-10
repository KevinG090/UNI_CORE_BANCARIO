# Banking Core API

FastAPI + psycopg2 — Core bancario para gestión de clientes, cupos y créditos.

## Requisitos

- Python 3.13+
- PostgreSQL 14+ con schema `banking` ya creado

## Setup local

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# Editar .env con los datos de tu BD

uvicorn main:app --reload
```

Docs en: http://localhost:8000/docs

## Deploy en Vercel

1. Agregar las variables de entorno en Vercel (Project Settings → Environment Variables):
   - `POSTGRES_SERVER`, `POSTGRES_PORT`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`
   - `POOL_MIN_CONN=1`, `POOL_MAX_CONN=5`

2. `vercel --prod`

## Endpoints principales

### Clientes
| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/api/clientes/` | Listar clientes |
| POST | `/api/clientes/` | Crear cliente |
| GET | `/api/clientes/{id}` | Obtener cliente |
| PATCH | `/api/clientes/{id}` | Actualizar cliente |
| GET | `/api/clientes/{id}/resumen` | Vista 360° (cliente + cupo + créditos) |

### Cupos
| Método | Ruta | Descripción |
|--------|------|-------------|
| POST | `/api/cupos/` | Aprobar cupo |
| GET | `/api/cupos/{id}` | Obtener cupo |
| GET | `/api/cupos/cliente/{cliente_id}` | Cupo activo del cliente |

### Créditos & Pagos
| Método | Ruta | Descripción |
|--------|------|-------------|
| POST | `/api/creditos/compra` | Registrar compra (genera crédito) |
| GET | `/api/creditos/{id}` | Obtener crédito |
| GET | `/api/creditos/{id}/cuotas` | Plan de cuotas |
| GET | `/api/creditos/cupo/{cupo_id}` | Créditos de un cupo |
| POST | `/api/creditos/pago` | Registrar pago (parcial o total) |

## Flujo típico

```
1. POST /api/clientes/            → Crear cliente (estado: EN_ESTUDIO)
2. POST /api/cupos/               → Aprobar cupo (estado cliente → ACTIVO)
3. POST /api/creditos/compra      → Compra: usa el cupo, genera crédito + cuotas
4. GET  /api/creditos/{id}/cuotas → Ver plan de pagos
5. POST /api/creditos/pago        → Abonar (parcial o total)
```
