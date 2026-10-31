import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

/**
 * Une clases de Tailwind y resuelve los choques: cn('p-2', 'p-4') deja 'p-4'.
 * Es la utilidad que esperan los componentes copiados de shadcn/ui.
 */
export function cn(...clases: ClassValue[]) {
  return twMerge(clsx(clases))
}
