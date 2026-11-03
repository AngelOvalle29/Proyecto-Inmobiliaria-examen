import { createColumnHelper } from '@tanstack/react-table'
import { useState, type FormEvent } from 'react'
import { useNavigate, useSearchParams } from 'react-router'

import {
  ETIQUETAS_TIPO_CLIENTE,
  nombreCliente,
  useClientes,
  type Cliente,
  type FiltrosClientes,
  type TipoCliente,
} from '../../api/crm/consultas'
import { useDesactivarCliente } from '../../api/crm/mutaciones'
import { usePaises } from '../../api/core/consultas'
import { TablaDatos, type AccionFila } from '../../componentes/comunes/TablaDatos'
import { Button } from '../../componentes/ui/button'
import { Input } from '../../componentes/ui/input'
import { Select } from '../../componentes/ui/select'
import { ADMINISTRAN_CRM, ESCRIBEN_CRM, rolPermitido } from '../../menu'
import { useSesion } from '../../sesion/useSesion'
import { DialogoReasignar } from './DialogoReasignar'

const columna = createColumnHelper<Cliente>()

const COLUMNAS = [
  columna.accessor('codigo', { header: 'Código' }),
  columna.accessor((cliente) => nombreCliente(cliente), {
    id: 'nombre',
    header: 'Nombre',
  }),
  columna.accessor('tipo', {
    header: 'Tipo',
    cell: ({ getValue }) => ETIQUETAS_TIPO_CLIENTE[getValue()],
  }),
  columna.accessor((cliente) => cliente.pais.nombre, { id: 'pais', header: 'País' }),
  columna.accessor((cliente) => cliente.agente_asignado.nombre_completo, {
    id: 'agente',
    header: 'Agente',
  }),
]

/**
 * Clientes (spec 012, §5). Un agente solo ve su cartera, porque la API ya la
 * filtra (regla 3). Los filtros y la página viven en la URL, como en
 * ListaPropiedades.
 */
export function ListaClientes() {
  const { usuario } = useSesion()
  const navegar = useNavigate()
  const [parametros, setParametros] = useSearchParams()
  const [paraReasignar, setParaReasignar] = useState<Cliente | null>(null)
  const desactivar = useDesactivarCliente()
  const paises = usePaises()

  const filtros: FiltrosClientes = {
    page: Number(parametros.get('page') ?? '1'),
    tipo: (parametros.get('tipo') as TipoCliente | null) ?? undefined,
    pais: parametros.get('pais') ? Number(parametros.get('pais')) : undefined,
    buscar: parametros.get('buscar') ?? undefined,
  }
  const consulta = useClientes(filtros)

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

  const rol = usuario?.rol ?? ''
  const puedeEscribir = rolPermitido(rol, ESCRIBEN_CRM)
  const puedeReasignar = rolPermitido(rol, ADMINISTRAN_CRM)
  const acciones: AccionFila<Cliente>[] = []
  if (puedeEscribir) {
    acciones.push({
      etiqueta: 'Editar',
      ejecutar: (fila) => navegar(`/crm/clientes/${fila.id}/editar`),
    })
  }
  if (puedeReasignar) {
    acciones.push({ etiqueta: 'Reasignar', ejecutar: (fila) => setParaReasignar(fila) })
  }
  if (puedeEscribir) {
    acciones.push({
      etiqueta: 'Desactivar',
      variante: 'destructive',
      confirmacion: (fila) =>
        `¿Desactivar ${fila.codigo} · ${nombreCliente(fila)}? Dejará de aparecer en las listas.`,
      ejecutar: (fila) => desactivar.mutateAsync(fila.id),
    })
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h1 className="font-editorial text-4xl leading-none">Clientes</h1>
        {puedeEscribir && (
          <Button onClick={() => navegar('/crm/clientes/nuevo')}>Nuevo cliente</Button>
        )}
      </div>

      <div className="flex flex-wrap items-end gap-3">
        <Select
          aria-label="Tipo"
          className="w-40"
          value={parametros.get('tipo') ?? ''}
          onChange={(evento) => filtrar('tipo', evento.target.value)}
        >
          <option value="">Todos los tipos</option>
          {Object.entries(ETIQUETAS_TIPO_CLIENTE).map(([valor, etiqueta]) => (
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
            placeholder="Nombre, documento, NIT o código"
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
        mensajeVacio="Ningún cliente coincide con los filtros."
        paginacion={{
          pagina: filtros.page ?? 1,
          total: consulta.data?.count ?? 0,
          alCambiarPagina: cambiarPagina,
        }}
      />

      <DialogoReasignar
        cliente={paraReasignar}
        alCerrar={() => setParaReasignar(null)}
      />
    </div>
  )
}
