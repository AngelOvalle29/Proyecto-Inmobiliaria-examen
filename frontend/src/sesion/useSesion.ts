import { createContext, useContext } from 'react'

import type { UsuarioActual } from '../api/usuarios/consultas'
import type { Tokens } from '../api/usuarios/mutaciones'

/**
 * - cargando: hay un token de refresco y se está recuperando el usuario.
 * - sin-sesion: no hay sesión, o la API rechazó el token de refresco.
 * - sin-conexion: hay sesión, pero la API no respondió (red, o Render dormido).
 * - con-sesion: usuario cargado.
 */
export type EstadoSesion = 'cargando' | 'sin-sesion' | 'sin-conexion' | 'con-sesion'

export interface ValorSesion {
  estado: EstadoSesion
  usuario: UsuarioActual | null
  /** Guarda los tokens recibidos del login y carga al usuario. */
  abrirSesion: (tokens: Tokens) => void
  /** Borra los tokens y la caché de TanStack Query (spec 010, regla 6). */
  cerrarSesion: () => void
  /**
   * Cierra la sesión porque el usuario lo pidió: el login no recuerda su
   * página, que no es del siguiente usuario. Si la sesión vence, sí se recuerda.
   */
  salir: () => void
  /** false después de salir: RutaProtegida no guarda la ruta actual. */
  recordarRuta: boolean
  /** Vuelve a pedir el usuario después de un error de conexión. */
  reintentar: () => void
}

export const ContextoSesion = createContext<ValorSesion | null>(null)

/** La sesión actual. Es el único estado global del frontend (docs/frontend.md §3). */
export function useSesion(): ValorSesion {
  const valor = useContext(ContextoSesion)
  if (!valor) {
    throw new Error('useSesion debe usarse dentro de ProveedorSesion')
  }
  return valor
}
