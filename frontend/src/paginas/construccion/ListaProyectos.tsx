import { createColumnHelper } from '@tanstack/react-table'
import { useNavigate, useSearchParams } from 'react-router'

import {
  ETIQUETAS_ESTADO_PROYECTO,
  useProyectos,
  type EstadoProyecto,
  type FiltrosProyectos,
  type Proyecto,
} from '../../api/construccion/consultas'
import { TablaDatos, type AccionFila } from '../../componentes/comunes/TablaDatos'
import { Button } from '../../componentes/ui/button'
import { Select } from '../../componentes/ui/select'
import { ESCRIBEN_CONSTRUCCION, rolPermitido } from '../../menu'
import { useSesion } from '../../sesion/useSesion'

const columna = createColumnHelper<Proyecto>()

const COLUMNAS = [
  columna.accessor('codigo', { header: 'Código' }),
  columna.accessor('nombre', { header: 'Nombre' }),
  columna.accessor((proyecto) => proyecto.propiedad.codigo, {
    id: 'propiedad',
    header: 'Propiedad',
  }),
  columna.accessor((proyecto) => proyecto.constructora.nombre, {
    id: 'constructora',
    header: 'Constructora',
  }),
  columna.accessor('estado', {
    header: 'Estado',
    cell: ({ getValue }) => ETIQUETAS_ESTADO_PROYECTO[getValue()],
  }),
  columna.accessor('porcentaje_avance', {
    header: 'Avance',
    cell: ({ getValue }) => `${getValue() ?? 0} %`,
  }),
]

/**
 * Proyectos de construcción (spec 018, §5). Las acciones del proyecto y sus
 * pagos están en su detalle (§10), como los contratos de venta de B.
 */
export function ListaProyectos() {
  const { usuario } = useSesion()
  const navegar = useNavigate()
  const [parametros, setParametros] = useSearchParams()

  const filtros: FiltrosProyectos = {
    page: Number(parametros.get('page') ?? '1'),
    estado: (parametros.get('estado') as EstadoProyecto | null) ?? undefined,
  }
  const consulta = useProyectos(filtros)

  const filtrarEstado = (estado: string) => {
    setParametros(estado ? { estado } : {})
  }

  const cambiarPagina = (pagina: number) => {
    const siguientes = new URLSearchParams(parametros)
    siguientes.set('page', String(pagina))
    setParametros(siguientes)
  }

  const acciones: AccionFila<Proyecto>[] = [
    {
      etiqueta: 'Ver detalle',
      ejecutar: (fila) => navegar(`/construccion/proyectos/${fila.id}`),
    },
  ]

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Proyectos de construcción</h1>
        {rolPermitido(usuario?.rol ?? '', ESCRIBEN_CONSTRUCCION) && (
          <Button onClick={() => navegar('/construccion/proyectos/nuevo')}>
            Nuevo proyecto
          </Button>
        )}
      </div>

      <Select
        aria-label="Estado"
        className="w-48"
        value={parametros.get('estado') ?? ''}
        onChange={(evento) => filtrarEstado(evento.target.value)}
      >
        <option value="">Todos los estados</option>
        {Object.entries(ETIQUETAS_ESTADO_PROYECTO).map(([valor, etiqueta]) => (
          <option key={valor} value={valor}>
            {etiqueta}
          </option>
        ))}
      </Select>

      <TablaDatos
        columnas={COLUMNAS}
        datos={consulta.data?.results}
        cargando={consulta.isPending}
        error={consulta.error}
        acciones={acciones}
        mensajeVacio="Ningún proyecto coincide con el filtro."
        paginacion={{
          pagina: filtros.page ?? 1,
          total: consulta.data?.count ?? 0,
          alCambiarPagina: cambiarPagina,
        }}
      />
    </div>
  )
}
