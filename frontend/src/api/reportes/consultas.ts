import { useMutation, useQuery } from '@tanstack/react-query'
import { isAxiosError } from 'axios'

import { clienteApi } from '../cliente'
import { nombreCliente } from '../crm/consultas'
import type { components, operations } from '../tipos.generados'

export type Reporte = components['schemas']['Reporte']
export type DefinicionReporte = components['schemas']['CatalogoReporte']
export type FiltroReporte = components['schemas']['FiltroReporte']
export type FilaReporte = Reporte['filas']['results'][number]
type PaginaCatalogo = components['schemas']['PaginatedCatalogoReporteList']
type Parametros = NonNullable<operations['v1_reportes_retrieve']['parameters']['query']>
export type ValoresFiltros = Record<string, string>

export function useCatalogoReportes() {
  return useQuery({
    queryKey: ['reportes', 'catalogo'],
    queryFn: async () => (await clienteApi.get<PaginaCatalogo>('/reportes/')).data,
  })
}

export function useReporte(slug: string, filtros: ValoresFiltros, pagina: number) {
  return useQuery({
    queryKey: ['reportes', slug, filtros, pagina],
    queryFn: async () => {
      const params: Parametros = { ...filtros, page: pagina }
      return (await clienteApi.get<Reporte>(`/reportes/${slug}/`, { params })).data
    },
    enabled: Boolean(slug),
    retry: false,
  })
}

type Opcion =
  | components['schemas']['Ciudad']
  | components['schemas']['Moneda']
  | components['schemas']['Pais']
  | components['schemas']['TipoPropiedad']
  | components['schemas']['Agente']
  | components['schemas']['Cliente']

function etiquetaOpcion(opcion: Opcion): string {
  if ('usuario' in opcion) return opcion.usuario.nombre_completo
  if ('razon_social' in opcion) return nombreCliente(opcion)
  return opcion.nombre ?? ''
}

/** Catálogos paginados: búsqueda y siguiente página sin traerlos completos. */
export function useOpcionesFiltro(origen: string, texto: string, pagina: number) {
  return useQuery({
    queryKey: ['reportes', 'opciones', origen, texto, pagina],
    queryFn: async () => {
      const respuesta = await clienteApi.get<
        | components['schemas']['PaginatedCiudadList']
        | components['schemas']['PaginatedMonedaList']
        | components['schemas']['PaginatedPaisList']
        | components['schemas']['PaginatedTipoPropiedadList']
        | components['schemas']['PaginatedAgenteList']
        | components['schemas']['PaginatedClienteList']
      >(origen, { params: { buscar: texto || undefined, page: pagina } })
      return {
        siguiente: respuesta.data.next,
        opciones: respuesta.data.results.map((opcion) => ({
          // Solo la moneda se filtra por código; lo demás, por id, aunque
          // agentes y clientes también tengan un código.
          valor:
            origen === '/monedas/' && 'codigo' in opcion
              ? opcion.codigo!
              : String(opcion.id),
          etiqueta: etiquetaOpcion(opcion),
        })),
      }
    },
    enabled: origen.startsWith('/'),
  })
}

export function useDescargarReporte() {
  return useMutation({
    mutationFn: async ({
      slug,
      formato,
      filtros,
      codigo,
    }: {
      slug: string
      formato: 'excel' | 'pdf'
      filtros: ValoresFiltros
      codigo: string
    }) => {
      try {
        const respuesta = await clienteApi.get<Blob>(`/reportes/${slug}/${formato}/`, {
          params: filtros,
          responseType: 'blob',
        })
        const nombre =
          /filename="([^"]+)"/.exec(
            String(respuesta.headers['content-disposition']),
          )?.[1] ?? `${codigo}_${slug}.${formato === 'excel' ? 'xlsx' : 'pdf'}`
        const url = URL.createObjectURL(respuesta.data)
        const enlace = document.createElement('a')
        enlace.href = url
        enlace.download = nombre
        enlace.click()
        setTimeout(() => URL.revokeObjectURL(url), 1000)
      } catch (error) {
        // Axios recibe también los errores JSON como Blob en una descarga.
        if (isAxiosError(error) && error.response?.data instanceof Blob) {
          try {
            error.response.data = JSON.parse(await error.response.data.text())
          } catch {
            /* El manejador común mostrará el error genérico. */
          }
        }
        throw error
      }
    },
  })
}
