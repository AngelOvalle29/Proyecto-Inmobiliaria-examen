import { useQuery } from '@tanstack/react-query'

import { clienteApi } from '../cliente'
import type { components } from '../tipos.generados'

export type UsuarioActual = components['schemas']['UsuarioActual']

export const CLAVE_USUARIO_ACTUAL = ['usuarios', 'yo'] as const

/**
 * Usuario dueño de la sesión (GET /api/v1/auth/yo/). Solo consulta cuando hay
 * un token de refresco: sin él no hay sesión que recuperar. Si el token de
 * acceso no existe o venció, el interceptor de cliente.ts lo renueva primero.
 */
export function useUsuarioActual(habilitada: boolean) {
  return useQuery({
    queryKey: CLAVE_USUARIO_ACTUAL,
    queryFn: async () => (await clienteApi.get<UsuarioActual>('/auth/yo/')).data,
    enabled: habilitada,
    // Un 401 aquí no se arregla reintentando, y el usuario no cambia mientras
    // dura la sesión.
    retry: false,
    staleTime: Infinity,
  })
}
