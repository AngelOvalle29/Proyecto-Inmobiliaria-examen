import { useMutation, useQueryClient } from '@tanstack/react-query'

import { clienteApi } from '../cliente'
import type { components } from '../tipos.generados'
import type { Propiedad } from './consultas'

type CambiarEstado = components['schemas']['CambiarEstado']

/**
 * Lo que se envía para crear una propiedad: los campos escribibles del esquema.
 * Los de solo lectura (id, código, estado, resúmenes) los pone el backend.
 */
export type DatosNuevaPropiedad = Pick<
  Propiedad,
  | 'nombre'
  | 'tipo_id'
  | 'ciudad_id'
  | 'direccion'
  | 'area_m2'
  | 'area_construida_m2'
  | 'precio_lista'
  | 'moneda_id'
  | 'es_publica'
  | 'descripcion'
>

/**
 * Después de escribir, se invalidan las consultas de propiedades: TanStack
 * Query las vuelve a pedir y la lista se actualiza sin recargar la página.
 */
function useInvalidarPropiedades() {
  const clienteConsultas = useQueryClient()
  return () =>
    clienteConsultas.invalidateQueries({ queryKey: ['catalogo', 'propiedades'] })
}

/** POST /propiedades/: el backend asigna el código PROP-NNNNN (spec 003). */
export function useCrearPropiedad() {
  const invalidar = useInvalidarPropiedades()
  return useMutation({
    mutationFn: async (datos: DatosNuevaPropiedad) =>
      (await clienteApi.post<Propiedad>('/propiedades/', datos)).data,
    onSuccess: invalidar,
  })
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
