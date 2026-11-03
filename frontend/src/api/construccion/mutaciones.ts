import { useMutation, useQueryClient } from '@tanstack/react-query'

import { clienteApi } from '../cliente'
import type { components } from '../tipos.generados'
import type { Constructora } from './consultas'

export type DatosConstructora = components['schemas']['ConstructoraEntrada']
export type DatosEditarConstructora =
  components['schemas']['PatchedConstructoraEntrada']

/**
 * Después de escribir se invalida todo lo de construcción: la lista y el
 * detalle de la constructora empiezan con ['construccion'] (spec 018, §6).
 */
function useInvalidarConstruccion() {
  const clienteConsultas = useQueryClient()
  return () => clienteConsultas.invalidateQueries({ queryKey: ['construccion'] })
}

/** POST /constructoras/: el backend asigna el código CST-0001 (spec 006, regla 8). */
export function useCrearConstructora() {
  const invalidar = useInvalidarConstruccion()
  return useMutation({
    mutationFn: async (datos: DatosConstructora) =>
      (await clienteApi.post<Constructora>('/constructoras/', datos)).data,
    onSuccess: invalidar,
  })
}

/** PATCH /constructoras/{id}/: solo lo que cambia. */
export function useEditarConstructora() {
  const invalidar = useInvalidarConstruccion()
  return useMutation({
    mutationFn: async ({ id, ...datos }: DatosEditarConstructora & { id: number }) =>
      (await clienteApi.patch<Constructora>(`/constructoras/${id}/`, datos)).data,
    onSuccess: invalidar,
  })
}

/**
 * DELETE /constructoras/{id}/: borrado lógico. Responde 409 si la constructora
 * tiene un proyecto activo (spec 017, regla 23).
 */
export function useDesactivarConstructora() {
  const invalidar = useInvalidarConstruccion()
  return useMutation({
    mutationFn: async (id: number) => {
      await clienteApi.delete(`/constructoras/${id}/`)
    },
    onSuccess: invalidar,
  })
}
