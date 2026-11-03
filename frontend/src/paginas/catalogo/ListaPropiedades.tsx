import { createColumnHelper } from '@tanstack/react-table'
import { useState, type FormEvent } from 'react'
import { useNavigate, useSearchParams } from 'react-router'

import {
  ETIQUETAS_ESTADO,
  usePropiedades,
  useTiposPropiedad,
  type EstadoPropiedad,
  type FiltrosPropiedades,
  type Propiedad,
} from '../../api/catalogo/consultas'
import { useDesactivarPropiedad } from '../../api/catalogo/mutaciones'
import { TablaDatos, type AccionFila } from '../../componentes/comunes/TablaDatos'
import { Button } from '../../componentes/ui/button'
import { Input } from '../../componentes/ui/input'
import { Select } from '../../componentes/ui/select'
import { formatearFecha, formatearMoneda } from '../../lib/formato'
import { ESCRIBEN_CATALOGO, rolPermitido } from '../../menu'
import { useSesion } from '../../sesion/useSesion'
import { DialogoCambiarEstado } from './DialogoCambiarEstado'

const columna = createColumnHelper<Propiedad>()

const COLUMNAS = [
  // Spec 019: la portada identifica a la propiedad en la lista; sin foto, un
  // marcador del mismo tamaño para que las filas no salten.
  columna.accessor('portada_url', {
    header: 'Foto',
    cell: ({ getValue, row }) => {
      const url = getValue()
      return url ? (
        <img
          src={url}
          alt={`Portada de ${row.original.nombre}`}
          loading="lazy"
          className="h-12 w-16 rounded-lg object-cover"
        />
      ) : (
        <span
          aria-label="Sin foto"
          className="block h-12 w-16 rounded-lg border border-dashed border-ceniza bg-niebla"
        />
      )
    },
  }),
  columna.accessor('codigo', { header: 'Código' }),
  columna.accessor('nombre', { header: 'Nombre' }),
  columna.accessor((propiedad) => propiedad.tipo.nombre, {
    id: 'tipo',
    header: 'Tipo',
  }),
  columna.accessor((propiedad) => propiedad.ciudad, {
    id: 'ubicacion',
    header: 'Ubicación',
    cell: ({ getValue }) => `${getValue().nombre}, ${getValue().pais.nombre}`,
  }),
  columna.accessor('estado', {
    header: 'Estado',
    cell: ({ getValue }) => ETIQUETAS_ESTADO[getValue()],
  }),
  columna.accessor('precio_lista', {
    header: 'Precio de lista',
    cell: ({ getValue, row }) =>
      formatearMoneda(getValue(), row.original.moneda.codigo),
  }),
  columna.accessor('creado_en', {
    header: 'Registrada',
    cell: ({ getValue }) => formatearFecha(getValue()),
  }),
]

/**
 * Ejemplo de lista (spec 010, §5): la pantalla que los demás copian. Los
 * filtros y la página viven en la URL (?tipo=2&page=3), así que recargar o
 * compartir el enlace conserva lo que se estaba viendo.
 */
export function ListaPropiedades() {
  const { usuario } = useSesion()
  const navegar = useNavigate()
  const [parametros, setParametros] = useSearchParams()
  const [paraCambiarEstado, setParaCambiarEstado] = useState<Propiedad | null>(null)
  const desactivar = useDesactivarPropiedad()
  const tipos = useTiposPropiedad()

  const filtros: FiltrosPropiedades = {
    page: Number(parametros.get('page') ?? '1'),
    tipo: parametros.get('tipo') ? Number(parametros.get('tipo')) : undefined,
    estado: (parametros.get('estado') as EstadoPropiedad | null) ?? undefined,
    buscar: parametros.get('buscar') ?? undefined,
  }
  const consulta = usePropiedades(filtros)

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

  /** Cambia de página sin tocar los filtros. */
  const cambiarPagina = (pagina: number) => {
    const siguientes = new URLSearchParams(parametros)
    siguientes.set('page', String(pagina))
    setParametros(siguientes)
  }

  const buscar = (evento: FormEvent<HTMLFormElement>) => {
    evento.preventDefault()
    filtrar('buscar', String(new FormData(evento.currentTarget).get('buscar') ?? ''))
  }

  const puedeEscribir = rolPermitido(usuario?.rol ?? '', ESCRIBEN_CATALOGO)
  // Ver ficha la tienen todos los roles; las demás, solo quien escribe en el
  // catálogo (spec 014, regla 2).
  const verFicha: AccionFila<Propiedad> = {
    etiqueta: 'Ver ficha',
    ejecutar: (fila) => navegar(`/catalogo/propiedades/${fila.id}`),
  }
  const acciones: AccionFila<Propiedad>[] = puedeEscribir
    ? [
        verFicha,
        { etiqueta: 'Cambiar estado', ejecutar: (fila) => setParaCambiarEstado(fila) },
        {
          etiqueta: 'Desactivar',
          variante: 'destructive',
          confirmacion: (fila) =>
            `¿Desactivar ${fila.codigo} · ${fila.nombre}? Dejará de aparecer en las listas.`,
          ejecutar: (fila) => desactivar.mutateAsync(fila.id),
        },
      ]
    : [verFicha]

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h1 className="font-editorial text-4xl leading-none">Propiedades</h1>
        {puedeEscribir && (
          <Button onClick={() => navegar('/catalogo/propiedades/nueva')}>
            Nueva propiedad
          </Button>
        )}
      </div>

      <div className="flex flex-wrap items-end gap-3">
        <Select
          aria-label="Tipo"
          className="w-48"
          value={parametros.get('tipo') ?? ''}
          onChange={(evento) => filtrar('tipo', evento.target.value)}
        >
          <option value="">Todos los tipos</option>
          {tipos.data?.map((tipo) => (
            <option key={tipo.id} value={tipo.id}>
              {tipo.nombre}
            </option>
          ))}
        </Select>
        <Select
          aria-label="Estado"
          className="w-48"
          value={parametros.get('estado') ?? ''}
          onChange={(evento) => filtrar('estado', evento.target.value)}
        >
          <option value="">Todos los estados</option>
          {Object.entries(ETIQUETAS_ESTADO).map(([valor, etiqueta]) => (
            <option key={valor} value={valor}>
              {etiqueta}
            </option>
          ))}
        </Select>
        <form onSubmit={buscar} className="flex gap-2">
          <Input
            name="buscar"
            aria-label="Buscar"
            placeholder="Código, nombre o dirección"
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
        mensajeVacio="Ninguna propiedad coincide con los filtros."
        paginacion={{
          pagina: filtros.page ?? 1,
          total: consulta.data?.count ?? 0,
          alCambiarPagina: cambiarPagina,
        }}
      />

      <DialogoCambiarEstado
        recurso="propiedades"
        elemento={paraCambiarEstado}
        alCerrar={() => setParaCambiarEstado(null)}
      />
    </div>
  )
}
