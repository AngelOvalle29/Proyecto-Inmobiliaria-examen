import type { ReactNode } from 'react'

import type { CitaAgente } from '../../api/ia/mutaciones'

/** Las marcas [1], [2]… que el modelo pone en el texto (spec 005, regla 2). */
const MARCA = /\[(\d+)\]/g

interface Props {
  respuesta: string
  citas: CitaAgente[]
  /** Distingue los enlaces de cada respuesta: la pantalla muestra varias. */
  prefijo: string
}

/**
 * La respuesta del agente con cada [n] enlazado a su cita (spec 018, regla
 * 9). Si el modelo menciona un número que no está entre las citas, se deja
 * como texto: no se enlaza a una fuente que no existe.
 */
export function RespuestaConCitas({ respuesta, citas, prefijo }: Props) {
  const numeros = new Set(citas.map((cita) => cita.numero))
  const partes: ReactNode[] = []
  let desde = 0
  for (const marca of respuesta.matchAll(MARCA)) {
    const numero = Number(marca[1])
    partes.push(respuesta.slice(desde, marca.index))
    partes.push(
      numeros.has(numero) ? (
        <a
          key={marca.index}
          href={`#${prefijo}-cita-${numero}`}
          className="font-medium text-oxido hover:underline"
        >
          [{numero}]
        </a>
      ) : (
        marca[0]
      ),
    )
    desde = marca.index + marca[0].length
  }
  partes.push(respuesta.slice(desde))

  return (
    <div className="flex flex-col gap-3">
      <p className="text-sm whitespace-pre-line">{partes}</p>
      {citas.length > 0 && (
        <ol className="flex flex-col gap-2 border-t border-ceniza pt-3">
          {citas.map((cita) => (
            <li
              key={cita.numero}
              id={`${prefijo}-cita-${cita.numero}`}
              className="text-xs text-tenue"
            >
              <span className="font-medium text-tinta">
                [{cita.numero}] {cita.documento} · {cita.seccion}
              </span>
              <span className="block italic">«{cita.extracto}…»</span>
            </li>
          ))}
        </ol>
      )}
    </div>
  )
}
