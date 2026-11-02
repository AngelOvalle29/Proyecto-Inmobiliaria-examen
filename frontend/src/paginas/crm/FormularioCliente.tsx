import { useNavigate, useParams } from 'react-router'
import { z } from 'zod'

import { useBuscarCiudades, usePaises } from '../../api/core/consultas'
import {
  ETIQUETAS_TIPO_CLIENTE,
  useCliente,
  useOpcionesAgente,
  type Cliente,
} from '../../api/crm/consultas'
import { useCrearCliente, useEditarCliente } from '../../api/crm/mutaciones'
import { leerErrorApi } from '../../api/errores'
import {
  FormularioDatos,
  type CampoFormulario,
} from '../../componentes/comunes/FormularioDatos'
import { ROLES } from '../../menu'
import { useSesion } from '../../sesion/useSesion'

/**
 * Los campos de persona y de empresa son opcionales en el objeto y se exigen en
 * superRefine según el tipo: visibleSi oculta un campo, pero Zod lo seguiría
 * validando (spec 012, regla 4). Si fueran obligatorios aquí, una empresa
 * nunca pasaría, porque le faltarían nombre y apellidos.
 */
const esquema = z
  .object({
    tipo: z.enum(['PERSONA', 'EMPRESA'], { message: 'Elija el tipo.' }),
    nombre: z.string().max(100),
    apellidos: z.string().max(100),
    documento_identidad: z.string().max(30),
    razon_social: z.string().max(200),
    nit: z.string().max(30),
    email: z.union([z.literal(''), z.email('Escriba un correo válido.')]),
    telefono: z.string().max(30),
    pais: z.string().min(1, 'Elija el país.'),
    ciudad: z.string(),
    direccion: z.string().max(255),
    agente_asignado: z.string(),
    notas: z.string(),
  })
  .superRefine((datos, contexto) => {
    const obligatorios: [keyof typeof datos, string][] =
      datos.tipo === 'EMPRESA'
        ? [
            ['razon_social', 'Escriba la razón social.'],
            ['nit', 'Escriba el NIT.'],
          ]
        : [
            ['nombre', 'Escriba el nombre.'],
            ['apellidos', 'Escriba los apellidos.'],
            ['documento_identidad', 'Escriba el documento de identidad.'],
          ]
    for (const [campo, mensaje] of obligatorios) {
      if (!datos[campo].trim()) {
        contexto.addIssue({ code: 'custom', path: [campo], message: mensaje })
      }
    }
  })

type Datos = z.infer<typeof esquema>

function useOpcionesCiudad(texto: string, valores: Datos) {
  const pais = valores.pais ? Number(valores.pais) : undefined
  const consulta = useBuscarCiudades(texto, pais)
  return {
    opciones: (consulta.data ?? []).map((ciudad) => ({
      valor: String(ciudad.id),
      etiqueta: ciudad.nombre,
    })),
    cargando: consulta.isFetching,
  }
}

interface PropsFormulario {
  /** El cliente a editar; sin él, el formulario crea uno nuevo. */
  cliente?: Cliente
}

/**
 * Formulario de cliente (spec 012, §5). Al editar no se cambian el tipo ni el
 * agente: el agente se cambia con Reasignar. País y ciudad sí, y la ciudad
 * muestra la actual con su etiqueta inicial (spec 010, regla 15).
 */
