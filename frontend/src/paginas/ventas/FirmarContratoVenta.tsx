import { useNavigate, useSearchParams } from 'react-router'
import { z } from 'zod'

import {
  useOpcionesDocumento,
  useOpcionesPropiedad,
  useOpcionesUnidad,
} from '../../api/catalogo/consultas'
import { useMonedas } from '../../api/core/consultas'
import {
  useCotizacion,
  useOpcionesCliente,
  type Cotizacion,
} from '../../api/crm/consultas'
import { leerErrorApi } from '../../api/errores'
import { ETIQUETAS_MODALIDAD, type Modalidad } from '../../api/ventas/consultas'
import { useFirmarContratoVenta, type DatosFirma } from '../../api/ventas/mutaciones'
import {
  FormularioDatos,
  type CampoFormulario,
} from '../../componentes/comunes/FormularioDatos'
import { fechaDeHoy, formatearMoneda } from '../../lib/formato'

const monto = z
  .string()
  .regex(/^\d+(\.\d{1,2})?$/, 'Escriba un número, con hasta dos decimales.')
  .or(z.literal(''))

const objeto = z.object({
  cliente: z.string(),
  propiedad: z.string(),
  unidad: z.string(),
  monto_total: monto,
  moneda: z.string(),
  fecha_firma: z.string().min(1, 'Elija la fecha de firma.'),
  modalidad: z.enum(['CONTADO', 'FINANCIADO'], { message: 'Elija la modalidad.' }),
  enganche: monto,
  numero_cuotas: z.string().regex(/^\d*$/, 'Escriba un número entero.'),
  tasa_interes_anual: monto,
  fecha_primera_cuota: z.string(),
  observaciones: z.string(),
  documento: z.string(),
})

type Datos = z.infer<typeof objeto>

/**
 * Los campos que solo aplican a un caso se exigen en superRefine (spec 012,
 * regla 4). `conCotizacion` decide cuáles: desde una cotización, cliente, bien,
 * monto y moneda salen de ella (spec 007, regla 7). Los rangos los valida la API.
 */
function crearEsquema(conCotizacion: boolean) {
  return objeto.superRefine((datos, contexto) => {
    const obligatorios: [keyof Datos, string][] = []
    if (!conCotizacion) {
      obligatorios.push(
        ['cliente', 'Busque y elija el cliente.'],
        ['propiedad', 'Busque y elija la propiedad.'],
        ['monto_total', 'Escriba el monto total.'],
        ['moneda', 'Elija la moneda.'],
      )
    }
    if (datos.modalidad === 'FINANCIADO') {
      obligatorios.push(
        ['numero_cuotas', 'Escriba el número de cuotas.'],
        ['tasa_interes_anual', 'Escriba la tasa de interés.'],
        ['fecha_primera_cuota', 'Elija la fecha de la primera cuota.'],
      )
    }
    for (const [campo, mensaje] of obligatorios) {
      if (!datos[campo]) {
        contexto.addIssue({ code: 'custom', path: [campo], message: mensaje })
      }
    }
  })
}

const esFinanciado = (valores: Datos) => valores.modalidad === 'FINANCIADO'

const CAMPOS_DE_LA_VENTA: CampoFormulario<Datos>[] = [
  { nombre: 'fecha_firma', etiqueta: 'Fecha de firma', tipo: 'fecha' },
  {
    nombre: 'modalidad',
    etiqueta: 'Modalidad',
    tipo: 'seleccion',
    opciones: Object.entries(ETIQUETAS_MODALIDAD).map(([valor, etiqueta]) => ({
      valor,
      etiqueta,
    })),
  },
  {
    nombre: 'enganche',
    etiqueta: 'Enganche',
    tipo: 'numero',
    ayuda: 'Opcional.',
    visibleSi: esFinanciado,
  },
  {
    nombre: 'numero_cuotas',
    etiqueta: 'Número de cuotas',
    tipo: 'numero',
    ayuda: 'Entre 1 y 360.',
    visibleSi: esFinanciado,
  },
  {
    nombre: 'tasa_interes_anual',
    etiqueta: 'Tasa de interés anual (%)',
    tipo: 'numero',
    visibleSi: esFinanciado,
  },
  {
    nombre: 'fecha_primera_cuota',
    etiqueta: 'Fecha de la primera cuota',
    tipo: 'fecha',
    visibleSi: esFinanciado,
  },
  {
    nombre: 'observaciones',
    etiqueta: 'Observaciones',
    tipo: 'area',
    ayuda: 'Opcional.',
  },
  {
    nombre: 'documento',
    etiqueta: 'Documento del contrato',
    tipo: 'relacion',
    dependeDe: 'propiedad',
    marcador: 'Primero elija la propiedad',
    ayuda: 'Opcional. También se puede vincular después, desde el detalle.',
    buscar: useOpcionesDocumento,
  },
]

interface PropsFormulario {
  /** La cotización aprobada de la que sale el contrato; sin ella, se firma directo. */
  cotizacion?: Cotizacion
}

