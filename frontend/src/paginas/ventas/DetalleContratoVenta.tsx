import { createColumnHelper } from '@tanstack/react-table'
import { useState } from 'react'
import { useParams } from 'react-router'

import { leerErrorApi } from '../../api/errores'
import {
  ETIQUETAS_ESTADO_CONTRATO,
  ETIQUETAS_ESTADO_CUOTA,
  ETIQUETAS_MODALIDAD,
  useContratoVenta,
  type ContratoVentaDetalle,
  type Cuota,
} from '../../api/ventas/consultas'
import { useAnularContratoVenta } from '../../api/ventas/mutaciones'
import { Dialogo } from '../../componentes/comunes/Dialogo'
import { TablaDatos, type AccionFila } from '../../componentes/comunes/TablaDatos'
import { Button } from '../../componentes/ui/button'
import { formatearFecha, formatearMoneda } from '../../lib/formato'
import { ADMINISTRAN_CRM, REGISTRAN_PAGOS, rolPermitido } from '../../menu'
import { useSesion } from '../../sesion/useSesion'
import { DialogoPagarCuota } from './DialogoPagarCuota'

const columna = createColumnHelper<Cuota>()

/**
 * Las columnas de dinero necesitan la moneda del contrato. La mora solo se
 * marca en un contrato vigente: la API la calcula por cuota, sin mirar si el
 * contrato se anuló.
 */
function crearColumnas(moneda: string, vigente: boolean) {
  const dinero = (monto: string) => formatearMoneda(monto, moneda)
  return [
    columna.accessor('numero', { header: 'Cuota' }),
    columna.accessor('fecha_vencimiento', {
      header: 'Vence',
      cell: ({ getValue }) => formatearFecha(getValue()),
    }),
    columna.accessor('monto_capital', {
      header: 'Capital',
      cell: ({ getValue }) => dinero(getValue()),
    }),
    columna.accessor('monto_interes', {
      header: 'Interés',
      cell: ({ getValue }) => dinero(getValue()),
    }),
    columna.accessor('monto_total', {
      header: 'Total',
      cell: ({ getValue }) => dinero(getValue()),
    }),
    columna.accessor('saldo', {
      header: 'Saldo',
      cell: ({ getValue }) => dinero(getValue()),
    }),
    columna.accessor('estado', {
      header: 'Estado',
      // La mora no es un estado guardado: la API la calcula (spec 007, regla 17).
      cell: ({ row }) => (
        <>
          {ETIQUETAS_ESTADO_CUOTA[row.original.estado ?? 'PENDIENTE']}
          {vigente && row.original.en_mora && (
            <span className="ml-2 rounded bg-red-50 px-1.5 py-0.5 text-xs font-medium whitespace-nowrap text-red-700">
              En mora
            </span>
          )}
        </>
      ),
    }),
  ]
}

function Dato({ etiqueta, valor }: { etiqueta: string; valor: string }) {
  return (
    <div>
      <dt className="text-xs text-slate-500">{etiqueta}</dt>
      <dd className="text-sm">{valor}</dd>
    </div>
  )
}

