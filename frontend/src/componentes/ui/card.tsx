// Copiado de shadcn/ui. Ver el comentario de button.tsx.
import type { ComponentProps } from 'react'

import { cn } from '../../lib/utils'

export function Card({ className, ...props }: ComponentProps<'div'>) {
  return (
    <div
      // Spec 022: 16px de radio y sin sombra.
      className={cn('rounded-2xl border border-ceniza bg-blanco', className)}
      {...props}
    />
  )
}

export function CardHeader({ className, ...props }: ComponentProps<'div'>) {
  return <div className={cn('flex flex-col gap-1 p-6 pb-2', className)} {...props} />
}

export function CardTitle({ className, ...props }: ComponentProps<'h2'>) {
  return (
    <h2 className={cn('font-editorial text-3xl leading-none', className)} {...props} />
  )
}

export function CardContent({ className, ...props }: ComponentProps<'div'>) {
  return <div className={cn('p-6 pt-2', className)} {...props} />
}
