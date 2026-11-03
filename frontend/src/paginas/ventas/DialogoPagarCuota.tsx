import { z } from 'zod'

import type { Cuota } from '../../api/ventas/consultas'
import { usePagarCuota } from '../../api/ventas/mutaciones'
import { Dialogo } from '../../componentes/comunes/Dialogo'
import {
  FormularioDatos,
  type CampoFormulario,
} from '../../componentes/comunes/FormularioDatos'
import { Button } from '../../componentes/ui/button'
import { fechaDeHoy, formatearMoneda } from '../../lib/formato'

const esquema = z.object({
  monto: z
    .string()
    .regex(/^\d+(\.\d{1,2})?$/, 'Escriba un número, con hasta dos decimales.'),
  fecha: z.string().min(1, 'Elija la fecha del pago.'),
  referencia: z.string().max(100),
})

type Datos = z.infer<typeof esquema>

const CAMPOS: CampoFormulario<Datos>[] = [
  { nombre: 'monto', etiqueta: 'Monto', tipo: 'numero' },
  { nombre: 'fecha', etiqueta: 'Fecha del pago', tipo: 'fecha' },
  { nombre: 'referencia', etiqueta: 'Referencia', tipo: 'texto', ayuda: 'Opcional.' },
]

interface Props {
  /** La cuota a pagar; null cierra el diálogo. */
  cuota: Cuota | null
  /** Código de la moneda del contrato, para mostrar el saldo. */
  moneda: string
  alCerrar: () => void
}

/**
 * Registra un pago de cuota. El monto se propone con el saldo y se puede bajar:
 * un pago parcial deja la cuota PARCIAL. Que no exceda el saldo y que la fecha
 * sea válida lo decide la API (spec 007, regla 16).
 */
export function DialogoPagarCuota({ cuota, moneda, alCerrar }: Props) {
  const pagar = usePagarCuota()

  const guardar = async (datos: Datos) => {
    if (cuota) {
      await pagar.mutateAsync({ id: cuota.id, ...datos })
      alCerrar()
    }
  }

  return (
    <Dialogo
      abierto={cuota !== null}
      titulo={`Pagar la cuota ${cuota?.numero ?? ''}`}
      alCerrar={alCerrar}
    >
      {cuota && (
        <>
          <p className="text-sm text-tenue">
            Falta pagar {formatearMoneda(cuota.saldo, moneda)}
          </p>
          <FormularioDatos
            key={cuota.id}
            campos={CAMPOS}
            esquema={esquema}
            valoresIniciales={{
              monto: cuota.saldo,
              fecha: fechaDeHoy(),
              referencia: '',
            }}
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
