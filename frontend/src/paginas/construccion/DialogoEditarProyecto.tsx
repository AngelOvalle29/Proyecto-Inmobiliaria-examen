import { z } from 'zod'

import { ESTADOS_ACTIVOS, type ProyectoDetalle } from '../../api/construccion/consultas'
import {
  useEditarProyecto,
  type DatosEditarProyecto,
} from '../../api/construccion/mutaciones'
import { Dialogo } from '../../componentes/comunes/Dialogo'
import {
  FormularioDatos,
  type CampoFormulario,
} from '../../componentes/comunes/FormularioDatos'
import { Button } from '../../componentes/ui/button'

const esquema = z.object({
  nombre: z.string().trim().min(1, 'Escriba el nombre.').max(200),
  fecha_fin_estimada: z.string().min(1, 'Elija la fecha de fin estimada.'),
  presupuesto_total: z
    .string()
    .regex(/^\d+(\.\d{1,2})?$/, 'Escriba un número, con hasta dos decimales.'),
})

type Datos = z.infer<typeof esquema>

interface Props {
  proyecto: ProyectoDetalle
  abierto: boolean
  alCerrar: () => void
}

/**
 * Edita un proyecto (spec 017, regla 17). Un proyecto activo cambia sus tres
 * campos; uno finalizado, solo el presupuesto: subirlo es la forma de pagar un
 * finiquito que no cabía. La API rechaza cualquier campo que el estado no
 * admita aunque no cambie, por eso se envía solo lo que se muestra.
 */
export function DialogoEditarProyecto({ proyecto, abierto, alCerrar }: Props) {
  const editar = useEditarProyecto()
  const activo = ESTADOS_ACTIVOS.includes(proyecto.estado)

  const campos: CampoFormulario<Datos>[] = [
    ...(activo
      ? ([
          { nombre: 'nombre', etiqueta: 'Nombre', tipo: 'texto' },
          {
            nombre: 'fecha_fin_estimada',
            etiqueta: 'Fecha de fin estimada',
            tipo: 'fecha',
          },
        ] satisfies CampoFormulario<Datos>[])
      : []),
    {
      nombre: 'presupuesto_total',
      etiqueta: `Presupuesto (${proyecto.moneda.codigo})`,
      tipo: 'numero',
      ayuda: 'No puede quedar por debajo de lo ya programado y pagado.',
    },
  ]

  const guardar = async (datos: Datos) => {
    const cambios: DatosEditarProyecto = { presupuesto_total: datos.presupuesto_total }
    if (activo) {
      cambios.nombre = datos.nombre
      cambios.fecha_fin_estimada = datos.fecha_fin_estimada
    }
    await editar.mutateAsync({ id: proyecto.id, ...cambios })
    alCerrar()
  }

  return (
    <Dialogo abierto={abierto} titulo={`Editar ${proyecto.codigo}`} alCerrar={alCerrar}>
      {abierto && (
        <>
          <FormularioDatos
            campos={campos}
            esquema={esquema}
            valoresIniciales={{
              nombre: proyecto.nombre,
              fecha_fin_estimada: proyecto.fecha_fin_estimada,
              presupuesto_total: proyecto.presupuesto_total,
            }}
            alEnviar={guardar}
            textoEnviar="Guardar cambios"
          />
          <Button variant="outline" className="self-start" onClick={alCerrar}>
            Cancelar
          </Button>
        </>
      )}
    </Dialogo>
  )
}
