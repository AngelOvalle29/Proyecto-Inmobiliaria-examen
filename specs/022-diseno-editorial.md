# 022 · Diseño visual editorial

| Campo | Valor |
|---|---|
| **Número** | 022 |
| **Estado** | En revisión |
| **Autor** | Marco André Bolaños Rojas (rol B) |
| **Revisor** | Por asignar |
| **Fecha** | 2026-11-03 |
| **Apps afectadas** | `frontend/` (estilos, componentes de `componentes/ui`, layouts y clases de color de las páginas). Sin cambios en el backend |
| **Rama** | `feature/022-diseno-editorial` |
| **Pull request** | — |

---

## 1. Problema

El sistema usa los grises y azules por defecto de Tailwind y shadcn/ui: funciona,
pero no tiene identidad visual. El equipo eligió una guía de estilo editorial
(DESIGN.md, "Azione"): lienzo crema, franjas negras, un rojizo "óxido" para los
paneles de marca, títulos en serif editorial y etiquetas en monoespaciada.

Esa guía está pensada para un sitio de agencia, con fotos a pantalla completa y
titulares enormes. Esta spec la adapta a un sistema de gestión con tablas y
formularios, sin cambiar ninguna pantalla ni regla de negocio.

## 2. Alcance

**Incluye:**
- Los tokens de color y tipografía del DESIGN.md, en `src/index.css`.
- Los componentes base (`button`, `card`, `input`, `select`, `label`, `table`)
  con las formas del diseño.
- El menú lateral negro y el inicio de sesión como díptico editorial.
- Reemplazar en todas las páginas las clases `slate-*` y `bg-white` por los tokens.

**No incluye:**
- Fotografías, el hero a pantalla completa, la marquesina de clientes ni el pie
  de contacto del DESIGN.md: no hay fotos con derechos de uso y no aplican a un
  sistema interno.
- Cambios de estructura en las pantallas, en las rutas o en la API.
- Modo oscuro.

## 3. Reglas

1. **Colores.** Solo los del DESIGN.md, con nombre en español: `negro`
   (#000000), `crema` (#fbfaf6), `tinta` (#222222), `niebla` (#e3e3e9), `ceniza`
   (#dadbdd), `blanco` (#ffffff) y `oxido` (#813413).
   - Se agrega `tenue` (#5c5b57) para el texto secundario: el DESIGN.md no tiene
     un gris medio, y este cumple el contraste AA (4.5:1) sobre crema.
   - **Excepción:** los mensajes de error, aviso y éxito conservan rojo, ámbar y
     verde. El DESIGN.md prohíbe colores saturados, pero un error tiene que
     distinguirse sin depender del contexto.
2. **Tipografía.** Los sustitutos gratuitos que propone el DESIGN.md, desde
   Google Fonts:
   - Cormorant Garamond, peso 400, para títulos (`font-editorial`).
   - Archivo para el texto (`font-sans`).
   - IBM Plex Mono para etiquetas, botones, menú y encabezados de tabla
     (`font-mono`), en mayúsculas y con tracking (`tracking-etiqueta`).
3. **Formas.**
   - Tarjetas y paneles con 16px de radio (`rounded-2xl`).
   - Botones en píldora (`rounded-full`).
   - Campos subrayados, sin caja.
   - Sin sombras ni degradados.
4. **El óxido se reserva a los paneles de marca y a los enlaces.** Los botones
   principales van en tinta, como pide el DESIGN.md.
5. **Accesibilidad.** Todo control mantiene un foco visible: anillo óxido en
   botones y una línea más gruesa en los campos.

## 4. Modelo de datos

Sin cambios.

## 5. API

Sin cambios.

## 6. Componentes y archivos

| Archivo | Cambio |
|---|---|
| `index.html` | Las tres fuentes de Google Fonts |
| `src/index.css` | `@theme` con colores, fuentes y tracking; fondo crema |
| `componentes/ui/button.tsx` | Píldora mono; variante nueva `inverse` (contorno crema sobre negro) |
| `componentes/ui/card.tsx` | 16px, sin sombra; título en serif |
| `componentes/ui/input.tsx`, `select.tsx` | Subrayados, sin caja |
| `componentes/ui/label.tsx`, `table.tsx` | Etiquetas y encabezados mono en mayúsculas |
| `layouts/LayoutPrincipal.tsx` | Menú negro con enlaces mono; el activo, en píldora crema |
| `paginas/auth/Login.tsx` | Panel óxido con el título en serif y el formulario al lado |
| Páginas | `slate-*` y `bg-white` pasan a los tokens; títulos de página en serif |

## 7. Auditoría

No aplica: no hay escrituras nuevas.

## 8. Criterios de aceptación

- [ ] El lienzo es crema, el menú negro y los títulos de página en serif
- [ ] Botones en píldora con etiqueta mono en mayúsculas; sin sombras
- [ ] Los campos son subrayados y muestran el foco
- [ ] El inicio de sesión muestra el panel óxido, y en el teléfono queda arriba
      del formulario
- [ ] Los errores, avisos y éxitos se siguen distinguiendo
- [ ] No queda ninguna clase `slate-*` ni `bg-white` en `src/`
- [ ] `npm run lint`, `npm run typecheck` y `npm run build` pasan

## 9. Pruebas

| Nivel | Caso |
|---|---|
| Estático | `lint`, `typecheck` y `build` |
| Manual, local | Inicio de sesión, una lista, un formulario, un detalle y los reportes, en escritorio y en teléfono |

## 10. Decisiones y alternativas descartadas

- **Adaptar y no copiar el DESIGN.md** (decidido por B). El hero, la marquesina
  y las fotos son de un sitio de agencia; en un sistema de gestión estorbarían.
- **Google Fonts y no paquetes npm** (decidido por B). No agrega dependencias.
  A cambio, el navegador descarga las fuentes de Google; si fallan, quedan las
  de respaldo del sistema.
- **Tokens con nombre en español** (`crema`, `oxido`…), como el resto del
  dominio (`CLAUDE.md` §7). Tailwind v4 genera las clases de cada token.
- **Spec e implementación en el mismo PR** (decidido por B): es el día del
  cierre y el cambio es solo visual.

## 11. Trabajo con agentes de IA

**Sesión 2026-11-03 (Claude Code, rol B).** El equipo entregó la guía DESIGN.md.
El agente propuso adaptarla al ERP y B eligió el alcance, las fuentes y el
proceso entre las opciones planteadas. El agente revisó los estilos existentes,
escribió los tokens y los componentes base, y reemplazó las clases de color en
las páginas con una tabla de equivalencias (§6).
