import { createColumnHelper } from '@tanstack/react-table'
import type { FormEvent } from 'react'
import { useNavigate, useSearchParams } from 'react-router'

import {
  ETIQUETAS_TIPO_PROVEEDOR,
  useProveedores,
  type FiltrosProveedores,
  type Proveedor,
  type TipoProveedor,
} from '../../api/compras/consultas'
import { useDesactivarProveedor } from '../../api/compras/mutaciones'
import { usePaises } from '../../api/core/consultas'
import { TablaDatos, type AccionFila } from '../../componentes/comunes/TablaDatos'
import { Button } from '../../componentes/ui/button'
import { Input } from '../../componentes/ui/input'
import { Select } from '../../componentes/ui/select'
import { ESCRIBEN_COMPRAS, rolPermitido } from '../../menu'
import { useSesion } from '../../sesion/useSesion'

const columna = createColumnHelper<Proveedor>()

const COLUMNAS = [
  columna.accessor('codigo', { header: 'Código' }),
  columna.accessor('nombre', { header: 'Nombre' }),
  columna.accessor('tipo', {
    header: 'Tipo',
    cell: ({ getValue }) => ETIQUETAS_TIPO_PROVEEDOR[getValue()],
  }),
  // Un propietario particular puede no tener NIT (spec 006, regla 2).
  columna.accessor('nit', {
    header: 'NIT',
    cell: ({ getValue }) => getValue() || '—',
  }),
  columna.accessor((proveedor) => proveedor.pais.nombre, {
    id: 'pais',
    header: 'País',
  }),
]

/**
 * Proveedores (spec 018, §5). Todos los roles los ven; crear, editar y
 * desactivar, solo administración y gerencia (regla 2). Los filtros y la
 * página viven en la URL, como en ListaClientes: así recargar o compartir el
 * enlace deja la misma vista.
 */
export function ListaProveedores() {
  const { usuario } = useSesion()
  const navegar = useNavigate()
  const [parametros, setParametros] = useSearchParams()
  const desactivar = useDesactivarProveedor()
  const paises = usePaises()

  const filtros: FiltrosProveedores = {
    page: Number(parametros.get('page') ?? '1'),
    tipo: (parametros.get('tipo') as TipoProveedor | null) ?? undefined,
    pais: parametros.get('pais') ? Number(parametros.get('pais')) : undefined,
    buscar: parametros.get('buscar') ?? undefined,
  }
  const consulta = useProveedores(filtros)

  /** Cambia un filtro y vuelve a la página 1. */
  const filtrar = (nombre: string, valor: string) => {
    const siguientes = new URLSearchParams(parametros)
    if (valor) {
      siguientes.set(nombre, valor)
    } else {
      siguientes.delete(nombre)
    }
    siguientes.delete('page')
    setParametros(siguientes)
  }

  const cambiarPagina = (pagina: number) => {
    const siguientes = new URLSearchParams(parametros)
    siguientes.set('page', String(pagina))
    setParametros(siguientes)
  }

  const buscar = (evento: FormEvent<HTMLFormElement>) => {
    evento.preventDefault()
    filtrar('buscar', String(new FormData(evento.currentTarget).get('buscar') ?? ''))
  }

  const puedeEscribir = rolPermitido(usuario?.rol ?? '', ESCRIBEN_COMPRAS)
  const acciones: AccionFila<Proveedor>[] = puedeEscribir
    ? [
        {
          etiqueta: 'Editar',
          ejecutar: (fila) => navegar(`/compras/proveedores/${fila.id}/editar`),
        },
        {
          etiqueta: 'Desactivar',
          variante: 'destructive',
          // Desactivar no se deshace desde las pantallas (spec 018, §2).
          confirmacion: (fila) =>
            `¿Desactivar ${fila.codigo} · ${fila.nombre}? Dejará de aparecer en las listas.`,
          ejecutar: (fila) => desactivar.mutateAsync(fila.id),
        },
      ]
    : []

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Proveedores</h1>
        {puedeEscribir && (
          <Button onClick={() => navegar('/compras/proveedores/nuevo')}>
            Nuevo proveedor
          </Button>
        )}
      </div>

      <div className="flex flex-wrap items-end gap-3">
        <Select
          aria-label="Tipo"
          className="w-52"
          value={parametros.get('tipo') ?? ''}
          onChange={(evento) => filtrar('tipo', evento.target.value)}
        >
          <option value="">Todos los tipos</option>
          {Object.entries(ETIQUETAS_TIPO_PROVEEDOR).map(([valor, etiqueta]) => (
            <option key={valor} value={valor}>
              {etiqueta}
            </option>
          ))}
        </Select>
        <Select
          aria-label="País"
          className="w-48"
          value={parametros.get('pais') ?? ''}
          onChange={(evento) => filtrar('pais', evento.target.value)}
        >
          <option value="">Todos los países</option>
          {paises.data?.map((pais) => (
            <option key={pais.id} value={pais.id}>
              {pais.nombre}
            </option>
          ))}
        </Select>
        <form onSubmit={buscar} className="flex gap-2">
          <Input
            name="buscar"
            aria-label="Buscar"
            placeholder="Nombre, NIT o código"
            className="w-64"
            defaultValue={parametros.get('buscar') ?? ''}
          />
          <Button type="submit" variant="outline">
            Buscar
          </Button>
        </form>
      </div>

      <TablaDatos
        columnas={COLUMNAS}
        datos={consulta.data?.results}
        cargando={consulta.isPending}
        error={consulta.error}
        acciones={acciones}
        mensajeVacio="Ningún proveedor coincide con los filtros."
        paginacion={{
          pagina: filtros.page ?? 1,
          total: consulta.data?.count ?? 0,
          alCambiarPagina: cambiarPagina,
        }}
      />
    </div>
  )
}
