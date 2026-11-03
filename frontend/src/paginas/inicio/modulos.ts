/**
 * Qué cuenta el tablero de Inicio en cada módulo (spec 023, regla 2). Cada
 * entrada apunta a una pantalla del menú: si el rol no la ve, el tablero
 * tampoco la muestra. Agregar un dato es agregar una línea aquí.
 */
export interface DatoModulo {
  /** La pantalla del menú; de ahí salen los permisos y el enlace. */
  ruta: string
  etiqueta: string
  /** Lista de la API que se cuenta. */
  api: string
  /** Un segundo número, con un filtro de estado de la misma lista. */
  detalle?: { etiqueta: string; filtros: Record<string, string> }
}

export const DATOS_POR_MODULO: DatoModulo[] = [
  {
    ruta: '/catalogo/propiedades',
    etiqueta: 'Propiedades',
    api: '/propiedades/',
    detalle: { etiqueta: 'Disponibles', filtros: { estado: 'DISPONIBLE' } },
  },
  { ruta: '/crm/clientes', etiqueta: 'Clientes', api: '/clientes/' },
  {
    ruta: '/crm/cotizaciones',
    etiqueta: 'Cotizaciones',
    api: '/cotizaciones/',
    detalle: { etiqueta: 'Esperan respuesta', filtros: { estado: 'ENVIADA' } },
  },
  { ruta: '/crm/agentes', etiqueta: 'Agentes', api: '/agentes/' },
  {
    ruta: '/ventas/contratos',
    etiqueta: 'Contratos de venta',
    api: '/contratos-venta/',
    detalle: { etiqueta: 'Vigentes', filtros: { estado: 'VIGENTE' } },
  },
  {
    ruta: '/arrendamientos/contratos',
    etiqueta: 'Contratos de arrendamiento',
    api: '/contratos-arrendamiento/',
    detalle: { etiqueta: 'Vigentes', filtros: { estado: 'VIGENTE' } },
  },
  { ruta: '/compras/proveedores', etiqueta: 'Proveedores', api: '/proveedores/' },
  {
    ruta: '/compras/contratos',
    etiqueta: 'Contratos de compra',
    api: '/contratos-compra/',
    detalle: { etiqueta: 'En proceso', filtros: { estado: 'EN_PROCESO' } },
  },
  {
    ruta: '/construccion/constructoras',
    etiqueta: 'Constructoras',
    api: '/constructoras/',
  },
  {
    ruta: '/construccion/proyectos',
    etiqueta: 'Proyectos',
    api: '/proyectos-construccion/',
    detalle: { etiqueta: 'En ejecución', filtros: { estado: 'EN_EJECUCION' } },
  },
  {
    ruta: '/asistente/documentos',
    etiqueta: 'Documentos del asistente',
    api: '/documentos-agente/',
  },
]
