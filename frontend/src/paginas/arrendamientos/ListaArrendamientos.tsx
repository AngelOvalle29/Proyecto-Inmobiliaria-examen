import { createColumnHelper } from '@tanstack/react-table'
import { useNavigate, useSearchParams } from 'react-router'

import {
  ETIQUETAS_ESTADO_ARRENDAMIENTO,
  useArrendamientos,
  type Arrendamiento,
  type EstadoArrendamiento,
  type FiltrosArrendamientos,
} from '../../api/arrendamientos/consultas'
import { TablaDatos, type AccionFila } from '../../componentes/comunes/TablaDatos'
import { Button } from '../../componentes/ui/button'
import { Select } from '../../componentes/ui/select'
import { formatearFecha, formatearMoneda } from '../../lib/formato'
import { ESCRIBEN_CRM, rolPermitido } from '../../menu'
import { useSesion } from '../../sesion/useSesion'

const columna = createColumnHelper<Arrendamiento>()

const COLUMNAS = [
  columna.accessor('codigo', { header: 'Código' }),
  columna.accessor((contrato) => contrato.cliente.nombre, {
    id: 'cliente',
    header: 'Cliente',
  }),
  columna.accessor(
    (contrato) => contrato.unidad?.codigo ?? contrato.propiedad?.codigo ?? '—',
    { id: 'bien', header: 'Bien' },
  ),
  columna.accessor('renta_mensual', {
    header: 'Renta',
    cell: ({ row }) =>
      formatearMoneda(row.original.renta_mensual, row.original.moneda.codigo),
  }),
  columna.accessor('fecha_fin', {
    header: 'Fin',
    cell: ({ getValue }) => formatearFecha(getValue()),
  }),
  columna.accessor('estado', {
    header: 'Estado',
    cell: ({ row }) => ETIQUETAS_ESTADO_ARRENDAMIENTO[row.original.estado ?? 'VIGENTE'],
  }),
]

/** Contratos de arrendamiento (spec 012, §5). Las acciones están en su detalle. */
export function ListaArrendamientos() {
  const { usuario } = useSesion()
  const navegar = useNavigate()
  const [parametros, setParametros] = useSearchParams()

  const filtros: FiltrosArrendamientos = {
    page: Number(parametros.get('page') ?? '1'),
    estado: (parametros.get('estado') as EstadoArrendamiento | null) ?? undefined,
  }
  const consulta = useArrendamientos(filtros)

  const filtrarEstado = (estado: string) => {
    setParametros(estado ? { estado } : {})
  }

  const cambiarPagina = (pagina: number) => {
    const siguientes = new URLSearchParams(parametros)
    siguientes.set('page', String(pagina))
    setParametros(siguientes)
  }

  const acciones: AccionFila<Arrendamiento>[] = [
    {
      etiqueta: 'Ver detalle',
      ejecutar: (fila) => navegar(`/arrendamientos/contratos/${fila.id}`),
    },
  ]

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Contratos de arrendamiento</h1>
        {rolPermitido(usuario?.rol ?? '', ESCRIBEN_CRM) && (
          <Button onClick={() => navegar('/arrendamientos/contratos/nuevo')}>
            Nuevo contrato
          </Button>
        )}
      </div>

      <Select
        aria-label="Estado"
        className="w-48"
        value={parametros.get('estado') ?? ''}
        onChange={(evento) => filtrarEstado(evento.target.value)}
      >
        <option value="">Todos los estados</option>
        {Object.entries(ETIQUETAS_ESTADO_ARRENDAMIENTO).map(([valor, etiqueta]) => (
          <option key={valor} value={valor}>
            {etiqueta}
          </option>
        ))}
      </Select>

      <TablaDatos
        columnas={COLUMNAS}
        datos={consulta.data?.results}
        cargando={consulta.isPending}
        error={consulta.error}
        acciones={acciones}
        mensajeVacio="Ningún contrato coincide con el filtro."
        paginacion={{
          pagina: filtros.page ?? 1,
          total: consulta.data?.count ?? 0,
          alCambiarPagina: cambiarPagina,
        }}
      />
    </div>
  )
}
