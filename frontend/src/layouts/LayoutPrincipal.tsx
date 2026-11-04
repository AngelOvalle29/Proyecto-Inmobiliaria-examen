import { useState } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router'

import { Button } from '../componentes/ui/button'
import { cn } from '../lib/utils'
import { agruparMenu, MENU, rolPermitido, type GrupoMenu } from '../menu'
import { useSesion } from '../sesion/useSesion'

// Spec 023: lo que el usuario plegó se recuerda en este navegador. Es solo una
// preferencia de pantalla: si el almacenamiento falla, el menú funciona igual.
const CLAVE_GRUPOS = 'inmobiliaria.menu.grupos-plegados'
const CLAVE_OCULTO = 'inmobiliaria.menu.oculto'

function leer<T>(clave: string, porDefecto: T): T {
  try {
    const valor = localStorage.getItem(clave)
    return valor === null ? porDefecto : (JSON.parse(valor) as T)
  } catch {
    return porDefecto
  }
}

function guardar(clave: string, valor: unknown) {
  try {
    localStorage.setItem(clave, JSON.stringify(valor))
  } catch {
    // Sin almacenamiento, la preferencia dura hasta recargar.
  }
}

/**
 * Marco de las pantallas con sesión: menú lateral filtrado por rol (spec 010,
 * regla 3), usuario actual y cerrar sesión. Solo se muestra detrás de
 * RutaProtegida, así que siempre hay usuario.
 */
export function LayoutPrincipal() {
  const { usuario, salir } = useSesion()
  const [oculto, setOculto] = useState(() => leer(CLAVE_OCULTO, false))

  const entradas = MENU.filter((entrada) =>
    rolPermitido(usuario?.rol ?? '', entrada.roles),
  )

  const cambiarOculto = (valor: boolean) => {
    setOculto(valor)
    guardar(CLAVE_OCULTO, valor)
  }

  return (
    <div className="flex min-h-screen">
      {/* Spec 022: el menú es la franja negra del diseño, con etiquetas mono
          en crema y la marca en serif editorial. Spec 023: se puede ocultar. */}
      {!oculto && (
        <aside className="flex w-60 shrink-0 flex-col bg-negro p-5 text-crema">
          <div className="mb-8 flex items-start justify-between gap-2">
            <p className="font-editorial text-3xl leading-none">Inmobiliaria</p>
            <button
              type="button"
              onClick={() => cambiarOculto(true)}
              aria-label="Ocultar el menú"
              title="Ocultar el menú"
              className="rounded-full px-2 font-mono text-lg leading-none text-crema/70 hover:bg-crema/10 hover:text-crema"
            >
              ‹
            </button>
          </div>
          <nav className="flex flex-col gap-3">
            {/* Se agrupa después de filtrar por rol: un grupo sin entradas
                visibles no muestra su título. */}
            {agruparMenu(entradas).map((grupo) => (
              <GrupoDelMenu key={grupo.titulo ?? 'sin-grupo'} grupo={grupo} />
            ))}
          </nav>
          <div className="mt-auto flex flex-col gap-3 border-t border-crema/30 pt-4">
            <div>
              <p className="font-editorial text-xl leading-tight">
                {usuario?.nombre_completo}
              </p>
              <p className="font-mono text-[11px] tracking-etiqueta text-crema/60 uppercase">
                {usuario?.rol}
              </p>
            </div>
            <NavLink
              to="/cuenta/contrasena"
              className="font-mono text-[11px] tracking-etiqueta text-crema/70 uppercase hover:text-crema hover:underline"
            >
              Cambiar contraseña
            </NavLink>
            <Button variant="inverse" size="sm" onClick={salir}>
              Cerrar sesión
            </Button>
          </div>
        </aside>
      )}
      <main className="min-w-0 flex-1 p-6 md:p-8">
        {oculto && (
          <Button
            variant="outline"
            size="sm"
            className="mb-4"
            onClick={() => cambiarOculto(false)}
          >
            Mostrar menú
          </Button>
        )}
        <Outlet />
      </main>
    </div>
  )
}

/**
 * Un grupo del menú que se despliega y se pliega (spec 023, regla 4). El grupo
 * de la página abierta se muestra siempre desplegado, para no perder dónde se
 * está.
 */
function GrupoDelMenu({ grupo }: { grupo: GrupoMenu }) {
  const { pathname } = useLocation()
  const [plegados, setPlegados] = useState<string[]>(() => leer(CLAVE_GRUPOS, []))

  if (!grupo.titulo) {
    return <Enlaces grupo={grupo} />
  }

  const titulo = grupo.titulo
  const contieneActual = grupo.entradas.some(
    (entrada) => pathname === entrada.ruta || pathname.startsWith(`${entrada.ruta}/`),
  )
  const desplegado = contieneActual || !plegados.includes(titulo)

  const alternar = () => {
    // Se lee de nuevo: otro grupo pudo cambiar la lista guardada.
    const actuales = leer<string[]>(CLAVE_GRUPOS, [])
    const nuevos = desplegado
      ? [...actuales.filter((t) => t !== titulo), titulo]
      : actuales.filter((t) => t !== titulo)
    guardar(CLAVE_GRUPOS, nuevos)
    setPlegados(nuevos)
  }

  return (
    <div className="flex flex-col gap-0.5">
      <button
        type="button"
        onClick={alternar}
        disabled={contieneActual}
        aria-expanded={desplegado}
        className="flex items-center justify-between rounded-full px-3 py-1 font-mono text-[11px] tracking-etiqueta text-crema/60 uppercase hover:bg-crema/10 hover:text-crema disabled:hover:bg-transparent"
      >
        {titulo}
        <span aria-hidden="true">{desplegado ? '−' : '+'}</span>
      </button>
      {desplegado && <Enlaces grupo={grupo} />}
    </div>
  )
}

function Enlaces({ grupo }: { grupo: GrupoMenu }) {
  return (
    <>
      {grupo.entradas.map((entrada) => (
        <NavLink
          key={entrada.ruta}
          to={entrada.ruta}
          end
          className={({ isActive }) =>
            cn(
              'rounded-full px-3 py-1.5 font-mono text-xs tracking-etiqueta uppercase hover:bg-crema/10',
              isActive && 'bg-crema text-negro hover:bg-crema',
            )
          }
        >
          {entrada.etiqueta}
        </NavLink>
      ))}
    </>
  )
}
