# 014 · Pantallas del catálogo: ficha de propiedad, unidades, avalúos, documentos y tipos

| Campo | Valor |
|---|---|
| **Número** | 014 |
| **Estado** | Implementada |
| **Autor** | Douglas Gerardo Morales Velásquez (rol A) |
| **Revisor** | Marco André Bolaños Rojas (Lilfacce) |
| **Fecha** | 2026-10-31 |
| **Apps afectadas** | `frontend/` (`paginas/catalogo` y `api/catalogo`); en el backend, solo la búsqueda de unidades en `catalogo` |
| **Rama** | `feature/014-pantallas-catalogo` |
| **Pull request** | DouGMV/Proyecto-Inmobiliaria#67 (spec aprobada en #57) |

---

## 1. Problema

El catálogo tiene su API completa (specs 003 y 011), pero en pantalla solo hay
la lista de propiedades y el formulario para crear una (spec 010). Falta lo que
se muestra en la demostración: ver una propiedad con sus unidades, su historial
de avalúos y sus documentos; editarla; y administrar los tipos de propiedad.

## 2. Alcance

**Incluye:**
- **Ficha de propiedad** con cuatro pestañas: datos, unidades, avalúos y
  documentos.
- **Editar una propiedad.**
- **Unidades:** agregar, editar, cambiar de estado y desactivar.
- **Avalúos:** registrar y desactivar. No se editan (spec 011, regla 3).
- **Documentos:** subir, descargar, editar sus datos y desactivar.
- **Tipos de propiedad:** lista, crear, editar y desactivar.
- **Backend:** `GET /propiedades/{id}/unidades/` acepta `?buscar=` por código
  (regla 11). Es el único cambio en el backend.

Todo con los componentes de la spec 010, y siguiendo `ListaPropiedades`,
`NuevaPropiedad` y `DialogoCambiarEstado` como ejemplo.

**No incluye:**
- Mapa, línea de tiempo (`EventoPropiedad`) y gráficas: siguen en "solo si
  sobra tiempo" del plan.
- Otros cambios en el backend: los demás endpoints ya existen.
- Pruebas automáticas del frontend (spec 010, §10).

## 3. Reglas

1. **La ficha es una página**, `/catalogo/propiedades/{id}`, y cada pestaña
   carga sus datos solo cuando se abre: una propiedad con 60 unidades no debe
   pedir sus documentos si nadie los mira.
   - La pestaña elegida va en la URL (`?pestana=documentos`), así se puede
     recargar o compartir.
2. **Permisos** (specs 003 y 011):
   - todos leen y descargan;
   - escriben `ADMINISTRADOR` y `GERENTE`;
   - los tipos de propiedad, solo `ADMINISTRADOR`.
   Las acciones y botones que el rol no puede usar no se muestran. El backend
   igual responde 403.
3. **Unidades solo si el tipo las admite.** La pestaña Unidades aparece solo
   cuando el tipo de la propiedad tiene `requiere_unidades`. Si no, la API
   respondería 409 `TIPO_SIN_UNIDADES`.
4. **Las acciones que piden datos son diálogos de la página**, con
   `FormularioDatos` dentro: nueva unidad, editar unidad, registrar avalúo,
   subir documento y editar documento. Cambiar el estado de una unidad reutiliza
   el diálogo del catálogo.
5. **Subir un documento** usa un campo de archivo nuevo en `FormularioDatos`
   (`tipo: 'archivo'`), que envía el formulario como `multipart/form-data`.
   - El navegador revisa la extensión y el tamaño (hasta 10 MB) para avisar
     antes de subir.
   - Esa revisión del navegador es la que aparece **junto al campo**.
   - La regla de verdad es la de la API, que revisa el contenido (spec 011,
     regla 6). Su error, 400 `ARCHIVO_NO_PERMITIDO`, aparece **arriba del
     formulario**. Es un error de dominio con su propio código, y desde #56
     `FormularioDatos` solo pone junto a un campo los errores `VALIDACION`
     (observación de B en la revisión).
6. **Descargar** pide la URL firmada en el momento del clic y la abre en una
   pestaña nueva.
   - La URL vence a los 5 minutos (spec 011, regla 10), así que **nunca se
     guarda en caché** ni se muestra como enlace fijo.
7. **Vencimientos:**
   - un documento vencido se marca en rojo;
   - uno que vence en los próximos 30 días, en ámbar.
   Se calcula con la fecha de hoy al mostrarlo, como la mora de ventas.
8. **Avalúos:** del más reciente al más antiguo, con su valor y su moneda. El
   primero se resalta como el valor vigente de la propiedad.
9. **Editar una propiedad** reutiliza los campos de Nueva propiedad, con los
   valores actuales. La ciudad muestra la actual con `etiquetaInicial`
   (spec 010, regla 15). El estado no se edita aquí: tiene su propia acción
   (spec 003, regla 7).
