import { useEffect, useState } from 'react'

import { useEstadoServicio } from '../../api/core/consultas'
import { Button } from '../../componentes/ui/button'

// A partir de cuánto tiempo de espera se avisa que el servidor está despertando.
const ESPERA_ANTES_DE_AVISAR_MS = 5_000

/**
 * Muestra si la API y su base de datos responden. Nació como la página mínima de
 * la spec 002 (§6); desde la spec 010 es una tarjeta de la pantalla de inicio.
 */
export function EstadoServicio() {
  const consulta = useEstadoServicio()
  const despertando = useDemora(consulta.isFetching, ESPERA_ANTES_DE_AVISAR_MS)

  let mensaje: string
  if (consulta.isFetching) {
    mensaje = despertando
      ? 'El servidor está despertando. En el plan gratuito puede tardar alrededor de un minuto.'
      : 'Consultando el estado de la API…'
  } else if (consulta.isError) {
    mensaje = `No se pudo conectar con la API (${import.meta.env.VITE_API_URL}).`
  } else if (consulta.data?.base_datos === 'ok') {
    mensaje = 'API en línea · base de datos: ok'
  } else {
    mensaje = 'La API responde, pero su base de datos no.'
  }

  return (
    <div className="flex flex-col items-start gap-3">
      <p role="status" className="text-sm">
        {mensaje}
      </p>
      <Button
        variant="outline"
        size="sm"
        onClick={() => consulta.refetch()}
        disabled={consulta.isFetching}
      >
        Volver a consultar
      </Button>
    </div>
  )
}

/** true si `activo` lleva más de `ms` milisegundos en true. */
function useDemora(activo: boolean, ms: number): boolean {
  const [vencida, setVencida] = useState(false)

  useEffect(() => {
    if (!activo) {
      return
    }
    const temporizador = setTimeout(() => setVencida(true), ms)
    return () => {
      clearTimeout(temporizador)
      setVencida(false)
    }
  }, [activo, ms])

  return activo && vencida
}
