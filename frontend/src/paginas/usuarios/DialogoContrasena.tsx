import { z } from 'zod'

import type { UsuarioListado } from '../../api/usuarios/consultas'
import { useRestablecerContrasena } from '../../api/usuarios/mutaciones'
import { Dialogo } from '../../componentes/comunes/Dialogo'
import {
  FormularioDatos,
  type CampoFormulario,
} from '../../componentes/comunes/FormularioDatos'
import { Button } from '../../componentes/ui/button'

/**
 * Contraseña nueva y su confirmación. El largo mínimo se adelanta aquí; los
 * demás validadores (común, parecida al correo) los aplica la API y su motivo
 * sale junto al campo (spec 026, regla 3).
 */
const esquemaContrasenaNueva = z
  .object({
    password: z.string().min(10, 'Al menos 10 caracteres.'),
    confirmar: z.string(),
  })
  .refine((datos) => datos.password === datos.confirmar, {
    message: 'Las dos contraseñas no coinciden.',
    path: ['confirmar'],
  })

type Datos = z.infer<typeof esquemaContrasenaNueva>

const CAMPOS_CONTRASENA: CampoFormulario<Datos>[] = [
  { nombre: 'password', etiqueta: 'Contraseña nueva', tipo: 'contrasena' },
  { nombre: 'confirmar', etiqueta: 'Repita la contraseña', tipo: 'contrasena' },
]

interface Props {
  usuario: UsuarioListado | null
  alCerrar: () => void
}

/**
 * Un administrador restablece la contraseña de otra cuenta (spec 026). El
 * sistema no envía correos: se la comunica a la persona por un medio privado.
 */
export function DialogoContrasena({ usuario, alCerrar }: Props) {
  const restablecer = useRestablecerContrasena()

  const guardar = async (datos: Datos) => {
    if (usuario) {
      await restablecer.mutateAsync({ id: usuario.id, password: datos.password })
      alCerrar()
    }
  }

  return (
    <Dialogo
      abierto={usuario !== null}
      titulo="Restablecer contraseña"
      alCerrar={alCerrar}
    >
      {usuario && (
        <>
          <p className="text-sm text-tenue">
            {usuario.nombre_completo} · {usuario.email}. Comuníquele la contraseña nueva
            por un medio privado.
          </p>
          <FormularioDatos
            key={usuario.id}
            campos={CAMPOS_CONTRASENA}
            esquema={esquemaContrasenaNueva}
            valoresIniciales={{ password: '', confirmar: '' }}
            alEnviar={guardar}
            textoEnviar="Restablecer"
          />
          <Button variant="outline" className="self-start" onClick={alCerrar}>
            Cancelar
          </Button>
        </>
      )}
    </Dialogo>
  )
}
