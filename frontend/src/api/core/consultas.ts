import { useQuery } from '@tanstack/react-query'

import { clienteApi } from '../cliente'
import type { components } from '../tipos.generados'

// El tipo sale del esquema OpenAPI del backend (npm run gen:api), nunca se
// escribe a mano: si el backend cambia un campo, el frontend deja de compilar.
export type EstadoServicio = components['schemas']['EstadoServicio']
export type Ciudad = components['schemas']['Ciudad']
type PaginaPaises = components['schemas']['PaginatedPaisList']
type PaginaMonedas = components['schemas']['PaginatedMonedaList']
type PaginaCiudades = components['schemas']['PaginatedCiudadList']

// Países y monedas son catálogos cortos (cinco de cada uno en la demo) y casi no
// cambian: una página alcanza, y se guardan en caché un buen rato.
const CINCO_MINUTOS = 5 * 60_000

export function usePaises() {
  return useQuery({
    queryKey: ['core', 'paises'],
    queryFn: async () => (await clienteApi.get<PaginaPaises>('/paises/')).data.results,
    staleTime: CINCO_MINUTOS,
  })
}

export function useMonedas() {
  return useQuery({
    queryKey: ['core', 'monedas'],
    queryFn: async () =>
      (await clienteApi.get<PaginaMonedas>('/monedas/')).data.results,
    staleTime: CINCO_MINUTOS,
  })
}

/**
 * Ciudades de un país cuyo nombre contiene el texto (spec 010, regla 11). Sin
 * país no consulta: la ciudad depende del país elegido (regla 12).
 */
export function useBuscarCiudades(texto: string, paisId: number | undefined) {
  return useQuery({
    queryKey: ['core', 'ciudades', paisId, texto],
    queryFn: async () =>
      (
        await clienteApi.get<PaginaCiudades>('/ciudades/', {
          params: { pais: paisId, buscar: texto || undefined },
        })
      ).data.results,
    enabled: paisId !== undefined,
  })
}

/** Estado de la API y de su base de datos (GET /api/v1/health/). */
export function useEstadoServicio() {
  return useQuery({
    queryKey: ['core', 'estado-servicio'],
    queryFn: async () => {
      const respuesta = await clienteApi.get<EstadoServicio>('/health/', {
        // 503 no es un fallo de la petición: es la API diciendo que su base de
        // datos no responde, con el mismo formato que un 200.
        validateStatus: (codigo) => codigo === 200 || codigo === 503,
      })
      return respuesta.data
    },
    // Un reintento: la primera petición puede fallar mientras Render despierta.
    retry: 1,
  })
}
