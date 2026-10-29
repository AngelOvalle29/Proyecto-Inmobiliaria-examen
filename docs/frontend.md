# Frontend

## 1. Stack

| Necesidad | Librería | Razón |
|---|---|---|
| Base | React 19 + Vite + TypeScript | Compila a archivos estáticos: no hay servidor que mantener |
| Rutas | React Router | Navegación y protección por rol |
| Datos del servidor | TanStack Query | Cache, reintentos, invalidación y estados de carga |
| Tablas | TanStack Table | Paginación contra el servidor, orden y filtros |
| Formularios | React Hook Form + Zod | Validación tipada que refleja las reglas del backend |
| Componentes | shadcn/ui + Tailwind CSS | Se copian al proyecto; no son una dependencia opaca |
| Gráficas | Recharts | Tableros dentro del sistema (Power BI va aparte) |
| HTTP | Axios | Interceptores para el token JWT y su renovación |
| Fechas | date-fns | Formato local y cálculos de rangos |
| Tipos de la API | openapi-typescript | Genera los tipos desde el esquema del backend |

**Por qué Vite y no Next.js:** las ventajas de Next son el renderizado en
servidor y sus rutas de API. No necesitamos ninguna de las dos, porque el
backend ya es Django. Next solo agregaría un proceso Node más que desplegar.

---

## 2. Estructura

```
frontend/src/
├── main.tsx
├── App.tsx                    # rutas y proveedores
├── api/
│   ├── cliente.ts             # instancia de Axios con interceptores
│   ├── tipos.generados.ts     # generado, NO editar a mano
│   └── <dominio>/             # hooks de consulta y mutación por dominio
│       ├── consultas.ts
│       └── mutaciones.ts
├── componentes/
│   ├── ui/                    # shadcn/ui
│   └── comunes/               # TablaDatos, SelectorFecha, BadgeEstado…
├── layouts/
│   ├── LayoutPrincipal.tsx
│   └── LayoutAuth.tsx
├── paginas/
│   ├── auth/
│   ├── catalogo/
│   ├── crm/
│   ├── ventas/
│   ├── arrendamientos/
│   ├── compras/
│   ├── construccion/
│   ├── reportes/
│   ├── agente/
│   └── auditoria/
├── hooks/
├── lib/                       # formato de moneda, fechas, utilidades
└── tipos/
```

Las carpetas de `paginas/` son las mismas apps del backend. Así cada integrante
trabaja su bloque vertical completo sin pisarse con los demás.

---

## 3. Reglas

- **Nunca `fetch` ni `axios` directamente en un componente.** Todo acceso a la
  API pasa por un hook de TanStack Query en `api/<dominio>/`.
- **Los tipos de la API no se escriben a mano.** Se generan con
  `npm run gen:api` desde el esquema OpenAPI que publica drf-spectacular. Si
  alguien cambia un campo en el modelo de Django, el frontend deja de compilar
  en vez de fallar en producción.
- **Una pantalla de reportes, no dieciocho.** El endpoint `/api/v1/reportes/`
  devuelve el catálogo con los filtros que acepta cada reporte; la pantalla
  construye el formulario leyendo esa definición. Agregar el reporte 19 no
  toca el frontend.
- **La tabla es un componente común.** `TablaDatos` recibe columnas, el hook de
  consulta y los filtros. Todas las listas del sistema la usan.
- **Nombres en español**, igual que en el backend: `ListaPropiedades`,
  `useCrearCotizacion`, `formatearMoneda`.
- **Sin estado global salvo el usuario autenticado.** TanStack Query ya guarda
  el estado del servidor; no hace falta Redux ni Zustand para esto.
- **Todo monto se muestra con su moneda.** Usar `formatearMoneda(monto, moneda)`
  de `lib/`, nunca concatenar un símbolo a mano.
- **Toda lista se pagina contra el servidor.** Nunca traer todo y filtrar en el
  navegador.

---

## 4. Pantallas

### Acceso
Login, recuperación de contraseña y menú que cambia según el rol del usuario.

### Catálogo
- **Lista de propiedades.** Tabla y vista de tarjetas, con filtros por país,
  ciudad, tipo, estado y rango de precio. Mapa opcional con los marcadores.
- **Ficha de propiedad.** Pestañas: datos generales, unidades, avalúos,
  documentos y línea de tiempo del historial. Es la pantalla más vistosa para
  la defensa, conviene cuidarla.
- **Formulario de propiedad**, con carga de documentos.

### CRM
Clientes con su cartera, y cotizaciones con un constructor de líneas que
calcula subtotales, descuentos y total en vivo.

### Ventas
Contratos, generación del plan de pagos y registro de cuotas con su estado.

### Arrendamientos
Contratos vigentes, calendario de cobros y registro de pagos de renta.

### Compras y construcción
Proveedores, contratos de compra, proyectos con barra de avance y pagos a
constructoras.

### Reportes
Pantalla única: selector de reporte, formulario de filtros construido
dinámicamente, vista previa en tabla y botones de descarga en Excel y PDF.

### Agente de IA
Conversación con historial, respuestas con las citas de las fuentes
desplegables, y aviso claro cuando el agente no encuentra información.

### Auditoría
Tabla filtrable de la bitácora del sistema y de la del agente, con el detalle
de valores anteriores y nuevos.

---

## 5. Autenticación

- El token de acceso se guarda en memoria; el de refresco en `localStorage`.
- Un interceptor de Axios renueva el token de acceso cuando la API responde
  401, reintenta la petición original y, si la renovación falla, envía al
  login.
- Las rutas se protegen con un componente `RutaProtegida` que recibe los roles
  permitidos.
- El menú se arma desde los roles: lo que el usuario no puede hacer no se
  muestra, pero **el backend igual valida**. El frontend nunca es la frontera
  de seguridad.

---

## 6. Variables de entorno

Vite solo expone al navegador las variables que empiezan con `VITE_`. **Nunca
poner secretos ahí**: todo lo que lleve ese prefijo termina visible en el
código compilado.

```
VITE_API_URL=http://localhost:8000/api/v1
VITE_ENTORNO=desarrollo
```

---

## 7. Calidad

- **oxlint** y Prettier, con las mismas reglas para todos (`npm run lint` corre
  los dos). Se usa oxlint y no ESLint porque es el que trae la plantilla
  oficial de Vite desde 2026; revisa las reglas de React y TypeScript que
  importan aquí, como las reglas de los hooks.
- **TypeScript 5.9**, no 7: `openapi-typescript`, que genera los tipos de la API,
  solo admite TypeScript 5. Se sube cuando lo soporte.
- `npm run typecheck` en cada pull request, junto con las pruebas del backend.
- Modo estricto de TypeScript activado. Nada de `any` sin justificar en el
  pull request.
