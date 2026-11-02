import { useMutation, useQueryClient } from '@tanstack/react-query'

import { clienteApi } from '../cliente'
import type { components } from '../tipos.generados'
import type { ContratoVentaDetalle, Cuota } from './consultas'

export type DatosFirma = components['schemas']['FirmarContrato']
export type DatosPagoCuota = components['schemas']['PagoCuota']

/**
 * Firmar y anular cambian el estado del bien, y firmar consume la cotización:
 * además de ventas se invalidan el catálogo y CRM (spec 007, reglas 10 y 15).
 */
function useInvalidarVenta() {
  const clienteConsultas = useQueryClient()
  return () =>
    Promise.all(
      ['ventas', 'catalogo', 'crm'].map((dominio) =>
        clienteConsultas.invalidateQueries({ queryKey: [dominio] }),
      ),
    )
}

/** POST /contratos-venta/, con cotización o sin ella (regla 7). */
export function useFirmarContratoVenta() {
  const invalidar = useInvalidarVenta()
  return useMutation({
    mutationFn: async (datos: DatosFirma) =>
      (await clienteApi.post<ContratoVentaDetalle>('/contratos-venta/', datos)).data,
    onSuccess: invalidar,
  })
}

/** POST /contratos-venta/{id}/anular/: responde 409 si ya tiene pagos (regla 15). */
export function useAnularContratoVenta() {
  const invalidar = useInvalidarVenta()
  return useMutation({
    mutationFn: async (id: number) =>
      (await clienteApi.post<ContratoVentaDetalle>(`/contratos-venta/${id}/anular/`))
        .data,
    onSuccess: invalidar,
  })
}

/** POST /cuotas/{id}/pagos/: un pago parcial deja la cuota PARCIAL (regla 16). */
export function usePagarCuota() {
  const clienteConsultas = useQueryClient()
  return useMutation({
    mutationFn: async ({ id, ...datos }: DatosPagoCuota & { id: number }) =>
      (await clienteApi.post<Cuota>(`/cuotas/${id}/pagos/`, datos)).data,
    onSuccess: () => clienteConsultas.invalidateQueries({ queryKey: ['ventas'] }),
  })
}

/** POST /contratos-venta/{id}/documento/: vincula o cambia (reglas 23 y 24). */
export function useVincularDocumentoVenta() {
  const clienteConsultas = useQueryClient()
  return useMutation({
    mutationFn: async ({ id, documento }: { id: number; documento: number }) =>
      (
        await clienteApi.post<ContratoVentaDetalle>(
          `/contratos-venta/${id}/documento/`,
          { documento },
        )
      ).data,
    onSuccess: () => clienteConsultas.invalidateQueries({ queryKey: ['ventas'] }),
  })
}
