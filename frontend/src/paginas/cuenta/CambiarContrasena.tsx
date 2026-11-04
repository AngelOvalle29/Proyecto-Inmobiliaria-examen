import { useState } from 'react'
import { z } from 'zod'

import { useCambiarMiContrasena } from '../../api/usuarios/mutaciones'
import {
  FormularioDatos,
  type CampoFormulario,
} from '../../componentes/comunes/FormularioDatos'

const esquema = z
  .object({
    actual: z.string().min(1, 'Escriba su contraseña actual.'),
    nueva: z.string().min(10, 'Al menos 10 caracteres.'),
    confirmar: z.string(),
  })
  .refine((datos) => datos.nueva === datos.confirmar, {
    message: 'Las dos contraseñas no coinciden.',
    path: ['confirmar'],
  })

type Datos = z.infer<typeof esquema>

const CAMPOS: CampoFormulario<Datos>[] = [
  { nombre: 'actual', etiqueta: 'Contraseña actual', tipo: 'contrasena' },
  {
    nombre: 'nueva',
    etiqueta: 'Contraseña nueva',
    tipo: 'contrasena',
    ayuda: 'Al menos 10 caracteres, que no sea común ni parecida a su correo.',
  },
  { nombre: 'confirmar', etiqueta: 'Repita la contraseña nueva', tipo: 'contrasena' },
]

/**
 * Cualquier usuario cambia su contraseña (spec 026, regla 9). Si la actual no
 * es correcta, el error sale junto a ese campo. La sesión sigue abierta.
 */
export function CambiarContrasena() {
  const cambiar = useCambiarMiContrasena()
  // Al terminar, el formulario se vuelve a montar vacío con otra key.
  const [cambios, setCambios] = useState(0)

  const guardar = async (datos: Datos) => {
    await cambiar.mutateAsync({ actual: datos.actual, nueva: datos.nueva })
    setCambios((n) => n + 1)
  }

  return (
    <div className="flex max-w-xl flex-col gap-4">
      <h1 className="font-editorial text-4xl leading-none">Cambiar contraseña</h1>
      {cambios > 0 && (
        <p role="status" className="rounded-md bg-green-50 p-3 text-sm text-green-800">
          Su contraseña se cambió. Úsela la próxima vez que inicie sesión.
        </p>
      )}
      <FormularioDatos
        key={cambios}
        campos={CAMPOS}
        esquema={esquema}
        valoresIniciales={{ actual: '', nueva: '', confirmar: '' }}
        alEnviar={guardar}
        textoEnviar="Cambiar contraseña"
      />
    </div>
  )
}
