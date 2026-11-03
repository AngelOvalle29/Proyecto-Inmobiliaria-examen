import { useMutation, useQueryClient } from '@tanstack/react-query'

import { clienteApi } from '../cliente'
import type { components } from '../tipos.generados'
import type { Proveedor } from './consultas'

export type DatosProveedor = components['schemas']['ProveedorEntrada']
export type DatosEditarProveedor = components['schemas']['PatchedProveedorEntrada']

/**
 * Después de escribir se invalida todo lo de compras: la lista y el detalle
 * del proveedor empiezan con ['compras'] (spec 018, §6).
 */
function useInvalidarCompras() {
  const clienteConsultas = useQueryClient()
  return () => clienteConsultas.invalidateQueries({ queryKey: ['compras'] })
}

/** POST /proveedores/: el backend asigna el código PRV-0001 (spec 006, regla 8). */
export function useCrearProveedor() {
  const invalidar = useInvalidarCompras()
  return useMutation({
    mutationFn: async (datos: DatosProveedor) =>
      (await clienteApi.post<Proveedor>('/proveedores/', datos)).data,
    onSuccess: invalidar,
  })
}

/**
 * PATCH /proveedores/{id}/. La API revisa las reglas sobre el resultado final:
 * si cambia el tipo a banco, el NIT que ya tenía debe existir.
 */
export function useEditarProveedor() {
  const invalidar = useInvalidarCompras()
  return useMutation({
    mutationFn: async ({ id, ...datos }: DatosEditarProveedor & { id: number }) =>
      (await clienteApi.patch<Proveedor>(`/proveedores/${id}/`, datos)).data,
    onSuccess: invalidar,
  })
}

/**
 * DELETE /proveedores/{id}/: borrado lógico. Responde 409 si el proveedor
 * tiene un contrato de compra en proceso (spec 017, regla 22).
 */
export function useDesactivarProveedor() {
  const invalidar = useInvalidarCompras()
  return useMutation({
    mutationFn: async (id: number) => {
      await clienteApi.delete(`/proveedores/${id}/`)
    },
    onSuccess: invalidar,
  })
}
