import { createColumnHelper } from '@tanstack/react-table'
import { useState, type FormEvent } from 'react'
import { useNavigate, useSearchParams } from 'react-router'

import { useAgentes, type Agente, type FiltrosAgentes } from '../../api/crm/consultas'
import { useDesactivarAgente } from '../../api/crm/mutaciones'
import { TablaDatos, type AccionFila } from '../../componentes/comunes/TablaDatos'
import { Button } from '../../componentes/ui/button'
import { Input } from '../../componentes/ui/input'
import { formatearFecha } from '../../lib/formato'
import { ADMINISTRAN_CRM, rolPermitido } from '../../menu'
import { useSesion } from '../../sesion/useSesion'
import { DialogoEditarAgente } from './DialogoEditarAgente'

const columna = createColumnHelper<Agente>()

const COLUMNAS = [
  columna.accessor('codigo', { header: 'Código' }),
  columna.accessor((agente) => agente.usuario.nombre_completo, {
    id: 'nombre',
    header: 'Nombre',
  }),
  columna.accessor((agente) => agente.pais?.nombre ?? '—', {
    id: 'pais',
    header: 'País',
  }),
  columna.accessor('porcentaje_comision', {
    header: 'Comisión',
    cell: ({ getValue }) => `${getValue()} %`,
  }),
  columna.accessor('fecha_ingreso', {
    header: 'Ingreso',
    cell: ({ getValue }) => formatearFecha(getValue()),
  }),
  columna.accessor('clientes_activos', { header: 'Clientes activos' }),
]

/** Agentes (spec 012, §5). Solo administrador y gerente los administran. */
export function ListaAgentes() {
  const { usuario } = useSesion()
  const navegar = useNavigate()
  const [parametros, setParametros] = useSearchParams()
  const [paraEditar, setParaEditar] = useState<Agente | null>(null)
  const desactivar = useDesactivarAgente()

  const filtros: FiltrosAgentes = {
    page: Number(parametros.get('page') ?? '1'),
    buscar: parametros.get('buscar') ?? undefined,
  }
  const consulta = useAgentes(filtros)

  const cambiarPagina = (pagina: number) => {
    const siguientes = new URLSearchParams(parametros)
    siguientes.set('page', String(pagina))
    setParametros(siguientes)
  }

  const buscar = (evento: FormEvent<HTMLFormElement>) => {
    evento.preventDefault()
    const texto = String(new FormData(evento.currentTarget).get('buscar') ?? '')
    setParametros(texto ? { buscar: texto } : {})
  }

  const puedeAdministrar = rolPermitido(usuario?.rol ?? '', ADMINISTRAN_CRM)
  const acciones: AccionFila<Agente>[] = puedeAdministrar
    ? [
        { etiqueta: 'Editar', ejecutar: (fila) => setParaEditar(fila) },
        {
          etiqueta: 'Desactivar',
          variante: 'destructive',
          confirmacion: (fila) =>
            `¿Desactivar ${fila.codigo} · ${fila.usuario.nombre_completo}?`,
          // Con clientes activos, la API responde 409 y la tabla muestra el
          // mensaje (spec 004, regla 4).
          ejecutar: (fila) => desactivar.mutateAsync(fila.id),
        },
      ]
    : []

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Agentes</h1>
        {puedeAdministrar && (
          <Button onClick={() => navegar('/crm/agentes/nuevo')}>Nuevo agente</Button>
        )}
      </div>

      <form onSubmit={buscar} className="flex gap-2">
        <Input
          name="buscar"
          aria-label="Buscar"
          placeholder="Nombre, correo o código"
          className="w-64"
          defaultValue={parametros.get('buscar') ?? ''}
        />
        <Button type="submit" variant="outline">
          Buscar
        </Button>
      </form>

      <TablaDatos
        columnas={COLUMNAS}
        datos={consulta.data?.results}
        cargando={consulta.isPending}
        error={consulta.error}
        acciones={acciones}
        mensajeVacio="Ningún agente coincide con la búsqueda."
        paginacion={{
          pagina: filtros.page ?? 1,
          total: consulta.data?.count ?? 0,
          alCambiarPagina: cambiarPagina,
        }}
      />

      <DialogoEditarAgente agente={paraEditar} alCerrar={() => setParaEditar(null)} />
    </div>
  )
}
