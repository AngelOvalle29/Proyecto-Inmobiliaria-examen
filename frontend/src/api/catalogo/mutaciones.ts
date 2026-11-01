import { useMutation, useQueryClient } from '@tanstack/react-query'

import { clienteApi } from '../cliente'
import type { components } from '../tipos.generados'
import type { Propiedad, Unidad } from './consultas'

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

/**
 * PATCH /propiedades/{id}/. El estado no va aquí: tiene su propia acción
 * (spec 003, regla 7).
 */
export function useActualizarPropiedad() {
  const invalidar = useInvalidarPropiedades()
  return useMutation({
    mutationFn: async ({ id, ...datos }: DatosNuevaPropiedad & { id: number }) =>
      (await clienteApi.patch<Propiedad>(`/propiedades/${id}/`, datos)).data,
    onSuccess: invalidar,
  })
}

/**
 * POST /{recurso}/{id}/cambiar-estado/ con el estado nuevo y el motivo. La
 * propiedad y la unidad tienen la misma acción con la misma entrada (spec 003),
 * así que un solo hook sirve para las dos (spec 014, regla 4). Se invalida
 * todo el catálogo: la lista, la ficha y las unidades.
 */
export function useCambiarEstado(recurso: 'propiedades' | 'unidades') {
  const clienteConsultas = useQueryClient()
  return useMutation({
    mutationFn: async ({ id, ...datos }: CambiarEstado & { id: number }) =>
      (await clienteApi.post(`/${recurso}/${id}/cambiar-estado/`, datos)).data,
    onSuccess: () => clienteConsultas.invalidateQueries({ queryKey: ['catalogo'] }),
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

/** Los campos escribibles de una unidad; la propiedad sale de la URL. */
export type DatosUnidad = Pick<
  Unidad,
  | 'codigo'
  | 'nivel'
  | 'area_m2'
  | 'habitaciones'
  | 'banos'
  | 'precio_lista'
  | 'moneda_id'
>

function useInvalidarUnidades() {
  const clienteConsultas = useQueryClient()
  return () =>
    clienteConsultas.invalidateQueries({ queryKey: ['catalogo', 'unidades'] })
}

/** POST /propiedades/{id}/unidades/. Un código repetido en la propiedad da 409. */
export function useCrearUnidad(propiedad: number) {
  const invalidar = useInvalidarUnidades()
  return useMutation({
    mutationFn: async (datos: DatosUnidad) =>
      (await clienteApi.post<Unidad>(`/propiedades/${propiedad}/unidades/`, datos))
        .data,
    onSuccess: invalidar,
  })
}

/** PATCH /unidades/{id}/. Como en la propiedad, el estado tiene su propia acción. */
export function useActualizarUnidad() {
  const invalidar = useInvalidarUnidades()
  return useMutation({
    mutationFn: async ({ id, ...datos }: DatosUnidad & { id: number }) =>
      (await clienteApi.patch<Unidad>(`/unidades/${id}/`, datos)).data,
    onSuccess: invalidar,
  })
}

/** DELETE /unidades/{id}/: borrado lógico. */
export function useDesactivarUnidad() {
  const invalidar = useInvalidarUnidades()
  return useMutation({
    mutationFn: async (id: number) => {
      await clienteApi.delete(`/unidades/${id}/`)
    },
    onSuccess: invalidar,
  })
}
