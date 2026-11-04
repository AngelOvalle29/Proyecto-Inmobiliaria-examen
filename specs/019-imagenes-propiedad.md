# 019 · Imágenes de las propiedades

| Campo | Valor |
|---|---|
| **Número** | 019 |
| **Estado** | Implementada y verificada en producción (2026-11-03) |
| **Autor** | Douglas (rol A) |
| **Revisor** | Marco André Bolaños Rojas (Lilfacce), aprobó la spec en DouGMV/Proyecto-Inmobiliaria#68 |
| **Fecha** | 2026-11-01 |
| **Apps afectadas** | `catalogo` (modelo, servicios, selectores, API) y `frontend/` (`paginas/catalogo`) |
| **Rama** | `feature/019-imagenes-propiedad` |
| **Pull request** | — |

---

## 1. Problema

Las propiedades del catálogo no tienen fotos. Un gerente que revisa el
inventario, o un agente que prepara una cotización, solo ve datos: no puede
mostrarle a un cliente cómo es el edificio o el terreno, y en la lista todas
las propiedades se ven iguales.

Se necesita una galería por propiedad, con una foto de portada que identifique
a la propiedad en la lista.

## 2. Alcance

**Incluye:**
- **Galería en la ficha:** una pestaña *Imágenes* para subir, ver, describir,
  ordenar, elegir la portada y desactivar.
- **Portada en la lista de propiedades:** una miniatura en cada fila.
- **Backend:** modelo `ImagenPropiedad`, sus servicios auditados y su API.

Usa lo que dejaron las specs 011 y 014: el almacenamiento en Supabase, la
revisión del contenido por sus primeros bytes, la URL firmada y el campo
`'archivo'` de `FormularioDatos`.

**No incluye:**
- **Imágenes en el PDF de la cotización:** queda para "solo si sobra tiempo".
- **Imágenes de las unidades:** las del edificio bastan por ahora.
- **Fotos del avance de obra:** si se quieren, van en la spec del bloque C
  (017 o 018).
- **La consulta pública:** si el equipo la hace, podrá usar la portada.
- **Recortar o reducir las imágenes (miniaturas):** pediría Pillow, una
  dependencia nueva (§10). El navegador las muestra reducidas con CSS.
- **Imágenes en `seed_demo`:** el comando subiría archivos a Supabase cada vez
  que se carga la demo. Las de la demostración se suben a mano.

## 3. Reglas de negocio

**Archivos**

1. **Archivos aceptados:** JPG o PNG, de hasta **5 MB**.
   - El tipo se comprueba por el contenido, con las mismas firmas que los
     documentos (spec 011, regla 6).
   - El límite es menor que el de los documentos porque una propiedad tiene
     varias fotos y el plan gratuito de Supabase tiene 1 GB.
2. **Hasta 10 imágenes activas por propiedad.** La undécima responde 409
   `LIMITE_IMAGENES`. Desactivar una libera su lugar.
3. **El archivo se guarda con un nombre generado:**
   `imagenes/<código de propiedad>/<uuid>.<extensión>`, como los documentos
   (spec 011, regla 8).
4. **El archivo no se reemplaza.** Se editan la descripción y el orden; una foto
   distinta es una imagen nueva.
5. **Desactivar una imagen no borra su archivo** (`CLAUDE.md` §7).

**Portada y orden**

6. **Una propiedad con imágenes tiene exactamente una portada.**
   - La primera imagen que se sube queda como portada.
   - **Marcar portada** pasa la marca de la portada anterior a la elegida, en una
     sola transacción.
   - Al desactivar la portada, pasa a ser portada la siguiente según el orden.
     Si no queda ninguna, la propiedad se queda sin portada.
7. **Orden:** cada imagen tiene un número de orden. La galería se muestra por
   orden y, a igual orden, por fecha de subida. Una imagen nueva va al final.

**Lectura y permisos**

8. **Ver exige sesión.** El bucket sigue privado: la API entrega cada imagen
   con una **URL firmada que vence en 5 minutos** (spec 011, regla 10).
   - Firmar una URL de S3 es un cálculo local con la llave; no consulta a
     Supabase. Por eso se puede firmar la portada de cada fila de la lista.
