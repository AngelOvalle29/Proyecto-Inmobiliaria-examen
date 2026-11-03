import { createColumnHelper } from '@tanstack/react-table'
import { useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router'

import {
  ETIQUETAS_ESTADO_CONTRATO_COMPRA,
  useContratosCompra,
  type ContratoCompra,
  type EstadoContratoCompra,
  type FiltrosContratosCompra,
} from '../../api/compras/consultas'
import {
  useAnularContratoCompra,
  useCompletarContratoCompra,
} from '../../api/compras/mutaciones'
import { DialogoMotivo } from '../../componentes/comunes/DialogoMotivo'
import { TablaDatos, type AccionFila } from '../../componentes/comunes/TablaDatos'
import { Button } from '../../componentes/ui/button'
import { Select } from '../../componentes/ui/select'
import { formatearFecha, formatearMoneda } from '../../lib/formato'
import { ESCRIBEN_COMPRAS, rolPermitido } from '../../menu'
import { useSesion } from '../../sesion/useSesion'

const columna = createColumnHelper<ContratoCompra>()

const COLUMNAS = [
  columna.accessor('codigo', { header: 'Código' }),
  columna.accessor((contrato) => contrato.proveedor.nombre, {
    id: 'proveedor',
    header: 'Proveedor',
  }),
  columna.accessor((contrato) => contrato.propiedad.codigo, {
    id: 'propiedad',
    header: 'Propiedad',
  }),
  columna.accessor('fecha_compra', {
    header: 'Fecha',
    cell: ({ getValue }) => formatearFecha(getValue()),
  }),
  // El costo total lo calcula la API: monto + gastos legales + impuestos
  // (spec 017, regla 3). Aquí solo se muestra (spec 018, regla 6).
  columna.accessor('costo_total', {
    header: 'Costo total',
    cell: ({ row }) =>
      formatearMoneda(row.original.costo_total, row.original.moneda.codigo),
  }),
  columna.accessor('estado', {
    header: 'Estado',
    cell: ({ getValue }) => ETIQUETAS_ESTADO_CONTRATO_COMPRA[getValue()],
  }),
]

/**
 * Contratos de compra (spec 018, §5). No tienen detalle: la lista ya muestra lo
 * importante, y sus dos acciones van en la fila (§10). Completar y Anular solo
 * se ofrecen en un contrato EN_PROCESO (regla 3) y solo a quien escribe.
 */
export function ListaContratosCompra() {
  const { usuario } = useSesion()
  const navegar = useNavigate()
  const [parametros, setParametros] = useSearchParams()
  const [paraAnular, setParaAnular] = useState<ContratoCompra | null>(null)
  const completar = useCompletarContratoCompra()
  const anular = useAnularContratoCompra()

  const filtros: FiltrosContratosCompra = {
    page: Number(parametros.get('page') ?? '1'),
    estado: (parametros.get('estado') as EstadoContratoCompra | null) ?? undefined,
  }
  const consulta = useContratosCompra(filtros)

  const filtrarEstado = (estado: string) => {
    setParametros(estado ? { estado } : {})
  }

  const cambiarPagina = (pagina: number) => {
    const siguientes = new URLSearchParams(parametros)
    siguientes.set('page', String(pagina))
    setParametros(siguientes)
  }

  const puedeEscribir = rolPermitido(usuario?.rol ?? '', ESCRIBEN_COMPRAS)
  const noEnProceso = (fila: ContratoCompra) => fila.estado !== 'EN_PROCESO'
  const acciones: AccionFila<ContratoCompra>[] = puedeEscribir
    ? [
        {
          etiqueta: 'Completar',
          oculta: noEnProceso,
          // No se deshace: la propiedad pasa a ser de la agencia (regla 6).
          confirmacion: (fila) =>
            `¿Completar ${fila.codigo}? La propiedad ${fila.propiedad.codigo} pasará a adquirida.`,
          ejecutar: (fila) => completar.mutateAsync(fila.id),
        },
        {
          etiqueta: 'Anular',
          variante: 'destructive',
          oculta: noEnProceso,
          ejecutar: (fila) => setParaAnular(fila),
        },
      ]
    : []

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Contratos de compra</h1>
        {puedeEscribir && (
          <Button onClick={() => navegar('/compras/contratos/nuevo')}>
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
        {Object.entries(ETIQUETAS_ESTADO_CONTRATO_COMPRA).map(([valor, etiqueta]) => (
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

      <DialogoMotivo
        abierto={paraAnular !== null}
        titulo={`Anular ${paraAnular?.codigo ?? ''}`}
        descripcion="La propiedad sigue en negociación y puede tener otro contrato."
        textoConfirmar="Anular contrato"
        alConfirmar={(motivo) =>
          anular.mutateAsync({ id: (paraAnular as ContratoCompra).id, motivo })
        }
        alCerrar={() => setParaAnular(null)}
      />
    </div>
  )
}
