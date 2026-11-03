import { z } from 'zod'

import type { Agente } from '../../api/crm/consultas'
import { useEditarAgente } from '../../api/crm/mutaciones'
import { Dialogo } from '../../componentes/comunes/Dialogo'
import {
  FormularioDatos,
  type CampoFormulario,
} from '../../componentes/comunes/FormularioDatos'
import { Button } from '../../componentes/ui/button'

const esquema = z.object({
  porcentaje_comision: z.string().min(1, 'Escriba la comisión.'),
})

type Datos = z.infer<typeof esquema>

const CAMPOS: CampoFormulario<Datos>[] = [
  {
    nombre: 'porcentaje_comision',
    etiqueta: 'Comisión (%)',
    tipo: 'numero',
    ayuda: 'Entre 0 y 100, con dos decimales.',
  },
]

interface Props {
  /** El agente a editar; null cierra el diálogo. */
  agente: Agente | null
  alCerrar: () => void
}

/**
 * Cambia la comisión del agente. El rango lo valida la API (spec 004, regla 3)
 * y FormularioDatos muestra su error junto al campo. Se monta con key para que
 * el campo empiece siempre con la comisión del agente elegido.
 */
export function DialogoEditarAgente({ agente, alCerrar }: Props) {
  const editar = useEditarAgente()

  const guardar = async (datos: Datos) => {
    if (agente) {
      await editar.mutateAsync({ id: agente.id, ...datos })
      alCerrar()
    }
  }

  return (
    <Dialogo
      abierto={agente !== null}
      titulo={`Editar ${agente?.codigo ?? ''}`}
      alCerrar={alCerrar}
    >
      {agente && (
        <>
          <p className="text-sm text-tenue">{agente.usuario.nombre_completo}</p>
          <FormularioDatos
            key={agente.id}
            campos={CAMPOS}
            esquema={esquema}
            valoresIniciales={{ porcentaje_comision: agente.porcentaje_comision }}
            alEnviar={guardar}
            textoEnviar="Guardar"
          />
          <Button variant="outline" className="self-start" onClick={alCerrar}>
            Cancelar
          </Button>
        </>
      )}
    </Dialogo>
  )
}
