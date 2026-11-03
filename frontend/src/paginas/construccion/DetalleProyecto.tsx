import { createColumnHelper } from '@tanstack/react-table'
import { useState, type ReactNode } from 'react'
import { Link, useParams } from 'react-router'

import {
  ESTADOS_ACTIVOS,
  ETIQUETAS_ESTADO_PAGO,
  ETIQUETAS_ESTADO_PROYECTO,
  ETIQUETAS_TIPO_PAGO,
  usePagosDeProyecto,
  useProyecto,
  type PagoConstructora,
  type ProyectoDetalle,
} from '../../api/construccion/consultas'
import {
  useAccionProyecto,
  useAccionProyectoConMotivo,
  useAnularPago,
  type AccionSinDatos,
} from '../../api/construccion/mutaciones'
import { leerErrorApi } from '../../api/errores'
import { Dialogo } from '../../componentes/comunes/Dialogo'
import { DialogoMotivo } from '../../componentes/comunes/DialogoMotivo'
import { TablaDatos, type AccionFila } from '../../componentes/comunes/TablaDatos'
import { Button } from '../../componentes/ui/button'
import { formatearFecha, formatearMoneda } from '../../lib/formato'
import { ESCRIBEN_CONSTRUCCION, PAGAN_CONSTRUCCION, rolPermitido } from '../../menu'
import { useSesion } from '../../sesion/useSesion'
import { DialogoAvance } from './DialogoAvance'
import { DialogoEditarProyecto } from './DialogoEditarProyecto'
import { DialogoPagar } from './DialogoPagar'
import { DialogoProgramarPago } from './DialogoProgramarPago'

const columna = createColumnHelper<PagoConstructora>()

const COLUMNAS_PAGOS = [
  columna.accessor('codigo', { header: 'Código' }),
  columna.accessor('tipo', {
    header: 'Tipo',
    cell: ({ getValue }) => ETIQUETAS_TIPO_PAGO[getValue()],
  }),
  columna.accessor('monto', {
    header: 'Monto',
    cell: ({ row }) => formatearMoneda(row.original.monto, row.original.moneda.codigo),
  }),
  columna.accessor('fecha_programada', {
    header: 'Programado',
    cell: ({ getValue }) => formatearFecha(getValue()),
  }),
  columna.accessor('estado', {
    header: 'Estado',
    cell: ({ row }) => ETIQUETAS_ESTADO_PAGO[row.original.estado ?? 'PROGRAMADO'],
  }),
  columna.accessor('fecha_pago', {
    header: 'Pagado',
    cell: ({ getValue }) => {
      const fecha = getValue()
      return fecha ? formatearFecha(fecha) : '—'
    },
  }),
  columna.accessor('referencia_pago', {
    header: 'Referencia',
    cell: ({ getValue }) => getValue() || '—',
  }),
]

/** Lo que pregunta cada acción sin datos antes de ejecutarse. */
const CONFIRMACIONES: Record<AccionSinDatos, { titulo: string; texto: string }> = {
  iniciar: {
    titulo: 'Iniciar la obra',
    texto: 'La propiedad pasará a en construcción.',
  },
  reanudar: {
    titulo: 'Reanudar la obra',
    texto: 'El proyecto vuelve a en ejecución.',
  },
  finalizar: {
    titulo: 'Finalizar la obra',
    texto:
      'La propiedad y sus unidades en construcción pasarán a disponibles. Después solo se puede subir el presupuesto, para un finiquito.',
  },
}

function Dato({ etiqueta, valor }: { etiqueta: string; valor: ReactNode }) {
  return (
    <div>
      <dt className="text-xs text-tenue">{etiqueta}</dt>
      <dd className="text-sm">{valor}</dd>
    </div>
  )
}

