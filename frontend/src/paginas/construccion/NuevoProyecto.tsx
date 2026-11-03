import { useNavigate } from 'react-router'
import { z } from 'zod'

import { useOpcionesPropiedad } from '../../api/catalogo/consultas'
import { useOpcionesConstructora } from '../../api/construccion/consultas'
import { useCrearProyecto } from '../../api/construccion/mutaciones'
import { useMonedas } from '../../api/core/consultas'
import {
  FormularioDatos,
  type CampoFormulario,
} from '../../componentes/comunes/FormularioDatos'

const esquema = z.object({
  nombre: z.string().trim().min(1, 'Escriba el nombre.').max(200),
  propiedad: z.string().min(1, 'Busque y elija la propiedad.'),
  constructora: z.string().min(1, 'Busque y elija la constructora.'),
  fecha_inicio: z.string().min(1, 'Elija la fecha de inicio.'),
  // Que no sea anterior al inicio lo revisa la API (spec 017, regla 11): su
  // error llega por campo y sale arriba, como todo error de dominio.
  fecha_fin_estimada: z.string().min(1, 'Elija la fecha de fin estimada.'),
  presupuesto_total: z
    .string()
    .regex(/^\d+(\.\d{1,2})?$/, 'Escriba un número, con hasta dos decimales.'),
  moneda: z.string().min(1, 'Elija la moneda.'),
})

type Datos = z.infer<typeof esquema>

/**
 * Solo propiedades adquiridas: son las que se pueden construir (spec 018,
 * regla 7). Hook propio por la misma razón que en NuevoContratoCompra.
 */
function useOpcionesPropiedadAdquirida(texto: string) {
  return useOpcionesPropiedad(texto, undefined, 'ADQUIRIDA')
}

/**
 * Registra un proyecto PLANIFICADO (spec 018, §5). No toca la propiedad hasta
 * que se inicia (spec 017, regla 12). Al crearlo se abre su detalle, donde
 * están sus acciones y sus pagos.
 */
export function NuevoProyecto() {
  const navegar = useNavigate()
  const crear = useCrearProyecto()
  const monedas = useMonedas()

  const campos: CampoFormulario<Datos>[] = [
    { nombre: 'nombre', etiqueta: 'Nombre del proyecto', tipo: 'texto' },
    {
      nombre: 'propiedad',
      etiqueta: 'Propiedad',
      tipo: 'relacion',
      ayuda: 'Solo se ofrecen las propiedades adquiridas.',
      buscar: useOpcionesPropiedadAdquirida,
    },
    {
      nombre: 'constructora',
      etiqueta: 'Constructora',
      tipo: 'relacion',
      buscar: useOpcionesConstructora,
    },
    { nombre: 'fecha_inicio', etiqueta: 'Fecha de inicio', tipo: 'fecha' },
    { nombre: 'fecha_fin_estimada', etiqueta: 'Fecha de fin estimada', tipo: 'fecha' },
    { nombre: 'presupuesto_total', etiqueta: 'Presupuesto', tipo: 'numero' },
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

  const guardar = async (datos: Datos) => {
    const creado = await crear.mutateAsync({
      nombre: datos.nombre,
      propiedad: Number(datos.propiedad),
      constructora: Number(datos.constructora),
      fecha_inicio: datos.fecha_inicio,
      fecha_fin_estimada: datos.fecha_fin_estimada,
      presupuesto_total: datos.presupuesto_total,
      moneda: Number(datos.moneda),
    })
    navegar(`/construccion/proyectos/${creado.id}`)
  }

  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-2xl font-semibold">Nuevo proyecto de construcción</h1>
      <FormularioDatos
        campos={campos}
        esquema={esquema}
        valoresIniciales={{
          nombre: '',
          propiedad: '',
          constructora: '',
          fecha_inicio: '',
          fecha_fin_estimada: '',
          presupuesto_total: '',
          moneda: '',
        }}
        alEnviar={guardar}
        textoEnviar="Registrar proyecto"
      />
    </div>
  )
}
