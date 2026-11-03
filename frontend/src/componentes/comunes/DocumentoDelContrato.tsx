import { useState } from 'react'
import { Link } from 'react-router'
import { z } from 'zod'

import { useOpcionesDocumento } from '../../api/catalogo/consultas'
import { useDescargarDocumento } from '../../api/catalogo/mutaciones'
import { leerErrorApi } from '../../api/errores'
import type { components } from '../../api/tipos.generados'
import { Button } from '../ui/button'
import { Dialogo } from './Dialogo'
import { FormularioDatos, type CampoFormulario } from './FormularioDatos'

// propiedad no se muestra: FormularioDatos se la pasa al buscador en valores.
const esquema = z.object({
  propiedad: z.string(),
  documento: z.string().min(1, 'Busque y elija el documento.'),
})

type Datos = z.infer<typeof esquema>

const CAMPOS: CampoFormulario<Datos>[] = [
  {
    nombre: 'documento',
    etiqueta: 'Documento',
    tipo: 'relacion',
    buscar: useOpcionesDocumento,
  },
]

interface Props {
  documento: components['schemas']['DocumentoOficialResumen'] | null
  /** La propiedad del bien; si es una unidad, la de su edificio. */
  propiedad: number
  puedeCambiar: boolean
  /** Llama a la mutación; si falla, FormularioDatos muestra el error. */
  alVincular: (documento: number) => Promise<unknown>
}

/**
 * El documento firmado de un contrato de venta o de arrendamiento (spec 007,
 * reglas 23 y 24; spec 008, reglas 17 y 18). Se puede cambiar, pero no quitar.
 * Va aquí y no en cada página porque las dos lo muestran igual.
 */
export function DocumentoDelContrato({
  documento,
  propiedad,
  puedeCambiar,
  alVincular,
}: Props) {
  const descargar = useDescargarDocumento()
  const [abierto, setAbierto] = useState(false)

  const guardar = async (datos: Datos) => {
    await alVincular(Number(datos.documento))
    setAbierto(false)
  }

  return (
    <div className="flex flex-wrap items-center justify-between gap-2 rounded-2xl border border-ceniza bg-blanco p-4">
      <div>
        <p className="text-xs text-tenue">Documento del contrato</p>
        <p className="text-sm">{documento?.nombre ?? 'Sin documento'}</p>
        {descargar.isError && (
          <p role="alert" className="text-sm text-red-700">
            {leerErrorApi(descargar.error).mensaje}
          </p>
        )}
      </div>
      <div className="flex gap-2">
        {documento && (
          <Button
            variant="outline"
            disabled={descargar.isPending}
            onClick={() => descargar.mutate(documento.id)}
          >
            Descargar
          </Button>
        )}
        {puedeCambiar && (
          <Button variant="outline" onClick={() => setAbierto(true)}>
            {documento ? 'Cambiar' : 'Vincular'}
          </Button>
        )}
      </div>

      <Dialogo
        abierto={abierto}
        titulo={documento ? 'Cambiar el documento' : 'Vincular un documento'}
        alCerrar={() => setAbierto(false)}
      >
        {abierto && (
          <>
            <p className="text-sm text-tenue">
              Se elige entre los documentos de tipo Contrato de la propiedad. Si aún no
              está,{' '}
              <Link
                className="underline"
                to={`/catalogo/propiedades/${propiedad}?pestana=documentos`}
              >
                súbalo en su ficha
              </Link>
              .
            </p>
            <FormularioDatos
              campos={CAMPOS}
              esquema={esquema}
              valoresIniciales={{ propiedad: String(propiedad), documento: '' }}
              alEnviar={guardar}
              textoEnviar="Guardar"
            />
            <Button
              variant="outline"
              className="self-start"
              onClick={() => setAbierto(false)}
            >
              Cancelar
            </Button>
          </>
        )}
      </Dialogo>
    </div>
  )
}
