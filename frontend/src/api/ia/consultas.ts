import { keepPreviousData, useQuery } from '@tanstack/react-query'

import { clienteApi } from '../cliente'
import type { components, operations } from '../tipos.generados'

export type DocumentoAgente = components['schemas']['DocumentoAgente']
export type TipoDocumentoAgente = components['schemas']['TipoDocumentoRAGEnum']
export type EstadoIndexacion = components['schemas']['EstadoIndexacionEnum']
type PaginaDocumentosAgente = components['schemas']['PaginatedDocumentoAgenteList']

/** Filtros de GET /documentos-agente/: página, tipo, estado y título. */
export type FiltrosDocumentosAgente = NonNullable<
  operations['v1_documentos_agente_list']['parameters']['query']
>

export const ETIQUETAS_TIPO_DOCUMENTO_AGENTE: Record<TipoDocumentoAgente, string> = {
  POLITICA: 'Política de la agencia',
  MANUAL: 'Manual de procesos',
  LEGAL: 'Requisito legal',
  PLANTILLA: 'Plantilla',
  FICHA_PROPIEDAD: 'Ficha de propiedad',
}

export const ETIQUETAS_ESTADO_INDEXACION: Record<EstadoIndexacion, string> = {
  PENDIENTE: 'Pendiente',
  INDEXADO: 'Indexado',
  ERROR: 'Error',
}

/** Cada cuánto se vuelve a pedir la lista mientras la cola trabaja. */
const INTERVALO_MS = 5_000
/**
 * Un pendiente de hace más de 10 minutos ya no va a cambiar solo: con los
 * reintentos, una indexación tarda a lo sumo unos 7 (spec 020, §10).
 */
const PENDIENTE_RECIENTE_MS = 10 * 60_000

/** true si algún documento sigue pendiente y se modificó hace poco. */
export function hayPendienteReciente(
  documentos: DocumentoAgente[],
  ahora = Date.now(),
) {
  return documentos.some(
    (documento) =>
      documento.estado_indexacion === 'PENDIENTE' &&
      ahora - new Date(documento.actualizado_en).getTime() < PENDIENTE_RECIENTE_MS,
  )
}

/**
 * Los documentos del agente (spec 020). Mientras haya un pendiente reciente,
 * la lista se vuelve a pedir cada 5 segundos: así la pantalla muestra el
 * avance de la cola sin recargar. Sin pendientes recientes, deja de consultar.
 */
export function useDocumentosAgente(filtros: FiltrosDocumentosAgente) {
  return useQuery({
    queryKey: ['ia', 'documentos', filtros],
    queryFn: async () =>
      (
        await clienteApi.get<PaginaDocumentosAgente>('/documentos-agente/', {
          params: filtros,
        })
      ).data,
    placeholderData: keepPreviousData,
    refetchInterval: (consulta) =>
      hayPendienteReciente(consulta.state.data?.results ?? []) ? INTERVALO_MS : false,
  })
}
