import { keepPreviousData, useQuery } from '@tanstack/react-query'

import { clienteApi } from '../cliente'
import type { components, operations } from '../tipos.generados'

export type Propiedad = components['schemas']['Propiedad']
type PaginaUnidades = components['schemas']['PaginatedUnidadList']
export type TipoPropiedad = components['schemas']['TipoPropiedad']
export type EstadoPropiedad = components['schemas']['EstadoPropiedadEnum']
type PaginaPropiedades = components['schemas']['PaginatedPropiedadList']
type PaginaTipos = components['schemas']['PaginatedTipoPropiedadList']

/** Filtros que acepta GET /propiedades/, tal como los documenta el esquema. */
export type FiltrosPropiedades = NonNullable<
  operations['v1_propiedades_list']['parameters']['query']
>

/**
 * Etiqueta de cada estado. Record<EstadoPropiedad, …> obliga a cubrirlos
 * todos: si el backend agrega un estado, el frontend deja de compilar hasta
 * que se le ponga etiqueta.
 */
export const ETIQUETAS_ESTADO: Record<EstadoPropiedad, string> = {
  EN_NEGOCIACION: 'En negociación',
  ADQUIRIDA: 'Adquirida',
  EN_CONSTRUCCION: 'En construcción',
  DISPONIBLE: 'Disponible',
  RESERVADA: 'Reservada',
  VENDIDA: 'Vendida',
  ARRENDADA: 'Arrendada',
  BAJA: 'Baja',
}

/**
 * Una página de propiedades con sus filtros (spec 010, regla 7). Los filtros
 * van a la API; el navegador nunca filtra. keepPreviousData deja la página
 * anterior a la vista mientras llega la siguiente, en vez de vaciar la tabla.
 */
export function usePropiedades(filtros: FiltrosPropiedades) {
  return useQuery({
    queryKey: ['catalogo', 'propiedades', filtros],
    queryFn: async () =>
      (await clienteApi.get<PaginaPropiedades>('/propiedades/', { params: filtros }))
        .data,
    placeholderData: keepPreviousData,
  })
}

/** Tipos de propiedad activos. Son pocos (siete): caben en una página. */
/** Las unidades de una propiedad; sin propiedad elegida no consulta nada. */
export function useUnidadesDePropiedad(propiedad: number | undefined) {
  return useQuery({
    queryKey: ['catalogo', 'unidades', propiedad],
    queryFn: async () =>
      (await clienteApi.get<PaginaUnidades>(`/propiedades/${propiedad}/unidades/`)).data
        .results,
    enabled: propiedad !== undefined,
  })
}

export function useTiposPropiedad() {
  return useQuery({
    queryKey: ['catalogo', 'tipos-propiedad'],
    queryFn: async () =>
      (await clienteApi.get<PaginaTipos>('/tipos-propiedad/')).data.results,
    staleTime: 5 * 60_000,
  })
}
