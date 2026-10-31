import { keepPreviousData, useQuery } from '@tanstack/react-query'

import { clienteApi } from '../cliente'
import type { components, operations } from '../tipos.generados'

export type Cliente = components['schemas']['Cliente']
export type Agente = components['schemas']['Agente']
export type TipoCliente = components['schemas']['TipoEnum']
type PaginaClientes = components['schemas']['PaginatedClienteList']
type PaginaAgentes = components['schemas']['PaginatedAgenteList']

/** Filtros que acepta GET /clientes/, tal como los documenta el esquema. */
export type FiltrosClientes = NonNullable<
  operations['v1_clientes_list']['parameters']['query']
>
export type FiltrosAgentes = NonNullable<
  operations['v1_agentes_list']['parameters']['query']
>

/** Record<TipoCliente, …> obliga a cubrir todos los tipos que tenga el backend. */
export const ETIQUETAS_TIPO_CLIENTE: Record<TipoCliente, string> = {
  PERSONA: 'Persona',
  EMPRESA: 'Empresa',
}

/** Cómo se nombra a un cliente: persona o empresa (spec 004, regla 6). */
export function nombreCliente(cliente: Cliente): string {
  return cliente.tipo === 'EMPRESA'
    ? (cliente.razon_social ?? '')
    : `${cliente.nombre ?? ''} ${cliente.apellidos ?? ''}`
}

/**
 * Una página de clientes. La API ya entrega solo los que el usuario puede ver:
 * un agente recibe su cartera (spec 012, regla 3).
 */
export function useClientes(filtros: FiltrosClientes) {
  return useQuery({
    queryKey: ['crm', 'clientes', filtros],
    queryFn: async () =>
      (await clienteApi.get<PaginaClientes>('/clientes/', { params: filtros })).data,
    placeholderData: keepPreviousData,
  })
}

/** Un cliente, para el formulario de edición. */
export function useCliente(id: number) {
  return useQuery({
    queryKey: ['crm', 'clientes', 'detalle', id],
    queryFn: async () => (await clienteApi.get<Cliente>(`/clientes/${id}/`)).data,
  })
}

/** Una página de agentes activos. */
export function useAgentes(filtros: FiltrosAgentes) {
  return useQuery({
    queryKey: ['crm', 'agentes', filtros],
    queryFn: async () =>
      (await clienteApi.get<PaginaAgentes>('/agentes/', { params: filtros })).data,
    placeholderData: keepPreviousData,
  })
}

/** Agentes que coinciden con el texto, para CampoRelacion (spec 010, regla 11). */
export function useOpcionesAgente(texto: string) {
  const consulta = useQuery({
    queryKey: ['crm', 'agentes', 'buscar', texto],
    queryFn: async () =>
      (
        await clienteApi.get<PaginaAgentes>('/agentes/', {
          params: { buscar: texto || undefined },
        })
      ).data.results,
  })
  return {
    opciones: (consulta.data ?? []).map((agente) => ({
      valor: String(agente.id),
      etiqueta: `${agente.codigo ?? ''} · ${agente.usuario.nombre_completo}`,
    })),
    cargando: consulta.isFetching,
  }
}
