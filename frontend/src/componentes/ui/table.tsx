// Copiado de shadcn/ui. Ver el comentario de button.tsx. Solo estilos: la
// lógica de columnas y paginación vive en componentes/comunes/TablaDatos.tsx.
import type { ComponentProps } from 'react'

import { cn } from '../../lib/utils'

export function Table({ className, ...props }: ComponentProps<'table'>) {
  return (
    <div className="w-full overflow-x-auto">
      <table className={cn('w-full text-sm', className)} {...props} />
    </div>
  )
}

export function TableHeader(props: ComponentProps<'thead'>) {
  return <thead className="border-b border-slate-200" {...props} />
}

export function TableBody(props: ComponentProps<'tbody'>) {
  return <tbody className="[&_tr:last-child]:border-0" {...props} />
}

export function TableRow({ className, ...props }: ComponentProps<'tr'>) {
  return (
    <tr
      className={cn('border-b border-slate-100 hover:bg-slate-50', className)}
      {...props}
    />
  )
}

export function TableHead({ className, ...props }: ComponentProps<'th'>) {
  return (
    <th
      className={cn('h-10 px-3 text-left font-medium text-slate-500', className)}
      {...props}
    />
  )
}

export function TableCell({ className, ...props }: ComponentProps<'td'>) {
  return <td className={cn('px-3 py-2 align-middle', className)} {...props} />
}
