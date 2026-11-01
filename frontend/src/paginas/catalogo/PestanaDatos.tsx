import { ETIQUETAS_ESTADO, type Propiedad } from '../../api/catalogo/consultas'
import { formatearFecha, formatearMoneda } from '../../lib/formato'

/** Pestaña Datos de la ficha: los datos generales de la propiedad. */
export function PestanaDatos({ propiedad }: { propiedad: Propiedad }) {
  const filas: [string, string][] = [
    ['Tipo', propiedad.tipo.nombre],
    ['Estado', ETIQUETAS_ESTADO[propiedad.estado]],
    ['Ubicación', `${propiedad.ciudad.nombre}, ${propiedad.ciudad.pais.nombre}`],
    ['Dirección', propiedad.direccion],
    ['Área del terreno', `${propiedad.area_m2} m²`],
    [
      'Área construida',
      propiedad.area_construida_m2 ? `${propiedad.area_construida_m2} m²` : '—',
    ],
    [
      'Precio de lista',
      formatearMoneda(propiedad.precio_lista, propiedad.moneda.codigo),
    ],
    ['Consulta pública', propiedad.es_publica ? 'Sí' : 'No'],
    ['Registrada', formatearFecha(propiedad.creado_en)],
  ]

  return (
    <div className="flex flex-col gap-4">
      <dl className="grid gap-x-6 gap-y-3 text-sm sm:grid-cols-2">
        {filas.map(([etiqueta, valor]) => (
          <div key={etiqueta}>
            <dt className="text-slate-500">{etiqueta}</dt>
            <dd className="font-medium">{valor}</dd>
          </div>
        ))}
      </dl>
      {propiedad.descripcion && (
        <div className="text-sm">
          <p className="text-slate-500">Descripción</p>
          <p>{propiedad.descripcion}</p>
        </div>
      )}
    </div>
  )
}
