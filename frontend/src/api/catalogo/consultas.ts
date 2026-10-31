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

/**
 * Propiedades para CampoRelacion. No se filtra por DISPONIBLE: un edificio con
 * unidades disponibles puede tener otro estado. El estado se muestra en la
 * opción, y si el bien no se puede cotizar o vender lo responde la API.
 */
export function useOpcionesPropiedad(texto: string) {
  const consulta = usePropiedades({ buscar: texto || undefined })
  return {
    opciones: (consulta.data?.results ?? []).map((propiedad) => ({
      valor: String(propiedad.id),
      etiqueta: `${propiedad.codigo} · ${propiedad.nombre} (${ETIQUETAS_ESTADO[propiedad.estado]})`,
    })),
    cargando: consulta.isFetching,
  }
}

/** La API no busca unidades: se filtra por texto lo que devuelve la propiedad. */
export function useOpcionesUnidad(texto: string, valores: { propiedad: string }) {
  const propiedad = valores.propiedad ? Number(valores.propiedad) : undefined
  const consulta = useUnidadesDePropiedad(propiedad)
  const buscado = texto.toLowerCase()
  return {
    opciones: (consulta.data ?? [])
      .filter((unidad) => unidad.codigo.toLowerCase().includes(buscado))
      .map((unidad) => ({
        valor: String(unidad.id),
        etiqueta: `${unidad.codigo} (${ETIQUETAS_ESTADO[unidad.estado]})`,
      })),
    cargando: consulta.isFetching,
  }
}

export function useTiposPropiedad() {
  return useQuery({
    queryKey: ['catalogo', 'tipos-propiedad'],
    queryFn: async () =>
      (await clienteApi.get<PaginaTipos>('/tipos-propiedad/')).data.results,
    staleTime: 5 * 60_000,
  })
}
