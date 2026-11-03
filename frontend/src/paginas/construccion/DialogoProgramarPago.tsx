import { z } from 'zod'

import { useDocumentos } from '../../api/catalogo/consultas'
import {
  ETIQUETAS_TIPO_PAGO,
  type ProyectoDetalle,
  type TipoPago,
} from '../../api/construccion/consultas'
import { useProgramarPago } from '../../api/construccion/mutaciones'
import { Dialogo } from '../../componentes/comunes/Dialogo'
import {
  FormularioDatos,
  type CampoFormulario,
} from '../../componentes/comunes/FormularioDatos'
import { Button } from '../../componentes/ui/button'
import { fechaDeHoy, formatearMoneda } from '../../lib/formato'

const esquema = z.object({
  tipo: z.enum(['ANTICIPO', 'AVANCE', 'FINIQUITO', 'EXTRA'], {
    message: 'Elija el tipo de pago.',
  }),
  monto: z
    .string()
    .regex(/^\d+(\.\d{1,2})?$/, 'Escriba un número, con hasta dos decimales.'),
  fecha_programada: z.string().min(1, 'Elija la fecha programada.'),
  documento: z.string(),
  observaciones: z.string(),
  // No es un campo que se muestre: lleva la propiedad del proyecto hasta el
  // buscador de documentos, que la recibe en `valores`.
  propiedad: z.string(),
})

type Datos = z.infer<typeof esquema>

/**
 * Documentos de la propiedad del proyecto, para respaldar el pago (spec 017,
 * regla 20). Son pocos: se filtra por texto lo que devuelve la API. Que el
 * documento sea de la misma propiedad lo revisa también la API.
 */
function useOpcionesDocumentoDeLaPropiedad(texto: string, valores: Datos) {
  const consulta = useDocumentos(Number(valores.propiedad))
  const buscado = texto.toLowerCase()
  return {
    opciones: (consulta.data?.results ?? [])
      .filter((documento) => documento.nombre.toLowerCase().includes(buscado))
      .map((documento) => ({
        valor: String(documento.id),
        etiqueta: documento.nombre,
      })),
    cargando: consulta.isFetching,
  }
}

interface Props {
  proyecto: ProyectoDetalle
  abierto: boolean
  alCerrar: () => void
}

/**
 * Programa un pago a la constructora del proyecto (spec 018, §5). Va en la
 * moneda del proyecto (regla 20). El finiquito solo se ofrece con la obra
 * finalizada; si el pago supera el disponible, la API responde 409
 * PRESUPUESTO_EXCEDIDO y la salida es subir el presupuesto (regla 19).
 */
export function DialogoProgramarPago({ proyecto, abierto, alCerrar }: Props) {
  const programar = useProgramarPago()
  const finalizado = proyecto.estado === 'FINALIZADO'
  const moneda = proyecto.moneda.codigo

  const tipos = (Object.keys(ETIQUETAS_TIPO_PAGO) as TipoPago[]).filter(
    (tipo) => tipo !== 'FINIQUITO' || finalizado,
  )

  const campos: CampoFormulario<Datos>[] = [
    {
      nombre: 'tipo',
      etiqueta: 'Tipo de pago',
      tipo: 'seleccion',
      opciones: tipos.map((tipo) => ({
        valor: tipo,
        etiqueta: ETIQUETAS_TIPO_PAGO[tipo],
      })),
      ayuda: finalizado ? undefined : 'El finiquito se programa al finalizar la obra.',
    },
    { nombre: 'monto', etiqueta: `Monto (${moneda})`, tipo: 'numero' },
    { nombre: 'fecha_programada', etiqueta: 'Fecha programada', tipo: 'fecha' },
    {
      nombre: 'documento',
      etiqueta: 'Documento de respaldo',
      tipo: 'relacion',
      ayuda: 'Opcional. Un documento de la propiedad.',
      buscar: useOpcionesDocumentoDeLaPropiedad,
    },
    {
      nombre: 'observaciones',
      etiqueta: 'Observaciones',
      tipo: 'area',
      ayuda: 'Opcional.',
    },
  ]

  const guardar = async (datos: Datos) => {
    await programar.mutateAsync({
      proyecto: proyecto.id,
      tipo: datos.tipo,
      monto: datos.monto,
      fecha_programada: datos.fecha_programada,
      documento: datos.documento ? Number(datos.documento) : null,
      observaciones: datos.observaciones,
    })
    alCerrar()
  }

  return (
    <Dialogo abierto={abierto} titulo="Programar pago" alCerrar={alCerrar}>
      {abierto && (
        <>
          <p className="text-sm text-tenue">
            Disponible: {formatearMoneda(proyecto.disponible, moneda)}
          </p>
          <FormularioDatos
            campos={campos}
            esquema={esquema}
            valoresIniciales={{
              tipo: undefined,
              monto: '',
              fecha_programada: fechaDeHoy(),
              documento: '',
              observaciones: '',
              propiedad: String(proyecto.propiedad.id),
            }}
            alEnviar={guardar}
            textoEnviar="Programar pago"
          />
          <Button variant="outline" className="self-start" onClick={alCerrar}>
            Cancelar
          </Button>
        </>
      )}
    </Dialogo>
  )
}
