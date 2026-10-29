import { useState } from 'react'

import {
  ETIQUETAS_ESTADO,
  type EstadoPropiedad,
  type Propiedad,
} from '../../api/catalogo/consultas'
import { useCambiarEstadoPropiedad } from '../../api/catalogo/mutaciones'
import { leerErrorApi } from '../../api/errores'
import { Dialogo } from '../../componentes/comunes/Dialogo'
import { Button } from '../../componentes/ui/button'
import { Input } from '../../componentes/ui/input'
import { Label } from '../../componentes/ui/label'
import { Select } from '../../componentes/ui/select'

interface Props {
  /** La propiedad a cambiar; null cierra el diálogo. */
  propiedad: Propiedad | null
  alCerrar: () => void
}

/**
 * Pide el estado nuevo y el motivo antes de llamar a /cambiar-estado/. El
 * motivo es obligatorio porque queda en la bitácora (spec 003, §7). Es la
 * confirmación de esta acción (spec 010, regla 13).
 */
export function DialogoCambiarEstado({ propiedad, alCerrar }: Props) {
  const cambiar = useCambiarEstadoPropiedad()
  const [estado, setEstado] = useState<EstadoPropiedad | ''>('')
  const [motivo, setMotivo] = useState('')

  const cerrar = () => {
    setEstado('')
    setMotivo('')
    cambiar.reset()
    alCerrar()
  }

  const confirmar = () => {
    if (!propiedad || estado === '') {
      return
    }
    cambiar.mutate({ id: propiedad.id, estado, motivo }, { onSuccess: cerrar })
  }

  return (
    <Dialogo
      abierto={propiedad !== null}
      titulo={`Cambiar el estado de ${propiedad?.codigo ?? ''}`}
      alCerrar={cerrar}
    >
      <p className="text-sm text-slate-600">
        Estado actual: {propiedad && ETIQUETAS_ESTADO[propiedad.estado]}
      </p>
      {cambiar.isError && (
        <p role="alert" className="rounded-md bg-red-50 p-3 text-sm text-red-700">
          {leerErrorApi(cambiar.error).mensaje}
        </p>
      )}
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="estado-nuevo">Estado nuevo</Label>
        <Select
          id="estado-nuevo"
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
        <Label htmlFor="motivo">Motivo</Label>
        <Input
          id="motivo"
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