10. **Errores de la API**, como en la spec 010 (regla 8):
    - un 409 (`PROPIEDAD_CON_UNIDADES`, `DOCUMENTO_EN_USO`,
      `UNIDAD_DUPLICADA`…) arriba de la tabla o del formulario;
    - un 400 de validación, junto a su campo.
11. **Búsqueda de unidades en la API** (pedida por B en #56).
    `GET /propiedades/{id}/unidades/?buscar=` filtra por código, sin
    distinguir mayúsculas. Así `useOpcionesUnidad` (spec 012) busca en la API y
    no solo en la primera página. Es un filtro en `catalogo/filters.py`, como
    el de las propiedades.

## 4. Modelo de datos

Sin cambios. Los tipos salen de `npm run gen:api`.

## 5. Pantallas y rutas

| Ruta | Pantalla | Roles |
|---|---|---|
| `/catalogo/propiedades` | La lista actual, con la acción **Ver ficha** en cada fila | Todos |
| `/catalogo/propiedades/{id}` | **Ficha**, pestaña *Datos*: datos generales y el último avalúo. Botones Editar y Cambiar estado | Todos (escriben admin y gerente) |
| `…?pestana=unidades` | `TablaDatos` de unidades: código, nivel, área, habitaciones, baños, estado, precio. Acciones: Editar, Cambiar estado, Desactivar. Botón Nueva unidad | Todos (escriben admin y gerente); solo si el tipo admite unidades |
| `…?pestana=avaluos` | Historial: fecha, valor, perito, metodología. Acción: Desactivar. Botón Registrar avalúo | Todos (escriben admin y gerente) |
| `…?pestana=documentos` | Tipo, nombre, emisión, vencimiento (marcado), emisor. Acciones: Descargar, Editar datos, Desactivar. Botón Subir documento. Filtro por tipo | Todos (escriben admin y gerente) |
| `/catalogo/propiedades/{id}/editar` | `FormularioDatos` con los valores actuales | Admin, gerente |
| `/catalogo/tipos` | `TablaDatos` de tipos: nombre, descripción, admite unidades. Acciones: Editar (diálogo), Desactivar. Botón Nuevo tipo (diálogo) | Todos leen; escribe solo admin |

**Menú**, grupo *Catálogo*: Propiedades y Tipos de propiedad. "Nueva
propiedad" pasa al botón de la lista, como en la spec 012.

## 6. Componentes y módulos

```
src/api/catalogo/consultas.ts    + usePropiedad, useAvaluos, useDocumentos; useUnidadesDePropiedad
                                   (ya existe, de #56) se amplía con página y búsqueda,
                                   en vez de crear otro hook con la misma clave de caché
src/api/catalogo/mutaciones.ts   + editar propiedad; crear, editar y desactivar unidad;
                                   registrar y desactivar avalúo; subir, editar, desactivar
                                   y descargar documento; crear, editar y desactivar tipo
src/componentes/comunes/FormularioDatos.tsx   + campo tipo 'archivo' (regla 5)
src/lib/formato.ts               + estadoVencimiento(fecha) → 'vencido' | 'por-vencer' | 'vigente'
src/paginas/catalogo/
  FichaPropiedad.tsx             pestañas (regla 1)
  PestanaDatos.tsx, PestanaUnidades.tsx, PestanaAvaluos.tsx, PestanaDocumentos.tsx
  EditarPropiedad.tsx            (comparte los campos con NuevaPropiedad)
  DialogoUnidad.tsx, DialogoAvaluo.tsx, DialogoDocumento.tsx
  ListaTiposPropiedad.tsx, DialogoTipoPropiedad.tsx
```

`NuevaPropiedad` y `EditarPropiedad` comparten la declaración de los campos y el
esquema en un solo módulo (`camposPropiedad.ts`), para no repetirlos.

## 7. Auditoría

No aplica: cada acción llama a un endpoint que ya audita (specs 003 y 011).

## 8. Criterios de aceptación

- [x] La ficha abre en *Datos*; cada pestaña carga sus datos solo al abrirla, y
      la pestaña se conserva al recargar
- [x] Una casa no muestra la pestaña Unidades; un edificio sí
- [x] Agregar una unidad con un código repetido muestra el 409 de la API
- [x] Desactivar una propiedad con unidades activas muestra el 409 de la API
- [x] Registrar un avalúo lo pone primero en el historial; uno con fecha futura
      muestra el error junto al campo
- [ ] Subir un PDF lo agrega a la lista, y Descargar lo abre en una pestaña nueva
- [x] Un archivo de otra extensión, o de más de 10 MB, muestra el error del
      navegador junto al campo, sin subirlo
- [x] Un archivo cuyo contenido no es PDF, JPG ni PNG (un `.exe` renombrado)
      muestra arriba del formulario el 400 `ARCHIVO_NO_PERMITIDO` de la API
- [x] `?buscar=` en las unidades de una propiedad filtra por código, y la
      búsqueda de unidades de la spec 012 encuentra las que no están en la
      primera página
- [x] Un documento vencido se ve en rojo y uno por vencer en ámbar
- [x] Desactivar un documento que respalda un avalúo muestra el 409 de la API
- [x] Editar una propiedad muestra su ciudad actual y guarda los cambios
- [x] Un gerente no ve las acciones de tipos de propiedad; un administrador sí
- [x] `CONSULTA` ve la ficha, las pestañas y Descargar, sin ningún botón de
      escritura
- [ ] En producción, subir y descargar funcionan contra Supabase
- [x] `npm run lint`, `npm run typecheck` y `npm run build` pasan

## 9. Pruebas

| Nivel | Caso |
|---|---|
| Manual, local | Cada criterio de §8 con `seed_demo` y un usuario por rol |
| Manual, producción | Subir y descargar un documento contra Supabase; recorrer la ficha |
| Estático | `typecheck` con los tipos generados |

## 10. Decisiones y alternativas descartadas

- **Pestañas en una página, no una página por sección.** La ficha es lo que
  más se muestra en la defensa (`docs/frontend.md` §4). Con pestañas, todo lo
  de una propiedad queda en un solo lugar y en una sola dirección.
- **Carga por pestaña.** Pedir todo al abrir la ficha haría cuatro consultas
  aunque solo se mire una pestaña. Con TanStack Query, una pestaña ya visitada
  vuelve a abrirse sin esperar.
- **Campo de archivo dentro de `FormularioDatos`**, y no un formulario aparte:
  así la subida también muestra los errores de la API junto al campo, como el
  resto (spec 010, regla 8).
- **La URL de descarga no se guarda.** Vence a los 5 minutos; guardarla
  daría enlaces rotos que parecen funcionar.

## 11. Trabajo con agentes de IA

**Sesión 2026-10-31 (Claude Code, rol A).** El agente redactó el borrador a
partir de:
- las specs 003, 010, 011 y 012;
- `docs/frontend.md` §4;
- las rutas del catálogo en `backend/apps/catalogo/urls.py`, para confirmar que
  no hace falta tocar el backend.

**Revisión de B en #57.** Pidió dos ajustes antes de aprobar, ya aplicados:
- **La búsqueda de unidades:** A la había prometido en #56, pero la spec decía
  "sin cambios en el backend". Se incluye aquí (regla 11 y criterio de §8).
- **El error de contenido de un archivo** sale arriba del formulario, no junto
  al campo (regla 5 y criterios de §8).

También sugirió ampliar `useUnidadesDePropiedad` en vez de crear `useUnidades`
con la misma clave de caché (§6).

**Plan de implementación:**
1. La ficha con sus pestañas, la pestaña Datos y Editar propiedad, que depende
   de `etiquetaInicial` (#52).
2. Unidades, con la búsqueda `?buscar=` en la API (backend) y su prueba.
3. Avalúos y documentos, con el campo de archivo y la descarga.
4. Tipos de propiedad, el menú y la verificación de §8 en local y en
   producción.

**Ajustes durante la implementación (incremento 3, 2026-10-31):**
- **Quién arma el `multipart/form-data`.** El campo `'archivo'` de
  `FormularioDatos` solo guarda el `File` elegido; el `FormData` lo arma la
  mutación `useSubirDocumento`. Así `FormularioDatos` no sabe nada de cómo se
  envía cada entidad, igual que con las demás. La revisión de extensión y
  tamaño va en el esquema de Zod de la pantalla, y su error sale junto al
  campo (regla 5).
- **Un cambio de una línea en el backend**, además de la regla 11:
  `AvaluoSerializer.documento` lleva `allow_null=True`. No cambia lo que
  responde la API; corrige el esquema, que decía que el documento siempre
  viene, y con él el tipo generado del frontend.
- **Descargar con la ventana bloqueada.** El navegador solo deja abrir una
  pestaña durante el clic, así que se abre antes de pedir la URL. Si el
  navegador la bloquea igual, el documento se abre en la misma pestaña.
- **La pestaña Datos muestra el último avalúo** (§5) con la misma consulta que
  la pestaña Avalúos.

**Verificación local (incremento 4, 2026-11-01).** Se recorrió §8 con un
gerente, un usuario de consulta y un administrador de prueba. Quedan dos
criterios sin marcar:
- **Descargar en una pestaña nueva:** el panel del navegador del agente
  bloquea las ventanas nuevas, así que usó el respaldo (abrir en la misma
  pestaña) y el navegador ofreció descargar el PDF: A lo confirmó. Falta ver
  la pestaña nueva en un navegador normal.
- **Subir y descargar en producción**, contra Supabase.