function Formulario({ cotizacion }: PropsFormulario) {
  const navegar = useNavigate()
  const firmar = useFirmarContratoVenta()
  const monedas = useMonedas()

  const camposSinCotizacion: CampoFormulario<Datos>[] = [
    {
      nombre: 'cliente',
      etiqueta: 'Cliente',
      tipo: 'relacion',
      buscar: useOpcionesCliente,
    },
    {
      nombre: 'propiedad',
      etiqueta: 'Propiedad',
      tipo: 'relacion',
      buscar: useOpcionesPropiedad,
    },
    {
      nombre: 'unidad',
      etiqueta: 'Unidad',
      tipo: 'relacion',
      dependeDe: 'propiedad',
      marcador: 'Primero elija la propiedad',
      ayuda: 'Solo si la propiedad se vende por unidades.',
      buscar: useOpcionesUnidad,
    },
    { nombre: 'monto_total', etiqueta: 'Monto total', tipo: 'numero' },
    {
      nombre: 'moneda',
      etiqueta: 'Moneda',
      tipo: 'seleccion',
      opciones: (monedas.data ?? []).map((moneda) => ({
        valor: String(moneda.id),
        etiqueta: `${moneda.codigo} · ${moneda.nombre}`,
      })),
    },
  ]

  /** Del formulario (todo texto) a lo que espera la API. */
  const guardar = async (datos: Datos) => {
    const comunes: DatosFirma = {
      fecha_firma: datos.fecha_firma,
      modalidad: datos.modalidad as Modalidad,
      observaciones: datos.observaciones,
      documento: datos.documento ? Number(datos.documento) : undefined,
    }
    if (datos.modalidad === 'FINANCIADO') {
      comunes.enganche = datos.enganche || undefined
      comunes.numero_cuotas = Number(datos.numero_cuotas)
      comunes.tasa_interes_anual = datos.tasa_interes_anual
      comunes.fecha_primera_cuota = datos.fecha_primera_cuota
    }
    const contrato = await firmar.mutateAsync(
      cotizacion
        ? { ...comunes, cotizacion: cotizacion.id }
        : {
            ...comunes,
            cliente: Number(datos.cliente),
            // La API acepta una propiedad o una unidad, nunca las dos.
            ...(datos.unidad
              ? { unidad: Number(datos.unidad) }
              : { propiedad: Number(datos.propiedad) }),
            monto_total: datos.monto_total,
            moneda: Number(datos.moneda),
          },
    )
    navegar(`/ventas/contratos/${contrato.id}`)
  }

  return (
    <FormularioDatos
      campos={[...(cotizacion ? [] : camposSinCotizacion), ...CAMPOS_DE_LA_VENTA]}
      esquema={crearEsquema(cotizacion !== undefined)}
      valoresIniciales={{
        cliente: '',
        // Con cotización no se muestra: la usa el buscador de documentos.
        propiedad: String(
          cotizacion?.propiedad?.id ?? cotizacion?.unidad?.propiedad.id ?? '',
        ),
        unidad: '',
        monto_total: '',
        moneda: '',
        fecha_firma: fechaDeHoy(),
        modalidad: 'CONTADO',
        enganche: '',
        numero_cuotas: '',
        tasa_interes_anual: '',
        fecha_primera_cuota: '',
        observaciones: '',
        documento: '',
      }}
      alEnviar={guardar}
      textoEnviar="Firmar contrato"
    />
  )
}

/**
 * Firma de un contrato de venta (spec 012, regla 8). Con ?cotizacion=<id> llega
 * desde la fila de una cotización aprobada, y solo faltan fecha, modalidad y plan.
 */
export function FirmarContratoVenta() {
  const [parametros] = useSearchParams()
  const idCotizacion = parametros.get('cotizacion')
  const consulta = useCotizacion(idCotizacion ? Number(idCotizacion) : undefined)
  const cotizacion = consulta.data

  return (
    <div className="flex flex-col gap-4">
      <h1 className="font-editorial text-4xl leading-none">Firmar contrato de venta</h1>
      {!idCotizacion && <Formulario />}
      {idCotizacion && consulta.isPending && (
        <p className="text-sm text-tenue">Cargando…</p>
      )}
      {consulta.isError && (
        <p role="alert" className="rounded-md bg-red-50 p-3 text-sm text-red-700">
          {leerErrorApi(consulta.error).mensaje}
        </p>
      )}
      {cotizacion && (
        <>
          <p className="text-sm text-tenue">
            Desde {cotizacion.codigo}: {cotizacion.cliente.nombre} ·{' '}
            {cotizacion.unidad?.codigo ?? cotizacion.propiedad?.codigo} ·{' '}
            {formatearMoneda(cotizacion.total, cotizacion.moneda.codigo)}
          </p>
          <Formulario cotizacion={cotizacion} />
        </>
      )}
    </div>
  )
}
