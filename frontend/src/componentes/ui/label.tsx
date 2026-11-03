// Copiado de shadcn/ui, sin Radix: un <label> nativo con sus estilos.
import type { ComponentProps } from 'react'

import { cn } from '../../lib/utils'

export function Label({ className, ...props }: ComponentProps<'label'>) {
  // Spec 022: etiqueta mono en mayúsculas, como las anotaciones del diseño.
  return (
    <label
      className={cn(
        'font-mono text-xs tracking-etiqueta text-tenue uppercase',
        className,
      )}
      {...props}
    />
  )
}
