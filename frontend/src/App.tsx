import { createBrowserRouter, RouterProvider } from 'react-router'

import { LayoutAuth } from './layouts/LayoutAuth'
import { LayoutPrincipal } from './layouts/LayoutPrincipal'
import { Login } from './paginas/auth/Login'
import { ListaPropiedades } from './paginas/catalogo/ListaPropiedades'
import { NuevaPropiedad } from './paginas/catalogo/NuevaPropiedad'
import { NoEncontrada } from './paginas/errores/NoEncontrada'
import { Inicio } from './paginas/inicio/Inicio'

/**
 * Rutas del frontend (spec 010, §5). Para agregar una pantalla: una ruta aquí y
 * una línea en menu.ts. Desde el incremento 2, las rutas con sesión pasan por
 * RutaProtegida.
 *
 * En Vercel, vercel.json manda toda ruta a index.html: así recargar
 * /catalogo/propiedades no da 404, porque es React Router quien la resuelve.
 */
const enrutador = createBrowserRouter([
  {
    element: <LayoutAuth />,
    children: [{ path: '/login', element: <Login /> }],
  },
  {
    element: <LayoutPrincipal />,
    children: [
      { path: '/', element: <Inicio /> },
      { path: '/catalogo/propiedades', element: <ListaPropiedades /> },
      { path: '/catalogo/propiedades/nueva', element: <NuevaPropiedad /> },
      { path: '*', element: <NoEncontrada /> },
    ],
  },
])

export function App() {
  return <RouterProvider router={enrutador} />
}
