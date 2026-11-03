import { useNavigate, useParams } from 'react-router'
import { z } from 'zod'

import { usePaises } from '../../api/core/consultas'
import { useConstructora, type Constructora } from '../../api/construccion/consultas'
import {
  useCrearConstructora,
  useEditarConstructora,
} from '../../api/construccion/mutaciones'
import { leerErrorApi } from '../../api/errores'
import {
  FormularioDatos,
  type CampoFormulario,
} from '../../componentes/comunes/FormularioDatos'

const esquema = z.object({
  nombre: z.string().trim().min(1, 'Escriba el nombre.').max(200),
  // Una constructora siempre es una empresa: el NIT es obligatorio (spec 006,
  // regla 4). Que no esté repetido en el país lo revisa la API (409).
  nit: z.string().trim().min(1, 'Escriba el NIT.').max(30),
  contacto: z.string().max(150),
  email: z.union([z.literal(''), z.email('Escriba un correo válido.')]),
  telefono: z.string().max(30),
  pais: z.string().min(1, 'Elija el país.'),
  // Opcional, de 1 a 5 (regla 6). Se escribe como texto y se convierte al
  // guardar; vacía significa "sin calificar".
  calificacion: z.union([
    z.literal(''),
    z.string().regex(/^[1-5]$/, 'La calificación va de 1 a 5.'),
  ]),
})

type Datos = z.infer<typeof esquema>

interface PropsFormulario {
  /** La constructora a editar; sin ella, el formulario crea una nueva. */
  constructora?: Constructora
}

/** Formulario de constructora (spec 018, §5). Al editar se cambia todo, también el país. */
function Formulario({ constructora }: PropsFormulario) {
  const navegar = useNavigate()
  const crear = useCrearConstructora()
  const editar = useEditarConstructora()
  const paises = usePaises()
  const editando = constructora !== undefined

  const campos: CampoFormulario<Datos>[] = [
    { nombre: 'nombre', etiqueta: 'Nombre', tipo: 'texto' },
    { nombre: 'nit', etiqueta: 'NIT', tipo: 'texto' },
    {
      nombre: 'contacto',
      etiqueta: 'Persona de contacto',
      tipo: 'texto',
      ayuda: 'Opcional.',
    },
    { nombre: 'email', etiqueta: 'Correo', tipo: 'texto', ayuda: 'Opcional.' },
    { nombre: 'telefono', etiqueta: 'Teléfono', tipo: 'texto', ayuda: 'Opcional.' },
    {
      nombre: 'pais',
      etiqueta: 'País',
      tipo: 'seleccion',
      opciones: (paises.data ?? []).map((pais) => ({
        valor: String(pais.id),
        etiqueta: pais.nombre,
      })),
    },
    {
      nombre: 'calificacion',
      etiqueta: 'Calificación',
      tipo: 'numero',
      ayuda: 'Opcional, de 1 a 5.',
    },
  ]

  /** Del formulario (todo texto) a lo que espera la API. */
  const guardar = async (datos: Datos) => {
    const aEnviar = {
      nombre: datos.nombre,
      nit: datos.nit,
      contacto: datos.contacto,
      email: datos.email,
      telefono: datos.telefono,
      pais: Number(datos.pais),
      calificacion: datos.calificacion ? Number(datos.calificacion) : null,
    }
    if (constructora) {
      await editar.mutateAsync({ id: constructora.id, ...aEnviar })
      navegar('/construccion/constructoras')
      return
    }
    const creada = await crear.mutateAsync(aEnviar)
    navegar(`/construccion/constructoras?buscar=${creada.codigo ?? ''}`)
  }

  return (
    <FormularioDatos
      campos={campos}
      esquema={esquema}
      valoresIniciales={{
        nombre: constructora?.nombre ?? '',
        nit: constructora?.nit ?? '',
        contacto: constructora?.contacto ?? '',
        email: constructora?.email ?? '',
        telefono: constructora?.telefono ?? '',
        pais: constructora ? String(constructora.pais.id) : '',
        calificacion: constructora?.calificacion
          ? String(constructora.calificacion)
          : '',
      }}
      alEnviar={guardar}
      textoEnviar={editando ? 'Guardar cambios' : 'Crear constructora'}
    />
  )
}

export function NuevaConstructora() {
  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-2xl font-semibold">Nueva constructora</h1>
      <Formulario />
    </div>
  )
}

/** Espera a la constructora: FormularioDatos toma sus valores iniciales una sola vez. */
export function EditarConstructora() {
  const { id } = useParams()
  const consulta = useConstructora(Number(id))

  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-2xl font-semibold">
        Editar constructora {consulta.data?.codigo ?? ''}
      </h1>
      {consulta.isPending && <p className="text-sm text-slate-500">Cargando…</p>}
      {consulta.isError && (
        <p role="alert" className="rounded-md bg-red-50 p-3 text-sm text-red-700">
          {leerErrorApi(consulta.error).mensaje}
        </p>
      )}
      {consulta.data && <Formulario constructora={consulta.data} />}
    </div>
  )
}
