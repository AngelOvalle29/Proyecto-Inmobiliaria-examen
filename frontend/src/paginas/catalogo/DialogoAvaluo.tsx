import { z } from 'zod'

import { useDocumentos } from '../../api/catalogo/consultas'
import { useRegistrarAvaluo } from '../../api/catalogo/mutaciones'
import { useMonedas } from '../../api/core/consultas'
import { Dialogo } from '../../componentes/comunes/Dialogo'
import {
  FormularioDatos,
  type CampoFormulario,
} from '../../componentes/comunes/FormularioDatos'
import { Button } from '../../componentes/ui/button'
import { fechaDeHoy, formatearFecha } from '../../lib/formato'

// Solo el formato. Que la fecha no sea futura y que el valor sea mayor que
// cero lo valida la API (spec 011, regla 2), y su error sale junto al campo.
const esquemaAvaluo = z.object({
  fecha: z.string().min(1, 'Elija la fecha.'),
  valor: z
    .string()
    .regex(/^\d+(\.\d{1,2})?$/, 'Escriba un número, con hasta dos decimales.'),
  moneda_id: z.string().min(1, 'Elija la moneda.'),
  perito: z.string().min(1, 'Escriba el nombre del perito.').max(150),
  metodologia: z.string().min(1, 'Escriba la metodología.').max(150),
  documento_id: z.string(),
  observaciones: z.string(),
})

type DatosFormulario = z.infer<typeof esquemaAvaluo>

interface Props {
  propiedad: number
  abierto: boolean
  alCerrar: () => void
}

/**
 * Registrar un avalúo (spec 014, regla 4). No hay editar: un avalúo
 * equivocado se desactiva y se registra otro (spec 011, regla 3).
 */
export function DialogoAvaluo({ propiedad, abierto, alCerrar }: Props) {
  const registrar = useRegistrarAvaluo(propiedad)
  const monedas = useMonedas()
  // El respaldo se elige entre los documentos de tipo Avalúo de la propiedad.
  // Una propiedad tiene pocos, así que caben en la primera página.
  const documentos = useDocumentos(propiedad, { tipo: 'AVALUO' })

  const campos: CampoFormulario<DatosFormulario>[] = [
    { nombre: 'fecha', etiqueta: 'Fecha', tipo: 'fecha' },
    {
      nombre: 'moneda_id',
      etiqueta: 'Moneda',
      tipo: 'seleccion',
      opciones: (monedas.data ?? []).map((moneda) => ({
        valor: String(moneda.id),
        etiqueta: `${moneda.codigo} · ${moneda.nombre}`,
      })),
    },
    { nombre: 'valor', etiqueta: 'Valor', tipo: 'numero' },
    { nombre: 'perito', etiqueta: 'Perito', tipo: 'texto' },
    {
      nombre: 'metodologia',
      etiqueta: 'Metodología',
      tipo: 'texto',
      ayuda: 'Por ejemplo, comparativo de mercado.',
    },
    {
      nombre: 'documento_id',
      etiqueta: 'Documento de respaldo',
      tipo: 'seleccion',
      ayuda: 'Opcional. Se suben en la pestaña Documentos, con el tipo Avalúo.',
      opciones: (documentos.data?.results ?? []).map((documento) => ({
        valor: String(documento.id),
        etiqueta: `${documento.nombre} (${formatearFecha(documento.fecha_emision)})`,
      })),
    },
    {
      nombre: 'observaciones',
      etiqueta: 'Observaciones',
      tipo: 'area',
      ayuda: 'Opcional.',
    },
  ]

  const valoresIniciales: DatosFormulario = {
    fecha: fechaDeHoy(),
    valor: '',
    moneda_id: '',
    perito: '',
    metodologia: '',
    documento_id: '',
    observaciones: '',
  }

  const guardar = async (datos: DatosFormulario) => {
    await registrar.mutateAsync({
      fecha: datos.fecha,
      valor: datos.valor,
      moneda_id: Number(datos.moneda_id),
      perito: datos.perito,
      metodologia: datos.metodologia,
      documento_id: datos.documento_id ? Number(datos.documento_id) : null,
      observaciones: datos.observaciones,
    })
    alCerrar()
  }

  return (
    <Dialogo abierto={abierto} titulo="Registrar avalúo" alCerrar={alCerrar}>
      {/* Se dibuja solo abierto: cada apertura empieza con el formulario limpio. */}
      {abierto && (
        <FormularioDatos
          campos={campos}
          esquema={esquemaAvaluo}
          valoresIniciales={valoresIniciales}
          alEnviar={guardar}
          textoEnviar="Registrar avalúo"
        />
      )}
      <div className="flex justify-end">
        <Button variant="outline" onClick={alCerrar}>
          Cancelar
        </Button>
      </div>
    </Dialogo>
  )
}
