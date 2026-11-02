import { createColumnHelper } from '@tanstack/react-table'
import { useState } from 'react'

import { useTiposPropiedad, type TipoPropiedad } from '../../api/catalogo/consultas'
import { useDesactivarTipoPropiedad } from '../../api/catalogo/mutaciones'
import { TablaDatos, type AccionFila } from '../../componentes/comunes/TablaDatos'
import { Button } from '../../componentes/ui/button'
import { ROLES, rolPermitido } from '../../menu'
import { useSesion } from '../../sesion/useSesion'
import { DialogoTipoPropiedad } from './DialogoTipoPropiedad'

const columna = createColumnHelper<TipoPropiedad>()

const COLUMNAS = [
  columna.accessor('nombre', { header: 'Nombre' }),
  columna.accessor('descripcion', {
    header: 'Descripción',
    cell: ({ getValue }) => getValue() || '—',
  }),
  columna.accessor('requiere_unidades', {
    header: 'Admite unidades',
    cell: ({ getValue }) => (getValue() ? 'Sí' : 'No'),
  }),
]

/**
 * Tipos de propiedad (spec 014, §5). Todos los ven; solo el administrador
 * crea, edita y desactiva (regla 2). Son pocos y caben en una página, así que
 * la tabla no pagina: usa la misma consulta que los formularios.
 */
export function ListaTiposPropiedad() {
  const { usuario } = useSesion()
  const tipos = useTiposPropiedad()
  const desactivar = useDesactivarTipoPropiedad()
  // El diálogo: cerrado, un tipo nuevo (null) o uno a editar.
  const [editando, setEditando] = useState<TipoPropiedad | null | undefined>(undefined)

  const esAdministrador = rolPermitido(usuario?.rol ?? '', [ROLES.ADMINISTRADOR])
  const acciones: AccionFila<TipoPropiedad>[] = esAdministrador
    ? [
        { etiqueta: 'Editar', ejecutar: (fila) => setEditando(fila) },
        {
          etiqueta: 'Desactivar',
          variante: 'destructive',
          confirmacion: (fila) =>
            `¿Desactivar el tipo ${fila.nombre}? No se ofrecerá para propiedades nuevas; las que ya lo tienen lo conservan.`,
          ejecutar: (fila) => desactivar.mutateAsync(fila.id),
        },
      ]
    : []

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Tipos de propiedad</h1>
        {esAdministrador && (
          <Button onClick={() => setEditando(null)}>Nuevo tipo</Button>
        )}
      </div>

      <TablaDatos
        columnas={COLUMNAS}
        datos={tipos.data}
        cargando={tipos.isPending}
        error={tipos.error}
        acciones={acciones}
        mensajeVacio="No hay tipos de propiedad activos."
      />

      <DialogoTipoPropiedad
        abierto={editando !== undefined}
        tipo={editando ?? null}
        alCerrar={() => setEditando(undefined)}
      />
    </div>
  )
}
