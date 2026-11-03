// Selector nativo con los estilos de shadcn/ui. El Select de shadcn usa Radix;
// para listas cortas (monedas, tipos, estados) el <select> del navegador basta
// y es accesible sin dependencias. Las relaciones largas usan CampoRelacion
// (spec 010, regla 11).
import type { ComponentProps } from 'react'

import { cn } from '../../lib/utils'

export function Select({ className, ...props }: ComponentProps<'select'>) {
  return (
    <select
      className={cn(
        // Spec 022: campo subrayado, sin caja. El foco engrosa la línea en tinta.
        'h-9 w-full rounded-none border-0 border-b border-ceniza bg-transparent px-0 text-sm focus-visible:border-b-2 focus-visible:border-tinta focus-visible:outline-none disabled:opacity-50 aria-invalid:border-red-600',
        className,
      )}
      {...props}
    />
  )
}
