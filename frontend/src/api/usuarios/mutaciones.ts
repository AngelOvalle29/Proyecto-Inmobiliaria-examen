import { useMutation } from '@tanstack/react-query'

import { clienteApi } from '../cliente'
import type { components } from '../tipos.generados'

export type DatosLogin = components['schemas']['Login']
export type Tokens = components['schemas']['Tokens']

/** Par de tokens a cambio de correo y contraseña (POST /api/v1/auth/login/). */
export function useIniciarSesion() {
  return useMutation({
    mutationFn: async (datos: DatosLogin) =>
      (await clienteApi.post<Tokens>('/auth/login/', datos)).data,
  })
}
