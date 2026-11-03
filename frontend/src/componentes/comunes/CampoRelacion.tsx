import { useState } from 'react'

import { useRetraso } from '../../hooks/useRetraso'
import { Input } from '../ui/input'

export interface Opcion {
  valor: string
  etiqueta: string
}

/** Lo que devuelve el hook de búsqueda de un campo de relación. */
export interface ResultadoBusqueda {
  opciones: Opcion[]
  cargando: boolean
}

interface Props {
  id: string
  /** El id elegido, como texto; vacío si no hay ninguno. */
  valor: string
  alElegir: (valor: string) => void
  /**
   * Hook que busca en la API con el texto escrito (spec 010, regla 11). Es un
   * hook de api/<dominio>/, así que la búsqueda pasa por TanStack Query.
   */
  buscar: (texto: string) => ResultadoBusqueda
  deshabilitado?: boolean
  marcador?: string
  invalido?: boolean
  /**
   * Texto que se muestra al abrir el campo con un valor ya elegido, como la
   * ciudad actual de un cliente que se edita. Sin él, el campo tendría el id
   * pero se vería vacío (spec 010, regla 15).
   */
  etiquetaInicial?: string
}

/**
 * Campo para elegir un registro entre cientos (clientes, propiedades,
 * ciudades): se escribe parte del nombre y se elige de las coincidencias.
 */
export function CampoRelacion({
  id,
  valor,
  alElegir,
  buscar,
  deshabilitado,
  marcador = 'Escriba para buscar',
  invalido,
  etiquetaInicial = '',
}: Props) {
  // Solo es el valor de partida: después, el texto es lo que la persona escribe.
  const [texto, setTexto] = useState(etiquetaInicial)
  const [abierto, setAbierto] = useState(false)
  const textoRetrasado = useRetraso(texto)
  const { opciones, cargando } = buscar(textoRetrasado)

  // Cuando cambia el campo del que depende (el país), FormularioDatos le da a
  // este componente una key nueva: React lo vuelve a crear y el texto empieza
  // vacío. Por eso aquí no hace falta un efecto que lo borre.

  const elegir = (opcion: Opcion) => {
    setTexto(opcion.etiqueta)
    setAbierto(false)
    alElegir(opcion.valor)
  }

  return (
    <div className="relative">
      <Input
        id={id}
        value={texto}
        placeholder={marcador}
        disabled={deshabilitado}
        autoComplete="off"
        aria-invalid={invalido ? true : undefined}
        aria-expanded={abierto}
        role="combobox"
        onFocus={() => setAbierto(true)}
        // El retraso deja que el clic en una opción llegue antes de cerrar.
        onBlur={() => setTimeout(() => setAbierto(false), 150)}
        onChange={(evento) => {
          setTexto(evento.target.value)
          setAbierto(true)
          // Escribir de nuevo anula la elección anterior hasta elegir otra.
          if (valor !== '') {
            alElegir('')
          }
        }}
      />
      {abierto && !deshabilitado && (
        <ul
          role="listbox"
          className="absolute z-10 mt-1 max-h-56 w-full overflow-y-auto rounded-md border border-ceniza bg-blanco py-1 text-sm"
        >
          {cargando && <li className="px-3 py-2 text-tenue">Buscando…</li>}
          {!cargando && opciones.length === 0 && (
            <li className="px-3 py-2 text-tenue">Sin coincidencias.</li>
          )}
          {opciones.map((opcion) => (
            <li
              key={opcion.valor}
              role="option"
              aria-selected={opcion.valor === valor}
              className="cursor-pointer px-3 py-2 hover:bg-niebla"
              onMouseDown={(evento) => evento.preventDefault()}
              onClick={() => elegir(opcion)}
            >
              {opcion.etiqueta}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
