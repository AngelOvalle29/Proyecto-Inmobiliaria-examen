# Manual técnico

Sistema de gestión para una agencia inmobiliaria latinoamericana. Proyecto final
del curso Programación Comercial, Universidad Mesoamericana, Quetzaltenango.

> **Borrador.** La estructura es una propuesta para todo el equipo. Cada
> integrante completa su sección. Las marcadas *Pendiente* no se han escrito.

---

## 1. Descripción general

El sistema registra el ciclo de cada propiedad: compra, construcción,
documentación, avalúos, cotizaciones, venta y arrendamiento. Incluye un agente
de IA con recuperación de documentos, mensajería asíncrona, reportes exportables
y bitácoras de auditoría.

*Pendiente: el equipo completa el resumen de funcionalidades.*

## 2. Arquitectura

| Capa | Tecnología |
|---|---|
| Backend | Python 3.12, Django 5, Django REST Framework |
| Base de datos | PostgreSQL 16 con pgvector |
| Mensajería | RabbitMQ y Celery |
| Frontend | React 19, Vite y TypeScript |
| Despliegue | Render, Neon, CloudAMQP y Vercel |

Cada dominio es una app de Django, con las mismas capas:

```
views.py / serializers.py   HTTP: valida la entrada y formatea la salida
services.py                 escrituras: reglas de negocio y transacciones
selectors.py                lecturas: consultas y agregaciones
models.py                   datos: campos y constraints
```

El detalle está en `docs/arquitectura.md`, y las entidades en
`docs/modelo-datos.md`.

*Pendiente: rol A, diagrama y despliegue.*

## 3. Instalación

```bash
docker compose up -d
cd backend
python -m venv .venv
pip install -r requirements/dev.txt
python manage.py migrate
python manage.py seed_demo
python manage.py runserver
```

En otra terminal, el worker:

```bash
celery -A config worker -l info
```

Y el frontend:

```bash
cd frontend
npm install
npm run dev
```

Las variables de entorno se copian de `.env.example`. Ningún secreto va en el
repositorio.

**Pruebas:** `pytest`, desde `backend/`. En Windows fallan las pruebas que
generan PDF, porque WeasyPrint necesita librerías GTK; en la imagen de Docker
pasan.

*Pendiente: rol A, variables de producción. Si la spec 020 se fusiona, el worker
local necesita `-Q celery,documentos`.*

## 4. Catálogo, avalúos y documentos

*Pendiente: rol A.*

## 5. CRM, ventas y arrendamientos (rol B)

### 5.1 Entidades

| App | Entidades |
|---|---|
| `crm` | `Cliente`, `Agente`, `Cotizacion` |
| `ventas` | `ContratoVenta`, `CuotaPago` |
| `arrendamientos` | `ContratoArrendamiento`, `PagoRenta` |

Reglas completas: `specs/004-crm-clientes-agentes.md`,
`specs/007-cotizaciones-ventas.md` y `specs/008-arrendamientos.md`. Pantallas:
`specs/012-pantallas-bloque-b.md`.

### 5.2 Flujo de una venta

```
BORRADOR → ENVIADA → APROBADA → contrato VIGENTE → LIQUIDADO
                  ↘ RECHAZADA
```

| Paso | Servicio | Efecto en el bien |
|---|---|---|
| Aprobar cotización | `aprobar_cotizacion` | De `DISPONIBLE` a `RESERVADA` |
| Rechazar una aprobada | `rechazar_cotizacion` | De `RESERVADA` a `DISPONIBLE` |
| Firmar contrato | `firmar_contrato` | A `VENDIDA` |
| Anular contrato sin pagos | `anular_contrato` | De `VENDIDA` a `DISPONIBLE` |

- Un contrato se firma desde una cotización aprobada o sin ella.
- De contado, nace `LIQUIDADO` y sin cuotas.
- Financiado, genera cuotas fijas por sistema francés:
  `cuota = P · i / (1 − (1 + i)^−n)`. La última ajusta los centavos.
- Un pago puede ser parcial. Al pagar la última cuota, el contrato pasa a
  `LIQUIDADO`.

