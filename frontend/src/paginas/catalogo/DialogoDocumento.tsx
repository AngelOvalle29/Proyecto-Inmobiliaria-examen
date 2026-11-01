import { z } from 'zod'

import {
  ETIQUETAS_TIPO_DOCUMENTO,
  type DocumentoOficial,
  type TipoDocumento,
} from '../../api/catalogo/consultas'
import {
  useActualizarDocumento,
  useSubirDocumento,
  type DatosDocumento,
} from '../../api/catalogo/mutaciones'
import { Dialogo } from '../../componentes/comunes/Dialogo'
import {
  FormularioDatos,
  type CampoFormulario,
} from '../../componentes/comunes/FormularioDatos'
import { Button } from '../../componentes/ui/button'

/** Lo mismo que acepta la API (spec 011, regla 6). */
const EXTENSIONES = ['.pdf', '.jpg', '.jpeg', '.png']
const TAMANO_MAXIMO = 10 * 1024 * 1024

/**
 * Revisión del navegador antes de subir (spec 014, regla 5): la extensión y
 * el tamaño. Su error sale junto al campo. No mira el contenido: eso lo hace
 * la API, y su error (ARCHIVO_NO_PERMITIDO) sale arriba del formulario.
 */
// El valor es null mientras no se elige: FormularioDatos pide que el esquema
// entregue el mismo tipo que recibe, así que null se rechaza con un refine.
const archivo = z
  .instanceof(File)
  .nullable()
  // ': boolean' evita que TypeScript lo tome como guarda de tipo y cambie la salida.
  .refine((elegido): boolean => elegido !== null, 'Elija un archivo.')
  .refine(
    (elegido) =>
      !elegido || EXTENSIONES.some((ext) => elegido.name.toLowerCase().endsWith(ext)),
    'Solo se aceptan archivos PDF, JPG o PNG.',
  )
  .refine(
    (elegido) => !elegido || elegido.size <= TAMANO_MAXIMO,
    'El archivo pesa más de 10 MB.',
  )

// Los datos que se pueden editar después; la fecha de vencimiento es opcional.
const datosDocumento = {
  nombre: z.string().min(1, 'Escriba el nombre.').max(200),
  fecha_emision: z.string().min(1, 'Elija la fecha de emisión.'),
  fecha_vencimiento: z.string(),
  emisor: z.string().min(1, 'Escriba quién lo emitió.').max(150),
}

const esquemaSubir = z.object({
  ...datosDocumento,
  archivo,
  tipo: z.string().min(1, 'Elija el tipo.'),
})
const esquemaEditar = z.object(datosDocumento)

type DatosSubir = z.infer<typeof esquemaSubir>
type DatosEditar = z.infer<typeof esquemaEditar>

const CAMPOS_DATOS: CampoFormulario<DatosEditar>[] = [
  {
    nombre: 'nombre',
    etiqueta: 'Nombre',
    tipo: 'texto',
    ayuda: 'Por ejemplo, Escritura 1520.',
  },
  {
    nombre: 'emisor',
    etiqueta: 'Emisor',
    tipo: 'texto',
    ayuda: 'Notaría, municipalidad…',
  },
  { nombre: 'fecha_emision', etiqueta: 'Fecha de emisión', tipo: 'fecha' },
  {
    nombre: 'fecha_vencimiento',
    etiqueta: 'Fecha de vencimiento',
    tipo: 'fecha',
    ayuda: 'Opcional: déjela vacía si el documento no vence.',
  },
]

/** Del formulario a la API: un vencimiento vacío se guarda como null. */
function aDatosApi(datos: DatosEditar): DatosDocumento {
  return {
    nombre: datos.nombre,
    emisor: datos.emisor,
    fecha_emision: datos.fecha_emision,
    fecha_vencimiento: datos.fecha_vencimiento || null,
  }
}

interface Props {
  propiedad: number
  abierto: boolean
  /** El documento a editar; sin él, el diálogo sube uno nuevo. */
  documento: DocumentoOficial | null
  alCerrar: () => void
}

/**
 * Subir un documento o editar sus datos (spec 014, regla 4). Al editar no se
 * cambia el archivo ni el tipo (spec 011, regla 7): para eso se desactiva y se
 * sube otro.
 */
export function DialogoDocumento({ propiedad, abierto, documento, alCerrar }: Props) {
  return (
    <Dialogo
      abierto={abierto}
      titulo={documento ? `Editar ${documento.nombre}` : 'Subir documento'}
      alCerrar={alCerrar}
    >
      {/* Se dibuja solo abierto, con key por documento: los valores iniciales
          se fijan al montar, así cada apertura empieza limpia. */}
      {abierto &&
        (documento ? (
          <FormularioEditar
            key={documento.id}
            documento={documento}
            alCerrar={alCerrar}
          />
        ) : (
          <FormularioSubir propiedad={propiedad} alCerrar={alCerrar} />
        ))}
      <div className="flex justify-end">
        <Button variant="outline" onClick={alCerrar}>
          Cancelar
        </Button>
      </div>
    </Dialogo>
  )
}

function FormularioSubir({
  propiedad,
  alCerrar,
}: {
  propiedad: number
  alCerrar: () => void
}) {
  const subir = useSubirDocumento(propiedad)

  const campos: CampoFormulario<DatosSubir>[] = [
    {
      nombre: 'archivo',
      etiqueta: 'Archivo',
      tipo: 'archivo',
      aceptar: EXTENSIONES.join(','),
      ayuda: 'PDF, JPG o PNG, hasta 10 MB.',
    },
    {
      nombre: 'tipo',
      etiqueta: 'Tipo',
      tipo: 'seleccion',
      opciones: Object.entries(ETIQUETAS_TIPO_DOCUMENTO).map(([valor, etiqueta]) => ({
        valor,
        etiqueta,
      })),
    },
    // Los campos de datos son los mismos que al editar.
    ...(CAMPOS_DATOS as CampoFormulario<DatosSubir>[]),
  ]

  const guardar = async (datos: DatosSubir) => {
    if (!datos.archivo) {
      return
    }
    await subir.mutateAsync({
      ...aDatosApi(datos),
      archivo: datos.archivo,
      tipo: datos.tipo as TipoDocumento,
    })
    alCerrar()
  }

  return (
    <FormularioDatos
      campos={campos}
      esquema={esquemaSubir}
      valoresIniciales={{
        archivo: null,
        tipo: '',
        nombre: '',
        emisor: '',
        fecha_emision: '',
        fecha_vencimiento: '',
      }}
      alEnviar={guardar}
      textoEnviar="Subir documento"
    />
  )
}

function FormularioEditar({
  documento,
  alCerrar,
}: {
  documento: DocumentoOficial
  alCerrar: () => void
}) {
  const actualizar = useActualizarDocumento()

  const guardar = async (datos: DatosEditar) => {
    await actualizar.mutateAsync({ id: documento.id, ...aDatosApi(datos) })
    alCerrar()
  }

  return (
    <FormularioDatos
      campos={CAMPOS_DATOS}
      esquema={esquemaEditar}
      valoresIniciales={{
        nombre: documento.nombre,
        emisor: documento.emisor,
        fecha_emision: documento.fecha_emision,
        fecha_vencimiento: documento.fecha_vencimiento ?? '',
      }}
      alEnviar={guardar}
      textoEnviar="Guardar cambios"
    />
  )
}
