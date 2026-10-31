// Copiado de shadcn/ui, sin Radix: un <label> nativo con sus estilos.
import type { ComponentProps } from 'react'

import { cn } from '../../lib/utils'

export function Label({ className, ...props }: ComponentProps<'label'>) {
  return <label className={cn('text-sm font-medium', className)} {...props} />
}
