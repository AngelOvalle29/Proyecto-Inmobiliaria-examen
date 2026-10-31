import { Outlet } from 'react-router'

/** Marco de las pantallas sin sesión: solo el contenido, centrado. */
export function LayoutAuth() {
  return (
    <main className="flex min-h-screen items-center justify-center p-4">
      <Outlet />
    </main>
  )
}
