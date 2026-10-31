import { useMutation, useQueryClient } from '@tanstack/react-query'

import { clienteApi } from '../cliente'
import type { components } from '../tipos.generados'
import type { Agente, Cliente } from './consultas'

export type DatosCliente = components['schemas']['ClienteEntrada']
export type DatosEditarCliente = components['schemas']['PatchedClienteEntrada']
export type DatosEditarAgente = components['schemas']['PatchedAgenteEditar']

/**
 * Después de escribir se invalida todo lo de CRM: reasignar un cliente, por
 * ejemplo, cambia también los clientes activos que muestra la lista de agentes.
 */
function useInvalidarCrm() {
  const clienteConsultas = useQueryClient()
  return () => clienteConsultas.invalidateQueries({ queryKey: ['crm'] })
}

/** POST /clientes/: el backend asigna el código CLI-NNNNN (spec 004, regla 10). */
export function useCrearCliente() {
  const invalidar = useInvalidarCrm()
  return useMutation({
    mutationFn: async (datos: DatosCliente) =>
      (await clienteApi.post<Cliente>('/clientes/', datos)).data,
    onSuccess: invalidar,
  })
}

/** PATCH /clientes/{id}/: datos del cliente; nunca su agente. */
export function useEditarCliente() {
  const invalidar = useInvalidarCrm()
  return useMutation({
    mutationFn: async ({ id, ...datos }: DatosEditarCliente & { id: number }) =>
      (await clienteApi.patch<Cliente>(`/clientes/${id}/`, datos)).data,
    onSuccess: invalidar,
  })
}

/** DELETE /clientes/{id}/: borrado lógico. */
export function useDesactivarCliente() {
  const invalidar = useInvalidarCrm()
  return useMutation({
    mutationFn: async (id: number) => {
      await clienteApi.delete(`/clientes/${id}/`)
    },
    onSuccess: invalidar,
  })
}

/** POST /clientes/{id}/reasignar/ (spec 004, regla 11). */
export function useReasignarCliente() {
  const invalidar = useInvalidarCrm()
  return useMutation({
    mutationFn: async ({ id, agente }: { id: number; agente: number }) =>
      (await clienteApi.post<Cliente>(`/clientes/${id}/reasignar/`, { agente })).data,
    onSuccess: invalidar,
  })
}

/** PATCH /agentes/{id}/: comisión o fecha de ingreso. */
export function useEditarAgente() {
  const invalidar = useInvalidarCrm()
  return useMutation({
    mutationFn: async ({ id, ...datos }: DatosEditarAgente & { id: number }) =>
      (await clienteApi.patch<Agente>(`/agentes/${id}/`, datos)).data,
    onSuccess: invalidar,
  })
}

/** DELETE /agentes/{id}/: responde 409 si tiene clientes activos (regla 4). */
export function useDesactivarAgente() {
  const invalidar = useInvalidarCrm()
  return useMutation({
    mutationFn: async (id: number) => {
      await clienteApi.delete(`/agentes/${id}/`)
    },
    onSuccess: invalidar,
  })
}
