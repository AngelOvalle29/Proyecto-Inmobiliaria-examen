import { useQuery } from '@tanstack/react-query'

import { clienteApi } from '../cliente'
import type { components } from '../tipos.generados'

// Todas las listas paginadas comparten count; se toma el de una de ellas para no
// escribir el tipo a mano (spec 010).
type Conteo = Pick<components['schemas']['PaginatedClienteList'], 'count'>
type Reporte = components['schemas']['Reporte']

const UN_MINUTO = 60_000

/**
 * Cuántos registros devuelve una lista de la API, con sus filtros (spec 023,
 * regla 2). Pide una sola página y lee count: la API cuenta en SQL y respeta la
 * cartera del usuario, así el tablero nunca muestra datos ajenos.
 */
export function useConteo(ruta: string, filtros: Record<string, string> = {}) {
  return useQuery({
    queryKey: ['inicio', 'conteo', ruta, filtros],
    queryFn: async () =>
      (await clienteApi.get<Conteo>(ruta, { params: filtros })).data.count,
    staleTime: UN_MINUTO,
  })
}

/** Cuántas filas tiene un reporte de la spec 021, sin filtros (regla 3). */
export function useConteoReporte(slug: string) {
  return useQuery({
    queryKey: ['inicio', 'reporte', slug],
    queryFn: async () =>
      (await clienteApi.get<Reporte>(`/reportes/${slug}/`)).data.filas.count,
    staleTime: UN_MINUTO,
  })
}
