import { z } from 'zod'

import type { TipoPropiedad } from '../../api/catalogo/consultas'
import {
  useActualizarTipoPropiedad,
  useCrearTipoPropiedad,
} from '../../api/catalogo/mutaciones'
import { Dialogo } from '../../componentes/comunes/Dialogo'
import {
  FormularioDatos,
  type CampoFormulario,
} from '../../componentes/comunes/FormularioDatos'
import { Button } from '../../componentes/ui/button'

// Solo el formato; un nombre repetido lo rechaza la API junto al campo.
const esquemaTipo = z.object({
  nombre: z.string().min(1, 'Escriba el nombre.').max(50),
  descripcion: z.string().max(255),
  requiere_unidades: z.boolean(),
})

type DatosFormulario = z.infer<typeof esquemaTipo>

const CAMPOS: CampoFormulario<DatosFormulario>[] = [
  { nombre: 'nombre', etiqueta: 'Nombre', tipo: 'texto' },
  { nombre: 'descripcion', etiqueta: 'Descripción', tipo: 'area', ayuda: 'Opcional.' },
  {
    nombre: 'requiere_unidades',
    etiqueta: 'Admite unidades (apartamentos, locales)',
    tipo: 'booleano',
  },
]

interface Props {
  abierto: boolean
  /** El tipo a editar; sin él, el diálogo crea uno nuevo. */
  tipo: TipoPropiedad | null
  alCerrar: () => void
}

/** Crear o editar un tipo de propiedad (spec 014, §5). Solo el administrador. */
export function DialogoTipoPropiedad({ abierto, tipo, alCerrar }: Props) {
  const crear = useCrearTipoPropiedad()
  const actualizar = useActualizarTipoPropiedad()

  const guardar = async (datos: DatosFormulario) => {
    if (tipo) {
      await actualizar.mutateAsync({ id: tipo.id, ...datos })
    } else {
      await crear.mutateAsync(datos)
    }
    alCerrar()
  }

  return (
    <Dialogo
      abierto={abierto}
      titulo={tipo ? `Editar el tipo ${tipo.nombre}` : 'Nuevo tipo de propiedad'}
      alCerrar={alCerrar}
    >
      {/* Se dibuja solo abierto, con key por tipo: los valores iniciales se
          fijan al montar, así cada apertura empieza limpia. */}
      {abierto && (
        <FormularioDatos
          key={tipo?.id ?? 'nuevo'}
          campos={CAMPOS}
          esquema={esquemaTipo}
          valoresIniciales={{
            nombre: tipo?.nombre ?? '',
            descripcion: tipo?.descripcion ?? '',
            requiere_unidades: tipo?.requiere_unidades ?? false,
          }}
          alEnviar={guardar}
          textoEnviar={tipo ? 'Guardar cambios' : 'Crear tipo'}
        />
      )}
      <div className="flex justify-end">
        <Button variant="outline" onClick={alCerrar}>
          Cancelar
        </Button>
      </div>
    </Dialogo>
  )
}
