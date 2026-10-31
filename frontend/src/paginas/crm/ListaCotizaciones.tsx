import { createColumnHelper } from '@tanstack/react-table'
import { useNavigate, useSearchParams } from 'react-router'

import {
  ETIQUETAS_ESTADO_COTIZACION,
  useCotizaciones,
  type Cotizacion,
  type EstadoCotizacion,
  type FiltrosCotizaciones,
} from '../../api/crm/consultas'
import { useAccionCotizacion } from '../../api/crm/mutaciones'
import { TablaDatos, type AccionFila } from '../../componentes/comunes/TablaDatos'
import { Button } from '../../componentes/ui/button'
import { Select } from '../../componentes/ui/select'
import { formatearFecha, formatearMoneda } from '../../lib/formato'
import { ESCRIBEN_CRM, rolPermitido } from '../../menu'
import { useSesion } from '../../sesion/useSesion'

const columna = createColumnHelper<Cotizacion>()

const COLUMNAS = [
  columna.accessor('codigo', { header: 'Código' }),
  columna.accessor((cotizacion) => cotizacion.cliente.nombre, {
    id: 'cliente',
    header: 'Cliente',
  }),
  columna.accessor(
    (cotizacion) => cotizacion.unidad?.codigo ?? cotizacion.propiedad?.codigo ?? '—',
    { id: 'bien', header: 'Bien' },
  ),
  columna.accessor('total', {
    header: 'Total',
    cell: ({ row }) => formatearMoneda(row.original.total, row.original.moneda.codigo),
  }),
  columna.accessor('fecha_vencimiento', {
    header: 'Vence',
    cell: ({ getValue }) => formatearFecha(getValue()),
  }),
  columna.accessor('estado', {
    header: 'Estado',
    // Vencida no es un estado guardado: la API la calcula (spec 007, regla 4).
    cell: ({ row }) => (
      <>
        {ETIQUETAS_ESTADO_COTIZACION[row.original.estado ?? 'BORRADOR']}
        {row.original.vencida && (
          <span className="ml-2 rounded bg-red-50 px-1.5 py-0.5 text-xs font-medium text-red-700">
            Vencida
          </span>
        )}
      </>
    ),
  }),
]

/**
 * Cotizaciones (spec 012, §5). Cada acción aparece solo en el estado que la
 * permite (regla 2); la API lo vuelve a validar. Una aprobada se firma desde
 * su fila (regla 8).
 */
export function ListaCotizaciones() {
  const { usuario } = useSesion()
  const navegar = useNavigate()
  const [parametros, setParametros] = useSearchParams()
  const accion = useAccionCotizacion()

  const filtros: FiltrosCotizaciones = {
    page: Number(parametros.get('page') ?? '1'),
    estado: (parametros.get('estado') as EstadoCotizacion | null) ?? undefined,
  }
  const consulta = useCotizaciones(filtros)

  const filtrarEstado = (estado: string) => {
    setParametros(estado ? { estado } : {})
  }

  const cambiarPagina = (pagina: number) => {
    const siguientes = new URLSearchParams(parametros)
    siguientes.set('page', String(pagina))
    setParametros(siguientes)
  }

  const puedeEscribir = rolPermitido(usuario?.rol ?? '', ESCRIBEN_CRM)
  const acciones: AccionFila<Cotizacion>[] = puedeEscribir
    ? [
        {
          etiqueta: 'Enviar',
          oculta: (fila) => fila.estado !== 'BORRADOR' || fila.vencida,
          ejecutar: (fila) => accion.mutateAsync({ id: fila.id, accion: 'enviar' }),
        },
        {
          etiqueta: 'Aprobar',
          oculta: (fila) => fila.estado !== 'ENVIADA' || fila.vencida,
          confirmacion: (fila) =>
            `¿Aprobar ${fila.codigo}? Su propiedad o unidad quedará reservada.`,
          ejecutar: (fila) => accion.mutateAsync({ id: fila.id, accion: 'aprobar' }),
        },
        {
          etiqueta: 'Firmar contrato',
          oculta: (fila) => fila.estado !== 'APROBADA',
          ejecutar: (fila) => navegar(`/ventas/contratos/nuevo?cotizacion=${fila.id}`),
        },
        {
          etiqueta: 'Rechazar',
          variante: 'destructive',
          oculta: (fila) => fila.estado !== 'ENVIADA' && fila.estado !== 'APROBADA',
          confirmacion: (fila) =>
            fila.estado === 'APROBADA'
              ? `¿Rechazar ${fila.codigo}? Su propiedad o unidad volverá a estar disponible.`
              : `¿Rechazar ${fila.codigo}?`,
          ejecutar: (fila) => accion.mutateAsync({ id: fila.id, accion: 'rechazar' }),
        },
      ]
    : []

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Cotizaciones</h1>
        {puedeEscribir && (
          <Button onClick={() => navegar('/crm/cotizaciones/nueva')}>
            Nueva cotización
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
        {Object.entries(ETIQUETAS_ESTADO_COTIZACION).map(([valor, etiqueta]) => (
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
        mensajeVacio="Ninguna cotización coincide con el filtro."
        paginacion={{
          pagina: filtros.page ?? 1,
          total: consulta.data?.count ?? 0,
          alCambiarPagina: cambiarPagina,
        }}
      />
    </div>
  )
}
