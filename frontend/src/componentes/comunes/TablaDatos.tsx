import {
  flexRender,
  getCoreRowModel,
  useReactTable,
  type ColumnDef,
} from '@tanstack/react-table'
import { useState } from 'react'

import { leerErrorApi } from '../../api/errores'
import { totalPaginas } from '../../api/paginacion'
import { Button } from '../ui/button'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '../ui/table'
import { Dialogo } from './Dialogo'

/** Una acción por fila: aprobar, pagar, desactivar… (spec 010, regla 13). */
export interface AccionFila<T> {
  etiqueta: string
  /** Si la acción no se ofrece en esa fila (por ejemplo, ya está aprobada). */
  oculta?: (fila: T) => boolean
  /**
   * Pregunta de confirmación. Las acciones que no se pueden deshacer la llevan:
   * la tabla la muestra antes de ejecutar.
   */
  confirmacion?: (fila: T) => string
  variante?: 'outline' | 'destructive'
  /** Lo que hace: normalmente, llamar a una mutación con mutateAsync. */
  ejecutar: (fila: T) => Promise<unknown> | void
}

/** Paginación contra el servidor (spec 010, regla 7). */
export interface Paginacion {
  /** Página actual, desde 1. */
  pagina: number
  /** Total de registros, el `count` de la respuesta de la API. */
  total: number
  alCambiarPagina: (pagina: number) => void
}

interface Props<T> {
  // ColumnDef<T, any> es como TanStack Table tipa columnas con valores de
  // distinto tipo en la misma tabla.
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  columnas: ColumnDef<T, any>[]
  datos: T[] | undefined
  cargando?: boolean
  error?: unknown
  /** Sin paginación, muestra la lista tal como llega (spec 010, regla 14). */
  paginacion?: Paginacion
  acciones?: AccionFila<T>[]
  mensajeVacio?: string
}

/**
 * Tabla genérica de todas las listas del sistema (docs/frontend.md §3). Recibe
 * las columnas y los datos de un hook de consulta; no pide nada a la API por
 * su cuenta.
 */
export function TablaDatos<T>({
  columnas,
  datos,
  cargando = false,
  error,
  paginacion,
  acciones = [],
  mensajeVacio = 'No hay registros.',
}: Props<T>) {
  const [pendiente, setPendiente] = useState<{ accion: AccionFila<T>; fila: T } | null>(
    null,
  )
  const [errorAccion, setErrorAccion] = useState<string | null>(null)
  const [ejecutando, setEjecutando] = useState(false)

  // oxlint avisa que TanStack Table no se lleva con la memorización automática
  // del React Compiler. Este proyecto no usa el React Compiler (vite.config.ts),
  // así que no aplica.
  // oxlint-disable-next-line react/incompatible-library
  const tabla = useReactTable({
    data: datos ?? [],
    columns: columnas,
    getCoreRowModel: getCoreRowModel(),
    // La API ya entrega la página pedida: la tabla no pagina por su cuenta.
    manualPagination: true,
  })

  const ejecutar = async (accion: AccionFila<T>, fila: T) => {
    setErrorAccion(null)
    setEjecutando(true)
    try {
      await accion.ejecutar(fila)
      setPendiente(null)
    } catch (excepcion) {
      // Un 409 o un 403 se muestra arriba de la tabla con el mensaje de la API.
      setErrorAccion(leerErrorApi(excepcion).mensaje)
      setPendiente(null)
    } finally {
      setEjecutando(false)
    }
  }

  const alElegir = (accion: AccionFila<T>, fila: T) => {
    if (accion.confirmacion) {
      setPendiente({ accion, fila })
    } else {
      void ejecutar(accion, fila)
    }
  }

  const columnasVisibles = columnas.length + (acciones.length > 0 ? 1 : 0)
  const filas = tabla.getRowModel().rows
  // TanStack Query entrega error = null cuando no hubo error.
  const mensajeError = errorAccion ?? (error ? leerErrorApi(error).mensaje : null)

  return (
    <div className="flex flex-col gap-3">
      {mensajeError && (
        <p role="alert" className="rounded-md bg-red-50 p-3 text-sm text-red-700">
          {mensajeError}
        </p>
      )}

      <div className="rounded-lg border border-slate-200 bg-white">
        <Table>
          <TableHeader>
            {tabla.getHeaderGroups().map((grupo) => (
              <TableRow key={grupo.id}>
                {grupo.headers.map((encabezado) => (
                  <TableHead key={encabezado.id}>
                    {flexRender(
                      encabezado.column.columnDef.header,
                      encabezado.getContext(),
                    )}
                  </TableHead>
                ))}
                {acciones.length > 0 && (
                  <TableHead className="text-right">Acciones</TableHead>
                )}
              </TableRow>
            ))}
          </TableHeader>
          <TableBody>
            {filas.map((fila) => (
              <TableRow key={fila.id}>
                {fila.getVisibleCells().map((celda) => (
                  <TableCell key={celda.id}>
                    {flexRender(celda.column.columnDef.cell, celda.getContext())}
                  </TableCell>
                ))}
                {acciones.length > 0 && (
                  <TableCell className="text-right">
                    <div className="flex justify-end gap-2">
                      {acciones
                        .filter((accion) => !accion.oculta?.(fila.original))
                        .map((accion) => (
                          <Button
                            key={accion.etiqueta}
                            size="sm"
                            variant={accion.variante ?? 'outline'}
                            disabled={ejecutando}
                            onClick={() => alElegir(accion, fila.original)}
                          >
                            {accion.etiqueta}
                          </Button>
                        ))}
                    </div>
                  </TableCell>
                )}
              </TableRow>
            ))}
            {filas.length === 0 && (
              <TableRow>
                <TableCell
                  colSpan={columnasVisibles}
                  className="py-8 text-center text-slate-500"
                >
                  {cargando ? 'Cargando…' : mensajeVacio}
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>

      {paginacion && <ControlesPaginacion {...paginacion} />}

      <Dialogo
        abierto={pendiente !== null}
        titulo="Confirmar"
        alCerrar={() => setPendiente(null)}
      >
        <p className="text-sm">
          {pendiente && pendiente.accion.confirmacion?.(pendiente.fila)}
        </p>
        <div className="flex justify-end gap-2">
          <Button
            variant="outline"
            onClick={() => setPendiente(null)}
            disabled={ejecutando}
          >
            Cancelar
          </Button>
          <Button
            variant={
              pendiente?.accion.variante === 'destructive' ? 'destructive' : 'default'
            }
            disabled={ejecutando}
            onClick={() => pendiente && void ejecutar(pendiente.accion, pendiente.fila)}
          >
            {ejecutando ? 'Procesando…' : 'Confirmar'}
          </Button>
        </div>
      </Dialogo>
    </div>
  )
}

function ControlesPaginacion({ pagina, total, alCambiarPagina }: Paginacion) {
  const ultima = totalPaginas(total)
  return (
    <div className="flex items-center justify-between text-sm text-slate-600">
      <span>
        {total} {total === 1 ? 'registro' : 'registros'} · página {pagina} de {ultima}
      </span>
      <div className="flex gap-2">
        <Button
          variant="outline"
          size="sm"
          disabled={pagina <= 1}
          onClick={() => alCambiarPagina(pagina - 1)}
        >
          Anterior
        </Button>
        <Button
          variant="outline"
          size="sm"
          disabled={pagina >= ultima}
          onClick={() => alCambiarPagina(pagina + 1)}
        >
          Siguiente
        </Button>
      </div>
    </div>
  )
}
