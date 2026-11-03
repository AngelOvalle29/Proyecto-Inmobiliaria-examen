import { keepPreviousData, useQuery } from '@tanstack/react-query'

import { clienteApi } from '../cliente'
import type { components, operations } from '../tipos.generados'

export type Constructora = components['schemas']['Constructora']
type PaginaConstructoras = components['schemas']['PaginatedConstructoraList']

/** Filtros que acepta GET /constructoras/, tal como los documenta el esquema. */
export type FiltrosConstructoras = NonNullable<
  operations['v1_constructoras_list']['parameters']['query']
>

/**
 * Una página de constructoras activas con sus filtros (spec 018, §5).
 * calificacion_min deja fuera las que todavía no tienen calificación: así lo
 * resuelve la API.
 */
export function useConstructoras(filtros: FiltrosConstructoras) {
  return useQuery({
    queryKey: ['construccion', 'constructoras', filtros],
    queryFn: async () =>
      (
        await clienteApi.get<PaginaConstructoras>('/constructoras/', {
          params: filtros,
        })
      ).data,
    placeholderData: keepPreviousData,
  })
}

/** Una constructora, para su formulario de edición. */
export function useConstructora(id: number) {
  return useQuery({
    queryKey: ['construccion', 'constructoras', 'detalle', id],
    queryFn: async () =>
      (await clienteApi.get<Constructora>(`/constructoras/${id}/`)).data,
  })
}
