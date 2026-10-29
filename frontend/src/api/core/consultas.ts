import { useQuery } from '@tanstack/react-query'

import { clienteApi } from '../cliente'
import type { components } from '../tipos.generados'

// El tipo sale del esquema OpenAPI del backend (npm run gen:api), nunca se
// escribe a mano: si el backend cambia un campo, el frontend deja de compilar.
export type EstadoServicio = components['schemas']['EstadoServicio']

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
