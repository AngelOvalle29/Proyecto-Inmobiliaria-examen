import { createColumnHelper } from '@tanstack/react-table'
import { useState } from 'react'

import {
  ETIQUETAS_ESTADO_INDEXACION,
  ETIQUETAS_TIPO_DOCUMENTO_AGENTE,
  hayPendienteReciente,
  useDocumentosAgente,
  type DocumentoAgente,
  type EstadoIndexacion,
} from '../../api/ia/consultas'
import {
  useDesactivarDocumentoAgente,
  useReindexarDocumentoAgente,
} from '../../api/ia/mutaciones'
import { TablaDatos, type AccionFila } from '../../componentes/comunes/TablaDatos'
import { Button } from '../../componentes/ui/button'
import { Select } from '../../componentes/ui/select'
import { formatearFecha } from '../../lib/formato'
import { cn } from '../../lib/utils'
import { DialogoDocumentoAgente } from './DialogoDocumentoAgente'

const columna = createColumnHelper<DocumentoAgente>()

const COLORES_ESTADO: Record<EstadoIndexacion, string> = {
  PENDIENTE: 'bg-amber-50 text-amber-800',
  INDEXADO: 'bg-emerald-50 text-emerald-800',
  ERROR: 'bg-red-50 text-red-700',
}

const COLUMNAS = [
  columna.accessor('titulo', { header: 'Título' }),
  columna.accessor('tipo', {
    header: 'Tipo',
    cell: ({ getValue }) => ETIQUETAS_TIPO_DOCUMENTO_AGENTE[getValue()],
  }),
  columna.accessor('pais', {
    header: 'País',
    cell: ({ getValue }) => getValue()?.nombre ?? 'Todos',
  }),
  columna.accessor('version', { header: 'Versión' }),
  columna.accessor('estado_indexacion', {
    header: 'Estado',
    // El motivo del error va en el title: así se lee sin ocupar la tabla.
    cell: ({ getValue, row }) => (
      <span
        title={row.original.error_indexacion || undefined}
        className={cn(
          'rounded px-1.5 py-0.5 text-xs font-medium whitespace-nowrap',
          COLORES_ESTADO[getValue()],
        )}
      >
        {ETIQUETAS_ESTADO_INDEXACION[getValue()]}
      </span>
    ),
  }),
  columna.accessor('fragmentos', { header: 'Fragmentos' }),
  columna.accessor('fecha_indexacion', {
    header: 'Indexado',
    cell: ({ getValue }) => {
      const fecha = getValue()
      return fecha ? formatearFecha(fecha) : '—'
    },
  }),
]

/**
 * Documentos del asistente (spec 020): lo que el agente público consulta.
 * Subir o reemplazar un archivo encola su indexación en RabbitMQ; la lista se
 * actualiza sola mientras haya pendientes recientes, y así se ve el trabajo
 * del worker. Solo administración y gerencia (regla 14).
 */
export function ListaDocumentosAgente() {
  const [pagina, setPagina] = useState(1)
  const [estado, setEstado] = useState<EstadoIndexacion | ''>('')
  // El diálogo: cerrado, un documento nuevo (null) o uno a reemplazar.
  const [editando, setEditando] = useState<DocumentoAgente | null | undefined>(
    undefined,
  )
  const reindexar = useReindexarDocumentoAgente()
  const desactivar = useDesactivarDocumentoAgente()

  const consulta = useDocumentosAgente({
    page: pagina,
    estado_indexacion: estado || undefined,
  })
  const filas = consulta.data?.results ?? []
  const conError = filas.filter((fila) => fila.estado_indexacion === 'ERROR')

  const acciones: AccionFila<DocumentoAgente>[] = [
    { etiqueta: 'Reemplazar', ejecutar: (fila) => setEditando(fila) },
    {
      etiqueta: 'Reindexar',
      variante: 'outline',
      ejecutar: (fila) => reindexar.mutateAsync(fila.id),
    },
    {
      etiqueta: 'Desactivar',
      variante: 'destructive',
      confirmacion: (fila) =>
        `¿Desactivar ${fila.titulo}? El asistente dejará de usarlo en sus respuestas.`,
      ejecutar: (fila) => desactivar.mutateAsync(fila.id),
    },
  ]

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h1 className="font-editorial text-4xl leading-none">
          Documentos del asistente
        </h1>
        <Button onClick={() => setEditando(null)}>Subir documento</Button>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <Select
          aria-label="Estado de indexación"
          className="w-48"
          value={estado}
          onChange={(evento) => {
            setEstado(evento.target.value as EstadoIndexacion | '')
            setPagina(1)
          }}
        >
          <option value="">Todos los estados</option>
          {Object.entries(ETIQUETAS_ESTADO_INDEXACION).map(([valor, etiqueta]) => (
            <option key={valor} value={valor}>
              {etiqueta}
            </option>
          ))}
        </Select>
        {hayPendienteReciente(filas) && (
          <p className="text-sm text-tenue">
            Indexando en la cola… la lista se actualiza sola.
          </p>
        )}
      </div>

      {conError.length > 0 && (
        <div role="alert" className="rounded-md bg-red-50 p-3 text-sm text-red-700">
          {conError.map((fila) => (
            <p key={fila.id}>
              <span className="font-medium">{fila.titulo}:</span>{' '}
              {fila.error_indexacion}. Reindéxelo cuando el servicio vuelva.
            </p>
          ))}
        </div>
      )}

      <TablaDatos
        columnas={COLUMNAS}
        datos={consulta.data?.results}
        cargando={consulta.isPending}
        error={consulta.error}
        acciones={acciones}
        mensajeVacio={
          estado ? 'No hay documentos en ese estado.' : 'Todavía no hay documentos.'
        }
        paginacion={{
          pagina,
          total: consulta.data?.count ?? 0,
          alCambiarPagina: setPagina,
        }}
      />

      <DialogoDocumentoAgente
        abierto={editando !== undefined}
        documento={editando ?? null}
        alCerrar={() => setEditando(undefined)}
      />
    </div>
  )
}