function DatosDelProyecto({ proyecto }: { proyecto: ProyectoDetalle }) {
  const moneda = proyecto.moneda.codigo
  const avance = proyecto.porcentaje_avance ?? 0
  return (
    <div className="flex flex-col gap-4 rounded-2xl border border-ceniza bg-blanco p-4">
      <dl className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Dato
          etiqueta="Propiedad"
          valor={
            <Link
              className="underline"
              to={`/catalogo/propiedades/${proyecto.propiedad.id}`}
            >
              {proyecto.propiedad.codigo}
            </Link>
          }
        />
        <Dato etiqueta="Constructora" valor={proyecto.constructora.nombre} />
        <Dato etiqueta="Estado" valor={ETIQUETAS_ESTADO_PROYECTO[proyecto.estado]} />
        <Dato etiqueta="Inicio" valor={formatearFecha(proyecto.fecha_inicio)} />
        <Dato
          etiqueta="Fin estimado"
          valor={formatearFecha(proyecto.fecha_fin_estimada)}
        />
        <Dato
          etiqueta="Fin real"
          valor={
            proyecto.fecha_fin_real ? formatearFecha(proyecto.fecha_fin_real) : '—'
          }
        />
      </dl>

      <div className="flex flex-col gap-1">
        <div className="flex justify-between text-sm">
          <span className="text-tenue">Avance</span>
          <span className="font-medium">{avance} %</span>
        </div>
        <div
          role="progressbar"
          aria-label="Avance de la obra"
          aria-valuenow={avance}
          aria-valuemin={0}
          aria-valuemax={100}
          className="h-2 overflow-hidden rounded-full bg-niebla"
        >
          <div className="h-full bg-tinta" style={{ width: `${avance}%` }} />
        </div>
      </div>

      {/* Los tres montos los calcula la API (spec 018, §4 y regla 6). */}
      <dl className="grid grid-cols-3 gap-3 border-t border-niebla pt-3">
        <Dato
          etiqueta="Presupuesto"
          valor={formatearMoneda(proyecto.presupuesto_total, moneda)}
        />
        <Dato
          etiqueta="Comprometido"
          valor={formatearMoneda(proyecto.total_comprometido, moneda)}
        />
        <Dato
          etiqueta="Disponible"
          valor={
            <span className="font-medium">
              {formatearMoneda(proyecto.disponible, moneda)}
            </span>
          }
        />
      </dl>
    </div>
  )
}

/**
 * Detalle de un proyecto de construcción (spec 018, §5 y §10): sus datos, su
 * avance, presupuesto / comprometido / disponible y sus pagos. Las acciones del
 * proyecto son de administración y gerencia; programar, pagar y anular pagos,
 * también de contabilidad (regla 2). Cada acción se ofrece solo en el estado
 * que la admite (regla 3); si aun así la API la rechaza, su mensaje sale arriba.
 */
