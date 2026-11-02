import { useNavigate, useParams } from 'react-router'

import { usePropiedad, type Propiedad } from '../../api/catalogo/consultas'
import { useActualizarPropiedad } from '../../api/catalogo/mutaciones'
import { leerErrorApi } from '../../api/errores'
import { FormularioDatos } from '../../componentes/comunes/FormularioDatos'
import {
  aDatosApi,
  esquemaPropiedad,
  useCamposPropiedad,
  type DatosPropiedad,
} from './camposPropiedad'

/** Editar una propiedad (spec 014, regla 9). */
export function EditarPropiedad() {
  const { id } = useParams()
  const consulta = usePropiedad(Number(id))

  if (consulta.isPending) {
    return <p className="text-sm text-slate-500">Cargando la propiedad…</p>
  }
  if (consulta.isError) {
    return (
      <p className="text-sm text-red-700">{leerErrorApi(consulta.error).mensaje}</p>
    )
  }
  // El formulario se dibuja solo con la propiedad cargada: sus valores
  // iniciales se fijan una sola vez, al crearlo.
  return <Formulario propiedad={consulta.data} />
}

function Formulario({ propiedad }: { propiedad: Propiedad }) {
  const navegar = useNavigate()
  const actualizar = useActualizarPropiedad()
  const campos = useCamposPropiedad(propiedad.ciudad.nombre)

  const valoresIniciales: DatosPropiedad = {
    nombre: propiedad.nombre,
    tipo_id: String(propiedad.tipo.id),
    pais: String(propiedad.ciudad.pais.id),
    ciudad_id: String(propiedad.ciudad.id),
    direccion: propiedad.direccion,
    area_m2: propiedad.area_m2,
    area_construida_m2: propiedad.area_construida_m2 ?? '',
    precio_lista: propiedad.precio_lista,
    moneda_id: String(propiedad.moneda.id),
    es_publica: propiedad.es_publica ?? false,
    descripcion: propiedad.descripcion ?? '',
  }

  const guardar = async (datos: DatosPropiedad) => {
    await actualizar.mutateAsync({ id: propiedad.id, ...aDatosApi(datos) })
    navegar(`/catalogo/propiedades/${propiedad.id}`)
  }

  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-2xl font-semibold">
        Editar {propiedad.codigo} · {propiedad.nombre}
      </h1>
      <FormularioDatos
        campos={campos}
        esquema={esquemaPropiedad}
        valoresIniciales={valoresIniciales}
        alEnviar={guardar}
        textoEnviar="Guardar cambios"
      />
    </div>
  )
}
