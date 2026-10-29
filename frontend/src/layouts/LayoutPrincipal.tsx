import { NavLink, Outlet } from 'react-router'

import { cn } from '../lib/utils'
import { MENU } from '../menu'

/**
 * Marco de las pantallas con sesión: menú lateral y contenido. El menú se arma
 * desde MENU (menu.ts); el filtro por rol llega con la sesión (incremento 2).
 */
export function LayoutPrincipal() {
  return (
    <div className="flex min-h-screen">
      <aside className="w-56 shrink-0 border-r border-slate-200 bg-white p-4">
        <p className="mb-6 font-semibold">Inmobiliaria</p>
        <nav className="flex flex-col gap-1">
          {MENU.map((entrada) => (
            <NavLink
              key={entrada.ruta}
              to={entrada.ruta}
              end
              className={({ isActive }) =>
                cn(
                  'rounded-md px-3 py-2 text-sm hover:bg-slate-100',
                  isActive && 'bg-slate-100 font-medium',
                )
              }
            >
              {entrada.etiqueta}
            </NavLink>
          ))}
        </nav>
      </aside>
      <main className="flex-1 p-6">
        <Outlet />
      </main>
    </div>
  )
}