### 5.3 Flujo de un arrendamiento

| Acción | Servicio | Efecto |
|---|---|---|
| Firmar | `firmar_arrendamiento` | Genera todos los pagos; el bien pasa a `ARRENDADA` |
| Cobrar | `registrar_pago_renta` | Pago completo, con recargo si pasó la gracia |
| Renovar | `renovar_arrendamiento` | Contrato nuevo; el anterior queda `RENOVADO` |
| Rescindir | `rescindir_arrendamiento` | Cancela los pagos posteriores; el bien queda `DISPONIBLE` |
| Finalizar | `finalizar_arrendamiento` | Pasa a `VENCIDO`; el bien queda `DISPONIBLE` |

### 5.4 Permisos

| Rol | Clientes y cotizaciones | Firmar | Registrar pagos | Anular, rescindir o finalizar |
|---|---|---|---|---|
| `ADMINISTRADOR`, `GERENTE` | Todos | Sí | Sí | Sí |
| `AGENTE` | Su cartera | En su cartera | No | No |
| `CONTABILIDAD` | Lectura | No | Sí | No |
| `CONSULTA` | Lectura | No | No | No |

La cartera se aplica en `listar_clientes_visibles`. Un agente que pide algo ajeno
recibe 404, no 403, para no confirmar que existe.

### 5.5 Decisiones de diseño

- **La mora y el vencimiento se calculan.** No se guardan, para que nunca queden
  desactualizados.
- **Cada contrato y pago guarda su tasa al dólar.** Así un reporte no recalcula
  el pasado.
- **La comisión se guarda al firmar.** Con cotización, es del agente que cotizó.
- **Los contratos no se borran.** Anular es un estado.
- **Toda escritura se audita** con `registrar_auditoria`, dentro de la misma
  transacción.
- **`select_for_update`** protege los pagos simultáneos: el segundo espera y lee
  el saldo que dejó el primero.

### 5.6 API

| Recurso | Ruta |
|---|---|
| Clientes | `/api/v1/clientes/` |
| Agentes | `/api/v1/agentes/` |
| Cotizaciones | `/api/v1/cotizaciones/` |
| Contratos de venta | `/api/v1/contratos-venta/` |
| Contratos de arrendamiento | `/api/v1/contratos-arrendamiento/` |

La documentación completa de cada endpoint está en `/api/docs/`.

### 5.7 Datos de demostración

`seed_demo` carga agentes, clientes, contratos y cotizaciones ficticios, con
fechas relativas a hoy, para que siempre haya cuotas pagadas, parciales y en
mora. Las unidades `A-103` y `A-203` quedan libres para mostrar una venta en
vivo. Los comandos no duplican datos.

## 6. Compras y construcción

*Pendiente: rol C.*

## 7. Agente de IA y RAG

*Pendiente: rol C.*

## 8. Mensajería

*Pendiente: roles A y D.*

## 9. Auditoría

*Pendiente: rol D.*

## 10. Reportes

Capa genérica: *pendiente, rol D.*

### 10.1 Reportes comerciales (rol B)

*Disponibles cuando se fusione #80.*

| Código | Reporte | Contenido |
|---|---|---|
| R01 | Ventas por período | Contratos no anulados; totales por moneda, y por mes y país |
| R02 | Desempeño por agente | Cotizaciones, conversión, ventas y comisión |
| R03 | Embudo de cotizaciones | Conteos por estado y tasas |
| R04 | Ranking de clientes | Ordenado por venta en dólares, con saldos actuales |
| R10 | Estado de cuenta | Cuotas y rentas, con exigible, pagado y saldo |
| R11 | Morosidad | Deuda vencida por tramo y moneda |

Todos respetan la cartera, en el detalle y en los totales. Las reglas están en
`specs/021-reportes-restantes-power-bi.md`.

## 11. Power BI

*Pendiente: rol D.*

## 12. Despliegue

*Pendiente: rol A. Ver `specs/002-despliegue.md`.*

## 13. Uso de agentes de IA

*Pendiente: el equipo acuerda cómo declararlo. Cada spec tiene su §11.*
