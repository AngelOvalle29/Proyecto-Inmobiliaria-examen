import { z } from 'zod'

import type { ImagenPropiedad } from '../../api/catalogo/consultas'
import { useActualizarImagen, useSubirImagen } from '../../api/catalogo/mutaciones'
import { Dialogo } from '../../componentes/comunes/Dialogo'
import {
  FormularioDatos,
  type CampoFormulario,
} from '../../componentes/comunes/FormularioDatos'
import { Button } from '../../componentes/ui/button'

/** Lo mismo que acepta la API (spec 019, regla 1). */
const EXTENSIONES = ['.jpg', '.jpeg', '.png']
const TAMANO_MAXIMO = 5 * 1024 * 1024

/**
 * Revisión del navegador antes de subir, como en los documentos (spec 014,
 * regla 5): extensión y tamaño, con el error junto al campo. El contenido lo
 * revisa la API, y su ARCHIVO_NO_PERMITIDO sale arriba del formulario.
 */
const archivo = z
  .instanceof(File)
  .nullable()
  // ': boolean' evita que TypeScript lo tome como guarda de tipo y cambie la salida.
  .refine((elegido): boolean => elegido !== null, 'Elija una foto.')
  .refine(
    (elegido) =>
      !elegido || EXTENSIONES.some((ext) => elegido.name.toLowerCase().endsWith(ext)),
    'Solo se aceptan fotos JPG o PNG.',
  )
  .refine(
    (elegido) => !elegido || elegido.size <= TAMANO_MAXIMO,
    'La foto pesa más de 5 MB.',
  )

const descripcion = z.string().max(200)

const esquemaSubir = z.object({ archivo, descripcion })
const esquemaEditar = z.object({
  descripcion,
  orden: z.string().regex(/^[1-9]\d*$/, 'Escriba un número entero desde 1.'),
})

type DatosSubir = z.infer<typeof esquemaSubir>
type DatosEditar = z.infer<typeof esquemaEditar>

const CAMPO_DESCRIPCION = {
  nombre: 'descripcion',
  etiqueta: 'Descripción',
  tipo: 'texto',
  ayuda: 'Opcional. Por ejemplo, Fachada principal.',
} as const

interface Props {
  propiedad: number
  abierto: boolean
  /** La imagen a editar; sin ella, el diálogo sube una nueva. */
  imagen: ImagenPropiedad | null
  alCerrar: () => void
}

/**
 * Subir una foto o editar su descripción y su orden (spec 019, regla 4). La
 * foto no se reemplaza: una distinta es una imagen nueva.
 */
export function DialogoImagen({ propiedad, abierto, imagen, alCerrar }: Props) {
  return (
    <Dialogo
      abierto={abierto}
      titulo={imagen ? 'Editar imagen' : 'Subir imagen'}
      alCerrar={alCerrar}
    >
      {/* Se dibuja solo abierto, con key por imagen, como DialogoDocumento. */}
      {abierto &&
        (imagen ? (
          <FormularioEditar key={imagen.id} imagen={imagen} alCerrar={alCerrar} />
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
  const subir = useSubirImagen(propiedad)

  const campos: CampoFormulario<DatosSubir>[] = [
    {
      nombre: 'archivo',
      etiqueta: 'Foto',
      tipo: 'archivo',
      aceptar: EXTENSIONES.join(','),
      ayuda: 'JPG o PNG, hasta 5 MB. Hasta 10 por propiedad.',
    },
    CAMPO_DESCRIPCION,
  ]

  const guardar = async (datos: DatosSubir) => {
    if (!datos.archivo) {
      return
    }
    await subir.mutateAsync({ archivo: datos.archivo, descripcion: datos.descripcion })
    alCerrar()
  }

  return (
    <FormularioDatos
      campos={campos}
      esquema={esquemaSubir}
      valoresIniciales={{ archivo: null, descripcion: '' }}
      alEnviar={guardar}
      textoEnviar="Subir imagen"
    />
  )
}

function FormularioEditar({
  imagen,
  alCerrar,
}: {
  imagen: ImagenPropiedad
  alCerrar: () => void
}) {
  const actualizar = useActualizarImagen()

  const campos: CampoFormulario<DatosEditar>[] = [
    CAMPO_DESCRIPCION,
    {
      nombre: 'orden',
      etiqueta: 'Orden',
      tipo: 'numero',
      ayuda: 'La galería se muestra de menor a mayor.',
    },
  ]

  const guardar = async (datos: DatosEditar) => {
    await actualizar.mutateAsync({
      id: imagen.id,
      descripcion: datos.descripcion,
      orden: Number(datos.orden),
    })
    alCerrar()
  }

  return (
    <FormularioDatos
      campos={campos}
      esquema={esquemaEditar}
      valoresIniciales={{
        descripcion: imagen.descripcion ?? '',
        orden: String(imagen.orden ?? 1),
      }}
      alEnviar={guardar}
      textoEnviar="Guardar cambios"
    />
  )
}
