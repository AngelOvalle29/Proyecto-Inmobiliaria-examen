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
        'h-9 w-full rounded-md border border-slate-300 bg-white px-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-400 disabled:opacity-50 aria-invalid:border-red-500',
        className,
      )}
      {...props}
    />
  )
}
