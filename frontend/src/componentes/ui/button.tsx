// Copiado de shadcn/ui (https://ui.shadcn.com) y simplificado: sin la opción
// asChild, que necesitaría @radix-ui/react-slot. Los componentes de esta
// carpeta conservan su nombre original en inglés para que coincidan con la
// documentación de shadcn/ui (spec 010, §6).
import { cva, type VariantProps } from 'class-variance-authority'
import type { ComponentProps } from 'react'

import { cn } from '../../lib/utils'

const variantesBoton = cva(
  'inline-flex items-center justify-center gap-2 rounded-md text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-400 disabled:pointer-events-none disabled:opacity-50',
  {
    variants: {
      variant: {
        default: 'bg-slate-900 text-white hover:bg-slate-800',
        destructive: 'bg-red-600 text-white hover:bg-red-700',
        outline: 'border border-slate-300 bg-white hover:bg-slate-100',
        ghost: 'hover:bg-slate-100',
      },
      size: {
        default: 'h-9 px-4 py-2',
        sm: 'h-8 px-3',
      },
    },
    defaultVariants: { variant: 'default', size: 'default' },
  },
)

export function Button({
  className,
  variant,
  size,
  ...props
}: ComponentProps<'button'> & VariantProps<typeof variantesBoton>) {
  return (
    <button className={cn(variantesBoton({ variant, size }), className)} {...props} />
  )
}
