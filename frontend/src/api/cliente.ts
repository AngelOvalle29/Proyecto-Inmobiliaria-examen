import axios, { type InternalAxiosRequestConfig } from 'axios'

import type { components } from './tipos.generados'
import {
  borrarTokens,
  guardarAcceso,
  obtenerAcceso,
  obtenerRefresco,
} from '../sesion/tokens'

/**
 * Cliente HTTP único del frontend (docs/frontend.md §2). Ningún componente llama
 * a la API directamente: todo pasa por los hooks de TanStack Query de
 * src/api/<dominio>/, que usan este cliente.
 */
export const clienteApi = axios.create({
  baseURL: import.meta.env.VITE_API_URL,
  // En el plan gratuito, Render tarda alrededor de un minuto en despertar la API
  // (spec 002, §5.8). Con menos tiempo, la primera petición fallaría siempre.
  timeout: 90_000,
})

type RespuestaRenovacion = components['schemas']['RenovarToken']

// Rutas cuyo 401 nunca dispara la renovación (spec 010, regla 5): un 401 del
// login es una contraseña equivocada, y uno de refresh es un token de refresco
// vencido. Renovar ahí haría un ciclo.
const RUTAS_SIN_RENOVACION = ['/auth/login/', '/auth/refresh/']

// Lo que hace la sesión cuando la renovación falla: la registra ContextoSesion.
let alExpirarSesion: () => void = () => {}

export function registrarAlExpirarSesion(funcion: () => void): void {
  alExpirarSesion = funcion
}

// Toda petición lleva el token de acceso, si lo hay.
clienteApi.interceptors.request.use((config) => {
  const acceso = obtenerAcceso()
  if (acceso) {
    config.headers.Authorization = `Bearer ${acceso}`
  }
  return config
})

// La renovación en curso, si hay una. Si cuatro peticiones reciben 401 a la
// vez, las cuatro esperan esta misma promesa: se renueva una sola vez.
let renovacionEnCurso: Promise<string> | null = null

function renovarAcceso(refresco: string): Promise<string> {
  if (!renovacionEnCurso) {
    renovacionEnCurso = clienteApi
      .post<RespuestaRenovacion>('/auth/refresh/', { refresh: refresco })
      .then((respuesta) => {
        guardarAcceso(respuesta.data.access)
        return respuesta.data.access
      })
      .finally(() => {
        renovacionEnCurso = null
      })
  }
  return renovacionEnCurso
}

interface ConfigReintentable extends InternalAxiosRequestConfig {
  _reintentada?: boolean
}

// Ante un 401: renueva el token una vez y repite la petición (regla 5).
clienteApi.interceptors.response.use(undefined, async (error) => {
  const config: ConfigReintentable | undefined = error.config
  const refresco = obtenerRefresco()
  const esRutaDeSesion = RUTAS_SIN_RENOVACION.some((ruta) => config?.url === ruta)

  if (
    error.response?.status !== 401 ||
    !config ||
    config._reintentada ||
    esRutaDeSesion ||
    !refresco
  ) {
    throw error
  }

  config._reintentada = true
  try {
    const acceso = await renovarAcceso(refresco)
    config.headers.Authorization = `Bearer ${acceso}`
    return await clienteApi(config)
  } catch (errorRenovacion) {
    // Solo si la API rechazó el token de refresco (vencido o inválido) se
    // cierra la sesión. Si falló la red, o la petición repetida, se conserva.
    if (refrescoRechazado(errorRenovacion)) {
      borrarTokens()
      alExpirarSesion()
    }
    throw errorRenovacion
  }
})

function refrescoRechazado(error: unknown): boolean {
  return (
    axios.isAxiosError(error) &&
    error.config?.url === '/auth/refresh/' &&
    error.response?.status === 401
  )
}
