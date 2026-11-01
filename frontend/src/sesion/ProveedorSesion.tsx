import { useQueryClient } from '@tanstack/react-query'
import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'

import { registrarAlExpirarSesion } from '../api/cliente'
import { useUsuarioActual } from '../api/usuarios/consultas'
import type { Tokens } from '../api/usuarios/mutaciones'
import { borrarTokens, guardarTokens, obtenerRefresco } from './tokens'
import { ContextoSesion, type EstadoSesion, type ValorSesion } from './useSesion'

/**
 * Mantiene la sesión (spec 010, reglas 4 a 6). Al cargar la página, si hay un
 * token de refresco guardado, pide el usuario actual: el interceptor obtiene
 * antes un token de acceso nuevo, así que recargar no obliga a volver a entrar.
 */
export function ProveedorSesion({ children }: { children: ReactNode }) {
  const clienteConsultas = useQueryClient()
  const [hayRefresco, setHayRefresco] = useState(() => obtenerRefresco() !== null)
  const [recordarRuta, setRecordarRuta] = useState(true)
  const consulta = useUsuarioActual(hayRefresco)

  const cerrarSesion = useCallback(() => {
    borrarTokens()
    // Sin esto, el siguiente usuario vería en caché los datos del anterior.
    clienteConsultas.clear()
    setHayRefresco(false)
  }, [clienteConsultas])

  const salir = useCallback(() => {
    setRecordarRuta(false)
    cerrarSesion()
  }, [cerrarSesion])

  const abrirSesion = useCallback((tokens: Tokens) => {
    guardarTokens(tokens.access, tokens.refresh)
    setRecordarRuta(true)
    setHayRefresco(true)
  }, [])

  // Si el interceptor no logra renovar el token, la sesión se cierra aquí.
  useEffect(() => {
    registrarAlExpirarSesion(cerrarSesion)
  }, [cerrarSesion])

  const { refetch } = consulta
  const reintentar = useCallback(() => void refetch(), [refetch])

  let estado: EstadoSesion
  if (!hayRefresco) {
    estado = 'sin-sesion'
  } else if (consulta.isPending) {
    estado = 'cargando'
  } else if (consulta.isError) {
    estado = 'sin-conexion'
  } else {
    estado = 'con-sesion'
  }
  const usuario = estado === 'con-sesion' ? (consulta.data ?? null) : null

  const valor = useMemo<ValorSesion>(
    () => ({
      estado,
      usuario,
      abrirSesion,
      cerrarSesion,
      salir,
      recordarRuta,
      reintentar,
    }),
    [estado, usuario, abrirSesion, cerrarSesion, salir, recordarRuta, reintentar],
  )

  return <ContextoSesion.Provider value={valor}>{children}</ContextoSesion.Provider>
}