export function DetalleProyecto() {
  const { id } = useParams()
  const { usuario } = useSesion()
  const consulta = useProyecto(Number(id))
  const [pagina, setPagina] = useState(1)
  const pagos = usePagosDeProyecto(Number(id), pagina)
  const accion = useAccionProyecto()
  const accionConMotivo = useAccionProyectoConMotivo()
  const anularPago = useAnularPago()

  const [confirmando, setConfirmando] = useState<AccionSinDatos | null>(null)
  const [conMotivo, setConMotivo] = useState<'suspender' | 'cancelar' | null>(null)
  const [avanzando, setAvanzando] = useState(false)
  const [editando, setEditando] = useState(false)
  const [programando, setProgramando] = useState(false)
  const [paraPagar, setParaPagar] = useState<PagoConstructora | null>(null)
  const [paraAnular, setParaAnular] = useState<PagoConstructora | null>(null)
  const proyecto = consulta.data

  if (!proyecto) {
    return consulta.isError ? (
      <p role="alert" className="rounded-md bg-red-50 p-3 text-sm text-red-700">
        {leerErrorApi(consulta.error).mensaje}
      </p>
    ) : (
      <p className="text-sm text-tenue">Cargando…</p>
    )
  }

  const rol = usuario?.rol ?? ''
  const escribe = rolPermitido(rol, ESCRIBEN_CONSTRUCCION)
  const paga = rolPermitido(rol, PAGAN_CONSTRUCCION)
  const estado = proyecto.estado
  const activo = ESTADOS_ACTIVOS.includes(estado)
  const enEjecucion = estado === 'EN_EJECUCION'

  const accionesPago: AccionFila<PagoConstructora>[] = paga
    ? [
        {
          etiqueta: 'Pagar',
          oculta: (fila) => fila.estado !== 'PROGRAMADO',
          ejecutar: (fila) => setParaPagar(fila),
        },
        {
          etiqueta: 'Anular',
          variante: 'destructive',
          oculta: (fila) => fila.estado !== 'PROGRAMADO',
          ejecutar: (fila) => setParaAnular(fila),
        },
      ]
    : []

  const confirmarAccion = () => {
    if (confirmando) {
      accion.mutate(
        { id: proyecto.id, accion: confirmando },
        { onSettled: () => setConfirmando(null) },
      )
    }
  }

  // El error de la última acción sin datos; las demás lo muestran en su diálogo.
  const errorAccion = accion.isError ? leerErrorApi(accion.error).mensaje : null

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="font-editorial text-4xl leading-none">
            {proyecto.codigo} · {proyecto.nombre}
          </h1>
          <Link to="/construccion/proyectos" className="text-sm text-tenue underline">
            Volver a proyectos
          </Link>
        </div>
        {escribe && (
          <div className="flex flex-wrap gap-2">
            {estado === 'PLANIFICADO' && (
              <Button onClick={() => setConfirmando('iniciar')}>Iniciar</Button>
            )}
            {enEjecucion && (
              <Button onClick={() => setAvanzando(true)}>Registrar avance</Button>
            )}
            {/* Finalizar se ofrece solo con avance 100 (regla 3). */}
            {enEjecucion && proyecto.porcentaje_avance === 100 && (
              <Button onClick={() => setConfirmando('finalizar')}>Finalizar</Button>
            )}
            {enEjecucion && (
              <Button variant="outline" onClick={() => setConMotivo('suspender')}>
                Suspender
              </Button>
            )}
            {estado === 'SUSPENDIDO' && (
              <Button onClick={() => setConfirmando('reanudar')}>Reanudar</Button>
            )}
            {(activo || estado === 'FINALIZADO') && (
              <Button variant="outline" onClick={() => setEditando(true)}>
                Editar
              </Button>
            )}
            {activo && (
              <Button variant="destructive" onClick={() => setConMotivo('cancelar')}>
                Cancelar proyecto
              </Button>
            )}
          </div>
        )}
      </div>

      {errorAccion && (
        <p role="alert" className="rounded-md bg-red-50 p-3 text-sm text-red-700">
          {errorAccion}
        </p>
      )}

      <DatosDelProyecto proyecto={proyecto} />

      <div className="flex items-center justify-between">
        <h2 className="font-editorial text-2xl">Pagos a la constructora</h2>
        {/* Un proyecto cancelado ya no admite pagos (spec 017, regla 20). */}
        {paga && estado !== 'CANCELADO' && (
          <Button onClick={() => setProgramando(true)}>Programar pago</Button>
        )}
      </div>
      <TablaDatos
        columnas={COLUMNAS_PAGOS}
        datos={pagos.data?.results}
        cargando={pagos.isPending}
        error={pagos.error}
        acciones={accionesPago}
        mensajeVacio="Este proyecto todavía no tiene pagos."
        paginacion={{
          pagina,
          total: pagos.data?.count ?? 0,
          alCambiarPagina: setPagina,
        }}
      />

      <Dialogo
        abierto={confirmando !== null}
        titulo={confirmando ? CONFIRMACIONES[confirmando].titulo : ''}
        alCerrar={() => setConfirmando(null)}
      >
        <p className="text-sm text-tenue">
          {confirmando && CONFIRMACIONES[confirmando].texto}
        </p>
        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={() => setConfirmando(null)}>
            Volver
          </Button>
          <Button disabled={accion.isPending} onClick={confirmarAccion}>
            {accion.isPending ? 'Procesando…' : 'Confirmar'}
          </Button>
        </div>
      </Dialogo>

      <DialogoMotivo
        abierto={conMotivo !== null}
        titulo={conMotivo === 'cancelar' ? 'Cancelar el proyecto' : 'Suspender la obra'}
        descripcion={
          conMotivo === 'cancelar'
            ? 'La propiedad vuelve a adquirida y los pagos programados se anulan. Los pagados quedan como están.'
            : 'La obra queda en pausa hasta reanudarla.'
        }
        textoConfirmar={conMotivo === 'cancelar' ? 'Cancelar proyecto' : 'Suspender'}
        alConfirmar={(motivo) =>
          accionConMotivo.mutateAsync({
            id: proyecto.id,
            accion: conMotivo as 'suspender' | 'cancelar',
            motivo,
          })
        }
        alCerrar={() => setConMotivo(null)}
      />

      <DialogoMotivo
        abierto={paraAnular !== null}
        titulo={`Anular ${paraAnular?.codigo ?? ''}`}
        descripcion="El pago deja de comprometer el presupuesto."
        textoConfirmar="Anular pago"
        alConfirmar={(motivo) =>
          anularPago.mutateAsync({ id: (paraAnular as PagoConstructora).id, motivo })
        }
        alCerrar={() => setParaAnular(null)}
      />

      <DialogoAvance
        proyecto={proyecto}
        abierto={avanzando}
        alCerrar={() => setAvanzando(false)}
      />
      <DialogoEditarProyecto
        proyecto={proyecto}
        abierto={editando}
        alCerrar={() => setEditando(false)}
      />
      <DialogoProgramarPago
        proyecto={proyecto}
        abierto={programando}
        alCerrar={() => setProgramando(false)}
      />
      <DialogoPagar pago={paraPagar} alCerrar={() => setParaPagar(null)} />
    </div>
  )
}