function Formulario({ cliente }: PropsFormulario) {
  const navegar = useNavigate()
  const { usuario } = useSesion()
  const crear = useCrearCliente()
  const editar = useEditarCliente()
  const paises = usePaises()
  const editando = cliente !== undefined
  const esPersona = (valores: Datos) => valores.tipo !== 'EMPRESA'
  const esEmpresa = (valores: Datos) => valores.tipo === 'EMPRESA'

  const soloAlCrear: CampoFormulario<Datos>[] = [
    {
      nombre: 'tipo',
      etiqueta: 'Tipo',
      tipo: 'seleccion',
      opciones: Object.entries(ETIQUETAS_TIPO_CLIENTE).map(([valor, etiqueta]) => ({
        valor,
        etiqueta,
      })),
    },
  ]
  const ubicacion: CampoFormulario<Datos>[] = [
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
      nombre: 'ciudad',
      etiqueta: 'Ciudad',
      tipo: 'relacion',
      dependeDe: 'pais',
      marcador: 'Primero elija el país',
      ayuda: 'Opcional.',
      buscar: useOpcionesCiudad,
      etiquetaInicial: cliente?.ciudad?.nombre,
    },
  ]
  // A un agente la API lo asigna a sí mismo (spec 004, regla 12).
  const agente: CampoFormulario<Datos>[] =
    usuario?.rol === ROLES.AGENTE
      ? []
      : [
          {
            nombre: 'agente_asignado',
            etiqueta: 'Agente asignado',
            tipo: 'relacion',
            buscar: useOpcionesAgente,
          },
        ]

  const campos: CampoFormulario<Datos>[] = [
    ...(editando ? [] : soloAlCrear),
    { nombre: 'nombre', etiqueta: 'Nombre', tipo: 'texto', visibleSi: esPersona },
    { nombre: 'apellidos', etiqueta: 'Apellidos', tipo: 'texto', visibleSi: esPersona },
    {
      nombre: 'documento_identidad',
      etiqueta: 'Documento de identidad',
      tipo: 'texto',
      visibleSi: esPersona,
    },
    {
      nombre: 'razon_social',
      etiqueta: 'Razón social',
      tipo: 'texto',
      visibleSi: esEmpresa,
    },
    {
      nombre: 'nit',
      etiqueta: 'NIT',
      tipo: 'texto',
      ayuda: 'Obligatorio para una empresa.',
    },
    { nombre: 'email', etiqueta: 'Correo', tipo: 'texto', ayuda: 'Opcional.' },
    { nombre: 'telefono', etiqueta: 'Teléfono', tipo: 'texto', ayuda: 'Opcional.' },
    ...ubicacion,
    { nombre: 'direccion', etiqueta: 'Dirección', tipo: 'texto', ayuda: 'Opcional.' },
    ...(editando ? [] : agente),
    { nombre: 'notas', etiqueta: 'Notas', tipo: 'area', ayuda: 'Opcional.' },
  ]

  /** Del formulario (todo texto) a lo que espera la API. */
  const guardar = async (datos: Datos) => {
    const comunes = {
      nit: datos.nit,
      email: datos.email,
      telefono: datos.telefono,
      pais: Number(datos.pais),
      ciudad: datos.ciudad ? Number(datos.ciudad) : null,
      direccion: datos.direccion,
      notas: datos.notas,
    }
    const propios =
      datos.tipo === 'EMPRESA'
        ? { razon_social: datos.razon_social }
        : {
            nombre: datos.nombre,
            apellidos: datos.apellidos,
            documento_identidad: datos.documento_identidad,
          }

    if (cliente) {
      await editar.mutateAsync({ id: cliente.id, ...comunes, ...propios })
      navegar('/crm/clientes')
      return
    }
    const creado = await crear.mutateAsync({
      ...comunes,
      ...propios,
      tipo: datos.tipo,
      agente_asignado: datos.agente_asignado
        ? Number(datos.agente_asignado)
        : undefined,
    })
    navegar(`/crm/clientes?buscar=${creado.codigo ?? ''}`)
  }

  return (
    <FormularioDatos
      campos={campos}
      esquema={esquema}
      valoresIniciales={{
        tipo: cliente?.tipo ?? 'PERSONA',
        nombre: cliente?.nombre ?? '',
        apellidos: cliente?.apellidos ?? '',
        documento_identidad: cliente?.documento_identidad ?? '',
        razon_social: cliente?.razon_social ?? '',
        nit: cliente?.nit ?? '',
        email: cliente?.email ?? '',
        telefono: cliente?.telefono ?? '',
        pais: cliente ? String(cliente.pais.id) : '',
        ciudad: cliente?.ciudad ? String(cliente.ciudad.id) : '',
        direccion: cliente?.direccion ?? '',
        agente_asignado: '',
        notas: cliente?.notas ?? '',
      }}
      alEnviar={guardar}
      textoEnviar={editando ? 'Guardar cambios' : 'Crear cliente'}
    />
  )
}

export function NuevoCliente() {
  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-2xl font-semibold">Nuevo cliente</h1>
      <Formulario />
    </div>
  )
}

/** Espera al cliente: FormularioDatos toma sus valores iniciales una sola vez. */
export function EditarCliente() {
  const { id } = useParams()
  const consulta = useCliente(Number(id))

  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-2xl font-semibold">
        Editar cliente {consulta.data?.codigo ?? ''}
      </h1>
      {consulta.isPending && <p className="text-sm text-slate-500">Cargando…</p>}
      {consulta.isError && (
        <p role="alert" className="rounded-md bg-red-50 p-3 text-sm text-red-700">
          {leerErrorApi(consulta.error).mensaje}
        </p>
      )}
      {consulta.data && <Formulario cliente={consulta.data} />}
    </div>
  )
}
