import { keepPreviousData, useQuery } from '@tanstack/react-query'

import { clienteApi } from '../cliente'
import type { components, operations } from '../tipos.generados'

export type UsuarioActual = components['schemas']['UsuarioActual']
type PaginaUsuarios = components['schemas']['PaginatedUsuarioListadoList']

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

/**
 * Usuarios con rol de agente, para CampoRelacion. El filtro no es opcional:
 * crear_agente rechaza cualquier otro rol (spec 013, §2).
 */
export function useOpcionesUsuarioAgente(texto: string) {
  const consulta = useQuery({
    queryKey: ['usuarios', 'agentes', texto],
    queryFn: async () =>
      (
        await clienteApi.get<PaginaUsuarios>('/usuarios/', {
          params: { rol: 'AGENTE', buscar: texto || undefined },
        })
      ).data.results,
  })
  return {
    opciones: (consulta.data ?? []).map((usuario) => ({
      valor: String(usuario.id),
      etiqueta: `${usuario.nombre_completo} · ${usuario.email}`,
    })),
    cargando: consulta.isFetching,
  }
}

// ---------- Gestión de usuarios (spec 026) ----------

export type UsuarioListado = components['schemas']['UsuarioListado']
export type UsuarioDetalle = components['schemas']['UsuarioDetalle']

/** Filtros de GET /usuarios/: estado, rol, búsqueda y página. */
export type FiltrosUsuarios = NonNullable<
  operations['v1_usuarios_list']['parameters']['query']
>

/** Los usuarios del sistema; sin estado, solo los activos. */
export function useUsuarios(filtros: FiltrosUsuarios) {
  return useQuery({
    queryKey: ['usuarios', 'lista', filtros],
    queryFn: async () =>
      (await clienteApi.get<PaginaUsuarios>('/usuarios/', { params: filtros })).data,
    placeholderData: keepPreviousData,
  })
}

/** Una cuenta, para el formulario de edición. */
export function useUsuario(id: number) {
  return useQuery({
    queryKey: ['usuarios', 'detalle', id],
    queryFn: async () =>
      (await clienteApi.get<UsuarioDetalle>(`/usuarios/${id}/`)).data,
  })
}

export type NombreRol = components['schemas']['RolEnum']

/** Cómo se muestra cada rol. Record obliga a cubrir los cinco. */
export const ETIQUETAS_ROL: Record<NombreRol, string> = {
  ADMINISTRADOR: 'Administrador',
  GERENTE: 'Gerente',
  AGENTE: 'Agente',
  CONTABILIDAD: 'Contabilidad',
  CONSULTA: 'Consulta',
}
