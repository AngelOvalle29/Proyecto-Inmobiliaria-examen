import { useNavigate, useParams } from 'react-router'
import { z } from 'zod'

import { usePaises } from '../../api/core/consultas'
import { leerErrorApi } from '../../api/errores'
import {
  ETIQUETAS_ROL,
  useUsuario,
  type NombreRol,
  type UsuarioDetalle,
} from '../../api/usuarios/consultas'
import { useCrearUsuario, useEditarUsuario } from '../../api/usuarios/mutaciones'
import {
  FormularioDatos,
  type CampoFormulario,
} from '../../componentes/comunes/FormularioDatos'

const datosCuenta = {
  nombre_completo: z.string().min(1, 'Escriba el nombre.').max(150),
  rol: z.string().min(1, 'Elija el rol.'),
  pais: z.string(),
  telefono: z.string().max(30),
}

const esquemaEditar = z.object(datosCuenta)
const esquemaNuevo = z
  .object({
    email: z.email('Escriba un correo válido.'),
    ...datosCuenta,
    password: z.string().min(10, 'Al menos 10 caracteres.'),
    confirmar: z.string(),
  })
  .refine((datos) => datos.password === datos.confirmar, {
    message: 'Las dos contraseñas no coinciden.',
    path: ['confirmar'],
  })

type DatosEditar = z.infer<typeof esquemaEditar>
type DatosNuevo = z.infer<typeof esquemaNuevo>

const OPCIONES_ROL = Object.entries(ETIQUETAS_ROL).map(([valor, etiqueta]) => ({
  valor,
  etiqueta,
}))

/** Los campos que comparten crear y editar: nombre, rol, país y teléfono. */
function useCamposCuenta(): CampoFormulario<DatosEditar>[] {
  const paises = usePaises()
  return [
    { nombre: 'nombre_completo', etiqueta: 'Nombre completo', tipo: 'texto' },
    {
      nombre: 'rol',
      etiqueta: 'Rol',
      tipo: 'seleccion',
      opciones: OPCIONES_ROL,
      ayuda: 'Define qué pantallas ve y qué puede hacer.',
    },
    {
      nombre: 'pais',
      etiqueta: 'País',
      tipo: 'seleccion',
      opciones: (paises.data ?? []).map((pais) => ({
        valor: String(pais.id),
        etiqueta: pais.nombre,
      })),
      ayuda: 'Opcional.',
    },
    { nombre: 'telefono', etiqueta: 'Teléfono', tipo: 'texto', ayuda: 'Opcional.' },
  ]
}

/** Del formulario a la API: un país vacío se guarda como null. */
function aDatosApi(datos: DatosEditar) {
  return {
    nombre_completo: datos.nombre_completo,
    rol: datos.rol as NombreRol,
    pais_id: datos.pais ? Number(datos.pais) : null,
    telefono: datos.telefono,
  }
}

/** Nueva cuenta (spec 026). La contraseña inicial la escribe el administrador. */
export function NuevoUsuario() {
  const navegar = useNavigate()
  const crear = useCrearUsuario()
  const camposCuenta = useCamposCuenta()

  const campos: CampoFormulario<DatosNuevo>[] = [
    {
      nombre: 'email',
      etiqueta: 'Correo',
      tipo: 'texto',
      ayuda: 'Es el usuario para iniciar sesión. No se puede cambiar después.',
    },
    ...(camposCuenta as CampoFormulario<DatosNuevo>[]),
    {
      nombre: 'password',
      etiqueta: 'Contraseña inicial',
      tipo: 'contrasena',
      ayuda: 'Al menos 10 caracteres. Comuníquela por un medio privado.',
    },
    { nombre: 'confirmar', etiqueta: 'Repita la contraseña', tipo: 'contrasena' },
  ]

  const guardar = async (datos: DatosNuevo) => {
    await crear.mutateAsync({
      ...aDatosApi(datos),
      email: datos.email,
      password: datos.password,
    })
    navegar(`/usuarios?buscar=${encodeURIComponent(datos.email)}`)
  }

  return (
    <div className="flex max-w-2xl flex-col gap-4">
      <h1 className="font-editorial text-4xl leading-none">Nuevo usuario</h1>
      <FormularioDatos
        campos={campos}
        esquema={esquemaNuevo}
        valoresIniciales={{
          email: '',
          nombre_completo: '',
          rol: '',
          pais: '',
          telefono: '',
          password: '',
          confirmar: '',
        }}
        alEnviar={guardar}
        textoEnviar="Crear usuario"
      />
    </div>
  )
}

/** Editar nombre, rol, país y teléfono de una cuenta (spec 026). */
export function EditarUsuario() {
  const { id } = useParams()
  const consulta = useUsuario(Number(id))

  if (consulta.isPending) {
    return <p className="text-sm text-tenue">Cargando…</p>
  }
  if (consulta.isError) {
    return (
      <p role="alert" className="rounded-md bg-red-50 p-3 text-sm text-red-700">
        {leerErrorApi(consulta.error).mensaje}
      </p>
    )
  }
  return <FormularioEditar usuario={consulta.data} />
}

function FormularioEditar({ usuario }: { usuario: UsuarioDetalle }) {
  const navegar = useNavigate()
  const editar = useEditarUsuario()
  const campos = useCamposCuenta()

  const guardar = async (datos: DatosEditar) => {
    await editar.mutateAsync({ id: usuario.id, ...aDatosApi(datos) })
    navegar('/usuarios')
  }

  return (
    <div className="flex max-w-2xl flex-col gap-4">
      <div>
        <h1 className="font-editorial text-4xl leading-none">Editar usuario</h1>
        <p className="text-sm text-tenue">
          {usuario.email} · {usuario.activo ? 'Activo' : 'Desactivado'}
        </p>
      </div>
      <FormularioDatos
        campos={campos}
        esquema={esquemaEditar}
        valoresIniciales={{
          nombre_completo: usuario.nombre_completo,
          rol: usuario.rol,
          pais: usuario.pais ? String(usuario.pais.id) : '',
          telefono: usuario.telefono ?? '',
        }}
        alEnviar={guardar}
        textoEnviar="Guardar cambios"
      />
    </div>
  )
}