9. **Permisos:** suben, editan, marcan la portada y desactivan `ADMINISTRADOR` y
   `GERENTE`. Todos los roles autenticados ven, igual que el catálogo (spec 003,
   regla 8; spec 011, regla 11).

## 4. Modelo de datos

### `catalogo.ImagenPropiedad` (hereda `core.ModeloBase`)

| Campo | Tipo | Nota |
|---|---|---|
| `propiedad` | FK `Propiedad` | `PROTECT`, `related_name="imagenes"` |
| `archivo` | FileField | Ruta generada (regla 3) |
| `nombre_original` | CharField(255) | El nombre con que se subió |
| `tipo_contenido` | CharField(50) | `image/jpeg` o `image/png` |
| `tamano_bytes` | PositiveIntegerField | ≤ 5 MB (regla 1), constraint |
| `descripcion` | CharField(200) | Opcional. Sirve de texto alternativo (`alt`) |
| `orden` | PositiveSmallIntegerField | Regla 7 |
| `es_portada` | BooleanField | Regla 6 |

**Constraints:**
- `tamano_bytes` entre 1 byte y 5 MB.
- **Una sola portada activa por propiedad:** `UniqueConstraint(fields=["propiedad"],
  condition=Q(es_portada=True, activo=True))`. La base lo garantiza aunque dos
  personas marquen portada a la vez.

El límite de 10 (regla 2) no es un constraint: lo revisa el servicio después
de bloquear la propiedad con `select_for_update`, así dos subidas al mismo
tiempo no pasan juntas de 10.

`docs/modelo-datos.md` se actualiza en el PR de implementación.

## 5. API

| Método | Ruta | Permiso |
|---|---|---|
| GET, POST | `/api/v1/propiedades/{id}/imagenes/` · POST como `multipart/form-data` (`archivo`, `descripcion`) | Leer: todos · Subir: regla 9 |
| GET, PATCH, DELETE | `/api/v1/imagenes/{id}/` · PATCH solo `descripcion` y `orden` (regla 4) · DELETE desactiva | Regla 9 para escribir |
| POST | `/api/v1/imagenes/{id}/marcar-portada/` | Regla 9 |

**Cambio en `/propiedades/`:** la lista y el detalle agregan `portada_url`
(texto o `null`), la URL firmada de la portada.

**Ejemplo de respuesta** de `GET /propiedades/1/imagenes/`:

```json
{
  "count": 2,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": 7,
      "descripcion": "Fachada principal",
      "orden": 1,
      "es_portada": true,
      "url": "https://…supabase.co/…/imagenes/PROP-00001/3f2a….jpg?X-Amz-Expires=300…",
      "vence_en_segundos": 300,
      "nombre_original": "fachada.jpg",
      "creado_en": "2026-11-01T15:20:00Z"
    }
  ]
}
```

**Errores nuevos:**

| Código | Situación | HTTP |
|---|---|---|
| `LIMITE_IMAGENES` | La propiedad ya tiene 10 imágenes activas (regla 2) | 409 |

`ARCHIVO_NO_PERMITIDO` (400) ya existe (spec 011): aquí cubre lo que no es JPG
ni PNG, o pesa más de 5 MB.

## 6. Servicios y selectores

```python
# catalogo/services.py  (transaction.atomic y registrar_auditoria)
def subir_imagen(*, propiedad, archivo, descripcion, autor, ip) -> ImagenPropiedad
def actualizar_imagen(*, imagen, datos, autor, ip) -> ImagenPropiedad
def marcar_portada(*, imagen, autor, ip) -> ImagenPropiedad
def desactivar_imagen(*, imagen, autor, ip) -> None

# catalogo/selectors.py
def listar_imagenes(*, propiedad) -> QuerySet[ImagenPropiedad]   # activas, por orden
```

- `_validar_archivo` (spec 011) recibe las firmas y el tamaño máximo como
  parámetros, para servir a documentos e imágenes sin duplicarse.
- La URL firmada se arma en el serializer con `default_storage.url()`, como la
  descarga de documentos.
- `listar_propiedades_con_portada` agrega un `Prefetch` de la portada activa,
  para no hacer una consulta por fila (N+1). Es un selector aparte de
  `listar_propiedades` (ver §11).

**Frontend** (spec 010):

