import { useMutation, useQueryClient } from '@tanstack/react-query'

import { clienteApi } from '../cliente'
import type { components } from '../tipos.generados'
import type { DocumentoAgente, TipoDocumentoAgente } from './consultas'

/** Después de escribir, la lista se vuelve a pedir y muestra el estado nuevo. */
function useInvalidarDocumentos() {
  const clienteConsultas = useQueryClient()
  return () => clienteConsultas.invalidateQueries({ queryKey: ['ia', 'documentos'] })
}

export interface DatosSubirDocumentoAgente {
  archivo: File
  titulo: string
  tipo: TipoDocumentoAgente
  /** null si aplica a todos los países. */
  pais: number | null
}

/**
 * POST /documentos-agente/ como multipart/form-data: un archivo no viaja en
 * JSON. La API responde enseguida con el documento PENDIENTE; la indexación
 * la hace el worker (spec 020, regla 4).
 */
export function useSubirDocumentoAgente() {
  const invalidar = useInvalidarDocumentos()
  return useMutation({
    mutationFn: async (datos: DatosSubirDocumentoAgente) => {
      const formulario = new FormData()
      formulario.append('archivo', datos.archivo)
      formulario.append('titulo', datos.titulo)
      formulario.append('tipo', datos.tipo)
      // Sin país, la parte no se envía: la API lo guarda vacío.
      if (datos.pais !== null) {
        formulario.append('pais', String(datos.pais))
      }
      return (await clienteApi.post<DocumentoAgente>('/documentos-agente/', formulario))
        .data
    },
    onSuccess: invalidar,
  })
}

/** PATCH /documentos-agente/{id}/ con otro archivo (regla 2). */
export function useReemplazarDocumentoAgente() {
  const invalidar = useInvalidarDocumentos()
  return useMutation({
    mutationFn: async ({ id, archivo }: { id: number; archivo: File }) => {
      const formulario = new FormData()
      formulario.append('archivo', archivo)
      return (
        await clienteApi.patch<DocumentoAgente>(`/documentos-agente/${id}/`, formulario)
      ).data
    },
    onSuccess: invalidar,
  })
}

/** POST /documentos-agente/{id}/reindexar/: vuelve a encolar (regla 12). */
export function useReindexarDocumentoAgente() {
  const invalidar = useInvalidarDocumentos()
  return useMutation({
    mutationFn: async (id: number) =>
      (await clienteApi.post<DocumentoAgente>(`/documentos-agente/${id}/reindexar/`))
        .data,
    onSuccess: invalidar,
  })
}

/** DELETE /documentos-agente/{id}/: borrado lógico (regla 13). */
export function useDesactivarDocumentoAgente() {
  const invalidar = useInvalidarDocumentos()
  return useMutation({
    mutationFn: async (id: number) => {
      await clienteApi.delete(`/documentos-agente/${id}/`)
    },
    onSuccess: invalidar,
  })
}

export type RespuestaAgente = components['schemas']['RespuestaAgente']
export type CitaAgente = components['schemas']['Cita']

/**
 * POST /agente/consultas/: la pregunta de un visitante (spec 005). Es una
 * mutación y no una consulta: cada pregunta es una llamada nueva a Gemini, y
 * su respuesta no se guarda en caché (spec 018, §5: no se guardan).
 */
export function useConsultarAgente() {
  return useMutation({
    mutationFn: async (pregunta: string) =>
      (await clienteApi.post<RespuestaAgente>('/agente/consultas/', { pregunta })).data,
  })
}
