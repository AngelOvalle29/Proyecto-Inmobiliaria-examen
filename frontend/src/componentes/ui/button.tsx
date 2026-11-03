// Copiado de shadcn/ui (https://ui.shadcn.com) y simplificado: sin la opción
// asChild, que necesitaría @radix-ui/react-slot. Los componentes de esta
// carpeta conservan su nombre original en inglés para que coincidan con la
// documentación de shadcn/ui (spec 010, §6).
import { cva, type VariantProps } from 'class-variance-authority'
import type { ComponentProps } from 'react'

import { cn } from '../../lib/utils'

// Spec 022: píldora con la etiqueta en mono, mayúsculas y tracking. Sin
// sombras ni degradados; el color de marca (óxido) se reserva a los paneles.
const variantesBoton = cva(
  'inline-flex items-center justify-center gap-2 rounded-full font-mono whitespace-nowrap text-xs tracking-etiqueta uppercase transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-oxido focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50',
  {
    variants: {
      variant: {
        default: 'bg-tinta text-crema hover:bg-negro',
        destructive: 'bg-red-700 text-crema hover:bg-red-800',
        outline: 'border border-tinta bg-transparent hover:bg-niebla',
        ghost: 'hover:bg-niebla',
        // Contorno crema, para fondos oscuros (menú lateral).
        inverse: 'border border-crema bg-transparent text-crema hover:bg-crema/10',
      },
      size: {
        default: 'h-9 px-5',
        sm: 'h-8 px-4',
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
