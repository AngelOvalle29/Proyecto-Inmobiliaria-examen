import { useState } from 'react'
import type { ColumnDef } from '@tanstack/react-table'

import { leerErrorApi } from '../../api/errores'
import {
  useCatalogoReportes,
  useDescargarReporte,
  useOpcionesFiltro,
  useReporte,
  type DefinicionReporte,
  type FilaReporte,
  type FiltroReporte,
  type ValoresFiltros,
} from '../../api/reportes/consultas'
import { TablaDatos } from '../../componentes/comunes/TablaDatos'
import { Button } from '../../componentes/ui/button'
import { Input } from '../../componentes/ui/input'
import { Label } from '../../componentes/ui/label'
import { Select } from '../../componentes/ui/select'

export function Reportes() {
  const catalogo = useCatalogoReportes()
  const [elegido, setElegido] = useState('')
  const definicion = catalogo.data?.results.find((r) => r.slug === elegido)
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Reportes</h1>
        <p className="text-slate-600">
          Consulte los resultados y descargue el reporte completo en Excel o PDF.
        </p>
      </div>
      {catalogo.isPending && <p>Cargando reportes…</p>}
      {catalogo.error && <p role="alert">{leerErrorApi(catalogo.error).mensaje}</p>}
      <Label htmlFor="reporte">Reporte</Label>
      <Select id="reporte" value={elegido} onChange={(e) => setElegido(e.target.value)}>
        <option value="">Seleccione un reporte</option>
        {catalogo.data?.results.map((r) => (
          <option key={r.slug} value={r.slug}>
            {r.codigo} · {r.titulo}
          </option>
        ))}
      </Select>
      {definicion && <ConsultaReporte key={definicion.slug} definicion={definicion} />}
    </div>
  )
}

function ConsultaReporte({ definicion }: { definicion: DefinicionReporte }) {
  const [borrador, setBorrador] = useState<ValoresFiltros>({})
  const [filtros, setFiltros] = useState<ValoresFiltros>({})
  const [pagina, setPagina] = useState(1)
  const consulta = useReporte(definicion.slug, filtros, pagina)
  const descarga = useDescargarReporte()
  const columnas: ColumnDef<FilaReporte>[] = definicion.columnas.map((c) => ({
    accessorKey: c.nombre,
    header: c.etiqueta,
    cell: ({ row }) => mostrar(row.original[c.nombre], c.tipo),
  }))
  const aplicar = (valores: ValoresFiltros) => {
    setFiltros(Object.fromEntries(Object.entries(valores).filter(([, v]) => v !== '')))
    setPagina(1)
    descarga.reset()
  }
  return (
    <div className="space-y-5">
      <form
        onSubmit={(e) => {
          e.preventDefault()
          aplicar(borrador)
        }}
        className="space-y-4 rounded-lg border p-4"
      >
        <div className="grid gap-4 md:grid-cols-3">
          {definicion.filtros.map((filtro) => (
            <CampoFiltro
              key={filtro.nombre}
              filtro={filtro}
              valor={borrador[filtro.nombre] ?? ''}
              alCambiar={(valor) =>
                setBorrador({ ...borrador, [filtro.nombre]: valor })
              }
            />
          ))}
        </div>
        <div className="flex gap-2">
          <Button type="submit">Aplicar filtros</Button>
          <Button
            type="button"
            variant="outline"
            onClick={() => {
              setBorrador({})
              aplicar({})
            }}
          >
            Limpiar
          </Button>
        </div>
      </form>
      {consulta.error && (
        <div role="alert" className="text-red-700">
          <p>{leerErrorApi(consulta.error).mensaje}</p>
          {Object.entries(leerErrorApi(consulta.error).detalles).map(
            ([campo, error]) => (
              <p key={campo}>
                {campo}: {String(error)}
              </p>
            ),
          )}
        </div>
      )}
      <div className="flex flex-wrap gap-3">
        {(['excel', 'pdf'] as const).map((formato) => (
          <Button
            key={formato}
            variant="outline"
            disabled={!consulta.data || consulta.isFetching || descarga.isPending}
            onClick={() =>
              descarga.mutate({
                slug: definicion.slug,
                filtros,
                formato,
                codigo: definicion.codigo,
              })
            }
          >
            Descargar {formato === 'excel' ? 'Excel' : 'PDF'}
          </Button>
        ))}
        {descarga.isPending && <span>Generando archivo…</span>}
      </div>
      {descarga.error && (
        <p role="alert" className="text-red-700">
          {leerErrorApi(descarga.error).mensaje}
        </p>
      )}
      <TablaDatos
        columnas={columnas}
        datos={consulta.data?.filas.results}
        cargando={consulta.isFetching}
        error={consulta.error}
        paginacion={{
          pagina,
          total: consulta.data?.filas.count ?? 0,
          alCambiarPagina: setPagina,
        }}
      />
      {consulta.data && (
        <section className="space-y-3">
          <h2 className="text-lg font-semibold">Totales del resultado filtrado</h2>
          <Resumen valores={consulta.data.totales} />
          {consulta.data.agrupamientos.map((g, i) => (
            <details key={i} className="rounded border p-3">
              <summary>{g.etiqueta}</summary>
              <Resumen valores={g.valores} />
            </details>
          ))}
        </section>
      )}
    </div>
  )
}

