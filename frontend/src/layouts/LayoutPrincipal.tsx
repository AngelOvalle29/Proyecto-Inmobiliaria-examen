import { NavLink, Outlet, useNavigate } from 'react-router'

import { Button } from '../componentes/ui/button'
import { cn } from '../lib/utils'
import { MENU, rolPermitido } from '../menu'
import { useSesion } from '../sesion/useSesion'

/**
 * Marco de las pantallas con sesión: menú lateral filtrado por rol (spec 010,
 * regla 3), usuario actual y cerrar sesión. Solo se muestra detrás de
 * RutaProtegida, así que siempre hay usuario.
 */
export function LayoutPrincipal() {
  const { usuario, cerrarSesion } = useSesion()
  const navegar = useNavigate()

  const entradas = MENU.filter((entrada) =>
    rolPermitido(usuario?.rol ?? '', entrada.roles),
  )

  const salir = () => {
    // Primero se va al login y después se borra la sesión: así el login no
    // recuerda la página del usuario anterior.
    navegar('/login', { replace: true })
    cerrarSesion()
  }

  return (
    <div className="flex min-h-screen">
      <aside className="flex w-56 shrink-0 flex-col border-r border-slate-200 bg-white p-4">
        <p className="mb-6 font-semibold">Inmobiliaria</p>
        <nav className="flex flex-col gap-1">
          {entradas.map((entrada) => (
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
        <div className="mt-auto flex flex-col gap-2 border-t border-slate-200 pt-4">
          <div className="text-sm">
            <p className="font-medium">{usuario?.nombre_completo}</p>
            <p className="text-xs text-slate-500">{usuario?.rol}</p>
          </div>
          <Button variant="outline" size="sm" onClick={salir}>
            Cerrar sesión
          </Button>
        </div>
      </aside>
      <main className="min-w-0 flex-1 p-6">
        <Outlet />
      </main>
    </div>
  )
}
