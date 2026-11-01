import { createBrowserRouter, RouterProvider } from 'react-router'

import { RutaProtegida } from './componentes/comunes/RutaProtegida'
import { LayoutAuth } from './layouts/LayoutAuth'
import { LayoutPrincipal } from './layouts/LayoutPrincipal'
import { ESCRIBEN_CATALOGO, ESCRIBEN_CRM } from './menu'
import { DetalleArrendamiento } from './paginas/arrendamientos/DetalleArrendamiento'
import { FirmarArrendamiento } from './paginas/arrendamientos/FirmarArrendamiento'
import { ListaArrendamientos } from './paginas/arrendamientos/ListaArrendamientos'
import { Login } from './paginas/auth/Login'
import { EditarPropiedad } from './paginas/catalogo/EditarPropiedad'
import { FichaPropiedad } from './paginas/catalogo/FichaPropiedad'
import { ListaPropiedades } from './paginas/catalogo/ListaPropiedades'
import { ListaTiposPropiedad } from './paginas/catalogo/ListaTiposPropiedad'
import { NuevaPropiedad } from './paginas/catalogo/NuevaPropiedad'
import { EditarCliente, NuevoCliente } from './paginas/crm/FormularioCliente'
import { ListaAgentes } from './paginas/crm/ListaAgentes'
import { ListaClientes } from './paginas/crm/ListaClientes'
import { ListaCotizaciones } from './paginas/crm/ListaCotizaciones'
import { NuevaCotizacion } from './paginas/crm/NuevaCotizacion'
import { NoEncontrada } from './paginas/errores/NoEncontrada'
import { DetalleContratoVenta } from './paginas/ventas/DetalleContratoVenta'
import { FirmarContratoVenta } from './paginas/ventas/FirmarContratoVenta'
import { ListaContratosVenta } from './paginas/ventas/ListaContratosVenta'
import { Inicio } from './paginas/inicio/Inicio'

/**
 * Rutas del frontend (spec 010, §5). Para agregar una pantalla: una ruta aquí y
 * una línea en menu.ts. Todas las rutas con sesión pasan por RutaProtegida, y
 * las limitadas por rol la repiten con sus roles (spec 010, reglas 1 y 2).
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
    element: (
      <RutaProtegida>
        <LayoutPrincipal />
      </RutaProtegida>
    ),
    children: [
      { path: '/', element: <Inicio /> },
      { path: '/catalogo/propiedades', element: <ListaPropiedades /> },
      {
        path: '/catalogo/propiedades/nueva',
        element: (
          <RutaProtegida roles={ESCRIBEN_CATALOGO}>
            <NuevaPropiedad />
          </RutaProtegida>
        ),
      },
      { path: '/catalogo/propiedades/:id', element: <FichaPropiedad /> },
      {
        path: '/catalogo/propiedades/:id/editar',
        element: (
          <RutaProtegida roles={ESCRIBEN_CATALOGO}>
            <EditarPropiedad />
          </RutaProtegida>
        ),
      },
      // Todos la ven; los botones de escritura solo el administrador (spec 014).
      { path: '/catalogo/tipos', element: <ListaTiposPropiedad /> },
      { path: '/crm/clientes', element: <ListaClientes /> },
      {
        path: '/crm/clientes/nuevo',
        element: (
          <RutaProtegida roles={ESCRIBEN_CRM}>
            <NuevoCliente />
          </RutaProtegida>
        ),
      },
      {
        path: '/crm/clientes/:id/editar',
        element: (
          <RutaProtegida roles={ESCRIBEN_CRM}>
            <EditarCliente />
          </RutaProtegida>
        ),
      },
      { path: '/crm/agentes', element: <ListaAgentes /> },
      { path: '/crm/cotizaciones', element: <ListaCotizaciones /> },
      {
        path: '/crm/cotizaciones/nueva',
        element: (
          <RutaProtegida roles={ESCRIBEN_CRM}>
            <NuevaCotizacion />
          </RutaProtegida>
        ),
      },
      { path: '/ventas/contratos', element: <ListaContratosVenta /> },
      {
        path: '/ventas/contratos/nuevo',
        element: (
          <RutaProtegida roles={ESCRIBEN_CRM}>
            <FirmarContratoVenta />
          </RutaProtegida>
        ),
      },
      { path: '/ventas/contratos/:id', element: <DetalleContratoVenta /> },
      { path: '/arrendamientos/contratos', element: <ListaArrendamientos /> },
      {
        path: '/arrendamientos/contratos/nuevo',
        element: (
          <RutaProtegida roles={ESCRIBEN_CRM}>
            <FirmarArrendamiento />
          </RutaProtegida>
        ),
      },
      { path: '/arrendamientos/contratos/:id', element: <DetalleArrendamiento /> },
      { path: '*', element: <NoEncontrada /> },
    ],
  },
])

export function App() {
  return <RouterProvider router={enrutador} />
}
