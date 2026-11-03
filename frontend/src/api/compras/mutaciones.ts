import { useMutation, useQueryClient } from '@tanstack/react-query'

import { clienteApi } from '../cliente'
import type { components } from '../tipos.generados'
import type { ContratoCompra, Proveedor } from './consultas'

export type DatosProveedor = components['schemas']['ProveedorEntrada']
export type DatosEditarProveedor = components['schemas']['PatchedProveedorEntrada']
export type DatosContratoCompra = components['schemas']['ContratoCompraEntrada']

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

/**
 * Los contratos tocan una propiedad: además de compras se invalida el catálogo
 * completo, como useInvalidarVenta en ventas (spec 018, §6). Invalidar solo la
 * lista no basta: la ficha tiene su propia clave
 * ['catalogo', 'propiedades', 'detalle', id].
 */
function useInvalidarContratoCompra() {
  const clienteConsultas = useQueryClient()
  return () =>
    Promise.all(
      ['compras', 'catalogo'].map((dominio) =>
        clienteConsultas.invalidateQueries({ queryKey: [dominio] }),
      ),
    )
}

/**
 * POST /contratos-compra/: nace EN_PROCESO. Que la propiedad esté en
 * negociación y sin otro contrato, y el costo total, los resuelve la API
 * (spec 017, reglas 1 a 5).
 */
export function useCrearContratoCompra() {
  const invalidar = useInvalidarContratoCompra()
  return useMutation({
    mutationFn: async (datos: DatosContratoCompra) =>
      (await clienteApi.post<ContratoCompra>('/contratos-compra/', datos)).data,
    onSuccess: invalidar,
  })
}

/** POST /contratos-compra/{id}/completar/: la propiedad pasa a ADQUIRIDA (regla 6). */
export function useCompletarContratoCompra() {
  const invalidar = useInvalidarContratoCompra()
  return useMutation({
    mutationFn: async (id: number) =>
      (await clienteApi.post<ContratoCompra>(`/contratos-compra/${id}/completar/`))
        .data,
    onSuccess: invalidar,
  })
}

/** POST /contratos-compra/{id}/anular/: con motivo; la propiedad no cambia (regla 7). */
export function useAnularContratoCompra() {
  const invalidar = useInvalidarContratoCompra()
  return useMutation({
    mutationFn: async ({ id, motivo }: { id: number; motivo: string }) =>
      (
        await clienteApi.post<ContratoCompra>(`/contratos-compra/${id}/anular/`, {
          motivo,
        })
      ).data,
    onSuccess: invalidar,
  })
}
