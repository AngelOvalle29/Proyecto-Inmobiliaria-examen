# 023 · Tablero de inicio y menú plegable

| Campo | Valor |
|---|---|
| **Número** | 023 |
| **Estado** | En revisión |
| **Autor** | Marco André Bolaños Rojas (rol B) |
| **Revisor** | Por asignar |
| **Fecha** | 2026-11-03 |
| **Apps afectadas** | `frontend/` (`paginas/inicio`, `api/inicio` y `layouts/LayoutPrincipal.tsx`). Sin cambios en el backend |
| **Rama** | `feature/022-diseno-editorial` |
| **Pull request** | — |

---

## 1. Problema

Al entrar, la primera pantalla solo dice si el servidor responde. Un gerente no
ve de un vistazo cuántos clientes, contratos o proyectos hay, ni qué pide
atención.

Además, el menú creció a 15 entradas en 7 grupos y ocupa toda la columna. El
usuario necesita plegar los grupos que no usa, o esconder el menú para tener
más espacio.

## 2. Alcance

**Incluye:**
- Un tablero en Inicio con el total de cada módulo que el rol ve, y un segundo
  dato de estado donde aplica.
- Un panel destacado con las cuotas y rentas en mora y los bienes disponibles.
- Grupos del menú que se despliegan y se pliegan, y un botón para ocultar el
  menú completo.

**No incluye:**
- Gráficas: necesitarían una librería nueva. Los reportes y Power BI ya las
  cubren (spec 021).
- Un endpoint nuevo de resumen: se usan los existentes.

## 3. Reglas

1. **El tablero respeta los permisos del menú.** Un dato aparece solo si su
   pantalla aparece en el menú del rol (`rolPermitido`).
2. **Los totales salen de las listas de la API.** Se pide una página y se lee
   `count`. La API cuenta en SQL y aplica la cartera: un agente ve los totales
   de sus clientes, no los de toda la agencia.
3. **Los destacados salen de dos reportes de la spec 021:** R11 (morosidad) y
   R05 (inventario disponible). Los dos los pueden ver todos los roles.
4. **Menú plegable.**
   - Cada grupo con título se despliega o se pliega.
   - El grupo de la página abierta siempre está desplegado, para no perder dónde
     se está.
   - El botón ‹ oculta el menú, y "Mostrar menú" lo vuelve a abrir.
5. **La preferencia se recuerda en el navegador** (`localStorage`). Es solo una
   comodidad: si el almacenamiento falla o se borra, el menú se muestra completo.

## 4. Modelo de datos

Sin cambios.

## 5. API

Sin cambios. El tablero hace hasta 11 conteos, 7 segundos datos y 2 reportes, y
cada uno se guarda en caché un minuto.

## 6. Componentes y archivos

| Archivo | Qué hace |
|---|---|
| `api/inicio/consultas.ts` | `useConteo(ruta, filtros)` y `useConteoReporte(slug)` |
| `paginas/inicio/modulos.ts` | Qué se cuenta en cada pantalla; agregar un dato es una línea |
| `paginas/inicio/Inicio.tsx` | Saludo, destacados en el panel óxido (spec 022), tarjetas por grupo y estado del sistema |
| `layouts/LayoutPrincipal.tsx` | Grupos plegables (`GrupoDelMenu`) y menú que se oculta |

## 7. Auditoría

No aplica: solo lecturas.

## 8. Criterios de aceptación

- [ ] Inicio muestra una tarjeta por grupo del menú, con sus totales
- [ ] Un agente ve los totales de su cartera
- [ ] `CONSULTA` no ve "Documentos del asistente" en el tablero ni en el menú
- [ ] Plegar un grupo se recuerda al recargar
- [ ] El grupo de la página abierta no se pliega
- [ ] Ocultar el menú deja el contenido a todo el ancho, y "Mostrar menú" lo trae de vuelta
- [ ] `npm run lint`, `npm run typecheck` y `npm run build` pasan

## 9. Pruebas

| Nivel | Caso |
|---|---|
| Estático | `lint`, `typecheck` y `build` |
| Manual, local | Inicio como gerente y como agente; plegar, recargar y ocultar el menú |

## 10. Decisiones y alternativas descartadas

- **Contar con las listas existentes y no con un endpoint de resumen.** Son más
  peticiones, pero no toca el backend el día del cierre, y cada lista ya aplica
  permisos y cartera.
- **Sin librería de gráficas.** Los números en serif grande siguen el diseño
  editorial (spec 022).
- **La preferencia del menú en `localStorage` y no en el servidor.** Es por
  navegador, como pide una preferencia de pantalla.

## 11. Trabajo con agentes de IA

**Sesión 2026-11-03 (Claude Code, rol B).** B pidió un tablero con los datos de
cada módulo en Inicio y un menú plegable. El agente propuso usar los conteos de
las listas existentes y los dos reportes destacados, y escribió los componentes.
