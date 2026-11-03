import { z } from 'zod'

import type { ProyectoDetalle } from '../../api/construccion/consultas'
import { useRegistrarAvance } from '../../api/construccion/mutaciones'
import { Dialogo } from '../../componentes/comunes/Dialogo'
import {
  FormularioDatos,
  type CampoFormulario,
} from '../../componentes/comunes/FormularioDatos'
import { Button } from '../../componentes/ui/button'

const esquema = z.object({
  // Formato: un entero de 0 a 100. Que no baje del actual es regla de negocio
  // y la revisa la API (spec 017, regla 13).
  porcentaje: z.string().regex(/^(100|[1-9]?\d)$/, 'Escriba un entero de 0 a 100.'),
  descripcion: z.string().trim().min(1, 'Describa el avance.').max(500),
})

type Datos = z.infer<typeof esquema>

const CAMPOS: CampoFormulario<Datos>[] = [
  { nombre: 'porcentaje', etiqueta: 'Avance (%)', tipo: 'numero' },
  {
    nombre: 'descripcion',
    etiqueta: 'Qué se avanzó',
    tipo: 'area',
    ayuda: 'Queda en la bitácora del proyecto.',
  },
]

interface Props {
  proyecto: ProyectoDetalle
  abierto: boolean
  alCerrar: () => void
}

/** Registra el avance de una obra en ejecución (spec 018, §5; spec 017, regla 13). */
export function DialogoAvance({ proyecto, abierto, alCerrar }: Props) {
  const registrar = useRegistrarAvance()
  const actual = proyecto.porcentaje_avance ?? 0

  const guardar = async (datos: Datos) => {
    await registrar.mutateAsync({
      id: proyecto.id,
      porcentaje: Number(datos.porcentaje),
      descripcion: datos.descripcion,
    })
    alCerrar()
  }

  return (
    <Dialogo abierto={abierto} titulo="Registrar avance" alCerrar={alCerrar}>
      {abierto && (
        <>
          <p className="text-sm text-tenue">
            Avance actual: {actual} %. El nuevo no puede ser menor.
          </p>
          <FormularioDatos
            campos={CAMPOS}
            esquema={esquema}
            valoresIniciales={{ porcentaje: String(actual), descripcion: '' }}
            alEnviar={guardar}
            textoEnviar="Registrar avance"
          />
          <Button variant="outline" className="self-start" onClick={alCerrar}>
            Cancelar
          </Button>
        </>
      )}
    </Dialogo>
  )
}
