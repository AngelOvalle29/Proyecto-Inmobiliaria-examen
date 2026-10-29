import { useMutation, useQueryClient } from '@tanstack/react-query'

import { clienteApi } from '../cliente'
import type { components } from '../tipos.generados'
import type { Propiedad } from './consultas'

type CambiarEstado = components['schemas']['CambiarEstado']

/**
 * Después de escribir, se invalidan las consultas de propiedades: TanStack
 * Query las vuelve a pedir y la lista se actualiza sin recargar la página.
 */
function useInvalidarPropiedades() {
  const clienteConsultas = useQueryClient()
  return () =>
    clienteConsultas.invalidateQueries({ queryKey: ['catalogo', 'propiedades'] })
}

/** POST /propiedades/{id}/cambiar-estado/ con el estado nuevo y el motivo. */
export function useCambiarEstadoPropiedad() {
  const invalidar = useInvalidarPropiedades()
  return useMutation({
    mutationFn: async ({ id, ...datos }: CambiarEstado & { id: number }) =>
      (await clienteApi.post<Propiedad>(`/propiedades/${id}/cambiar-estado/`, datos))
        .data,
    onSuccess: invalidar,
  })
}

/** DELETE /propiedades/{id}/: borrado lógico (spec 003, regla 6). */
export function useDesactivarPropiedad() {
  const invalidar = useInvalidarPropiedades()
  return useMutation({
    mutationFn: async (id: number) => {
      await clienteApi.delete(`/propiedades/${id}/`)
    },
    onSuccess: invalidar,
  })
}
