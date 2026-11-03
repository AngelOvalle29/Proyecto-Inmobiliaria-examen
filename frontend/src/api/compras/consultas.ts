import { keepPreviousData, useQuery } from '@tanstack/react-query'

import { clienteApi } from '../cliente'
import type { components, operations } from '../tipos.generados'

export type Proveedor = components['schemas']['Proveedor']
export type TipoProveedor = components['schemas']['TipoProveedorEnum']
type PaginaProveedores = components['schemas']['PaginatedProveedorList']

/** Filtros que acepta GET /proveedores/, tal como los documenta el esquema. */
export type FiltrosProveedores = NonNullable<
  operations['v1_proveedores_list']['parameters']['query']
>

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
