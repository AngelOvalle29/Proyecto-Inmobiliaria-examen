import { useNavigate, useParams } from 'react-router'
import { z } from 'zod'

import {
  ETIQUETAS_TIPO_PROVEEDOR,
  useProveedor,
  type Proveedor,
} from '../../api/compras/consultas'
import { useCrearProveedor, useEditarProveedor } from '../../api/compras/mutaciones'
import { useBuscarCiudades, usePaises } from '../../api/core/consultas'
import { leerErrorApi } from '../../api/errores'
import {
  FormularioDatos,
  type CampoFormulario,
} from '../../componentes/comunes/FormularioDatos'

/**
 * El NIT es opcional en el objeto y se exige en superRefine según el tipo,
 * como en FormularioCliente (spec 012, regla 4). Así el aviso sale junto al
 * campo antes de enviar. La regla de verdad sigue siendo la de la API: si el
 * NIT llega vacío para un banco, responde 400 NIT_OBLIGATORIO, que se muestra
 * arriba del formulario porque es un error de dominio (spec 014, regla 5).
 */
const esquema = z
  .object({
    tipo: z.enum(
      ['PROPIETARIO_PARTICULAR', 'INMOBILIARIA', 'BANCO', 'GOBIERNO', 'OTRO'],
      { message: 'Elija el tipo.' },
    ),
    nombre: z.string().trim().min(1, 'Escriba el nombre.').max(200),
    nit: z.string().max(30),
    email: z.union([z.literal(''), z.email('Escriba un correo válido.')]),
    telefono: z.string().max(30),
    pais: z.string().min(1, 'Elija el país.'),
    ciudad: z.string(),
    direccion: z.string().max(255),
  })
  .superRefine((datos, contexto) => {
    // Spec 006, regla 2: solo el propietario particular puede omitir el NIT.
    if (datos.tipo !== 'PROPIETARIO_PARTICULAR' && !datos.nit.trim()) {
      contexto.addIssue({
        code: 'custom',
        path: ['nit'],
        message: 'El NIT es obligatorio para este tipo de proveedor.',
      })
    }
  })

type Datos = z.infer<typeof esquema>

/** Ciudades del país elegido, para CampoRelacion (spec 006, regla 7). */
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
  /** El proveedor a editar; sin él, el formulario crea uno nuevo. */
  proveedor?: Proveedor
}

/**
 * Formulario de proveedor (spec 018, §5). Al editar se puede cambiar todo,
 * también el tipo: la API revisa las reglas sobre el resultado final. La
 * ciudad muestra la actual con etiquetaInicial (spec 010, regla 15) y se vacía
 * al cambiar el país (dependeDe).
 */
function Formulario({ proveedor }: PropsFormulario) {
  const navegar = useNavigate()
  const crear = useCrearProveedor()
  const editar = useEditarProveedor()
  const paises = usePaises()
  const editando = proveedor !== undefined

  const campos: CampoFormulario<Datos>[] = [
    {
      nombre: 'tipo',
      etiqueta: 'Tipo',
      tipo: 'seleccion',
      opciones: Object.entries(ETIQUETAS_TIPO_PROVEEDOR).map(([valor, etiqueta]) => ({
        valor,
        etiqueta,
      })),
    },
    { nombre: 'nombre', etiqueta: 'Nombre', tipo: 'texto' },
    {
      nombre: 'nit',
      etiqueta: 'NIT',
      tipo: 'texto',
      ayuda: 'Opcional solo para un propietario particular.',
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
      nombre: 'ciudad',
      etiqueta: 'Ciudad',
      tipo: 'relacion',
      dependeDe: 'pais',
      marcador: 'Primero elija el país',
      ayuda: 'Opcional.',
      buscar: useOpcionesCiudad,
      etiquetaInicial: proveedor?.ciudad?.nombre,
    },
    { nombre: 'direccion', etiqueta: 'Dirección', tipo: 'texto', ayuda: 'Opcional.' },
  ]

  /** Del formulario (todo texto) a lo que espera la API. */
  const guardar = async (datos: Datos) => {
    const aEnviar = {
      tipo: datos.tipo,
      nombre: datos.nombre,
      nit: datos.nit,
      email: datos.email,
      telefono: datos.telefono,
      pais: Number(datos.pais),
      // null borra la ciudad: es opcional (spec 006, regla 7).
      ciudad: datos.ciudad ? Number(datos.ciudad) : null,
      direccion: datos.direccion,
    }
    if (proveedor) {
      await editar.mutateAsync({ id: proveedor.id, ...aEnviar })
      navegar('/compras/proveedores')
      return
    }
    const creado = await crear.mutateAsync(aEnviar)
    // Vuelve a la lista con el proveedor nuevo a la vista.
    navegar(`/compras/proveedores?buscar=${creado.codigo ?? ''}`)
  }

  return (
    <FormularioDatos
      campos={campos}
      esquema={esquema}
      valoresIniciales={{
        tipo: proveedor?.tipo ?? 'PROPIETARIO_PARTICULAR',
        nombre: proveedor?.nombre ?? '',
        nit: proveedor?.nit ?? '',
        email: proveedor?.email ?? '',
        telefono: proveedor?.telefono ?? '',
        pais: proveedor ? String(proveedor.pais.id) : '',
        ciudad: proveedor?.ciudad ? String(proveedor.ciudad.id) : '',
        direccion: proveedor?.direccion ?? '',
      }}
      alEnviar={guardar}
      textoEnviar={editando ? 'Guardar cambios' : 'Crear proveedor'}
    />
  )
}

export function NuevoProveedor() {
  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-2xl font-semibold">Nuevo proveedor</h1>
      <Formulario />
    </div>
  )
}

/** Espera al proveedor: FormularioDatos toma sus valores iniciales una sola vez. */
export function EditarProveedor() {
  const { id } = useParams()
  const consulta = useProveedor(Number(id))

  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-2xl font-semibold">
        Editar proveedor {consulta.data?.codigo ?? ''}
      </h1>
      {consulta.isPending && <p className="text-sm text-slate-500">Cargando…</p>}
      {consulta.isError && (
        <p role="alert" className="rounded-md bg-red-50 p-3 text-sm text-red-700">
          {leerErrorApi(consulta.error).mensaje}
        </p>
      )}
      {consulta.data && <Formulario proveedor={consulta.data} />}
    </div>
  )
}
