# NNN · Título de la funcionalidad

| Campo | Valor |
|---|---|
| **Número** | NNN |
| **Estado** | Borrador · En revisión · Aprobada · Implementada |
| **Autor** | Nombre |
| **Revisor** | Nombre de otro integrante |
| **Fecha** | AAAA-MM-DD |
| **Apps afectadas** | `catalogo`, `ventas`… |
| **Rama** | `feature/NNN-descripcion-corta` |
| **Pull request** | Enlace, una vez abierto |

---

## 1. Problema

Qué necesidad del negocio resuelve esto. En lenguaje de negocio, no técnico.
Dos o tres párrafos como máximo.

## 2. Alcance

**Incluye:**
- Lo que esta spec sí cubre

**No incluye:**
- Lo que queda explícitamente fuera, y en qué spec futura se atenderá

## 3. Reglas de negocio

Numeradas, para poder referenciarlas desde el código y las pruebas.

1. Una propiedad solo puede venderse si está en estado `DISPONIBLE`.
2. Al firmarse un contrato de venta, la propiedad pasa a `VENDIDA`.
3. …

## 4. Modelo de datos

Entidades nuevas o modificadas, con sus campos, tipos, constraints y
relaciones. Si no hay cambios al modelo, decirlo explícitamente.

## 5. API

| Método | Ruta | Descripción | Permiso |
|---|---|---|---|
| GET | `/api/v1/recurso/` | Listar con filtros | Autenticado |
| POST | `/api/v1/recurso/` | Crear | Rol GERENTE |

**Ejemplo de petición:**

```json
{ }
```

**Ejemplo de respuesta:**

```json
{ }
```

**Errores posibles:**

| Código | Situación | HTTP |
|---|---|---|
| `PROPIEDAD_NO_DISPONIBLE` | Se intenta vender una propiedad no disponible | 409 |

## 6. Servicios y selectores

Firmas de las funciones que se van a crear, con una línea de qué hace cada una.

```python
def registrar_venta(*, propiedad, cliente, agente, monto, moneda, usuario) -> ContratoVenta
def listar_contratos_vigentes(*, agente_id=None, pais_id=None) -> QuerySet[ContratoVenta]
```

## 7. Auditoría

Qué acciones se registran y con qué valores. Si la funcionalidad no escribe,
indicar que no aplica.

## 8. Criterios de aceptación

Lista verificable. Cada punto debe poder marcarse como cumplido o no cumplido,
sin ambigüedad.

- [ ] Se puede crear un contrato de venta desde una cotización aprobada
- [ ] Al crear el contrato, la propiedad cambia a `VENDIDA`
- [ ] Se genera el `EventoPropiedad` correspondiente
- [ ] Intentar vender una propiedad arrendada devuelve 409 con el código correcto
- [ ] La operación queda registrada en la bitácora de auditoría

## 9. Pruebas

Qué se va a probar y en qué nivel.

| Nivel | Caso |
|---|---|
| Servicio | Venta exitosa sobre propiedad disponible |
| Servicio | Venta rechazada sobre propiedad ya vendida |
| API | 201 al crear, 409 ante propiedad no disponible |

## 10. Decisiones y alternativas descartadas

Qué se consideró y por qué se eligió este camino. **Esta sección es la que se
usa en la defensa oral**, así que conviene llenarla con honestidad.

## 11. Trabajo con agentes de IA

Si se usó Claude Code, Codex u otro agente: qué partes se generaron, qué se
corrigió a mano y qué se descartó. Es la evidencia del proceso que pide el
curso.
