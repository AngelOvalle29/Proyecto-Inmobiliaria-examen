import { createColumnHelper } from '@tanstack/react-table'
import { useState, type FormEvent } from 'react'

import {
  ETIQUETAS_ESTADO,
  useUnidadesDePropiedad,
  type Unidad,
} from '../../api/catalogo/consultas'
import { useDesactivarUnidad } from '../../api/catalogo/mutaciones'
import { TablaDatos, type AccionFila } from '../../componentes/comunes/TablaDatos'
import { Button } from '../../componentes/ui/button'
import { Input } from '../../componentes/ui/input'
import { formatearMoneda } from '../../lib/formato'
import { DialogoCambiarEstado } from './DialogoCambiarEstado'
import { DialogoUnidad } from './DialogoUnidad'

const columna = createColumnHelper<Unidad>()

const COLUMNAS = [
  columna.accessor('codigo', { header: 'Código' }),
  columna.accessor('nivel', { header: 'Nivel' }),
  columna.accessor('area_m2', {
    header: 'Área',
    cell: ({ getValue }) => `${getValue()} m²`,
  }),
  columna.accessor('habitaciones', { header: 'Habitaciones' }),
  columna.accessor('banos', { header: 'Baños' }),
  columna.accessor('estado', {
    header: 'Estado',
    cell: ({ getValue }) => ETIQUETAS_ESTADO[getValue()],
  }),
  columna.accessor('precio_lista', {
    header: 'Precio de lista',
    cell: ({ getValue, row }) =>
      formatearMoneda(getValue(), row.original.moneda.codigo),
  }),
]

interface Props {
  propiedad: number
  puedeEscribir: boolean
}

/**
 * Pestaña Unidades de la ficha (spec 014, reglas 3 y 4). La búsqueda la hace
 * la API (?buscar=, regla 11). La página y la búsqueda viven en el estado de
 * la pestaña y no en la URL: la URL ya lleva la pestaña abierta.
 */
export function PestanaUnidades({ propiedad, puedeEscribir }: Props) {
  const [pagina, setPagina] = useState(1)
  const [buscado, setBuscado] = useState('')
  // El diálogo de datos: cerrado, una unidad nueva (null) o una a editar.
  const [editando, setEditando] = useState<Unidad | null | undefined>(undefined)
  const [paraCambiarEstado, setParaCambiarEstado] = useState<Unidad | null>(null)
  const desactivar = useDesactivarUnidad()

  const consulta = useUnidadesDePropiedad(propiedad, {
    page: pagina,
    buscar: buscado || undefined,
  })

  const buscar = (evento: FormEvent<HTMLFormElement>) => {
    evento.preventDefault()
    setBuscado(String(new FormData(evento.currentTarget).get('buscar') ?? ''))
    setPagina(1)
  }

  const acciones: AccionFila<Unidad>[] = puedeEscribir
    ? [
        { etiqueta: 'Editar', ejecutar: (fila) => setEditando(fila) },
        { etiqueta: 'Cambiar estado', ejecutar: (fila) => setParaCambiarEstado(fila) },
        {
          etiqueta: 'Desactivar',
          variante: 'destructive',
          confirmacion: (fila) =>
            `¿Desactivar la unidad ${fila.codigo}? Dejará de aparecer en las listas.`,
          ejecutar: (fila) => desactivar.mutateAsync(fila.id),
        },
      ]
    : []

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <form onSubmit={buscar} className="flex gap-2">
          <Input
            name="buscar"
            aria-label="Buscar unidad"
            placeholder="Código de la unidad"
            className="w-56"
          />
          <Button type="submit" variant="outline">
            Buscar
          </Button>
        </form>
        {puedeEscribir && (
          <Button onClick={() => setEditando(null)}>Nueva unidad</Button>
        )}
      </div>

      <TablaDatos
        columnas={COLUMNAS}
        datos={consulta.data?.results}
        cargando={consulta.isPending}
        error={consulta.error}
        acciones={acciones}
        mensajeVacio={
          buscado
            ? 'Ninguna unidad coincide con la búsqueda.'
            : 'Esta propiedad todavía no tiene unidades.'
        }
        paginacion={{
          pagina,
          total: consulta.data?.count ?? 0,
          alCambiarPagina: setPagina,
        }}
      />

      <DialogoUnidad
        propiedad={propiedad}
        abierto={editando !== undefined}
        unidad={editando ?? null}
        alCerrar={() => setEditando(undefined)}
      />
      <DialogoCambiarEstado
        recurso="unidades"
        elemento={paraCambiarEstado}
        alCerrar={() => setParaCambiarEstado(null)}
      />
    </div>
  )
}
