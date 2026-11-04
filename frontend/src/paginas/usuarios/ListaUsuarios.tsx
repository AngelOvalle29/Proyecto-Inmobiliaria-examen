import { createColumnHelper } from '@tanstack/react-table'
import { useState, type FormEvent } from 'react'
import { useNavigate, useSearchParams } from 'react-router'

import {
  ETIQUETAS_ROL,
  useUsuarios,
  type FiltrosUsuarios,
  type NombreRol,
  type UsuarioListado,
} from '../../api/usuarios/consultas'
import { useCambiarEstadoUsuario } from '../../api/usuarios/mutaciones'
import { TablaDatos, type AccionFila } from '../../componentes/comunes/TablaDatos'
import { Button } from '../../componentes/ui/button'
import { Input } from '../../componentes/ui/input'
import { Select } from '../../componentes/ui/select'
import { useSesion } from '../../sesion/useSesion'
import { DialogoContrasena } from './DialogoContrasena'

const columna = createColumnHelper<UsuarioListado>()

const COLUMNAS = [
  columna.accessor('nombre_completo', { header: 'Nombre' }),
  columna.accessor('email', { header: 'Correo' }),
  columna.accessor('rol', {
    header: 'Rol',
    cell: ({ getValue }) => ETIQUETAS_ROL[getValue() as NombreRol] ?? getValue(),
  }),
  columna.accessor((usuario) => usuario.pais?.nombre ?? '—', {
    id: 'pais',
    header: 'País',
  }),
  columna.accessor('activo', {
    header: 'Estado',
    cell: ({ getValue }) =>
      getValue() ? 'Activo' : <span className="text-tenue">Desactivado</span>,
  }),
]

const ESTADOS: Record<string, string> = {
  ACTIVOS: 'Activos',
  INACTIVOS: 'Desactivados',
  TODOS: 'Todos',
}

/**
 * Usuarios del sistema (spec 026). Solo administración llega aquí; la API lo
 * vuelve a revisar. Las reglas que protegen al último administrador y a los
 * agentes las aplica la API, y su 409 sale arriba de la tabla.
 */
export function ListaUsuarios() {
  const { usuario: yo } = useSesion()
  const navegar = useNavigate()
  const [parametros, setParametros] = useSearchParams()
  const [paraContrasena, setParaContrasena] = useState<UsuarioListado | null>(null)
  const cambiarEstado = useCambiarEstadoUsuario()

  const filtros: FiltrosUsuarios = {
    page: Number(parametros.get('page') ?? '1'),
    buscar: parametros.get('buscar') ?? undefined,
    rol: (parametros.get('rol') as FiltrosUsuarios['rol']) || undefined,
    estado: (parametros.get('estado') as FiltrosUsuarios['estado']) || undefined,
  }
  const consulta = useUsuarios(filtros)

  const cambiarFiltro = (nombre: string, valor: string) => {
    const siguientes = new URLSearchParams(parametros)
    if (valor) {
      siguientes.set(nombre, valor)
    } else {
      siguientes.delete(nombre)
    }
    siguientes.delete('page')
    setParametros(siguientes)
  }

  const buscar = (evento: FormEvent<HTMLFormElement>) => {
    evento.preventDefault()
    cambiarFiltro(
      'buscar',
      String(new FormData(evento.currentTarget).get('buscar') ?? ''),
    )
  }

  const esYo = (fila: UsuarioListado) => fila.id === yo?.id
  const acciones: AccionFila<UsuarioListado>[] = [
    { etiqueta: 'Editar', ejecutar: (fila) => navegar(`/usuarios/${fila.id}/editar`) },
    { etiqueta: 'Contraseña', ejecutar: (fila) => setParaContrasena(fila) },
    {
      etiqueta: 'Desactivar',
      variante: 'destructive',
      // Nadie se desactiva a sí mismo (regla 4): ni siquiera se ofrece.
      oculta: (fila) => !fila.activo || esYo(fila),
      confirmacion: (fila) =>
        `¿Desactivar a ${fila.nombre_completo}? No podrá iniciar sesión, y su sesión abierta se cerrará en la siguiente acción.`,
      ejecutar: (fila) =>
        cambiarEstado.mutateAsync({ id: fila.id, accion: 'desactivar' }),
    },
    {
      etiqueta: 'Reactivar',
      oculta: (fila) => fila.activo,
      ejecutar: (fila) =>
        cambiarEstado.mutateAsync({ id: fila.id, accion: 'reactivar' }),
    },
  ]

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h1 className="font-editorial text-4xl leading-none">Usuarios</h1>
        <Button onClick={() => navegar('/usuarios/nuevo')}>Nuevo usuario</Button>
      </div>

      <div className="flex flex-wrap items-end gap-3">
        <form onSubmit={buscar} className="flex gap-2">
          <Input
            name="buscar"
            aria-label="Buscar"
            placeholder="Nombre o correo"
            className="w-64"
            defaultValue={parametros.get('buscar') ?? ''}
          />
          <Button type="submit" variant="outline">
            Buscar
          </Button>
        </form>
        <Select
          aria-label="Rol"
          className="w-44"
          value={parametros.get('rol') ?? ''}
          onChange={(evento) => cambiarFiltro('rol', evento.target.value)}
        >
          <option value="">Todos los roles</option>
          {Object.entries(ETIQUETAS_ROL).map(([valor, etiqueta]) => (
            <option key={valor} value={valor}>
              {etiqueta}
            </option>
          ))}
        </Select>
        <Select
          aria-label="Estado"
          className="w-40"
          value={parametros.get('estado') ?? 'ACTIVOS'}
          onChange={(evento) => cambiarFiltro('estado', evento.target.value)}
        >
          {Object.entries(ESTADOS).map(([valor, etiqueta]) => (
            <option key={valor} value={valor}>
              {etiqueta}
            </option>
          ))}
        </Select>
      </div>

      <TablaDatos
        columnas={COLUMNAS}
        datos={consulta.data?.results}
        cargando={consulta.isPending}
        error={consulta.error}
        acciones={acciones}
        mensajeVacio="Ningún usuario coincide con los filtros."
        paginacion={{
          pagina: filtros.page ?? 1,
          total: consulta.data?.count ?? 0,
          alCambiarPagina: (pagina) => cambiarFiltro('page', String(pagina)),
        }}
      />

      <DialogoContrasena
        usuario={paraContrasena}
        alCerrar={() => setParaContrasena(null)}
      />
    </div>
  )
}
