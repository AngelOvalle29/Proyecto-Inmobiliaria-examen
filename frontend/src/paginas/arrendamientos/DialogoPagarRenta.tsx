import { useState } from 'react'

import type {
  ArrendamientoDetalle,
  PagoRenta,
} from '../../api/arrendamientos/consultas'
import { usePagarRenta } from '../../api/arrendamientos/mutaciones'
import { leerErrorApi } from '../../api/errores'
import { Dialogo } from '../../componentes/comunes/Dialogo'
import { Button } from '../../componentes/ui/button'
import { Input } from '../../componentes/ui/input'
import { Label } from '../../componentes/ui/label'
import { fechaDeHoy, formatearMoneda } from '../../lib/formato'

/**
 * El monto que correspondería a esa fecha. Es solo una propuesta para no
 * escribirlo mal: la regla vive en calcular_recargo del backend, que es quien
 * valida (spec 012, §5). Las fechas aaaa-mm-dd se comparan como texto.
 */
function proponerMonto(
  pago: PagoRenta,
  contrato: ArrendamientoDetalle,
  fecha: string,
): string {
  const limite = new Date(`${pago.fecha_vencimiento}T00:00:00Z`)
  limite.setUTCDate(limite.getUTCDate() + (contrato.dias_gracia ?? 0))
  const tarde = fecha > limite.toISOString().slice(0, 10)
  const renta = Number(pago.monto)
  // renta · porcentaje / 100, en centavos, para redondear como la API.
  const recargo = tarde ? Math.round(renta * Number(contrato.porcentaje_mora)) / 100 : 0
  return (renta + recargo).toFixed(2)
}

interface Props {
  /** El pago a registrar; null cierra el diálogo. */
  pago: PagoRenta | null
  contrato: ArrendamientoDetalle
  alCerrar: () => void
}

/**
 * Pago de un mes de renta. No usa FormularioDatos porque el monto cambia con la
 * fecha elegida, como DialogoCambiarEstado arma sus propios campos.
 */
export function DialogoPagarRenta({ pago, contrato, alCerrar }: Props) {
  return (
    <Dialogo
      abierto={pago !== null}
      titulo={`Pagar ${pago ? `${pago.periodo_mes}/${pago.periodo_anio}` : ''}`}
      alCerrar={alCerrar}
    >
      {pago && (
        <Contenido key={pago.id} pago={pago} contrato={contrato} alCerrar={alCerrar} />
      )}
    </Dialogo>
  )
}

function Contenido({
  pago,
  contrato,
  alCerrar,
}: {
  pago: PagoRenta
  contrato: ArrendamientoDetalle
  alCerrar: () => void
}) {
  const pagar = usePagarRenta()
  const [fecha, setFecha] = useState(fechaDeHoy())
  const [monto, setMonto] = useState(proponerMonto(pago, contrato, fechaDeHoy()))
  const [referencia, setReferencia] = useState('')

  const cambiarFecha = (nueva: string) => {
    setFecha(nueva)
    if (nueva) {
      setMonto(proponerMonto(pago, contrato, nueva))
    }
  }

  return (
    <>
      <p className="text-sm text-tenue">
        Renta: {formatearMoneda(pago.monto, contrato.moneda.codigo)}
      </p>
      {pagar.isError && (
        <p role="alert" className="rounded-md bg-red-50 p-3 text-sm text-red-700">
          {leerErrorApi(pagar.error).mensaje}
        </p>
      )}
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="pago-fecha">Fecha del pago</Label>
        <Input
          id="pago-fecha"
          type="date"
          value={fecha}
          onChange={(evento) => cambiarFecha(evento.target.value)}
        />
      </div>
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="pago-monto">Monto recibido</Label>
        <Input
          id="pago-monto"
          inputMode="decimal"
          value={monto}
          onChange={(evento) => setMonto(evento.target.value)}
        />
        <p className="text-xs text-tenue">
          Propuesto con la renta y el recargo de esa fecha. Confírmelo.
        </p>
      </div>
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="pago-referencia">Referencia</Label>
        <Input
          id="pago-referencia"
          maxLength={100}
          value={referencia}
          onChange={(evento) => setReferencia(evento.target.value)}
        />
      </div>
      <div className="flex justify-end gap-2">
        <Button variant="outline" onClick={alCerrar} disabled={pagar.isPending}>
          Cancelar
        </Button>
        <Button
          disabled={fecha === '' || monto === '' || pagar.isPending}
          onClick={() =>
            pagar.mutate(
              { id: pago.id, fecha, monto, referencia },
              { onSuccess: alCerrar },
            )
          }
        >
          {pagar.isPending ? 'Guardando…' : 'Registrar pago'}
        </Button>
      </div>
    </>
  )
}
