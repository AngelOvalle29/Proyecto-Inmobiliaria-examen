# 025 · Catálogo público del asistente generado desde la base

| Campo | Valor |
|---|---|
| **Número** | 025 |
| **Estado** | Implementada |
| **Autor** | Douglas Gerardo Morales Velásquez (rol A) |
| **Revisor** | Por asignar |
| **Fecha** | 2026-11-03 |
| **Apps afectadas** | `ia` (servicios y un módulo nuevo `catalogo_publico.py`); lee `catalogo` por sus selectores |
| **Rama** | `feature/025-catalogo-generado` |
| **Pull request** | Enlace, una vez abierto |

---

## 1. Problema

El asistente responde sobre propiedades gracias al documento "Catálogo público
de propiedades", que se escribió a mano con la disponibilidad del 3 de
noviembre. Cada venta, reserva o arrendamiento lo deja desactualizado: si en la
defensa se vende el apartamento A-103, el asistente seguirá diciendo que está
disponible hasta que alguien edite y vuelva a subir el documento.

## 2. Alcance

**Incluye:**
- Generar el catálogo desde la base, con las propiedades públicas
  (`es_publica`), sus unidades, precios y estado actual.
- Revisarlo antes de cada pregunta al asistente y, si el inventario cambió,
  regenerarlo e indexarlo en ese momento, para que la respuesta ya lo use.
- Registrar en la bitácora del agente cuándo se regeneró.

**No incluye:**
- Que el modelo llame herramientas por su cuenta (*function calling*) ni el
  modo interno para empleados: quedan para otra spec.
- Datos de propiedades no públicas, de clientes o de contratos.

## 3. Reglas de negocio

1. **Solo lo público.** El catálogo incluye las propiedades activas con
   `es_publica`, y nada más (spec 005, regla 5).
2. **Siempre al día.** Antes de responder, el asistente arma el catálogo con
   los datos actuales. Si el texto es distinto del guardado, lo reemplaza
   (nueva versión) y lo indexa en ese momento, sin pasar por la cola: la
   pregunta que sigue a una venta ya ve el cambio.
3. **Sin cambios, sin trabajo.** Si el texto es igual, no se escribe ni se
   indexa nada: el costo es una lectura del inventario.
4. **El texto depende solo de los datos.** No lleva la fecha ni la hora de
   generación: si las llevara, cambiaría en cada pregunta y se reindexaría
   siempre.
5. **Un solo documento.** Se llama "Catálogo público de propiedades". Si ya
   existe uno con ese título, subido a mano, el generado lo reemplaza. Si un
   administrador lo desactivó, no se vuelve a crear ni a activar.
6. **Sin propiedades públicas, sin documento.** Si no hay ninguna, no se crea.
7. **Bitácora.** Cuando la consulta regenera el catálogo, la bitácora del
   agente lo anota en `herramientas_invocadas`.

## 4. Modelo de datos

Sin cambios: el catálogo es un `DocumentoRAG` de tipo `FICHA_PROPIEDAD`.

## 5. API

Sin cambios. `POST /api/v1/agente/consultas/` tarda uno o dos segundos más
solo en la pregunta que sigue a un cambio del inventario.

## 6. Servicios y selectores

- `ia/catalogo_publico.py`: `armar_catalogo(propiedades, unidades)`, una
  función pura que convierte los datos en Markdown, con una sección `##` por
  propiedad para que cada cita apunte a su ficha.
- `ia/services.py`:
  - `sincronizar_catalogo_publico() -> bool` aplica las reglas 2 a 6 y
    devuelve si regeneró el documento. Reutiliza `crear_documento_rag`,
    `actualizar_contenido_documento` e `indexar_documento`.
  - `responder_consulta_publica` la llama antes de buscar fragmentos.
- Lee `catalogo` solo con `listar_propiedades_publicas` y `listar_unidades`
  (docs/arquitectura.md §3): `catalogo` no conoce a `ia`.

## 7. Auditoría

Crear o actualizar el documento y su indexación quedan en la bitácora del
sistema, como cualquier documento del asistente (spec 020). La bitácora del
agente anota la regeneración (regla 7).

## 8. Criterios de aceptación

- [x] Con propiedades públicas, la primera pregunta crea e indexa el catálogo
- [x] Una pregunta sin cambios en el inventario no reindexa
- [x] Vender o reservar una unidad cambia el catálogo en la pregunta siguiente
- [x] Una propiedad no pública no aparece
- [x] Un catálogo desactivado no se vuelve a crear
- [x] `pytest`, `ruff` pasan

## 9. Pruebas

| Nivel | Caso |
|---|---|
| Unidad | `armar_catalogo` con unidades disponibles, reservadas y vendidas, y con una propiedad sin unidades |
| Servicio | Crea, no reindexa sin cambios, reindexa tras un cambio de estado, respeta el desactivado, no crea sin propiedades públicas |
| Servicio | La consulta regenera antes de buscar y lo anota en la bitácora |

## 10. Decisiones y alternativas descartadas

- **Revisar en cada pregunta y no al cambiar el estado.** El cambio de estado
  vive en `catalogo`, que no puede llamar a `ia` sin crear una dependencia
  circular. Revisar al preguntar mantiene la dependencia en un solo sentido
  (`ia` lee `catalogo`).
- **Indexar sin la cola.** Por la cola, la pregunta inmediata a una venta
  todavía vería el texto anterior. Son pocos fragmentos: una sola llamada de
  embeddings.
- **Un documento generado y no una herramienta que el modelo llame.** Usa el
  mismo RAG y las mismas citas, sin cambiar el proveedor; las herramientas son
  el siguiente paso, con el modo interno.

## 11. Trabajo con agentes de IA

**Sesión 2026-11-03 (Claude Code, rol A).** Douglas pidió que el asistente no
se desactualizara con cada venta. El agente propuso generar el catálogo desde
la base o darle una herramienta al modelo; Douglas eligió la mejora y el
agente implementó la primera opción, por ser la que no cambia el proveedor ni
las citas.

El catálogo escrito a mano (`docs/asistente/catalogo-publico-propiedades.md`)
se quitó del repositorio: el generado ocupa su título y lo reemplaza en la
primera pregunta después del despliegue.
