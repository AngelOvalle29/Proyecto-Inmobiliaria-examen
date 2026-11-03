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
      className="m-auto w-full max-w-md rounded-2xl border border-ceniza p-0 backdrop:bg-tinta/40"
    >
      <div className="flex flex-col gap-4 p-6">
        <h2 className="font-editorial text-2xl">{titulo}</h2>
        {children}
      </div>
    </dialog>
  )
}
