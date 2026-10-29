// Copiado de shadcn/ui. Ver el comentario de button.tsx.
import type { ComponentProps } from 'react'

import { cn } from '../../lib/utils'

export function Input({ className, ...props }: ComponentProps<'input'>) {
  return (
    <input
      className={cn(
        'h-9 w-full rounded-md border border-slate-300 bg-white px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-400 disabled:opacity-50 aria-invalid:border-red-500',
        className,
      )}
      {...props}
    />
  )
}
