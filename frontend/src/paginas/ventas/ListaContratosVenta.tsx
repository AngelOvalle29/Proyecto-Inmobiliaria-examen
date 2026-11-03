import { createColumnHelper } from '@tanstack/react-table'
import { useNavigate, useSearchParams } from 'react-router'

import {
  ETIQUETAS_ESTADO_CONTRATO,
  ETIQUETAS_MODALIDAD,
  useContratosVenta,
  type ContratoVenta,
  type EstadoContrato,
  type FiltrosContratosVenta,
} from '../../api/ventas/consultas'
import { TablaDatos, type AccionFila } from '../../componentes/comunes/TablaDatos'
import { Button } from '../../componentes/ui/button'
import { Select } from '../../componentes/ui/select'
import { formatearMoneda } from '../../lib/formato'
import { ESCRIBEN_CRM, rolPermitido } from '../../menu'
import { useSesion } from '../../sesion/useSesion'

const columna = createColumnHelper<ContratoVenta>()

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
  columna.accessor('monto_total', {
    header: 'Monto',
    cell: ({ row }) =>
      formatearMoneda(row.original.monto_total, row.original.moneda.codigo),
  }),
  columna.accessor('modalidad', {
    header: 'Modalidad',
    cell: ({ getValue }) => ETIQUETAS_MODALIDAD[getValue()],
  }),
  columna.accessor('estado', {
    header: 'Estado',
    cell: ({ row }) => ETIQUETAS_ESTADO_CONTRATO[row.original.estado ?? 'VIGENTE'],
  }),
]

/** Contratos de venta (spec 012, §5). Las acciones están en su detalle. */
export function ListaContratosVenta() {
  const { usuario } = useSesion()
  const navegar = useNavigate()
  const [parametros, setParametros] = useSearchParams()

  const filtros: FiltrosContratosVenta = {
    page: Number(parametros.get('page') ?? '1'),
    estado: (parametros.get('estado') as EstadoContrato | null) ?? undefined,
  }
  const consulta = useContratosVenta(filtros)

  const filtrarEstado = (estado: string) => {
    setParametros(estado ? { estado } : {})
  }

  const cambiarPagina = (pagina: number) => {
    const siguientes = new URLSearchParams(parametros)
    siguientes.set('page', String(pagina))
    setParametros(siguientes)
  }

  const acciones: AccionFila<ContratoVenta>[] = [
    {
      etiqueta: 'Ver detalle',
      ejecutar: (fila) => navegar(`/ventas/contratos/${fila.id}`),
    },
  ]

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h1 className="font-editorial text-4xl leading-none">Contratos de venta</h1>
        {rolPermitido(usuario?.rol ?? '', ESCRIBEN_CRM) && (
          <Button onClick={() => navegar('/ventas/contratos/nuevo')}>
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
        {Object.entries(ETIQUETAS_ESTADO_CONTRATO).map(([valor, etiqueta]) => (
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
