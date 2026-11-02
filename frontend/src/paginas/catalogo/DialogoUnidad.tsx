import { z } from 'zod'

import type { Unidad } from '../../api/catalogo/consultas'
import {
  useActualizarUnidad,
  useCrearUnidad,
  type DatosUnidad,
} from '../../api/catalogo/mutaciones'
import { useMonedas } from '../../api/core/consultas'
import { Dialogo } from '../../componentes/comunes/Dialogo'
import {
  FormularioDatos,
  type CampoFormulario,
} from '../../componentes/comunes/FormularioDatos'
import { Button } from '../../componentes/ui/button'

// Solo el formato; que el área y el precio sean mayores que cero lo valida la
// API, y su error aparece junto al campo.
const decimal = z
  .string()
  .regex(/^\d+(\.\d{1,2})?$/, 'Escriba un número, con hasta dos decimales.')
const entero = z.string().regex(/^-?\d+$/, 'Escriba un número entero.')

const esquemaUnidad = z.object({
  codigo: z.string().min(1, 'Escriba el código.').max(20),
  nivel: entero,
  area_m2: decimal,
  habitaciones: entero,
  banos: entero,
  moneda_id: z.string().min(1, 'Elija la moneda.'),
  precio_lista: decimal,
})

type DatosFormulario = z.infer<typeof esquemaUnidad>

const UNIDAD_VACIA: DatosFormulario = {
  codigo: '',
  nivel: '',
  area_m2: '',
  habitaciones: '0',
  banos: '0',
  moneda_id: '',
  precio_lista: '',
}

interface Props {
  propiedad: number
  abierto: boolean
  /** La unidad a editar; sin ella, el diálogo crea una nueva. */
  unidad: Unidad | null
  alCerrar: () => void
}

/**
 * Crear o editar una unidad (spec 014, regla 4): un diálogo de la ficha con
 * FormularioDatos adentro, porque pide varios datos. El estado no se edita
 * aquí: tiene su propia acción.
 */
export function DialogoUnidad({ propiedad, abierto, unidad, alCerrar }: Props) {
  const crear = useCrearUnidad(propiedad)
  const actualizar = useActualizarUnidad()
  const monedas = useMonedas()

  const campos: CampoFormulario<DatosFormulario>[] = [
    {
      nombre: 'codigo',
      etiqueta: 'Código',
      tipo: 'texto',
      ayuda: 'Por ejemplo, A-101.',
    },
    { nombre: 'nivel', etiqueta: 'Nivel', tipo: 'numero' },
    { nombre: 'area_m2', etiqueta: 'Área (m²)', tipo: 'numero' },
    { nombre: 'habitaciones', etiqueta: 'Habitaciones', tipo: 'numero' },
    { nombre: 'banos', etiqueta: 'Baños', tipo: 'numero' },
    {
      nombre: 'moneda_id',
      etiqueta: 'Moneda',
      tipo: 'seleccion',
      opciones: (monedas.data ?? []).map((moneda) => ({
        valor: String(moneda.id),
        etiqueta: `${moneda.codigo} · ${moneda.nombre}`,
      })),
    },
    { nombre: 'precio_lista', etiqueta: 'Precio de lista', tipo: 'numero' },
  ]

  const valoresIniciales: DatosFormulario = unidad
    ? {
        codigo: unidad.codigo,
        nivel: String(unidad.nivel),
        area_m2: unidad.area_m2,
        habitaciones: String(unidad.habitaciones ?? 0),
        banos: String(unidad.banos ?? 0),
        moneda_id: String(unidad.moneda.id),
        precio_lista: unidad.precio_lista,
      }
    : UNIDAD_VACIA

  const guardar = async (datos: DatosFormulario) => {
    const paraApi: DatosUnidad = {
      codigo: datos.codigo,
      nivel: Number(datos.nivel),
      area_m2: datos.area_m2,
      habitaciones: Number(datos.habitaciones),
      banos: Number(datos.banos),
      moneda_id: Number(datos.moneda_id),
      precio_lista: datos.precio_lista,
    }
    if (unidad) {
      await actualizar.mutateAsync({ id: unidad.id, ...paraApi })
    } else {
      await crear.mutateAsync(paraApi)
    }
    alCerrar()
  }

  return (
    <Dialogo
      abierto={abierto}
      titulo={unidad ? `Editar la unidad ${unidad.codigo}` : 'Nueva unidad'}
      alCerrar={alCerrar}
    >
      {/* Se dibuja solo abierto, con key por unidad: los valores iniciales se
          fijan al montar, así cada apertura empieza limpia. */}
      {abierto && (
        <FormularioDatos
          key={unidad?.id ?? 'nueva'}
          campos={campos}
          esquema={esquemaUnidad}
          valoresIniciales={valoresIniciales}
          alEnviar={guardar}
          textoEnviar={unidad ? 'Guardar cambios' : 'Crear unidad'}
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
