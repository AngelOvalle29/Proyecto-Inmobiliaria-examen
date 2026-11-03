import { createColumnHelper } from '@tanstack/react-table'
import type { FormEvent } from 'react'
import { useNavigate, useSearchParams } from 'react-router'

import { usePaises } from '../../api/core/consultas'
import {
  useConstructoras,
  type Constructora,
  type FiltrosConstructoras,
} from '../../api/construccion/consultas'
import { useDesactivarConstructora } from '../../api/construccion/mutaciones'
import { TablaDatos, type AccionFila } from '../../componentes/comunes/TablaDatos'
import { Button } from '../../componentes/ui/button'
import { Input } from '../../componentes/ui/input'
import { Select } from '../../componentes/ui/select'
import { ESCRIBEN_CONSTRUCCION, rolPermitido } from '../../menu'
import { useSesion } from '../../sesion/useSesion'

const columna = createColumnHelper<Constructora>()

const COLUMNAS = [
  columna.accessor('codigo', { header: 'Código' }),
  columna.accessor('nombre', { header: 'Nombre' }),
  columna.accessor('nit', { header: 'NIT' }),
  columna.accessor((constructora) => constructora.pais.nombre, {
    id: 'pais',
    header: 'País',
  }),
  // Opcional: una constructora nueva todavía no tiene trabajos que calificar
  // (spec 006, regla 6).
  columna.accessor('calificacion', {
    header: 'Calificación',
    cell: ({ getValue }) => {
      const calificacion = getValue()
      return calificacion ? `${calificacion} de 5` : 'Sin calificar'
    },
  }),
]

const CALIFICACIONES = ['1', '2', '3', '4', '5']

/**
 * Constructoras (spec 018, §5). Todos los roles las ven; crear, editar y
 * desactivar, solo administración y gerencia (regla 2). Mismo esquema que
 * ListaProveedores: filtros y página en la URL.
 */
export function ListaConstructoras() {
  const { usuario } = useSesion()
  const navegar = useNavigate()
  const [parametros, setParametros] = useSearchParams()
  const desactivar = useDesactivarConstructora()
  const paises = usePaises()

  const filtros: FiltrosConstructoras = {
    page: Number(parametros.get('page') ?? '1'),
    pais: parametros.get('pais') ? Number(parametros.get('pais')) : undefined,
    calificacion_min: parametros.get('calificacion_min')
      ? Number(parametros.get('calificacion_min'))
      : undefined,
    buscar: parametros.get('buscar') ?? undefined,
  }
  const consulta = useConstructoras(filtros)

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

  const puedeEscribir = rolPermitido(usuario?.rol ?? '', ESCRIBEN_CONSTRUCCION)
  const acciones: AccionFila<Constructora>[] = puedeEscribir
    ? [
        {
          etiqueta: 'Editar',
          ejecutar: (fila) => navegar(`/construccion/constructoras/${fila.id}/editar`),
        },
        {
          etiqueta: 'Desactivar',
          variante: 'destructive',
          confirmacion: (fila) =>
            `¿Desactivar ${fila.codigo} · ${fila.nombre}? Dejará de aparecer en las listas.`,
          ejecutar: (fila) => desactivar.mutateAsync(fila.id),
        },
      ]
    : []

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h1 className="font-editorial text-4xl leading-none">Constructoras</h1>
        {puedeEscribir && (
          <Button onClick={() => navegar('/construccion/constructoras/nueva')}>
            Nueva constructora
          </Button>
        )}
      </div>

      <div className="flex flex-wrap items-end gap-3">
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
        <Select
          aria-label="Calificación mínima"
          className="w-52"
          value={parametros.get('calificacion_min') ?? ''}
          onChange={(evento) => filtrar('calificacion_min', evento.target.value)}
        >
          <option value="">Cualquier calificación</option>
          {CALIFICACIONES.map((valor) => (
            <option key={valor} value={valor}>
              {valor} o más
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
        mensajeVacio="Ninguna constructora coincide con los filtros."
        paginacion={{
          pagina: filtros.page ?? 1,
          total: consulta.data?.count ?? 0,
          alCambiarPagina: cambiarPagina,
        }}
      />
    </div>
  )
}
