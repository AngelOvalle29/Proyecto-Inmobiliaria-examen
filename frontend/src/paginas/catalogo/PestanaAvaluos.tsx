import { createColumnHelper } from '@tanstack/react-table'
import { useState } from 'react'

import { useAvaluos, type Avaluo } from '../../api/catalogo/consultas'
import { useDesactivarAvaluo } from '../../api/catalogo/mutaciones'
import { TablaDatos, type AccionFila } from '../../componentes/comunes/TablaDatos'
import { Button } from '../../componentes/ui/button'
import { formatearFecha, formatearMoneda } from '../../lib/formato'
import { DialogoAvaluo } from './DialogoAvaluo'

const columna = createColumnHelper<Avaluo>()

const COLUMNAS = [
  columna.accessor('fecha', {
    header: 'Fecha',
    cell: ({ getValue }) => formatearFecha(getValue()),
  }),
  columna.accessor('valor', {
    header: 'Valor',
    cell: ({ getValue, row }) =>
      formatearMoneda(getValue(), row.original.moneda.codigo),
  }),
  columna.accessor('perito', { header: 'Perito' }),
  columna.accessor('metodologia', { header: 'Metodología' }),
  columna.accessor('documento', {
    header: 'Respaldo',
    cell: ({ getValue }) => getValue()?.nombre ?? '—',
  }),
]

interface Props {
  propiedad: number
  puedeEscribir: boolean
}

/**
 * Pestaña Avalúos (spec 014, regla 8): el historial de plusvalía, del más
 * reciente al más antiguo. El primero es el valor vigente de la propiedad y
 * se resalta arriba de la tabla.
 */
export function PestanaAvaluos({ propiedad, puedeEscribir }: Props) {
  const [pagina, setPagina] = useState(1)
  const [registrando, setRegistrando] = useState(false)
  const desactivar = useDesactivarAvaluo()
  const consulta = useAvaluos(propiedad, pagina)
  // El vigente es el primero de la página 1; en otra página no se muestra.
  const vigente = pagina === 1 ? consulta.data?.results[0] : undefined

  const acciones: AccionFila<Avaluo>[] = puedeEscribir
    ? [
        {
          etiqueta: 'Desactivar',
          variante: 'destructive',
          confirmacion: (fila) =>
            `¿Desactivar el avalúo del ${formatearFecha(fila.fecha)}? Dejará de contar en el historial.`,
          ejecutar: (fila) => desactivar.mutateAsync(fila.id),
        },
      ]
    : []

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        {vigente ? (
          <div className="rounded-md border border-emerald-200 bg-emerald-50 px-4 py-2 text-sm">
            <span className="text-emerald-800">Valor vigente: </span>
            <span className="font-semibold">
              {formatearMoneda(vigente.valor, vigente.moneda.codigo)}
            </span>
            <span className="text-emerald-800">
              {' '}
              · avalúo del {formatearFecha(vigente.fecha)}
            </span>
          </div>
        ) : (
          <span />
        )}
        {puedeEscribir && (
          <Button onClick={() => setRegistrando(true)}>Registrar avalúo</Button>
        )}
      </div>

      <TablaDatos
        columnas={COLUMNAS}
        datos={consulta.data?.results}
        cargando={consulta.isPending}
        error={consulta.error}
        acciones={acciones}
        mensajeVacio="Esta propiedad todavía no tiene avalúos."
        paginacion={{
          pagina,
          total: consulta.data?.count ?? 0,
          alCambiarPagina: setPagina,
        }}
      />

      <DialogoAvaluo
        propiedad={propiedad}
        abierto={registrando}
        alCerrar={() => setRegistrando(false)}
      />
    </div>
  )
}
