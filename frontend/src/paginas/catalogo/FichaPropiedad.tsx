import { useState, type ReactNode } from 'react'
import { useNavigate, useParams, useSearchParams } from 'react-router'

import {
  ETIQUETAS_ESTADO,
  usePropiedad,
  useTiposPropiedad,
  type Propiedad,
} from '../../api/catalogo/consultas'
import { leerErrorApi } from '../../api/errores'
import { Button } from '../../componentes/ui/button'
import { Card, CardContent } from '../../componentes/ui/card'
import { cn } from '../../lib/utils'
import { ESCRIBEN_CATALOGO, rolPermitido } from '../../menu'
import { useSesion } from '../../sesion/useSesion'
import { DialogoCambiarEstado } from './DialogoCambiarEstado'
import { PestanaAvaluos } from './PestanaAvaluos'
import { PestanaDatos } from './PestanaDatos'
import { PestanaDocumentos } from './PestanaDocumentos'
import { PestanaUnidades } from './PestanaUnidades'

type Pestana = 'datos' | 'unidades' | 'avaluos' | 'documentos'

const ETIQUETAS_PESTANA: Record<Pestana, string> = {
  datos: 'Datos',
  unidades: 'Unidades',
  avaluos: 'Avalúos',
  documentos: 'Documentos',
}

/**
 * Ficha de una propiedad (spec 014, regla 1): una página con cuatro pestañas.
 * La pestaña elegida va en la URL (?pestana=documentos), así se puede recargar
 * o compartir. Solo se dibuja la pestaña abierta, así que cada una pide sus
 * datos a la API únicamente cuando alguien la mira.
 */
export function FichaPropiedad() {
  const { id } = useParams()
  const consulta = usePropiedad(Number(id))

  if (consulta.isPending) {
    return <p className="text-sm text-slate-500">Cargando la propiedad…</p>
  }
  if (consulta.isError) {
    return (
      <p className="text-sm text-red-700">{leerErrorApi(consulta.error).mensaje}</p>
    )
  }
  return <Ficha propiedad={consulta.data} />
}

function Ficha({ propiedad }: { propiedad: Propiedad }) {
  const navegar = useNavigate()
  const { usuario } = useSesion()
  const [parametros, setParametros] = useSearchParams()
  const [cambiandoEstado, setCambiandoEstado] = useState(false)
  const tipos = useTiposPropiedad()

  // Regla 3: la pestaña Unidades solo existe si el tipo las admite. El
  // resumen del tipo que trae la propiedad no dice si las admite; la lista de
  // tipos sí.
  const admiteUnidades =
    tipos.data?.find((tipo) => tipo.id === propiedad.tipo.id)?.requiere_unidades ??
    false
  const pestanas: Pestana[] = admiteUnidades
    ? ['datos', 'unidades', 'avaluos', 'documentos']
    : ['datos', 'avaluos', 'documentos']

  const pedida = parametros.get('pestana') as Pestana | null
  const abierta: Pestana = pedida && pestanas.includes(pedida) ? pedida : 'datos'
  const puedeEscribir = rolPermitido(usuario?.rol ?? '', ESCRIBEN_CATALOGO)

  let contenido: ReactNode
  if (abierta === 'datos') {
    contenido = <PestanaDatos propiedad={propiedad} />
  } else if (abierta === 'unidades') {
    contenido = (
      <PestanaUnidades propiedad={propiedad.id} puedeEscribir={puedeEscribir} />
    )
  } else if (abierta === 'avaluos') {
    contenido = (
      <PestanaAvaluos propiedad={propiedad.id} puedeEscribir={puedeEscribir} />
    )
  } else {
    contenido = (
      <PestanaDocumentos propiedad={propiedad.id} puedeEscribir={puedeEscribir} />
    )
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-sm text-slate-500">{propiedad.codigo}</p>
          <h1 className="text-2xl font-semibold">{propiedad.nombre}</h1>
          <p className="text-sm text-slate-600">
            {propiedad.tipo.nombre} · {ETIQUETAS_ESTADO[propiedad.estado]}
          </p>
        </div>
        {puedeEscribir && (
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => setCambiandoEstado(true)}>
              Cambiar estado
            </Button>
            <Button
              onClick={() => navegar(`/catalogo/propiedades/${propiedad.id}/editar`)}
            >
              Editar
            </Button>
          </div>
        )}
      </div>

      <div role="tablist" className="flex gap-1 border-b border-slate-200">
        {pestanas.map((pestana) => (
          <button
            key={pestana}
            role="tab"
            aria-selected={pestana === abierta}
            className={cn(
              '-mb-px border-b-2 px-4 py-2 text-sm',
              pestana === abierta
                ? 'border-slate-900 font-medium'
                : 'border-transparent text-slate-500 hover:text-slate-800',
            )}
            onClick={() => setParametros({ pestana })}
          >
            {ETIQUETAS_PESTANA[pestana]}
          </button>
        ))}
      </div>

      <Card>
        <CardContent className="pt-6">{contenido}</CardContent>
      </Card>

      <DialogoCambiarEstado
        recurso="propiedades"
        elemento={cambiandoEstado ? propiedad : null}
        alCerrar={() => setCambiandoEstado(false)}
      />
    </div>
  )
}
