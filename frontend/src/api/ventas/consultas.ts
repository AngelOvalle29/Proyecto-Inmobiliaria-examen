import { keepPreviousData, useQuery } from '@tanstack/react-query'

import { clienteApi } from '../cliente'
import type { components, operations } from '../tipos.generados'

export type ContratoVenta = components['schemas']['ContratoVenta']
export type ContratoVentaDetalle = components['schemas']['ContratoVentaDetalle']
export type Cuota = components['schemas']['Cuota']
export type EstadoContrato = components['schemas']['EstadoContratoEnum']
export type Modalidad = components['schemas']['ModalidadEnum']
type EstadoCuota = components['schemas']['EstadoCuotaEnum']
type PaginaContratos = components['schemas']['PaginatedContratoVentaList']

/** Filtros que acepta GET /contratos-venta/, tal como los documenta el esquema. */
export type FiltrosContratosVenta = NonNullable<
  operations['v1_contratos_venta_list']['parameters']['query']
>

export const ETIQUETAS_ESTADO_CONTRATO: Record<EstadoContrato, string> = {
  VIGENTE: 'Vigente',
  LIQUIDADO: 'Liquidado',
  ANULADO: 'Anulado',
}

export const ETIQUETAS_MODALIDAD: Record<Modalidad, string> = {
  CONTADO: 'Contado',
  FINANCIADO: 'Financiado',
}

export const ETIQUETAS_ESTADO_CUOTA: Record<EstadoCuota, string> = {
  PENDIENTE: 'Pendiente',
  PARCIAL: 'Parcial',
  PAGADA: 'Pagada',
}

/** Una página de contratos; la API aplica la cartera del agente. */
export function useContratosVenta(filtros: FiltrosContratosVenta) {
  return useQuery({
    queryKey: ['ventas', 'contratos', filtros],
    queryFn: async () =>
      (await clienteApi.get<PaginaContratos>('/contratos-venta/', { params: filtros }))
        .data,
    placeholderData: keepPreviousData,
  })
}

/** Un contrato con sus cuotas y su mora, que la API calcula al consultar. */
export function useContratoVenta(id: number) {
  return useQuery({
    queryKey: ['ventas', 'contratos', 'detalle', id],
    queryFn: async () =>
      (await clienteApi.get<ContratoVentaDetalle>(`/contratos-venta/${id}/`)).data,
  })
}
