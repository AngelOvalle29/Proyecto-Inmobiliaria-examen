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
}

export const MENU: EntradaMenu[] = [
  { ruta: '/', etiqueta: 'Inicio' },
  { ruta: '/catalogo/propiedades', etiqueta: 'Propiedades' },
  {
    ruta: '/catalogo/propiedades/nueva',
    etiqueta: 'Nueva propiedad',
    roles: [ROLES.ADMINISTRADOR, ROLES.GERENTE],
  },
]

/** true si el rol puede abrir la entrada (o la ruta) que declara esos roles. */
export function rolPermitido(rol: Rol | string, roles?: Rol[]): boolean {
  return roles === undefined || roles.some((permitido) => permitido === rol)
}
