/**
 * Menú del sistema, en una sola lista (spec 010, regla 3). Cada entrada dice
 * qué roles la ven; sin `roles`, la ven todos. Al agregar una pantalla, se
 * agrega aquí una línea y una ruta en App.tsx.
 *
 * Ocultar una entrada no es seguridad: el backend valida todo con TieneRol.
 */

/** Los cinco roles del sistema, como los nombra el backend (NombreRol). */
export const ROLES = {
  ADMINISTRADOR: 'ADMINISTRADOR',
  GERENTE: 'GERENTE',
  AGENTE: 'AGENTE',
  CONTABILIDAD: 'CONTABILIDAD',
  CONSULTA: 'CONSULTA',
} as const

export type Rol = (typeof ROLES)[keyof typeof ROLES]

export interface EntradaMenu {
  ruta: string
  etiqueta: string
  roles?: Rol[]
  /**
   * Título del grupo en el menú ("CRM", "Ventas"…). Las entradas sin grupo van
   * arriba, sin título (spec 010, regla 16).
   */
  grupo?: string
}

export interface GrupoMenu {
  /** undefined para las entradas sin grupo. */
  titulo: string | undefined
  entradas: EntradaMenu[]
}

// Quiénes escriben en el catálogo (regla 8 de la spec 003). Lo usan el menú y
// las rutas de App.tsx, para no repetir la lista.
export const ESCRIBEN_CATALOGO: Rol[] = [ROLES.ADMINISTRADOR, ROLES.GERENTE]

// Quiénes escriben en CRM (reglas 11 y 12 de la spec 004): el agente, solo en
// su cartera, porque eso lo decide la API.
export const ADMINISTRAN_CRM: Rol[] = [ROLES.ADMINISTRADOR, ROLES.GERENTE]
export const ESCRIBEN_CRM: Rol[] = [...ADMINISTRAN_CRM, ROLES.AGENTE]
// Firman los mismos que escriben en CRM; anulan los que lo administran
// (reglas 20 y 21 de la spec 007).
export const REGISTRAN_PAGOS: Rol[] = [...ADMINISTRAN_CRM, ROLES.CONTABILIDAD]

// Quiénes escriben en compras y en construcción: proveedores, constructoras,
// contratos de compra y proyectos (spec 006, regla 10, y spec 017, regla 24).
// Leen todos los roles.
export const ESCRIBEN_COMPRAS: Rol[] = [ROLES.ADMINISTRADOR, ROLES.GERENTE]
export const ESCRIBEN_CONSTRUCCION: Rol[] = [ROLES.ADMINISTRADOR, ROLES.GERENTE]
// Los pagos a constructoras los registra también contabilidad, como los de
// ventas (spec 017, regla 24).
export const PAGAN_CONSTRUCCION: Rol[] = [...ESCRIBEN_CONSTRUCCION, ROLES.CONTABILIDAD]

// Quiénes administran los documentos del asistente: también los leen solo
// ellos (regla 14 de la spec 020).
export const ADMINISTRAN_ASISTENTE: Rol[] = [ROLES.ADMINISTRADOR, ROLES.GERENTE]
// Solo administración gestiona cuentas de usuario (spec 026, regla 1).
export const ADMINISTRAN_USUARIOS: Rol[] = [ROLES.ADMINISTRADOR]
// Quiénes leen compras y construcción: lo que pagó la agencia y el
// presupuesto de las obras no es para agentes ni consulta (spec 024, regla 1).
export const LEEN_COMPRAS: Rol[] = [...ESCRIBEN_COMPRAS, ROLES.CONTABILIDAD]
export const LEEN_CONSTRUCCION: Rol[] = [...ESCRIBEN_CONSTRUCCION, ROLES.CONTABILIDAD]
// Un agente solo ve su propio perfil en la API (spec 024, regla 2): la
// pantalla de agentes no le sirve.
export const VEN_AGENTES: Rol[] = [
  ROLES.ADMINISTRADOR,
  ROLES.GERENTE,
  ROLES.CONTABILIDAD,
  ROLES.CONSULTA,
]

export const MENU: EntradaMenu[] = [
  { ruta: '/', etiqueta: 'Inicio' },
  { ruta: '/reportes', etiqueta: 'Reportes' },
  // "Nueva propiedad" es un botón de la lista, como en CRM (spec 014, §5).
  { ruta: '/catalogo/propiedades', etiqueta: 'Propiedades', grupo: 'Catálogo' },
  { ruta: '/catalogo/tipos', etiqueta: 'Tipos de propiedad', grupo: 'Catálogo' },
  { ruta: '/crm/clientes', etiqueta: 'Clientes', grupo: 'CRM' },
  { ruta: '/crm/cotizaciones', etiqueta: 'Cotizaciones', grupo: 'CRM' },
  { ruta: '/crm/agentes', etiqueta: 'Agentes', roles: VEN_AGENTES, grupo: 'CRM' },
  { ruta: '/ventas/contratos', etiqueta: 'Contratos de venta', grupo: 'Ventas' },
  {
    ruta: '/arrendamientos/contratos',
    etiqueta: 'Contratos de arrendamiento',
    grupo: 'Arrendamientos',
  },
  // Las entradas de "Nuevo…" son botones de cada lista (spec 018, §5).
  {
    ruta: '/compras/proveedores',
    etiqueta: 'Proveedores',
    roles: LEEN_COMPRAS,
    grupo: 'Compras',
  },
  {
    ruta: '/compras/contratos',
    etiqueta: 'Contratos de compra',
    roles: LEEN_COMPRAS,
    grupo: 'Compras',
  },
  {
    ruta: '/construccion/constructoras',
    etiqueta: 'Constructoras',
    roles: LEEN_CONSTRUCCION,
    grupo: 'Construcción',
  },
  {
    ruta: '/construccion/proyectos',
    etiqueta: 'Proyectos',
    roles: LEEN_CONSTRUCCION,
    grupo: 'Construcción',
  },
  // El asistente es público (spec 018, regla 8): aquí aparece para quien ya
  // inició sesión; la página no pide sesión.
  { ruta: '/asistente', etiqueta: 'Asistente', grupo: 'Asistente' },
  {
    ruta: '/asistente/documentos',
    etiqueta: 'Documentos del asistente',
    roles: ADMINISTRAN_ASISTENTE,
    grupo: 'Asistente',
  },
  {
    ruta: '/usuarios',
    etiqueta: 'Usuarios',
    roles: ADMINISTRAN_USUARIOS,
    grupo: 'Administración',
  },
]

/**
 * Reparte las entradas en grupos, en el orden en que aparece cada grupo en la
 * lista: así el orden del menú es el de MENU, y agregar una pantalla sigue
 * siendo una sola línea.
 */
export function agruparMenu(entradas: EntradaMenu[]): GrupoMenu[] {
  const grupos: GrupoMenu[] = []
  for (const entrada of entradas) {
    let grupo = grupos.find((existente) => existente.titulo === entrada.grupo)
    if (!grupo) {
      grupo = { titulo: entrada.grupo, entradas: [] }
      grupos.push(grupo)
    }
    grupo.entradas.push(entrada)
  }
  return grupos
}

/** true si el rol puede abrir la entrada (o la ruta) que declara esos roles. */
export function rolPermitido(rol: Rol | string, roles?: Rol[]): boolean {
  return roles === undefined || roles.some((permitido) => permitido === rol)
}
