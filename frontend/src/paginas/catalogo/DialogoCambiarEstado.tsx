import { useId, useState } from 'react'

import { ETIQUETAS_ESTADO, type EstadoPropiedad } from '../../api/catalogo/consultas'
import { useCambiarEstado } from '../../api/catalogo/mutaciones'
import { leerErrorApi } from '../../api/errores'
import { Dialogo } from '../../componentes/comunes/Dialogo'
import { Button } from '../../componentes/ui/button'
import { Input } from '../../componentes/ui/input'
import { Label } from '../../componentes/ui/label'
import { Select } from '../../componentes/ui/select'

/** Lo que el diálogo necesita de una propiedad o de una unidad. */
interface ConEstado {
  id: number
  codigo: string | null
  estado: EstadoPropiedad
}

interface Props {
  /** Qué se cambia: una propiedad o una unidad (spec 014, regla 4). */
  recurso: 'propiedades' | 'unidades'
  /** El elemento a cambiar; null cierra el diálogo. */
  elemento: ConEstado | null
  alCerrar: () => void
}

/**
 * Pide el estado nuevo y el motivo antes de llamar a /cambiar-estado/. El
 * motivo es obligatorio porque queda en la bitácora (spec 003, §7). Es la
 * confirmación de esta acción (spec 010, regla 13).
 */
export function DialogoCambiarEstado({ recurso, elemento, alCerrar }: Props) {
  const cambiar = useCambiarEstado(recurso)
  // La ficha dibuja dos de estos diálogos (propiedad y unidad): useId evita
  // ids repetidos, que harían que cada etiqueta apunte al campo del otro.
  const id = useId()
  const [estado, setEstado] = useState<EstadoPropiedad | ''>('')
  const [motivo, setMotivo] = useState('')

  const cerrar = () => {
    setEstado('')
    setMotivo('')
    cambiar.reset()
    alCerrar()
  }

  const confirmar = () => {
    if (!elemento || estado === '') {
      return
    }
    cambiar.mutate({ id: elemento.id, estado, motivo }, { onSuccess: cerrar })
  }

  return (
    <Dialogo
      abierto={elemento !== null}
      titulo={`Cambiar el estado de ${elemento?.codigo ?? ''}`}
      alCerrar={cerrar}
    >
      <p className="text-sm text-slate-600">
        Estado actual: {elemento && ETIQUETAS_ESTADO[elemento.estado]}
      </p>
      {cambiar.isError && (
        <p role="alert" className="rounded-md bg-red-50 p-3 text-sm text-red-700">
          {leerErrorApi(cambiar.error).mensaje}
        </p>
      )}
      <div className="flex flex-col gap-1.5">
        <Label htmlFor={`${id}-estado`}>Estado nuevo</Label>
        <Select
          id={`${id}-estado`}
          value={estado}
          onChange={(evento) => setEstado(evento.target.value as EstadoPropiedad)}
        >
          <option value="">Elija un estado</option>
          {Object.entries(ETIQUETAS_ESTADO).map(([valor, etiqueta]) => (
            <option key={valor} value={valor}>
              {etiqueta}
            </option>
          ))}
        </Select>
      </div>
      <div className="flex flex-col gap-1.5">
        <Label htmlFor={`${id}-motivo`}>Motivo</Label>
        <Input
          id={`${id}-motivo`}
          value={motivo}
          maxLength={255}
          onChange={(evento) => setMotivo(evento.target.value)}
        />
      </div>
      <div className="flex justify-end gap-2">
        <Button variant="outline" onClick={cerrar} disabled={cambiar.isPending}>
          Cancelar
        </Button>
        <Button
          onClick={confirmar}
          disabled={estado === '' || motivo.trim() === '' || cambiar.isPending}
        >
          {cambiar.isPending ? 'Guardando…' : 'Cambiar estado'}
        </Button>
      </div>
    </Dialogo>
  )
}
