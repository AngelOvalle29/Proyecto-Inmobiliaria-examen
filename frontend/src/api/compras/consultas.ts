import { keepPreviousData, useQuery } from '@tanstack/react-query'

import { clienteApi } from '../cliente'
import type { components, operations } from '../tipos.generados'

export type Proveedor = components['schemas']['Proveedor']
export type TipoProveedor = components['schemas']['TipoProveedorEnum']
export type ContratoCompra = components['schemas']['ContratoCompra']
export type EstadoContratoCompra = components['schemas']['EstadoContratoCompraEnum']
type PaginaProveedores = components['schemas']['PaginatedProveedorList']
type PaginaContratos = components['schemas']['PaginatedContratoCompraList']

/** Filtros que acepta GET /proveedores/, tal como los documenta el esquema. */
export type FiltrosProveedores = NonNullable<
  operations['v1_proveedores_list']['parameters']['query']
>

/** Filtros que acepta GET /contratos-compra/. */
export type FiltrosContratosCompra = NonNullable<
  operations['v1_contratos_compra_list']['parameters']['query']
>

/** Etiqueta de cada estado de un contrato de compra (spec 017, reglas 1, 6 y 7). */
export const ETIQUETAS_ESTADO_CONTRATO_COMPRA: Record<EstadoContratoCompra, string> = {
  EN_PROCESO: 'En proceso',
  COMPLETADO: 'Completado',
  ANULADO: 'Anulado',
}

/**
 * Etiqueta de cada tipo de proveedor (spec 006, regla 1). Record<TipoProveedor, …>
 * obliga a cubrirlos todos: si el backend agrega un tipo, el frontend deja de
 * compilar hasta que se le ponga etiqueta.
 */
export const ETIQUETAS_TIPO_PROVEEDOR: Record<TipoProveedor, string> = {
  PROPIETARIO_PARTICULAR: 'Propietario particular',
  INMOBILIARIA: 'Inmobiliaria',
  BANCO: 'Banco',
  GOBIERNO: 'Gobierno',
  OTRO: 'Otro',
}

/**
 * Una página de proveedores activos con sus filtros (spec 018, §5). Los
 * filtros van a la API; el navegador nunca filtra.
 */
export function useProveedores(filtros: FiltrosProveedores) {
  return useQuery({
    queryKey: ['compras', 'proveedores', filtros],
    queryFn: async () =>
      (await clienteApi.get<PaginaProveedores>('/proveedores/', { params: filtros }))
        .data,
    placeholderData: keepPreviousData,
  })
}

/**
 * Un proveedor, para su formulario de edición. La clave empieza igual que la
 * de la lista: al guardar se invalidan las dos.
 */
export function useProveedor(id: number) {
  return useQuery({
    queryKey: ['compras', 'proveedores', 'detalle', id],
    queryFn: async () => (await clienteApi.get<Proveedor>(`/proveedores/${id}/`)).data,
  })
}

/**
 * Proveedores activos que coinciden con el texto, para CampoRelacion (spec
 * 010, regla 11). La API solo devuelve activos: uno desactivado no se puede
 * elegir, y si llegara, la API respondería 400 (spec 017, regla 1).
 */
export function useOpcionesProveedor(texto: string) {
  const consulta = useProveedores({ buscar: texto || undefined })
  return {
    opciones: (consulta.data?.results ?? []).map((proveedor) => ({
      valor: String(proveedor.id),
      etiqueta: `${proveedor.codigo ?? ''} · ${proveedor.nombre}`,
    })),
    cargando: consulta.isFetching,
  }
}

/** Una página de contratos de compra con su filtro de estado (spec 018, §5). */
export function useContratosCompra(filtros: FiltrosContratosCompra) {
  return useQuery({
    queryKey: ['compras', 'contratos', filtros],
    queryFn: async () =>
      (await clienteApi.get<PaginaContratos>('/contratos-compra/', { params: filtros }))
        .data,
    placeholderData: keepPreviousData,
  })
}
