import { useNavigate } from 'react-router'
import { z } from 'zod'

import { useFirmarArrendamiento } from '../../api/arrendamientos/mutaciones'
import {
  useOpcionesDocumento,
  useOpcionesPropiedad,
  useOpcionesUnidad,
} from '../../api/catalogo/consultas'
import { useMonedas } from '../../api/core/consultas'
import { useOpcionesCliente } from '../../api/crm/consultas'
import {
  FormularioDatos,
  type CampoFormulario,
} from '../../componentes/comunes/FormularioDatos'
import { fechaDeHoy } from '../../lib/formato'

const monto = z
  .string()
  .regex(/^\d+(\.\d{1,2})?$/, 'Escriba un número, con hasta dos decimales.')
const entero = z.string().regex(/^\d+$/, 'Escriba un número entero.')

// Solo el formato: los rangos de la regla 3 de la spec 008 los valida la API.
const esquema = z.object({
  cliente: z.string().min(1, 'Busque y elija el cliente.'),
  propiedad: z.string().min(1, 'Busque y elija la propiedad.'),
  unidad: z.string(),
  fecha_inicio: z.string().min(1, 'Elija la fecha de inicio.'),
  duracion_meses: entero,
  renta_mensual: monto,
  moneda: z.string().min(1, 'Elija la moneda.'),
  deposito: monto.or(z.literal('')),
  dia_cobro: entero,
  dias_gracia: entero,
  porcentaje_mora: monto,
  documento: z.string(),
})

type Datos = z.infer<typeof esquema>

/**
 * Firma de un arrendamiento. La fecha de fin y el calendario de pagos los
 * genera la API (spec 008, reglas 3 y 4), por eso no están aquí.
 */
export function FirmarArrendamiento() {
  const navegar = useNavigate()
  const firmar = useFirmarArrendamiento()
  const monedas = useMonedas()

  const campos: CampoFormulario<Datos>[] = [
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
      ayuda: 'Solo si la propiedad se arrienda por unidades.',
      buscar: useOpcionesUnidad,
    },
    { nombre: 'fecha_inicio', etiqueta: 'Fecha de inicio', tipo: 'fecha' },
    {
      nombre: 'duracion_meses',
      etiqueta: 'Duración (meses)',
      tipo: 'numero',
      ayuda: 'Entre 1 y 120.',
    },
    { nombre: 'renta_mensual', etiqueta: 'Renta mensual', tipo: 'numero' },
    {
      nombre: 'moneda',
      etiqueta: 'Moneda',
      tipo: 'seleccion',
      opciones: (monedas.data ?? []).map((moneda) => ({
        valor: String(moneda.id),
        etiqueta: `${moneda.codigo} · ${moneda.nombre}`,
      })),
    },
    { nombre: 'deposito', etiqueta: 'Depósito', tipo: 'numero', ayuda: 'Opcional.' },
    {
      nombre: 'dia_cobro',
      etiqueta: 'Día de cobro',
      tipo: 'numero',
      ayuda: 'Entre 1 y 28.',
    },
    {
      nombre: 'dias_gracia',
      etiqueta: 'Días de gracia',
      tipo: 'numero',
      ayuda: 'Entre 0 y 31.',
    },
    { nombre: 'porcentaje_mora', etiqueta: 'Recargo por mora (%)', tipo: 'numero' },
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

  /** Del formulario (todo texto) a lo que espera la API. */
  const guardar = async (datos: Datos) => {
    const contrato = await firmar.mutateAsync({
      cliente: Number(datos.cliente),
      // La API acepta una propiedad o una unidad, nunca las dos.
      ...(datos.unidad
        ? { unidad: Number(datos.unidad) }
        : { propiedad: Number(datos.propiedad) }),
      fecha_inicio: datos.fecha_inicio,
      duracion_meses: Number(datos.duracion_meses),
      renta_mensual: datos.renta_mensual,
      moneda: Number(datos.moneda),
      deposito: datos.deposito || undefined,
      dia_cobro: Number(datos.dia_cobro),
      dias_gracia: Number(datos.dias_gracia),
      porcentaje_mora: datos.porcentaje_mora,
      documento: datos.documento ? Number(datos.documento) : undefined,
    })
    navegar(`/arrendamientos/contratos/${contrato.id}`)
  }

  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-2xl font-semibold">Firmar contrato de arrendamiento</h1>
      <FormularioDatos
        campos={campos}
        esquema={esquema}
        valoresIniciales={{
          cliente: '',
          propiedad: '',
          unidad: '',
          fecha_inicio: fechaDeHoy(),
          duracion_meses: '12',
          renta_mensual: '',
          moneda: '',
          deposito: '',
          dia_cobro: '1',
          dias_gracia: '0',
          porcentaje_mora: '0',
          documento: '',
        }}
        alEnviar={guardar}
        textoEnviar="Firmar contrato"
      />
    </div>
  )
}