```
src/api/catalogo/consultas.ts    + useImagenes(propiedad), con staleTime de 4 minutos (§10)
src/api/catalogo/mutaciones.ts   + subir, editar, marcar portada y desactivar imagen
src/paginas/catalogo/
  PestanaImagenes.tsx            cuadrícula de miniaturas; la portada marcada
  DialogoImagen.tsx              subir (campo 'archivo') y editar descripción y orden
  ListaPropiedades.tsx           + columna con la miniatura de la portada
  FichaPropiedad.tsx             + pestaña Imágenes
```

## 7. Auditoría

| Acción | Entidad | Valores |
|---|---|---|
| Subir | `ImagenPropiedad` | Todos los campos, menos el archivo, que se identifica por su ruta |
| Editar | `ImagenPropiedad` | `descripcion` y `orden`, antes y después |
| Marcar portada | Las dos imágenes | `es_portada` de la anterior y de la nueva, en la misma transacción |
| Desactivar | `ImagenPropiedad` | `activo`, y la nueva portada si cambió (regla 6) |

## 8. Criterios de aceptación

- [x] Subir un JPG lo agrega a la galería; la primera imagen queda como portada
- [ ] Un archivo que no es JPG ni PNG, o de más de 5 MB, muestra el error del
      navegador junto al campo; un `.exe` renombrado a `.jpg` muestra arriba del
      formulario el 400 `ARCHIVO_NO_PERMITIDO` de la API
- [x] La undécima imagen muestra el 409 `LIMITE_IMAGENES`
- [x] Marcar otra imagen como portada deja una sola portada, y la lista de
      propiedades muestra la nueva
- [x] Desactivar la portada pasa la marca a la siguiente según el orden
- [x] Cambiar el orden reordena la galería
- [x] La lista de propiedades muestra la miniatura de la portada, o un marcador
      si no tiene, sin una consulta por fila
- [x] `CONSULTA` ve la galería y las portadas, sin botones de escritura; un
      `POST` suyo responde 403
- [x] Cada escritura queda en la bitácora de auditoría
- [x] En producción, subir y ver funcionan contra Supabase
- [x] `pytest`, `ruff`, `npm run lint`, `npm run typecheck` y `npm run build`
      pasan

## 9. Pruebas

| Nivel | Caso |
|---|---|
| Servicio | La primera imagen queda como portada; las siguientes no |
| Servicio | Marcar portada deja una sola; desactivar la portada pasa la marca a la siguiente |
| Servicio | La undécima imagen lanza `LimiteImagenes` |
| Servicio | Un archivo con firma de PDF o de ejecutable lanza `ArchivoNoPermitido` |
| Modelo | El constraint rechaza dos portadas activas en la misma propiedad |
| API | 201 al subir, 403 para `CONSULTA`, 409 en el límite, `portada_url` en `/propiedades/` |
| API | La lista de propiedades no hace una consulta por fila (`django_assert_max_num_queries`) |
| Manual | Cada criterio de §8, en local y en producción |

Las pruebas guardan los archivos en una carpeta temporal (`MEDIA_ROOT` de
`config/settings/test.py`), como las de la spec 011: nunca suben a Supabase.

## 10. Decisiones y alternativas descartadas

- **Un modelo aparte y no un tipo más de `DocumentoOficial`.** Un documento es
  legal: tiene emisor, emisión y vencimiento, y respalda avalúos. Una foto no
  tiene nada de eso y sí necesita portada y orden. Mezclarlos llenaría los dos
  de campos vacíos.
- **Sin miniaturas en el servidor.** Recortarlas pide Pillow, una dependencia
  nueva. Con el límite de 5 MB y el navegador reduciendo la imagen, la galería
  funciona. Si la lista se vuelve lenta, se agrega en otra spec y se justifica.
- **Sin WebP.** Las firmas de JPG y PNG ya existen y están probadas; WebP pide
  revisar otra firma. Los teléfonos y cámaras entregan JPG.
- **URL firmada dentro de la respuesta, y no un endpoint por imagen.** Pedir
  una URL por foto haría diez peticiones para mostrar una galería. La consulta
  del frontend se vuelve a pedir a los 4 minutos (`staleTime`), antes de que
  las URL venzan a los 5.
