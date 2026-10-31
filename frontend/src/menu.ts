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

export const MENU: EntradaMenu[] = [
  { ruta: '/', etiqueta: 'Inicio' },
  { ruta: '/catalogo/propiedades', etiqueta: 'Propiedades', grupo: 'Catálogo' },
  {
    ruta: '/catalogo/propiedades/nueva',
    etiqueta: 'Nueva propiedad',
    roles: ESCRIBEN_CATALOGO,
    grupo: 'Catálogo',
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
