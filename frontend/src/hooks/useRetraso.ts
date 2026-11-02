import { useEffect, useState } from 'react'

/**
 * El valor, pero solo después de que deja de cambiar durante `ms` milisegundos.
 * Así una búsqueda mientras se escribe consulta la API una vez por pausa y no
 * una vez por tecla.
 */
export function useRetraso<T>(valor: T, ms = 300): T {
  const [retrasado, setRetrasado] = useState(valor)

  useEffect(() => {
    const temporizador = setTimeout(() => setRetrasado(valor), ms)
    return () => clearTimeout(temporizador)
  }, [valor, ms])

  return retrasado
}
