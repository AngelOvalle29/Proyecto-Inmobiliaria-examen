import { useMutation, useQueryClient } from '@tanstack/react-query'

import { clienteApi } from '../cliente'
import type { components } from '../tipos.generados'
import type { ArrendamientoDetalle, PagoRenta } from './consultas'

export type DatosFirmaArrendamiento = components['schemas']['FirmarArrendamiento']
type DatosRenovar = components['schemas']['RenovarArrendamiento']
type DatosPagarRenta = components['schemas']['PagarRenta']

/** Firmar y terminar un contrato cambian el estado del bien: invalida también el catálogo. */
function useInvalidarArrendamiento() {
  const clienteConsultas = useQueryClient()
  return () =>
    Promise.all(
      ['arrendamientos', 'catalogo'].map((dominio) =>
        clienteConsultas.invalidateQueries({ queryKey: [dominio] }),
      ),
    )
}

/** POST /contratos-arrendamiento/: genera todos sus pagos (spec 008, regla 4). */
export function useFirmarArrendamiento() {
  const invalidar = useInvalidarArrendamiento()
  return useMutation({
    mutationFn: async (datos: DatosFirmaArrendamiento) =>
      (await clienteApi.post<ArrendamientoDetalle>('/contratos-arrendamiento/', datos))
        .data,
    onSuccess: invalidar,
  })
}

/** POST .../renovar/: devuelve el contrato nuevo, no el anterior (regla 9). */
export function useRenovarArrendamiento() {
  const invalidar = useInvalidarArrendamiento()
  return useMutation({
    mutationFn: async ({ id, ...datos }: DatosRenovar & { id: number }) =>
      (
        await clienteApi.post<ArrendamientoDetalle>(
          `/contratos-arrendamiento/${id}/renovar/`,
          datos,
        )
      ).data,
    onSuccess: invalidar,
  })
}

/** POST .../rescindir/: cancela los pagos posteriores a la fecha (regla 10). */
export function useRescindirArrendamiento() {
  const invalidar = useInvalidarArrendamiento()
  return useMutation({
    mutationFn: async ({
      id,
      fecha_rescision,
    }: {
      id: number
      fecha_rescision: string
    }) =>
      (
        await clienteApi.post<ArrendamientoDetalle>(
          `/contratos-arrendamiento/${id}/rescindir/`,
          { fecha_rescision },
        )
      ).data,
    onSuccess: invalidar,
  })
}

/** POST .../finalizar/: solo si la fecha de fin ya pasó (regla 11). */
export function useFinalizarArrendamiento() {
  const invalidar = useInvalidarArrendamiento()
  return useMutation({
    mutationFn: async (id: number) =>
      (
        await clienteApi.post<ArrendamientoDetalle>(
          `/contratos-arrendamiento/${id}/finalizar/`,
        )
      ).data,
    onSuccess: invalidar,
  })
}

/** POST /pagos-renta/{id}/pagar/ (reglas 6 y 7). */
export function usePagarRenta() {
  const clienteConsultas = useQueryClient()
  return useMutation({
    mutationFn: async ({ id, ...datos }: DatosPagarRenta & { id: number }) =>
      (await clienteApi.post<PagoRenta>(`/pagos-renta/${id}/pagar/`, datos)).data,
    onSuccess: () =>
      clienteConsultas.invalidateQueries({ queryKey: ['arrendamientos'] }),
  })
}
