import { z } from 'zod'

import {
  ETIQUETAS_TIPO_DOCUMENTO_AGENTE,
  type DocumentoAgente,
  type TipoDocumentoAgente,
} from '../../api/ia/consultas'
import {
  useReemplazarDocumentoAgente,
  useSubirDocumentoAgente,
} from '../../api/ia/mutaciones'
import { usePaises } from '../../api/core/consultas'
import { Dialogo } from '../../componentes/comunes/Dialogo'
import {
  FormularioDatos,
  type CampoFormulario,
} from '../../componentes/comunes/FormularioDatos'
import { Button } from '../../componentes/ui/button'

/** Lo mismo que acepta la API (spec 020, regla 1). */
const TAMANO_MAXIMO = 200 * 1024

/**
 * Revisión del navegador antes de subir: la extensión y el tamaño, junto al
 * campo. Que sea texto UTF-8 lo revisa la API, y su error sale arriba.
 */
const archivo = z
  .instanceof(File)
  .nullable()
  // ': boolean' evita que TypeScript lo tome como guarda de tipo y cambie la salida.
  .refine((elegido): boolean => elegido !== null, 'Elija un archivo.')
  .refine(
    (elegido) => !elegido || elegido.name.toLowerCase().endsWith('.md'),
    'Solo se aceptan archivos Markdown (.md).',
  )
  .refine(
    (elegido) => !elegido || elegido.size <= TAMANO_MAXIMO,
    'El archivo pesa más de 200 KB.',
  )

const esquemaSubir = z.object({
  archivo,
  titulo: z.string().min(1, 'Escriba el título.').max(200),
  tipo: z.string().min(1, 'Elija el tipo.'),
  pais: z.string(),
})
const esquemaReemplazar = z.object({ archivo })

type DatosSubir = z.infer<typeof esquemaSubir>
type DatosReemplazar = z.infer<typeof esquemaReemplazar>

const CAMPO_ARCHIVO = {
  nombre: 'archivo',
  etiqueta: 'Archivo',
  tipo: 'archivo',
  aceptar: '.md',
  ayuda: 'Markdown (.md) de hasta 200 KB. Las secciones van con ##.',
} as const

interface Props {
  abierto: boolean
  /** El documento a reemplazar; sin él, el diálogo sube uno nuevo. */
  documento: DocumentoAgente | null
  alCerrar: () => void
}

/**
 * Subir un documento del agente o reemplazar su archivo (spec 020). La API
 * responde enseguida: la indexación la hace la cola, y la lista muestra su
 * avance.
 */
export function DialogoDocumentoAgente({ abierto, documento, alCerrar }: Props) {
  return (
    <Dialogo
      abierto={abierto}
      titulo={documento ? `Reemplazar ${documento.titulo}` : 'Subir documento'}
      alCerrar={alCerrar}
    >
      {/* Regla 3: el agente es público y envía el texto a Gemini. */}
      <p className="rounded-md bg-amber-50 p-3 text-sm text-amber-800">
        El asistente público responde con este texto y lo envía a Gemini. Suba solo
        documentos de la agencia, sin datos personales de clientes.
      </p>
      {abierto &&
        (documento ? (
          <FormularioReemplazar
            key={documento.id}
            documento={documento}
            alCerrar={alCerrar}
          />
        ) : (
          <FormularioSubir alCerrar={alCerrar} />
        ))}
      <div className="flex justify-end">
        <Button variant="outline" onClick={alCerrar}>
          Cancelar
        </Button>
      </div>
    </Dialogo>
  )
}

function FormularioSubir({ alCerrar }: { alCerrar: () => void }) {
  const subir = useSubirDocumentoAgente()
  const paises = usePaises()

  const campos: CampoFormulario<DatosSubir>[] = [
    CAMPO_ARCHIVO,
    { nombre: 'titulo', etiqueta: 'Título', tipo: 'texto' },
    {
      nombre: 'tipo',
      etiqueta: 'Tipo',
      tipo: 'seleccion',
      opciones: Object.entries(ETIQUETAS_TIPO_DOCUMENTO_AGENTE).map(
        ([valor, etiqueta]) => ({ valor, etiqueta }),
      ),
    },
    {
      nombre: 'pais',
      etiqueta: 'País',
      tipo: 'seleccion',
      ayuda: 'Opcional: déjelo vacío si aplica a todos los países.',
      opciones: (paises.data ?? []).map((pais) => ({
        valor: String(pais.id),
        etiqueta: pais.nombre,
      })),
    },
  ]

  const guardar = async (datos: DatosSubir) => {
    if (!datos.archivo) {
      return
    }
    await subir.mutateAsync({
      archivo: datos.archivo,
      titulo: datos.titulo,
      tipo: datos.tipo as TipoDocumentoAgente,
      pais: datos.pais ? Number(datos.pais) : null,
    })
    alCerrar()
  }

  return (
    <FormularioDatos
      campos={campos}
      esquema={esquemaSubir}
      valoresIniciales={{ archivo: null, titulo: '', tipo: '', pais: '' }}
      alEnviar={guardar}
      textoEnviar="Subir documento"
    />
  )
}

function FormularioReemplazar({
  documento,
  alCerrar,
}: {
  documento: DocumentoAgente
  alCerrar: () => void
}) {
  const reemplazar = useReemplazarDocumentoAgente()

  const guardar = async (datos: DatosReemplazar) => {
    if (!datos.archivo) {
      return
    }
    await reemplazar.mutateAsync({ id: documento.id, archivo: datos.archivo })
    alCerrar()
  }

  return (
    <FormularioDatos
      campos={[CAMPO_ARCHIVO]}
      esquema={esquemaReemplazar}
      valoresIniciales={{ archivo: null }}
      alEnviar={guardar}
      textoEnviar="Reemplazar archivo"
    />
  )
}
