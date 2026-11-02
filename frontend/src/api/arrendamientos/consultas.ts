import { keepPreviousData, useQuery } from '@tanstack/react-query'

import { clienteApi } from '../cliente'
import type { components, operations } from '../tipos.generados'

export type Arrendamiento = components['schemas']['Arrendamiento']
export type ArrendamientoDetalle = components['schemas']['ArrendamientoDetalle']
export type PagoRenta = components['schemas']['PagoRenta']
export type EstadoArrendamiento = components['schemas']['EstadoArrendamientoEnum']
type EstadoPagoRenta = components['schemas']['EstadoPagoRentaEnum']
type PaginaArrendamientos = components['schemas']['PaginatedArrendamientoList']

/** Filtros que acepta GET /contratos-arrendamiento/, según el esquema. */
export type FiltrosArrendamientos = NonNullable<
  operations['v1_contratos_arrendamiento_list']['parameters']['query']
>

export const ETIQUETAS_ESTADO_ARRENDAMIENTO: Record<EstadoArrendamiento, string> = {
  VIGENTE: 'Vigente',
  VENCIDO: 'Vencido',
  RESCINDIDO: 'Rescindido',
  RENOVADO: 'Renovado',
}

export const ETIQUETAS_ESTADO_PAGO_RENTA: Record<EstadoPagoRenta, string> = {
  PENDIENTE: 'Pendiente',
  PAGADO: 'Pagado',
  CANCELADO: 'Cancelado',
}

/** Una página de contratos; la API aplica la cartera del agente. */
export function useArrendamientos(filtros: FiltrosArrendamientos) {
  return useQuery({
    queryKey: ['arrendamientos', 'contratos', filtros],
    queryFn: async () =>
      (
        await clienteApi.get<PaginaArrendamientos>('/contratos-arrendamiento/', {
          params: filtros,
        })
      ).data,
    placeholderData: keepPreviousData,
  })
}

/** Un contrato con su calendario de pagos y su mora. */
export function useArrendamiento(id: number) {
  return useQuery({
    queryKey: ['arrendamientos', 'contratos', 'detalle', id],
    queryFn: async () =>
      (await clienteApi.get<ArrendamientoDetalle>(`/contratos-arrendamiento/${id}/`))
        .data,
  })
}
