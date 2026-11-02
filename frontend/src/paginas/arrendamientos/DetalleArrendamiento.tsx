import { createColumnHelper } from '@tanstack/react-table'
import { useState } from 'react'
import { Link, useParams } from 'react-router'

import {
  ETIQUETAS_ESTADO_ARRENDAMIENTO,
  ETIQUETAS_ESTADO_PAGO_RENTA,
  useArrendamiento,
  type ArrendamientoDetalle,
  type PagoRenta,
} from '../../api/arrendamientos/consultas'
import {
  useFinalizarArrendamiento,
  useVincularDocumentoArrendamiento,
} from '../../api/arrendamientos/mutaciones'
import { leerErrorApi } from '../../api/errores'
import { Dialogo } from '../../componentes/comunes/Dialogo'
import { DocumentoDelContrato } from '../../componentes/comunes/DocumentoDelContrato'
import { TablaDatos, type AccionFila } from '../../componentes/comunes/TablaDatos'
import { Button } from '../../componentes/ui/button'
import { fechaDeHoy, formatearFecha, formatearMoneda } from '../../lib/formato'
import {
  ADMINISTRAN_CRM,
  ESCRIBEN_CRM,
  REGISTRAN_PAGOS,
  rolPermitido,
} from '../../menu'
import { useSesion } from '../../sesion/useSesion'
import { DialogoPagarRenta } from './DialogoPagarRenta'
import { DialogoRenovar } from './DialogoRenovar'
import { DialogoRescindir } from './DialogoRescindir'

const columna = createColumnHelper<PagoRenta>()

