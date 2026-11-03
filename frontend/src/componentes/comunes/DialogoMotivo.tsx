import { z } from 'zod'

import { Button } from '../ui/button'
import { Dialogo } from './Dialogo'
import { FormularioDatos, type CampoFormulario } from './FormularioDatos'

const esquema = z.object({
  // El motivo queda en la bitácora; la API acepta hasta 255 caracteres.
  motivo: z.string().trim().min(1, 'Escriba el motivo.').max(255),
})

type Datos = z.infer<typeof esquema>

const CAMPOS: CampoFormulario<Datos>[] = [
  {
    nombre: 'motivo',
    etiqueta: 'Motivo',
    tipo: 'area',
    ayuda: 'Queda en la bitácora.',
  },
]

interface Props {
  abierto: boolean
  titulo: string
  /** Qué va a pasar, en una frase, para que la persona confirme sabiendo. */
  descripcion: string
  textoConfirmar: string
  /** Llama a la mutación (mutateAsync). Si falla, el error se muestra en el diálogo. */
  alConfirmar: (motivo: string) => Promise<unknown>
  alCerrar: () => void
}

/**
 * Diálogo de las acciones que solo piden un motivo (spec 018, §6): anular un
 * contrato de compra o un pago, suspender o cancelar un proyecto. Vive en
 * comunes porque no es de un dominio; B lo puede usar para anular contratos de
 * venta. Un 409 de la API sale arriba del formulario, como en todo
 * FormularioDatos.
 */
export function DialogoMotivo({
  abierto,
  titulo,
  descripcion,
  textoConfirmar,
  alConfirmar,
  alCerrar,
}: Props) {
  const guardar = async (datos: Datos) => {
    await alConfirmar(datos.motivo)
    alCerrar()
  }

  return (
    <Dialogo abierto={abierto} titulo={titulo} alCerrar={alCerrar}>
      {/* Se crea al abrir: así cada vez empieza vacío, sin el motivo anterior. */}
      {abierto && (
        <>
          <p className="text-sm text-slate-600">{descripcion}</p>
          <FormularioDatos
            campos={CAMPOS}
            esquema={esquema}
            valoresIniciales={{ motivo: '' }}
            alEnviar={guardar}
            textoEnviar={textoConfirmar}
          />
          <Button variant="outline" className="self-start" onClick={alCerrar}>
            Cancelar
          </Button>
        </>
      )}
    </Dialogo>
  )
}
