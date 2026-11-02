import { useNavigate } from 'react-router'

import { useCrearPropiedad } from '../../api/catalogo/mutaciones'
import { FormularioDatos } from '../../componentes/comunes/FormularioDatos'
import {
  aDatosApi,
  esquemaPropiedad,
  PROPIEDAD_VACIA,
  useCamposPropiedad,
  type DatosPropiedad,
} from './camposPropiedad'

/** Ejemplo de formulario (spec 010, §5): crear una propiedad. */
export function NuevaPropiedad() {
  const navegar = useNavigate()
  const crear = useCrearPropiedad()
  const campos = useCamposPropiedad()

  const guardar = async (datos: DatosPropiedad) => {
    const creada = await crear.mutateAsync(aDatosApi(datos))
    // Se abre su ficha, ya con el código que le asignó el backend.
    navegar(`/catalogo/propiedades/${creada.id}`)
  }

  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-2xl font-semibold">Nueva propiedad</h1>
      <FormularioDatos
        campos={campos}
        esquema={esquemaPropiedad}
        valoresIniciales={PROPIEDAD_VACIA}
        alEnviar={guardar}
        textoEnviar="Crear propiedad"
      />
    </div>
  )
}
