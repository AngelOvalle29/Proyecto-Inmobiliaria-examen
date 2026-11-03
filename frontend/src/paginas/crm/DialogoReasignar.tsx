import { useState } from 'react'

import { nombreCliente, useOpcionesAgente, type Cliente } from '../../api/crm/consultas'
import { useReasignarCliente } from '../../api/crm/mutaciones'
import { leerErrorApi } from '../../api/errores'
import { CampoRelacion } from '../../componentes/comunes/CampoRelacion'
import { Dialogo } from '../../componentes/comunes/Dialogo'
import { Button } from '../../componentes/ui/button'
import { Label } from '../../componentes/ui/label'

interface Props {
  /** El cliente a reasignar; null cierra el diálogo. */
  cliente: Cliente | null
  alCerrar: () => void
}

/**
 * Pasa el cliente a otro agente (spec 004, regla 11). Es un diálogo de la
 * página porque pide un dato, como DialogoCambiarEstado (spec 012, regla 1).
 * Contenido se monta solo mientras hay cliente: así, al volver a abrir, el
 * buscador de agente empieza vacío.
 */
export function DialogoReasignar({ cliente, alCerrar }: Props) {
  return (
    <Dialogo
      abierto={cliente !== null}
      titulo={`Reasignar ${cliente?.codigo ?? ''}`}
      alCerrar={alCerrar}
    >
      {cliente && <Contenido cliente={cliente} alCerrar={alCerrar} />}
    </Dialogo>
  )
}

function Contenido({ cliente, alCerrar }: { cliente: Cliente; alCerrar: () => void }) {
  const reasignar = useReasignarCliente()
  const [agente, setAgente] = useState('')

  return (
    <>
      <p className="text-sm text-tenue">
        {nombreCliente(cliente)} · agente actual:{' '}
        {cliente.agente_asignado.nombre_completo}
      </p>
      {reasignar.isError && (
        <p role="alert" className="rounded-md bg-red-50 p-3 text-sm text-red-700">
          {leerErrorApi(reasignar.error).mensaje}
        </p>
      )}
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="agente-nuevo">Agente nuevo</Label>
        <CampoRelacion
          id="agente-nuevo"
          valor={agente}
          alElegir={setAgente}
          buscar={useOpcionesAgente}
        />
      </div>
      <div className="flex justify-end gap-2">
        <Button variant="outline" onClick={alCerrar} disabled={reasignar.isPending}>
          Cancelar
        </Button>
        <Button
          disabled={agente === '' || reasignar.isPending}
          onClick={() =>
            reasignar.mutate(
              { id: cliente.id, agente: Number(agente) },
              { onSuccess: alCerrar },
            )
          }
        >
          {reasignar.isPending ? 'Guardando…' : 'Reasignar'}
        </Button>
      </div>
    </>
  )
}
