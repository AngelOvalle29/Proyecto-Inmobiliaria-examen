import { z } from 'zod'

import type { ArrendamientoDetalle } from '../../api/arrendamientos/consultas'
import { useRescindirArrendamiento } from '../../api/arrendamientos/mutaciones'
import { Dialogo } from '../../componentes/comunes/Dialogo'
import {
  FormularioDatos,
  type CampoFormulario,
} from '../../componentes/comunes/FormularioDatos'
import { Button } from '../../componentes/ui/button'
import { fechaDeHoy } from '../../lib/formato'

const esquema = z.object({
  fecha_rescision: z.string().min(1, 'Elija la fecha de rescisión.'),
})

type Datos = z.infer<typeof esquema>

const CAMPOS: CampoFormulario<Datos>[] = [
  {
    nombre: 'fecha_rescision',
    etiqueta: 'Fecha de rescisión',
    tipo: 'fecha',
    ayuda: 'Entre el inicio del contrato y hoy.',
  },
]

interface Props {
  contrato: ArrendamientoDetalle
  abierto: boolean
  alCerrar: () => void
}

/**
 * Rescindir registra algo que ya pasó, así que la fecha no puede ser futura; lo
 * valida la API (spec 008, regla 10). Se cancelan los pagos pendientes con
 * vencimiento posterior, y el bien vuelve a estar disponible.
 */
export function DialogoRescindir({ contrato, abierto, alCerrar }: Props) {
  const rescindir = useRescindirArrendamiento()

  const guardar = async (datos: Datos) => {
    await rescindir.mutateAsync({ id: contrato.id, ...datos })
    alCerrar()
  }

  return (
    <Dialogo
      abierto={abierto}
      titulo={`Rescindir ${contrato.codigo}`}
      alCerrar={alCerrar}
    >
      {abierto && (
        <>
          <p className="text-sm text-slate-600">
            Se cancelarán los pagos pendientes posteriores a esa fecha y la propiedad o
            unidad volverá a estar disponible.
          </p>
          <FormularioDatos
            campos={CAMPOS}
            esquema={esquema}
            valoresIniciales={{ fecha_rescision: fechaDeHoy() }}
            alEnviar={guardar}
            textoEnviar="Rescindir"
          />
          <Button variant="outline" className="self-start" onClick={alCerrar}>
            Cancelar
          </Button>
        </>
      )}
    </Dialogo>
  )
}
