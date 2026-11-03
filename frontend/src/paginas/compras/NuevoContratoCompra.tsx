import { useNavigate } from 'react-router'
import { z } from 'zod'

import { useOpcionesPropiedad } from '../../api/catalogo/consultas'
import { useOpcionesProveedor } from '../../api/compras/consultas'
import { useCrearContratoCompra } from '../../api/compras/mutaciones'
import { useMonedas } from '../../api/core/consultas'
import {
  FormularioDatos,
  type CampoFormulario,
} from '../../componentes/comunes/FormularioDatos'
import { fechaDeHoy } from '../../lib/formato'

const MONTO = /^\d+(\.\d{1,2})?$/
const MENSAJE_MONTO = 'Escriba un número, con hasta dos decimales.'

const esquema = z.object({
  proveedor: z.string().min(1, 'Busque y elija el proveedor.'),
  propiedad: z.string().min(1, 'Busque y elija la propiedad.'),
  // Que no sea futura lo revisa la API (spec 017, regla 4).
  fecha_compra: z.string().min(1, 'Elija la fecha de compra.'),
  monto: z.string().regex(MONTO, MENSAJE_MONTO),
  gastos_legales: z.string().regex(MONTO, MENSAJE_MONTO).or(z.literal('')),
  impuestos: z.string().regex(MONTO, MENSAJE_MONTO).or(z.literal('')),
  moneda: z.string().min(1, 'Elija la moneda.'),
  observaciones: z.string(),
})

type Datos = z.infer<typeof esquema>

/**
 * Solo propiedades en negociación: son las que se pueden comprar (spec 018,
 * regla 7). Es un hook propio porque FormularioDatos llama a buscar(texto,
 * valores): el estado no puede ir en el segundo argumento.
 */
function useOpcionesPropiedadEnNegociacion(texto: string) {
  return useOpcionesPropiedad(texto, undefined, 'EN_NEGOCIACION')
}

/**
 * Registra un contrato de compra EN_PROCESO (spec 018, §5). El costo total y
 * la tasa al dólar los calcula la API (spec 017, reglas 3 y 5): por eso no
 * están aquí, y la lista los muestra tal como quedaron.
 */
export function NuevoContratoCompra() {
  const navegar = useNavigate()
  const crear = useCrearContratoCompra()
  const monedas = useMonedas()

  const campos: CampoFormulario<Datos>[] = [
    {
      nombre: 'proveedor',
      etiqueta: 'Proveedor',
      tipo: 'relacion',
      buscar: useOpcionesProveedor,
    },
    {
      nombre: 'propiedad',
      etiqueta: 'Propiedad',
      tipo: 'relacion',
      ayuda: 'Solo se ofrecen las propiedades en negociación.',
      buscar: useOpcionesPropiedadEnNegociacion,
    },
    { nombre: 'fecha_compra', etiqueta: 'Fecha de compra', tipo: 'fecha' },
    { nombre: 'monto', etiqueta: 'Monto', tipo: 'numero' },
    {
      nombre: 'gastos_legales',
      etiqueta: 'Gastos legales',
      tipo: 'numero',
      ayuda: 'Opcional.',
    },
    { nombre: 'impuestos', etiqueta: 'Impuestos', tipo: 'numero', ayuda: 'Opcional.' },
    {
      nombre: 'moneda',
      etiqueta: 'Moneda',
      tipo: 'seleccion',
      opciones: (monedas.data ?? []).map((moneda) => ({
        valor: String(moneda.id),
        etiqueta: `${moneda.codigo} · ${moneda.nombre}`,
      })),
    },
    {
      nombre: 'observaciones',
      etiqueta: 'Observaciones',
      tipo: 'area',
      ayuda: 'Opcional.',
    },
  ]

  const guardar = async (datos: Datos) => {
    await crear.mutateAsync({
      proveedor: Number(datos.proveedor),
      propiedad: Number(datos.propiedad),
      fecha_compra: datos.fecha_compra,
      monto: datos.monto,
      // Vacíos valen 0 (spec 017, §4).
      gastos_legales: datos.gastos_legales || '0',
      impuestos: datos.impuestos || '0',
      moneda: Number(datos.moneda),
      observaciones: datos.observaciones,
    })
    navegar('/compras/contratos?estado=EN_PROCESO')
  }

  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-2xl font-semibold">Nuevo contrato de compra</h1>
      <FormularioDatos
        campos={campos}
        esquema={esquema}
        valoresIniciales={{
          proveedor: '',
          propiedad: '',
          fecha_compra: fechaDeHoy(),
          monto: '',
          gastos_legales: '',
          impuestos: '',
          moneda: '',
          observaciones: '',
        }}
        alEnviar={guardar}
        textoEnviar="Registrar contrato"
      />
    </div>
  )
}