function DatosDelContrato({ contrato }: { contrato: ContratoVentaDetalle }) {
  const moneda = contrato.moneda.codigo
  return (
    <dl className="grid grid-cols-2 gap-3 rounded-lg border border-slate-200 bg-white p-4 md:grid-cols-4">
      <Dato etiqueta="Cliente" valor={contrato.cliente.nombre} />
      <Dato
        etiqueta="Bien"
        valor={contrato.unidad?.codigo ?? contrato.propiedad?.codigo ?? '—'}
      />
      <Dato etiqueta="Agente" valor={contrato.agente.nombre_completo} />
      <Dato
        etiqueta="Estado"
        valor={ETIQUETAS_ESTADO_CONTRATO[contrato.estado ?? 'VIGENTE']}
      />
      <Dato etiqueta="Firma" valor={formatearFecha(contrato.fecha_firma)} />
      <Dato
        etiqueta="Monto total"
        valor={formatearMoneda(contrato.monto_total, moneda)}
      />
      <Dato etiqueta="Modalidad" valor={ETIQUETAS_MODALIDAD[contrato.modalidad]} />
      <Dato
        etiqueta="Comisión del agente"
        valor={formatearMoneda(contrato.comision_agente, moneda)}
      />
      {contrato.modalidad === 'FINANCIADO' && (
        <>
          <Dato
            etiqueta="Enganche"
            valor={formatearMoneda(contrato.enganche ?? '0', moneda)}
          />
          <Dato etiqueta="Cuotas" valor={String(contrato.numero_cuotas ?? '—')} />
          <Dato
            etiqueta="Tasa anual"
            valor={`${contrato.tasa_interes_anual ?? '—'} %`}
          />
        </>
      )}
    </dl>
  )
}

/**
 * Detalle de un contrato de venta (spec 012, §5): sus datos y sus cuotas con
 * mora. Pagan administrador, gerente y contabilidad; anulan los dos primeros
 * (spec 007, reglas 20 y 21).
 */
export function DetalleContratoVenta() {
  const { id } = useParams()
  const { usuario } = useSesion()
  const consulta = useContratoVenta(Number(id))
  const anular = useAnularContratoVenta()
  const [paraPagar, setParaPagar] = useState<Cuota | null>(null)
  const [confirmando, setConfirmando] = useState(false)
  const contrato = consulta.data

  if (!contrato) {
    return consulta.isError ? (
      <p role="alert" className="rounded-md bg-red-50 p-3 text-sm text-red-700">
        {leerErrorApi(consulta.error).mensaje}
      </p>
    ) : (
      <p className="text-sm text-slate-500">Cargando…</p>
    )
  }

  const rol = usuario?.rol ?? ''
  const vigente = contrato.estado === 'VIGENTE'
  const acciones: AccionFila<Cuota>[] =
    vigente && rolPermitido(rol, REGISTRAN_PAGOS)
      ? [
          {
            etiqueta: 'Pagar',
            oculta: (fila) => fila.estado === 'PAGADA',
            ejecutar: (fila) => setParaPagar(fila),
          },
        ]
      : []

  const confirmarAnular = () => {
    anular.mutate(contrato.id, { onSettled: () => setConfirmando(false) })
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Contrato {contrato.codigo}</h1>
        {vigente && rolPermitido(rol, ADMINISTRAN_CRM) && (
          <Button variant="destructive" onClick={() => setConfirmando(true)}>
            Anular
          </Button>
        )}
      </div>

      {anular.isError && (
        <p role="alert" className="rounded-md bg-red-50 p-3 text-sm text-red-700">
          {leerErrorApi(anular.error).mensaje}
        </p>
      )}

      <DatosDelContrato contrato={contrato} />

      {contrato.modalidad === 'FINANCIADO' && (
        <>
          <h2 className="text-lg font-semibold">Cuotas</h2>
          <TablaDatos
            columnas={crearColumnas(contrato.moneda.codigo, vigente)}
            datos={contrato.cuotas}
            acciones={acciones}
          />
        </>
      )}

      <DialogoPagarCuota
        cuota={paraPagar}
        moneda={contrato.moneda.codigo}
        alCerrar={() => setParaPagar(null)}
      />

      <Dialogo
        abierto={confirmando}
        titulo="Anular contrato"
        alCerrar={() => setConfirmando(false)}
      >
        <p className="text-sm text-slate-600">
          ¿Anular {contrato.codigo}? La propiedad o unidad volverá a estar disponible.
        </p>
        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={() => setConfirmando(false)}>
            Cancelar
          </Button>
          <Button
            variant="destructive"
            disabled={anular.isPending}
            onClick={confirmarAnular}
          >
            {anular.isPending ? 'Anulando…' : 'Anular'}
          </Button>
        </div>
      </Dialogo>
    </div>
  )
}
