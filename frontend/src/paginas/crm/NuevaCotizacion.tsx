import { useNavigate } from 'react-router'
import { z } from 'zod'

import {
  ETIQUETAS_ESTADO,
  usePropiedades,
  useUnidadesDePropiedad,
} from '../../api/catalogo/consultas'
import { useOpcionesCliente } from '../../api/crm/consultas'
import { useCrearCotizacion } from '../../api/crm/mutaciones'
import {
  FormularioDatos,
  type CampoFormulario,
} from '../../componentes/comunes/FormularioDatos'

const esquema = z.object({
  cliente: z.string().min(1, 'Busque y elija el cliente.'),
  propiedad: z.string().min(1, 'Busque y elija la propiedad.'),
  // Vacía si se cotiza la propiedad completa (spec 007, regla 1).
  unidad: z.string(),
  fecha_vencimiento: z.string().min(1, 'Elija la fecha de vencimiento.'),
  descuento: z
    .string()
    .regex(/^\d+(\.\d{1,2})?$/, 'Escriba un número, con hasta dos decimales.')
    .or(z.literal('')),
  observaciones: z.string(),
})

type Datos = z.infer<typeof esquema>

/**
 * No se filtra por DISPONIBLE: un edificio con unidades disponibles puede tener
 * otro estado. El estado se muestra en la opción, y la regla 5 de la spec 007
 * la valida la API.
 */
function useOpcionesPropiedad(texto: string) {
  const consulta = usePropiedades({ buscar: texto || undefined })
  return {
    opciones: (consulta.data?.results ?? []).map((propiedad) => ({
      valor: String(propiedad.id),
      etiqueta: `${propiedad.codigo} · ${propiedad.nombre} (${ETIQUETAS_ESTADO[propiedad.estado]})`,
    })),
    cargando: consulta.isFetching,
  }
}

/** La API no busca unidades: se filtra por texto lo que devuelve la propiedad. */
function useOpcionesUnidad(texto: string, valores: Datos) {
  const propiedad = valores.propiedad ? Number(valores.propiedad) : undefined
  const consulta = useUnidadesDePropiedad(propiedad)
  const buscado = texto.toLowerCase()
  return {
    opciones: (consulta.data ?? [])
      .filter((unidad) => unidad.codigo.toLowerCase().includes(buscado))
      .map((unidad) => ({
        valor: String(unidad.id),
        etiqueta: `${unidad.codigo} (${ETIQUETAS_ESTADO[unidad.estado]})`,
      })),
    cargando: consulta.isFetching,
  }
}

const CAMPOS: CampoFormulario<Datos>[] = [
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
  { nombre: 'fecha_vencimiento', etiqueta: 'Vence el', tipo: 'fecha' },
  { nombre: 'descuento', etiqueta: 'Descuento', tipo: 'numero', ayuda: 'Opcional.' },
  {
    nombre: 'observaciones',
    etiqueta: 'Observaciones',
    tipo: 'area',
    ayuda: 'Opcional.',
  },
]

/**
 * Emite una cotización en borrador. Precio, moneda y total los pone la API con
 * el precio de lista del bien (spec 007, regla 2), por eso no están aquí.
 */
export function NuevaCotizacion() {
  const navegar = useNavigate()
  const crear = useCrearCotizacion()

  const guardar = async (datos: Datos) => {
    await crear.mutateAsync({
      cliente: Number(datos.cliente),
      // La API acepta una propiedad o una unidad, nunca las dos (regla 1).
      ...(datos.unidad
        ? { unidad: Number(datos.unidad) }
        : { propiedad: Number(datos.propiedad) }),
      fecha_vencimiento: datos.fecha_vencimiento,
      descuento: datos.descuento || undefined,
      observaciones: datos.observaciones,
    })
    navegar('/crm/cotizaciones')
  }

  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-2xl font-semibold">Nueva cotización</h1>
      <FormularioDatos
        campos={CAMPOS}
        esquema={esquema}
        valoresIniciales={{
          cliente: '',
          propiedad: '',
          unidad: '',
          fecha_vencimiento: '',
          descuento: '',
          observaciones: '',
        }}
        alEnviar={guardar}
        textoEnviar="Crear cotización"
      />
    </div>
  )
}
