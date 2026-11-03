// Copiado de shadcn/ui. Ver el comentario de button.tsx.
import type { ComponentProps } from 'react'

import { cn } from '../../lib/utils'

export function Input({ className, ...props }: ComponentProps<'input'>) {
  return (
    <input
      className={cn(
        // Spec 022: campo subrayado, sin caja. El foco engrosa la línea en tinta.
        'h-9 w-full rounded-none border-0 border-b border-ceniza bg-transparent px-0 text-sm focus-visible:border-b-2 focus-visible:border-tinta focus-visible:outline-none disabled:opacity-50 aria-invalid:border-red-600',
        className,
      )}
      {...props}
    />
  )
}
