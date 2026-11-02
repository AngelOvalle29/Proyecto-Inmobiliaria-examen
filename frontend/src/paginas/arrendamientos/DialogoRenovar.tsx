import { useNavigate } from 'react-router'
import { z } from 'zod'

import type { ArrendamientoDetalle } from '../../api/arrendamientos/consultas'
import { useRenovarArrendamiento } from '../../api/arrendamientos/mutaciones'
import { Dialogo } from '../../componentes/comunes/Dialogo'
import {
  FormularioDatos,
  type CampoFormulario,
} from '../../componentes/comunes/FormularioDatos'
import { Button } from '../../componentes/ui/button'

const esquema = z.object({
  renta_mensual: z
    .string()
    .regex(/^\d+(\.\d{1,2})?$/, 'Escriba un número, con hasta dos decimales.'),
  duracion_meses: z.string().regex(/^\d+$/, 'Escriba un número entero.'),
})

type Datos = z.infer<typeof esquema>

const CAMPOS: CampoFormulario<Datos>[] = [
  { nombre: 'renta_mensual', etiqueta: 'Renta mensual', tipo: 'numero' },
  {
    nombre: 'duracion_meses',
    etiqueta: 'Duración (meses)',
    tipo: 'numero',
    ayuda: 'Entre 1 y 120.',
  },
]

interface Props {
  contrato: ArrendamientoDetalle
  abierto: boolean
  alCerrar: () => void
}

/**
 * Renovar crea un contrato nuevo que empieza al día siguiente del fin de este
 * (spec 008, regla 9): al terminar se abre el contrato nuevo.
 */
export function DialogoRenovar({ contrato, abierto, alCerrar }: Props) {
  const navegar = useNavigate()
  const renovar = useRenovarArrendamiento()

  const guardar = async (datos: Datos) => {
    const nuevo = await renovar.mutateAsync({
      id: contrato.id,
      renta_mensual: datos.renta_mensual,
      duracion_meses: Number(datos.duracion_meses),
    })
    alCerrar()
    navegar(`/arrendamientos/contratos/${nuevo.id}`)
  }

  return (
    <Dialogo
      abierto={abierto}
      titulo={`Renovar ${contrato.codigo}`}
      alCerrar={alCerrar}
    >
      {abierto && (
        <>
          <FormularioDatos
            campos={CAMPOS}
            esquema={esquema}
            valoresIniciales={{
              renta_mensual: contrato.renta_mensual,
              duracion_meses: String(contrato.duracion_meses),
            }}
            alEnviar={guardar}
            textoEnviar="Renovar"
          />
          <Button variant="outline" className="self-start" onClick={alCerrar}>
            Cancelar
          </Button>
        </>
      )}
    </Dialogo>
  )
}