function CampoFiltro({
  filtro,
  valor,
  alCambiar,
}: {
  filtro: FiltroReporte
  valor: string
  alCambiar: (valor: string) => void
}) {
  const id = `filtro-${filtro.nombre}`
  return (
    <div className="space-y-2">
      <Label htmlFor={id}>{filtro.etiqueta}</Label>
      {filtro.origen_opciones.startsWith('/') ? (
        <SelectorRemoto id={id} filtro={filtro} valor={valor} alCambiar={alCambiar} />
      ) : filtro.opciones.length > 0 ? (
        <Select id={id} value={valor} onChange={(e) => alCambiar(e.target.value)}>
          <option value="">Todos</option>
          {filtro.opciones.map((o) => (
            <option key={o.valor} value={o.valor}>
              {o.etiqueta}
            </option>
          ))}
        </Select>
      ) : (
        <Input
          id={id}
          type={
            filtro.tipo === 'fecha'
              ? 'date'
              : filtro.tipo === 'entero' || filtro.tipo === 'decimal'
                ? 'number'
                : 'text'
          }
          step={filtro.tipo === 'decimal' ? '0.01' : undefined}
          required={filtro.obligatorio}
          value={valor}
          onChange={(e) => alCambiar(e.target.value)}
        />
      )}
    </div>
  )
}

function SelectorRemoto({
  id,
  filtro,
  valor,
  alCambiar,
}: {
  id: string
  filtro: FiltroReporte
  valor: string
  alCambiar: (valor: string) => void
}) {
  const [texto, setTexto] = useState('')
  const [pagina, setPagina] = useState(1)
  const opciones = useOpcionesFiltro(filtro.origen_opciones, texto, pagina)
  return (
    <div className="space-y-2">
      {filtro.buscable && (
        <Input
          aria-label={`Buscar ${filtro.etiqueta}`}
          placeholder="Buscar…"
          value={texto}
          onChange={(e) => {
            setTexto(e.target.value)
            setPagina(1)
          }}
        />
      )}
      <Select id={id} value={valor} onChange={(e) => alCambiar(e.target.value)}>
        <option value="">Todos</option>
        {valor && !opciones.data?.opciones.some((o) => o.valor === valor) && (
          <option value={valor}>Seleccionado: {valor}</option>
        )}
        {opciones.data?.opciones.map((o) => (
          <option key={o.valor} value={o.valor}>
            {o.etiqueta}
          </option>
        ))}
      </Select>
      {opciones.isFetching && <p className="text-xs">Cargando opciones…</p>}
      {opciones.error && <p role="alert">{leerErrorApi(opciones.error).mensaje}</p>}
      <div className="flex gap-2">
        <Button
          type="button"
          size="sm"
          variant="outline"
          disabled={pagina <= 1}
          onClick={() => setPagina(pagina - 1)}
        >
          Anterior
        </Button>
        <Button
          type="button"
          size="sm"
          variant="outline"
          disabled={!opciones.data?.siguiente}
          onClick={() => setPagina(pagina + 1)}
        >
          Más opciones
        </Button>
      </div>
    </div>
  )
}

function mostrar(valor: unknown, tipo: string): string {
  if (valor === null || valor === undefined) return 'Sin dato'
  if (tipo === 'fecha') return String(valor).split('-').reverse().join('/')
  if (tipo === 'decimal')
    return Number(valor).toLocaleString('es-GT', {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    })
  if (tipo === 'fecha_hora')
    return new Date(String(valor)).toLocaleString('es-GT', {
      timeZone: 'America/Guatemala',
    })
  return String(valor)
}

function Resumen({ valores }: { valores: Record<string, unknown> }) {
  return (
    <dl className="grid gap-2 py-2 sm:grid-cols-2">
      {Object.entries(valores).map(([clave, valor]) => (
        <div key={clave}>
          <dt className="text-sm text-slate-600">{clave.replaceAll('_', ' ')}</dt>
          <dd>
            {typeof valor === 'object' && valor !== null ? (
              <Resumen valores={valor as Record<string, unknown>} />
            ) : (
              String(valor ?? '')
            )}
          </dd>
        </div>
      ))}
    </dl>
  )
}
