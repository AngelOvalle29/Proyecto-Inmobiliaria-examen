import { z } from 'zod'

import type { PagoConstructora } from '../../api/construccion/consultas'
import { usePagarPago } from '../../api/construccion/mutaciones'
import { Dialogo } from '../../componentes/comunes/Dialogo'
import {
  FormularioDatos,
  type CampoFormulario,
} from '../../componentes/comunes/FormularioDatos'
import { Button } from '../../componentes/ui/button'
import { fechaDeHoy, formatearMoneda } from '../../lib/formato'

const esquema = z.object({
  // Que no sea futura ni anterior al inicio de la obra (salvo un anticipo) lo
  // revisa la API (spec 017, regla 21).
  fecha_pago: z.string().min(1, 'Elija la fecha del pago.'),
  referencia_pago: z
    .string()
    .trim()
    .min(1, 'Escriba la referencia: número de transferencia o de cheque.')
    .max(100),
})

type Datos = z.infer<typeof esquema>

const CAMPOS: CampoFormulario<Datos>[] = [
  { nombre: 'fecha_pago', etiqueta: 'Fecha del pago', tipo: 'fecha' },
  { nombre: 'referencia_pago', etiqueta: 'Referencia', tipo: 'texto' },
]

interface Props {
  /** El pago a registrar; null cierra el diálogo. */
  pago: PagoConstructora | null
  alCerrar: () => void
}

/**
 * Registra que un pago programado salió (spec 018, §5). Después de pagarlo ya
 * no se ofrecen Pagar ni Anular: la tabla solo los muestra en PROGRAMADO.
 */
export function DialogoPagar({ pago, alCerrar }: Props) {
  const pagar = usePagarPago()

  const guardar = async (datos: Datos) => {
    if (pago) {
      await pagar.mutateAsync({ id: pago.id, ...datos })
      alCerrar()
    }
  }

  return (
    <Dialogo
      abierto={pago !== null}
      titulo={`Pagar ${pago?.codigo ?? ''}`}
      alCerrar={alCerrar}
    >
      {pago && (
        <>
          <p className="text-sm text-slate-600">
            {formatearMoneda(pago.monto, pago.moneda.codigo)} a{' '}
            {pago.proyecto.constructora.nombre}
          </p>
          <FormularioDatos
            key={pago.id}
            campos={CAMPOS}
            esquema={esquema}
            valoresIniciales={{ fecha_pago: fechaDeHoy(), referencia_pago: '' }}
            alEnviar={guardar}
            textoEnviar="Registrar pago"
          />
          <Button variant="outline" className="self-start" onClick={alCerrar}>
            Cancelar
          </Button>
        </>
      )}
    </Dialogo>
  )
}
