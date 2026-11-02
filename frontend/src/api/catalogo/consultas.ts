import { keepPreviousData, useQuery } from '@tanstack/react-query'

import { clienteApi } from '../cliente'
import type { components, operations } from '../tipos.generados'

export type Propiedad = components['schemas']['Propiedad']
export type Unidad = components['schemas']['Unidad']
type PaginaUnidades = components['schemas']['PaginatedUnidadList']

/** Filtros de GET /propiedades/{id}/unidades/: página y búsqueda por código. */
export type FiltrosUnidades = NonNullable<
  operations['v1_propiedades_unidades_list']['parameters']['query']
>
export type Avaluo = components['schemas']['Avaluo']
export type DocumentoOficial = components['schemas']['DocumentoOficial']
export type TipoDocumento = components['schemas']['TipoDocumentoEnum']
type PaginaAvaluos = components['schemas']['PaginatedAvaluoList']
type PaginaDocumentos = components['schemas']['PaginatedDocumentoOficialList']

/** Filtros de GET /propiedades/{id}/documentos/: página y tipo. */
export type FiltrosDocumentos = NonNullable<
  operations['v1_propiedades_documentos_list']['parameters']['query']
>
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

/** Etiqueta de cada tipo de documento (spec 011); como ETIQUETAS_ESTADO. */
export const ETIQUETAS_TIPO_DOCUMENTO: Record<TipoDocumento, string> = {
  ESCRITURA: 'Escritura',
  LICENCIA: 'Licencia',
  PLANO: 'Plano',
  CERTIFICACION: 'Certificación',
  AVALUO: 'Avalúo',
  CONTRATO: 'Contrato',
  OTRO: 'Otro',
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

/**
 * Una propiedad (GET /propiedades/{id}/), para su ficha y su edición. La clave
 * empieza igual que la de la lista: al guardar se invalidan las dos.
 */
export function usePropiedad(id: number) {
  return useQuery({
    queryKey: ['catalogo', 'propiedades', 'detalle', id],
    queryFn: async () => (await clienteApi.get<Propiedad>(`/propiedades/${id}/`)).data,
  })
}

/**
 * Una página de unidades de una propiedad, con búsqueda por código en la API
 * (spec 014, regla 11). Sin propiedad elegida no consulta nada. Lo usan la
 * pestaña Unidades de la ficha y useOpcionesUnidad: una sola clave de caché,
 * con la misma forma de respuesta.
 */
export function useUnidadesDePropiedad(
  propiedad: number | undefined,
  filtros: FiltrosUnidades = {},
) {
  return useQuery({
    queryKey: ['catalogo', 'unidades', propiedad, filtros],
    queryFn: async () =>
      (
        await clienteApi.get<PaginaUnidades>(`/propiedades/${propiedad}/unidades/`, {
          params: filtros,
        })
      ).data,
    enabled: propiedad !== undefined,
    placeholderData: keepPreviousData,
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

/**
 * Unidades de la propiedad elegida, para CampoRelacion. La búsqueda la hace la
 * API (?buscar=), así encuentra unidades que no están en la primera página.
 */
export function useOpcionesUnidad(texto: string, valores: { propiedad: string }) {
  const propiedad = valores.propiedad ? Number(valores.propiedad) : undefined
  const consulta = useUnidadesDePropiedad(propiedad, { buscar: texto || undefined })
  return {
    opciones: (consulta.data?.results ?? []).map((unidad) => ({
      valor: String(unidad.id),
      etiqueta: `${unidad.codigo} (${ETIQUETAS_ESTADO[unidad.estado]})`,
    })),
    cargando: consulta.isFetching,
  }
}

/**
 * Los avalúos de una propiedad, del más reciente al más antiguo: el backend
 * ya los ordena así (spec 011). Solo se piden al abrir la pestaña (regla 1).
 */
export function useAvaluos(propiedad: number, pagina: number) {
  return useQuery({
    queryKey: ['catalogo', 'avaluos', propiedad, pagina],
    queryFn: async () =>
      (
        await clienteApi.get<PaginaAvaluos>(`/propiedades/${propiedad}/avaluos/`, {
          params: { page: pagina },
        })
      ).data,
    placeholderData: keepPreviousData,
  })
}

/** Los documentos de una propiedad, con filtro por tipo. Sin propiedad no consulta. */
export function useDocumentos(
  propiedad: number | undefined,
  filtros: FiltrosDocumentos = {},
) {
  return useQuery({
    queryKey: ['catalogo', 'documentos', propiedad, filtros],
    queryFn: async () =>
      (
        await clienteApi.get<PaginaDocumentos>(
          `/propiedades/${propiedad}/documentos/`,
          {
            params: filtros,
          },
        )
      ).data,
    placeholderData: keepPreviousData,
    enabled: propiedad !== undefined,
  })
}

/**
 * Contratos escaneados de la propiedad elegida, para CampoRelacion (spec 007,
 * regla 23). Son pocos: se filtra por texto lo que devuelve la API.
 */
export function useOpcionesDocumento(texto: string, valores: { propiedad: string }) {
  const propiedad = valores.propiedad ? Number(valores.propiedad) : undefined
  const consulta = useDocumentos(propiedad, { tipo: 'CONTRATO' })
  const buscado = texto.toLowerCase()
  return {
    opciones: (consulta.data?.results ?? [])
      .filter((documento) => documento.nombre.toLowerCase().includes(buscado))
      .map((documento) => ({
        valor: String(documento.id),
        etiqueta: documento.nombre,
      })),
    cargando: consulta.isFetching,
  }
}

/** Tipos de propiedad activos. Son pocos (siete): caben en una página. */
export function useTiposPropiedad() {
  return useQuery({
    queryKey: ['catalogo', 'tipos-propiedad'],
    queryFn: async () =>
      (await clienteApi.get<PaginaTipos>('/tipos-propiedad/')).data.results,
    staleTime: 5 * 60_000,
  })
}
