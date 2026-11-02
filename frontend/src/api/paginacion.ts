/**
 * Paginación de la API (spec 010, regla 7). Todo listado viene de 25 en 25
 * (PAGE_SIZE en config/settings/base.py) con la forma de DRF:
 * { count, next, previous, results }. El tipo de cada respuesta paginada se
 * genera del esquema (por ejemplo PaginatedPropiedadList); aquí solo vive lo
 * que comparten todas.
 */

export const TAMANO_PAGINA = 25

/** Cuántas páginas hay para `total` registros. Siempre al menos 1. */
export function totalPaginas(total: number): number {
  return Math.max(1, Math.ceil(total / TAMANO_PAGINA))
}
