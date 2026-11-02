import type { ReactNode } from 'react'
import { Navigate, Outlet, useLocation } from 'react-router'

import { rolPermitido, type Rol } from '../../menu'
import { useSesion } from '../../sesion/useSesion'
import { Button } from '../ui/button'

interface Props {
  /** Roles que pueden abrir la ruta. Sin roles, cualquiera con sesión. */
  roles?: Rol[]
  /** Lo que se muestra si pasa. Sin children, las rutas hijas (Outlet). */
  children?: ReactNode
}

/**
 * Deja pasar solo con sesión y, si se indican, con uno de los roles
 * (spec 010, reglas 1 y 2). Es comodidad, no seguridad: el backend igual
 * rechaza con 403 lo que el rol no puede hacer.
 */
export function RutaProtegida({ roles, children }: Props) {
  const { estado, usuario, recordarRuta, reintentar } = useSesion()
  const ubicacion = useLocation()

  if (estado === 'cargando') {
    return <p className="p-6 text-sm text-slate-500">Cargando la sesión…</p>
  }
  if (estado === 'sin-conexion') {
    return (
      <div className="flex flex-col items-start gap-3 p-6">
        <p className="text-sm">
          No se pudo conectar con el servidor. Si estuvo inactivo, puede tardar
          alrededor de un minuto en despertar.
        </p>
        <Button variant="outline" size="sm" onClick={reintentar}>
          Reintentar
        </Button>
      </div>
    )
  }
  if (estado === 'sin-sesion' || !usuario) {
    // Se guarda la ruta pedida para volver a ella después de entrar, salvo que
    // el usuario haya salido: la página era suya (spec 010, regla 6).
    const desde = ubicacion.pathname + ubicacion.search
    return <Navigate to="/login" replace state={recordarRuta ? { desde } : null} />
  }
  if (!rolPermitido(usuario.rol, roles)) {
    return <p className="text-sm">No tiene permiso para ver esta página.</p>
  }
  return children ?? <Outlet />
}