/** Las columnas de dinero necesitan la moneda del contrato. */
function crearColumnas(moneda: string) {
  return [
    columna.accessor((pago) => `${pago.periodo_mes}/${pago.periodo_anio}`, {
      id: 'periodo',
      header: 'Período',
    }),
    columna.accessor('fecha_vencimiento', {
      header: 'Vence',
      cell: ({ getValue }) => formatearFecha(getValue()),
    }),
    columna.accessor('monto', {
      header: 'Renta',
      cell: ({ getValue }) => formatearMoneda(getValue(), moneda),
    }),
    columna.accessor('monto_pagado', {
      header: 'Pagado',
      cell: ({ getValue }) => {
        const pagado = getValue()
        return pagado ? formatearMoneda(pagado, moneda) : '—'
      },
    }),
    columna.accessor('fecha_pago', {
      header: 'Fecha de pago',
      cell: ({ getValue }) => {
        const fecha = getValue()
        return fecha ? formatearFecha(fecha) : '—'
      },
    }),
    columna.accessor('estado', {
      header: 'Estado',
      // La mora no es un estado guardado: la API la calcula (spec 008, regla 8).
      cell: ({ row }) => (
        <>
          {ETIQUETAS_ESTADO_PAGO_RENTA[row.original.estado ?? 'PENDIENTE']}
          {row.original.en_mora && (
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

function DatosDelContrato({ contrato }: { contrato: ArrendamientoDetalle }) {
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
        valor={ETIQUETAS_ESTADO_ARRENDAMIENTO[contrato.estado ?? 'VIGENTE']}
      />
      <Dato etiqueta="Inicio" valor={formatearFecha(contrato.fecha_inicio)} />
      <Dato etiqueta="Fin" valor={formatearFecha(contrato.fecha_fin)} />
      <Dato
        etiqueta="Renta mensual"
        valor={formatearMoneda(contrato.renta_mensual, moneda)}
      />
      <Dato
        etiqueta="Depósito"
        valor={formatearMoneda(contrato.deposito ?? '0', moneda)}
      />
      <Dato etiqueta="Día de cobro" valor={String(contrato.dia_cobro)} />
      <Dato etiqueta="Días de gracia" valor={String(contrato.dias_gracia ?? 0)} />
      <Dato etiqueta="Recargo por mora" valor={`${contrato.porcentaje_mora} %`} />
      {contrato.fecha_rescision && (
        <Dato etiqueta="Rescisión" valor={formatearFecha(contrato.fecha_rescision)} />
      )}
    </dl>
  )
}

/**
 * Detalle de un arrendamiento (spec 012, §5): sus datos y su calendario. Un pago
 * pendiente se puede pagar aunque el contrato haya terminado, porque se sigue
 * debiendo (spec 008, reglas 10 y 11). Permisos: reglas 13 a 15.
 */
export function DetalleArrendamiento() {
  const { id } = useParams()
  const { usuario } = useSesion()
  const consulta = useArrendamiento(Number(id))
  const finalizar = useFinalizarArrendamiento()
  const vincular = useVincularDocumentoArrendamiento()
  const [paraPagar, setParaPagar] = useState<PagoRenta | null>(null)
  const [dialogo, setDialogo] = useState<'renovar' | 'rescindir' | 'finalizar' | null>(
    null,
  )
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
  const terminaron = contrato.fecha_fin < fechaDeHoy()
  const puedeTerminar = vigente && rolPermitido(rol, ADMINISTRAN_CRM)
  const acciones: AccionFila<PagoRenta>[] = rolPermitido(rol, REGISTRAN_PAGOS)
    ? [
        {
          etiqueta: 'Pagar',
          oculta: (fila) => fila.estado !== 'PENDIENTE',
          ejecutar: (fila) => setParaPagar(fila),
        },
      ]
    : []

  const cerrar = () => setDialogo(null)

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-2xl font-semibold">Contrato {contrato.codigo}</h1>
        <div className="flex gap-2">
          {vigente && rolPermitido(rol, ESCRIBEN_CRM) && (
            <Button variant="outline" onClick={() => setDialogo('renovar')}>
              Renovar
            </Button>
          )}
          {puedeTerminar && terminaron && (
            <Button variant="outline" onClick={() => setDialogo('finalizar')}>
              Finalizar
            </Button>
          )}
          {puedeTerminar && (
            <Button variant="destructive" onClick={() => setDialogo('rescindir')}>
              Rescindir
            </Button>
          )}
        </div>
      </div>

      {finalizar.isError && (
        <p role="alert" className="rounded-md bg-red-50 p-3 text-sm text-red-700">
          {leerErrorApi(finalizar.error).mensaje}
        </p>
      )}

      {contrato.contrato_anterior && (
        <p className="text-sm text-slate-600">
          Renueva{' '}
          <Link
            className="underline"
            to={`/arrendamientos/contratos/${contrato.contrato_anterior}`}
          >
            el contrato anterior
          </Link>
          .
        </p>
      )}

      <DatosDelContrato contrato={contrato} />

      <DocumentoDelContrato
        documento={contrato.documento}
        propiedad={(contrato.propiedad?.id ?? contrato.unidad?.propiedad.id) as number}
        puedeCambiar={rolPermitido(rol, ESCRIBEN_CRM)}
        alVincular={(documento) => vincular.mutateAsync({ id: contrato.id, documento })}
      />

      <h2 className="text-lg font-semibold">Calendario de pagos</h2>
      <TablaDatos
        columnas={crearColumnas(contrato.moneda.codigo)}
        datos={contrato.pagos}
        acciones={acciones}
      />

      <DialogoPagarRenta
        pago={paraPagar}
        contrato={contrato}
        alCerrar={() => setParaPagar(null)}
      />
      <DialogoRenovar
        contrato={contrato}
        abierto={dialogo === 'renovar'}
        alCerrar={cerrar}
      />
      <DialogoRescindir
        contrato={contrato}
        abierto={dialogo === 'rescindir'}
        alCerrar={cerrar}
      />

      <Dialogo
        abierto={dialogo === 'finalizar'}
        titulo="Finalizar contrato"
        alCerrar={cerrar}
      >
        <p className="text-sm text-slate-600">
          ¿Finalizar {contrato.codigo}? La propiedad o unidad volverá a estar disponible
          y los pagos pendientes se seguirán debiendo.
        </p>
        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={cerrar}>
            Cancelar
          </Button>
          <Button
            disabled={finalizar.isPending}
            onClick={() => finalizar.mutate(contrato.id, { onSettled: cerrar })}
          >
            {finalizar.isPending ? 'Finalizando…' : 'Finalizar'}
          </Button>
        </div>
      </Dialogo>
    </div>
  )
}
