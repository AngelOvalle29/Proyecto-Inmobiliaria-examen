import { useEffect, useRef, type ReactNode } from 'react'

interface Props {
  abierto: boolean
  titulo: string
  alCerrar: () => void
  children: ReactNode
}

/**
 * Ventana modal con el <dialog> del navegador. showModal() ya bloquea el resto
 * de la página, atrapa el foco y cierra con Escape, sin dependencias.
 */
export function Dialogo({ abierto, titulo, alCerrar, children }: Props) {
  const referencia = useRef<HTMLDialogElement>(null)

  useEffect(() => {
    const dialogo = referencia.current
    if (!dialogo) {
      return
    }
    if (abierto && !dialogo.open) {
      dialogo.showModal()
    } else if (!abierto && dialogo.open) {
      dialogo.close()
    }
  }, [abierto])

  return (
    <dialog
      ref={referencia}
      onClose={alCerrar}
      className="m-auto w-full max-w-md rounded-lg border border-slate-200 p-0 shadow-lg backdrop:bg-slate-900/40"
    >
      <div className="flex flex-col gap-4 p-6">
        <h2 className="text-lg font-semibold">{titulo}</h2>
        {children}
      </div>
    </dialog>
  )
}
