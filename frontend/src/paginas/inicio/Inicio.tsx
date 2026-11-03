import { Link } from 'react-router'

import { useConteo, useConteoReporte } from '../../api/inicio/consultas'
import { Card, CardContent, CardHeader, CardTitle } from '../../componentes/ui/card'
import { agruparMenu, MENU, rolPermitido } from '../../menu'
import { useSesion } from '../../sesion/useSesion'
import { EstadoServicio } from '../estado/EstadoServicio'
import { DATOS_POR_MODULO, type DatoModulo } from './modulos'

/**
 * Primera pantalla después de entrar (spec 010, §5): un resumen de cada módulo
 * que el rol puede ver (spec 023).
 */
export function Inicio() {
  const { usuario } = useSesion()
  const rol = usuario?.rol ?? ''

  // Los mismos permisos que el menú: un dato aparece si su pantalla aparece.
  const visibles = MENU.filter((entrada) => rolPermitido(rol, entrada.roles))
  const grupos = agruparMenu(visibles)
    .filter((grupo) => grupo.titulo)
    .map((grupo) => ({
      titulo: grupo.titulo as string,
      datos: grupo.entradas
        .map((entrada) => DATOS_POR_MODULO.find((dato) => dato.ruta === entrada.ruta))
        .filter((dato): dato is DatoModulo => dato !== undefined),
    }))
    .filter((grupo) => grupo.datos.length > 0)

  return (
    <div className="flex flex-col gap-6">
      <div>
        <p className="font-mono text-xs tracking-etiqueta text-tenue uppercase">
          Inicio
        </p>
        <h1 className="font-editorial text-5xl leading-none">
          Hola, {usuario?.nombre_completo}
        </h1>
      </div>

      <Destacados />

      <section className="flex flex-col gap-3">
        <h2 className="font-editorial text-3xl leading-none">Módulos</h2>
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {grupos.map((grupo) => (
            <Card key={grupo.titulo}>
              <CardHeader>
                <p className="font-mono text-xs tracking-etiqueta text-tenue uppercase">
                  {grupo.titulo}
                </p>
              </CardHeader>
              <CardContent className="flex flex-col gap-4">
                {grupo.datos.map((dato) => (
                  <Dato key={dato.ruta} dato={dato} />
                ))}
              </CardContent>
            </Card>
          ))}
        </div>
      </section>

      <Card className="max-w-2xl">
        <CardHeader>
          <CardTitle>Estado del sistema</CardTitle>
        </CardHeader>
        <CardContent>
          <EstadoServicio />
        </CardContent>
      </Card>
    </div>
  )
}

/**
 * Lo que pide atención, en el panel óxido del diseño (spec 022). Los dos
 * reportes los pueden ver todos los roles (spec 021).
 */
function Destacados() {
  const mora = useConteoReporte('morosidad')
  const disponibles = useConteoReporte('inventario-disponible')

  return (
    <section className="grid overflow-hidden rounded-2xl bg-oxido text-crema md:grid-cols-2">
      <Destacado
        titulo="Cuotas y rentas en mora"
        valor={mora.data}
        cargando={mora.isPending}
        error={mora.isError}
        enlace="/reportes"
      />
      <Destacado
        titulo="Propiedades y unidades disponibles para vender o arrendar"
        valor={disponibles.data}
        cargando={disponibles.isPending}
        error={disponibles.isError}
        enlace="/catalogo/propiedades"
        separado
      />
    </section>
  )
}

function Destacado({
  titulo,
  valor,
  cargando,
  error,
  enlace,
  separado = false,
}: {
  titulo: string
  valor: number | undefined
  cargando: boolean
  error: boolean
  enlace: string
  separado?: boolean
}) {
  return (
    <div
      className={
        separado
          ? 'flex flex-col gap-2 border-t border-crema/30 p-6 md:border-t-0 md:border-l'
          : 'flex flex-col gap-2 p-6'
      }
    >
      <p className="font-editorial text-6xl leading-none">
        {cargando ? '…' : error ? '—' : valor}
      </p>
      <p className="text-lg leading-snug">{titulo}</p>
      <Link
        to={enlace}
        className="self-start font-mono text-xs tracking-etiqueta uppercase underline-offset-4 hover:underline"
      >
        Ver detalle →
      </Link>
    </div>
  )
}

/** Un número del tablero, con su segundo dato si lo tiene. */
function Dato({ dato }: { dato: DatoModulo }) {
  const total = useConteo(dato.api)
  // Sin detalle, la consulta se repite con la misma clave y TanStack Query la
  // reutiliza: no hace una segunda petición.
  const detalle = useConteo(dato.api, dato.detalle?.filtros)

  return (
    <Link to={dato.ruta} className="group flex items-end justify-between gap-3">
      <div>
        <p className="text-sm group-hover:underline">{dato.etiqueta}</p>
        {dato.detalle && (
          <p className="text-xs text-tenue">
            {dato.detalle.etiqueta}:{' '}
            {detalle.isPending ? '…' : detalle.isError ? '—' : detalle.data}
          </p>
        )}
      </div>
      <p className="font-editorial text-4xl leading-none">
        {total.isPending ? '…' : total.isError ? '—' : total.data}
      </p>
    </Link>
  )
}
