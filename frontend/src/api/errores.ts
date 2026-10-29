import { isAxiosError } from 'axios'

/**
 * Formato uniforme de error de la API (spec 001, apps/core/manejador_errores.py):
 *
 *   { "error": { "codigo": "VALIDACION", "mensaje": "...", "detalles": {...} } }
 *
 * Es el único tipo de respuesta escrito a mano: el esquema OpenAPI documenta
 * las respuestas exitosas, no el formato de error del manejador global.
 */
export interface ErrorApi {
  codigo: string
  mensaje: string
  /** En un 400 de validación: { campo: ["mensaje", ...] }. */
  detalles: Record<string, unknown>
}

/**
 * Convierte cualquier error de una petición en un ErrorApi, para mostrarlo
 * (spec 010, regla 8). Si la API no respondió (sin red, o Render despertando),
 * arma un mensaje propio.
 */
export function leerErrorApi(error: unknown): ErrorApi {
  if (isAxiosError(error)) {
    const cuerpo: unknown = error.response?.data
    if (
      typeof cuerpo === 'object' &&
      cuerpo !== null &&
      'error' in cuerpo &&
      typeof cuerpo.error === 'object' &&
      cuerpo.error !== null
    ) {
      return cuerpo.error as ErrorApi
    }
    if (!error.response) {
      return {
        codigo: 'SIN_CONEXION',
        mensaje: 'No se pudo conectar con el servidor. Intente de nuevo.',
        detalles: {},
      }
    }
  }
  return {
    codigo: 'DESCONOCIDO',
    mensaje: 'Ocurrió un error inesperado.',
    detalles: {},
  }
}
