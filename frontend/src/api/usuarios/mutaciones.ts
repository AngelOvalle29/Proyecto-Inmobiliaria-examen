import { useMutation, useQueryClient } from '@tanstack/react-query'

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

// ---------- Gestión de usuarios (spec 026) ----------

type UsuarioDetalle = components['schemas']['UsuarioDetalle']
export type DatosNuevoUsuario = components['schemas']['UsuarioCrear']
export type DatosEditarUsuario = components['schemas']['PatchedUsuarioEditar']

/** Después de escribir, la lista y el detalle se vuelven a pedir. */
function useInvalidarUsuarios() {
  const clienteConsultas = useQueryClient()
  return () => clienteConsultas.invalidateQueries({ queryKey: ['usuarios'] })
}

/** POST /usuarios/: solo administración (spec 026, regla 1). */
export function useCrearUsuario() {
  const invalidar = useInvalidarUsuarios()
  return useMutation({
    mutationFn: async (datos: DatosNuevoUsuario) =>
      (await clienteApi.post<UsuarioDetalle>('/usuarios/', datos)).data,
    onSuccess: invalidar,
  })
}

/** PATCH /usuarios/{id}/: nombre, rol, país y teléfono; el correo no. */
export function useEditarUsuario() {
  const invalidar = useInvalidarUsuarios()
  return useMutation({
    mutationFn: async ({ id, ...datos }: DatosEditarUsuario & { id: number }) =>
      (await clienteApi.patch<UsuarioDetalle>(`/usuarios/${id}/`, datos)).data,
    onSuccess: invalidar,
  })
}

/** POST /usuarios/{id}/desactivar/ o /reactivar/. */
export function useCambiarEstadoUsuario() {
  const invalidar = useInvalidarUsuarios()
  return useMutation({
    mutationFn: async ({
      id,
      accion,
    }: {
      id: number
      accion: 'desactivar' | 'reactivar'
    }) => (await clienteApi.post<UsuarioDetalle>(`/usuarios/${id}/${accion}/`)).data,
    onSuccess: invalidar,
  })
}

/** POST /usuarios/{id}/restablecer-contrasena/: responde 204. */
export function useRestablecerContrasena() {
  return useMutation({
    mutationFn: async ({ id, password }: { id: number; password: string }) => {
      await clienteApi.post(`/usuarios/${id}/restablecer-contrasena/`, { password })
    },
  })
}

/** POST /auth/cambiar-contrasena/: cualquier usuario, dando la actual. */
export function useCambiarMiContrasena() {
  return useMutation({
    mutationFn: async (datos: components['schemas']['CambiarContrasena']) => {
      await clienteApi.post('/auth/cambiar-contrasena/', datos)
    },
  })
}