- **El bucket sigue privado.** Hacer públicas las imágenes evitaría las URL
  firmadas, pero abriría el bucket entero, documentos legales incluidos, o
  pediría un segundo bucket con su propia configuración.
- **Límite de 10 por propiedad y 5 MB.** Con unas 15 propiedades de demo, el
  peor caso son 750 MB, dentro de 1 GB. En la práctica, una foto de teléfono
  pesa entre 2 y 4 MB.

## 11. Trabajo con agentes de IA

**Sesión 2026-11-01 (Claude Code, rol A).** A preguntó si convenía agregar
imágenes y dónde. El agente propuso cinco lugares: galería en la ficha,
portada en la lista, PDF de la cotización, consulta pública y avance de obra.
A eligió los dos primeros para esta spec, porque no dan puntos en la rúbrica y
el resto del plan va primero. Para el borrador, el agente revisó:
- la spec 011 y `catalogo/services.py`, para reutilizar las firmas, la ruta
  generada y la URL firmada;
- la spec 014, para la pestaña y el campo `'archivo'`;
- las dependencias instaladas, donde no está Pillow (§10).

**Depende de la spec 014** (#67): la pestaña va en la ficha que crea esa spec.

**Plan de implementación:**
1. Modelo, constraint y migración; `_validar_archivo` con parámetros; servicios,
   selectores, API y sus pruebas.
2. `portada_url` en `/propiedades/`, con su prueba de número de consultas.
3. Frontend: pestaña Imágenes, diálogo y miniatura en la lista; verificación de
   §8 en local y en producción.

**Sesión 2026-11-03 (Claude Code, rol A): implementación.** A pidió terminar la
spec antes de la entrega. Se siguió el plan en los tres incrementos.

Desviaciones respecto del borrador, decididas al implementar:
- **`listar_propiedades_con_portada` y no un `Prefetch` dentro de
  `listar_propiedades`.** Las demás apps (ventas, arrendamientos, compras,
  construcción, el agente) leen propiedades con `listar_propiedades`, y los
  campos `*_id` de sus serializers lo usan como queryset: el `Prefetch` les
  sumaría una consulta en cada lectura sin que usen la foto. Solo las dos
  vistas de propiedades usan el selector nuevo.
- **`portada_url` es `null` en la respuesta de crear y editar una propiedad**,
  porque esa instancia viene del servicio sin el `Prefetch`. La pantalla
  invalida la lista y la vuelve a pedir, así que no se nota; consultar la
  portada en el serializer rompería la regla de no acceder a la base ahí.
- **La galería se vuelve a pedir cada 4 minutos** (`refetchInterval`) además
  del `staleTime`: con la pestaña abierta sin interacción, las URL firmadas
  vencerían a los 5 sin que nada las renovara.
- **El texto del error de `_validar_archivo` se arma con los tipos aceptados**
  ("JPG o PNG", "PDF, JPG o PNG") y el tamaño máximo, para no duplicar la
  función. Los mensajes de los documentos quedan iguales.

Verificación:
- 20 pruebas nuevas (servicio, constraint y API, incluida la de que la lista no
  hace una consulta por fila); la suite completa pasa salvo las 10 de PDF que
  en Windows fallan por WeasyPrint, como siempre.
- En el navegador local, como gerente: subir dos fotos, la primera como
  portada, marcar la segunda y ver su miniatura en la lista.
- **Nota:** el `.env` local de A usa `STORAGE_BACKEND=s3`, así que esas dos
  fotos sintéticas (5 KB, sin datos) subieron al bucket de Supabase. Se
  borraron del bucket al terminar con `default_storage.delete`.
- Falta el criterio de producción (§8) y ver con `CONSULTA` en la pantalla que
  no aparecen los botones; la API ya responde 403 en las pruebas.

**Verificación en producción (2026-11-03, A).** Douglas subió las 14 fotos de
la demo (dos por propiedad, de Unsplash con su licencia; créditos fuera del
repositorio, junto a las fotos) contra Supabase, cambió la portada en la Torre
Mirador y la lista muestra las 7 miniaturas. Con `CONSULTA` la pestaña
Imágenes se ve sin botones. Queda sin marcar el criterio del error del
navegador con un archivo no permitido, que no se probó en pantalla; la API ya
lo cubre en las pruebas.
