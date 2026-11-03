import { useState } from 'react'

import { useImagenes, type ImagenPropiedad } from '../../api/catalogo/consultas'
import { useDesactivarImagen, useMarcarPortada } from '../../api/catalogo/mutaciones'
import { leerErrorApi } from '../../api/errores'
import { Dialogo } from '../../componentes/comunes/Dialogo'
import { Button } from '../../componentes/ui/button'
import { DialogoImagen } from './DialogoImagen'

/** Spec 019, regla 2. La API lo vuelve a revisar con LIMITE_IMAGENES. */
const MAXIMO_IMAGENES = 10

interface Props {
  propiedad: number
  puedeEscribir: boolean
}

/**
 * Pestaña Imágenes (spec 019): la galería en su orden, con la portada
 * marcada. Todos la ven; subir, editar, elegir la portada y desactivar solo
 * quien escribe en el catálogo (regla 9).
 */
export function PestanaImagenes({ propiedad, puedeEscribir }: Props) {
  const consulta = useImagenes(propiedad)
  const marcar = useMarcarPortada()
  const desactivar = useDesactivarImagen()
  // El diálogo: cerrado, una imagen nueva (null) o una a editar.
  const [editando, setEditando] = useState<ImagenPropiedad | null | undefined>(
    undefined,
  )
  const [porDesactivar, setPorDesactivar] = useState<ImagenPropiedad | null>(null)
  const [error, setError] = useState<string | null>(null)

  const imagenes = consulta.data?.results ?? []
  const lleno = imagenes.length >= MAXIMO_IMAGENES
  // TanStack Query entrega error = null cuando no hubo error.
  const mensajeError =
    error ?? (consulta.error ? leerErrorApi(consulta.error).mensaje : null)

  // Un 409 o un 403 se muestra arriba de la galería, como en TablaDatos.
  const ejecutar = async (accion: () => Promise<unknown>) => {
    setError(null)
    try {
      await accion()
    } catch (excepcion) {
      setError(leerErrorApi(excepcion).mensaje)
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-tenue">
          {imagenes.length} de {MAXIMO_IMAGENES} imágenes
        </p>
        {puedeEscribir && (
          <Button onClick={() => setEditando(null)} disabled={lleno}>
            Subir imagen
          </Button>
        )}
      </div>

      {mensajeError && (
        <p role="alert" className="rounded-md bg-red-50 p-3 text-sm text-red-700">
          {mensajeError}
        </p>
      )}

      {consulta.isPending && <p className="text-sm text-tenue">Cargando…</p>}
      {!consulta.isPending && imagenes.length === 0 && (
        <p className="text-sm text-tenue">Esta propiedad todavía no tiene imágenes.</p>
      )}

      <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {imagenes.map((imagen) => (
          <li
            key={imagen.id}
            className="flex flex-col overflow-hidden rounded-2xl border border-ceniza bg-blanco"
          >
            <div className="relative aspect-[4/3] bg-niebla">
              {/* El navegador reduce la foto: no hay miniaturas en el
                  servidor (spec 019, §10). */}
              <img
                src={imagen.url}
                alt={imagen.descripcion || imagen.nombre_original}
                loading="lazy"
                className="h-full w-full object-cover"
              />
              {imagen.es_portada && (
                <span className="absolute top-3 left-3 rounded-full bg-oxido px-3 py-1 font-mono text-[11px] tracking-etiqueta text-crema uppercase">
                  Portada
                </span>
              )}
            </div>
            <div className="flex flex-1 flex-col gap-3 p-4">
              <div>
                <p className="text-sm">{imagen.descripcion || 'Sin descripción'}</p>
                <p className="font-mono text-[11px] tracking-etiqueta text-tenue uppercase">
                  Orden {imagen.orden}
                </p>
              </div>
              {puedeEscribir && (
                <div className="mt-auto flex flex-wrap gap-2">
                  {!imagen.es_portada && (
                    <Button
                      size="sm"
                      variant="outline"
                      disabled={marcar.isPending}
                      onClick={() => void ejecutar(() => marcar.mutateAsync(imagen.id))}
                    >
                      Marcar portada
                    </Button>
                  )}
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => setEditando(imagen)}
                  >
                    Editar
                  </Button>
                  <Button
                    size="sm"
                    variant="destructive"
                    onClick={() => setPorDesactivar(imagen)}
                  >
                    Desactivar
                  </Button>
                </div>
              )}
            </div>
          </li>
        ))}
      </ul>

      <DialogoImagen
        propiedad={propiedad}
        abierto={editando !== undefined}
        imagen={editando ?? null}
        alCerrar={() => setEditando(undefined)}
      />

      <Dialogo
        abierto={porDesactivar !== null}
        titulo="Confirmar"
        alCerrar={() => setPorDesactivar(null)}
      >
        <p className="text-sm">
          ¿Desactivar esta imagen? Dejará de verse en la galería.
          {porDesactivar?.es_portada &&
            ' Es la portada: la siguiente de la galería pasará a serlo.'}
        </p>
        <div className="flex justify-end gap-2">
          <Button
            variant="outline"
            onClick={() => setPorDesactivar(null)}
            disabled={desactivar.isPending}
          >
            Cancelar
          </Button>
          <Button
            variant="destructive"
            disabled={desactivar.isPending}
            onClick={() => {
              const imagen = porDesactivar
              if (imagen) {
                void ejecutar(() => desactivar.mutateAsync(imagen.id)).then(() =>
                  setPorDesactivar(null),
                )
              }
            }}
          >
            {desactivar.isPending ? 'Procesando…' : 'Confirmar'}
          </Button>
        </div>
      </Dialogo>
    </div>
  )
}
