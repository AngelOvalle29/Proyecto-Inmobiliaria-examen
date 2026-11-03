import { createColumnHelper } from '@tanstack/react-table'
import { useState } from 'react'

import {
  ETIQUETAS_TIPO_DOCUMENTO,
  useDocumentos,
  type DocumentoOficial,
  type TipoDocumento,
} from '../../api/catalogo/consultas'
import {
  useDesactivarDocumento,
  useDescargarDocumento,
} from '../../api/catalogo/mutaciones'
import { TablaDatos, type AccionFila } from '../../componentes/comunes/TablaDatos'
import { Button } from '../../componentes/ui/button'
import { Select } from '../../componentes/ui/select'
import { estadoVencimiento, formatearFecha } from '../../lib/formato'
import { cn } from '../../lib/utils'
import { DialogoDocumento } from './DialogoDocumento'

const columna = createColumnHelper<DocumentoOficial>()

const COLUMNAS = [
  columna.accessor('tipo', {
    header: 'Tipo',
    cell: ({ getValue }) => ETIQUETAS_TIPO_DOCUMENTO[getValue()],
  }),
  columna.accessor('nombre', { header: 'Nombre' }),
  columna.accessor('fecha_emision', {
    header: 'Emisión',
    cell: ({ getValue }) => formatearFecha(getValue()),
  }),
  columna.accessor('fecha_vencimiento', {
    header: 'Vencimiento',
    cell: ({ getValue }) => <Vencimiento fecha={getValue()} />,
  }),
  columna.accessor('emisor', { header: 'Emisor' }),
]

/**
 * La fecha de vencimiento, en rojo si ya venció y en ámbar si vence en los
 * próximos 30 días (spec 014, regla 7). Lleva texto además del color, para
 * quien no distingue los colores.
 */
function Vencimiento({ fecha }: { fecha: string | null | undefined }) {
  if (!fecha) {
    return <span className="text-tenue">No vence</span>
  }
  const estado = estadoVencimiento(fecha)
  return (
    <span
      className={cn(
        estado === 'vencido' && 'font-medium text-red-700',
        estado === 'por-vencer' && 'font-medium text-amber-700',
      )}
    >
      {formatearFecha(fecha)}
      {estado === 'vencido' && ' · vencido'}
      {estado === 'por-vencer' && ' · por vencer'}
    </span>
  )
}

interface Props {
  propiedad: number
  puedeEscribir: boolean
}

/**
 * Pestaña Documentos (spec 014, reglas 5 a 7). Todos descargan; subir,
 * editar y desactivar solo quien escribe en el catálogo.
 */
export function PestanaDocumentos({ propiedad, puedeEscribir }: Props) {
  const [pagina, setPagina] = useState(1)
  const [tipo, setTipo] = useState<TipoDocumento | ''>('')
  // El diálogo: cerrado, un documento nuevo (null) o uno a editar.
  const [editando, setEditando] = useState<DocumentoOficial | null | undefined>(
    undefined,
  )
  const descargar = useDescargarDocumento()
  const desactivar = useDesactivarDocumento()

  const consulta = useDocumentos(propiedad, { page: pagina, tipo: tipo || undefined })

  const descargarFila: AccionFila<DocumentoOficial> = {
    etiqueta: 'Descargar',
    variante: 'outline',
    ejecutar: (fila) => descargar.mutateAsync(fila.id),
  }
  const acciones: AccionFila<DocumentoOficial>[] = puedeEscribir
    ? [
        descargarFila,
        { etiqueta: 'Editar datos', ejecutar: (fila) => setEditando(fila) },
        {
          etiqueta: 'Desactivar',
          variante: 'destructive',
          confirmacion: (fila) =>
            `¿Desactivar ${fila.nombre}? Dejará de aparecer en la lista.`,
          ejecutar: (fila) => desactivar.mutateAsync(fila.id),
        },
      ]
    : [descargarFila]

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <Select
          aria-label="Tipo de documento"
          className="w-48"
          value={tipo}
          onChange={(evento) => {
            setTipo(evento.target.value as TipoDocumento | '')
            setPagina(1)
          }}
        >
          <option value="">Todos los tipos</option>
          {Object.entries(ETIQUETAS_TIPO_DOCUMENTO).map(([valor, etiqueta]) => (
            <option key={valor} value={valor}>
              {etiqueta}
            </option>
          ))}
        </Select>
        {puedeEscribir && (
          <Button onClick={() => setEditando(null)}>Subir documento</Button>
        )}
      </div>

      <TablaDatos
        columnas={COLUMNAS}
        datos={consulta.data?.results}
        cargando={consulta.isPending}
        error={consulta.error}
        acciones={acciones}
        mensajeVacio={
          tipo
            ? 'No hay documentos de ese tipo.'
            : 'Esta propiedad todavía no tiene documentos.'
        }
        paginacion={{
          pagina,
          total: consulta.data?.count ?? 0,
          alCambiarPagina: setPagina,
        }}
      />

      <DialogoDocumento
        propiedad={propiedad}
        abierto={editando !== undefined}
        documento={editando ?? null}
        alCerrar={() => setEditando(undefined)}
      />
    </div>
  )
}
