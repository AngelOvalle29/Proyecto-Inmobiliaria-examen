import { createBrowserRouter, RouterProvider } from 'react-router'

import { RutaProtegida } from './componentes/comunes/RutaProtegida'
import { LayoutAuth } from './layouts/LayoutAuth'
import { LayoutPrincipal } from './layouts/LayoutPrincipal'
import {
  ADMINISTRAN_ASISTENTE,
  ADMINISTRAN_CRM,
  ESCRIBEN_CATALOGO,
  ESCRIBEN_COMPRAS,
  ESCRIBEN_CONSTRUCCION,
  ESCRIBEN_CRM,
  LEEN_COMPRAS,
  LEEN_CONSTRUCCION,
  VEN_AGENTES,
} from './menu'
import { DetalleArrendamiento } from './paginas/arrendamientos/DetalleArrendamiento'
import { FirmarArrendamiento } from './paginas/arrendamientos/FirmarArrendamiento'
import { ListaArrendamientos } from './paginas/arrendamientos/ListaArrendamientos'
import { Asistente } from './paginas/asistente/Asistente'
import { ListaDocumentosAgente } from './paginas/asistente/ListaDocumentosAgente'
import { Login } from './paginas/auth/Login'
import { EditarPropiedad } from './paginas/catalogo/EditarPropiedad'
import { FichaPropiedad } from './paginas/catalogo/FichaPropiedad'
import { ListaPropiedades } from './paginas/catalogo/ListaPropiedades'
import { ListaTiposPropiedad } from './paginas/catalogo/ListaTiposPropiedad'
import { NuevaPropiedad } from './paginas/catalogo/NuevaPropiedad'
import { EditarProveedor, NuevoProveedor } from './paginas/compras/FormularioProveedor'
import { ListaContratosCompra } from './paginas/compras/ListaContratosCompra'
import { ListaProveedores } from './paginas/compras/ListaProveedores'
import { NuevoContratoCompra } from './paginas/compras/NuevoContratoCompra'
import { DetalleProyecto } from './paginas/construccion/DetalleProyecto'
import {
  EditarConstructora,
  NuevaConstructora,
} from './paginas/construccion/FormularioConstructora'
import { ListaConstructoras } from './paginas/construccion/ListaConstructoras'
import { ListaProyectos } from './paginas/construccion/ListaProyectos'
import { NuevoProyecto } from './paginas/construccion/NuevoProyecto'
import { EditarCliente, NuevoCliente } from './paginas/crm/FormularioCliente'
import { ListaAgentes } from './paginas/crm/ListaAgentes'
import { ListaClientes } from './paginas/crm/ListaClientes'
import { ListaCotizaciones } from './paginas/crm/ListaCotizaciones'
import { NuevaCotizacion } from './paginas/crm/NuevaCotizacion'
import { NuevoAgente } from './paginas/crm/NuevoAgente'
import { NoEncontrada } from './paginas/errores/NoEncontrada'
import { DetalleContratoVenta } from './paginas/ventas/DetalleContratoVenta'
import { FirmarContratoVenta } from './paginas/ventas/FirmarContratoVenta'
import { ListaContratosVenta } from './paginas/ventas/ListaContratosVenta'
import { Inicio } from './paginas/inicio/Inicio'
import { Reportes } from './paginas/reportes/Reportes'

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
  // Pública, fuera de RutaProtegida: el asistente es para los visitantes del
  // sitio, sin cuenta (spec 018, regla 8).
  { path: '/asistente', element: <Asistente /> },
  {
    element: (
      <RutaProtegida>
        <LayoutPrincipal />
      </RutaProtegida>
    ),
    children: [
      { path: '/', element: <Inicio /> },
      { path: '/reportes', element: <Reportes /> },
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
      {
        path: '/crm/agentes',
        element: (
          <RutaProtegida roles={VEN_AGENTES}>
            <ListaAgentes />
          </RutaProtegida>
        ),
      },
      {
        path: '/crm/agentes/nuevo',
        element: (
          <RutaProtegida roles={ADMINISTRAN_CRM}>
            <NuevoAgente />
          </RutaProtegida>
        ),
      },
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
      // Compras y construcción: leen administración, gerencia y contabilidad
      // (spec 024, regla 1); los formularios, solo quien escribe (spec 018,
      // regla 2).
      {
        path: '/compras/proveedores',
        element: (
          <RutaProtegida roles={LEEN_COMPRAS}>
            <ListaProveedores />
          </RutaProtegida>
        ),
      },
      {
        path: '/compras/proveedores/nuevo',
        element: (
          <RutaProtegida roles={ESCRIBEN_COMPRAS}>
            <NuevoProveedor />
          </RutaProtegida>
        ),
      },
      {
        path: '/compras/proveedores/:id/editar',
        element: (
          <RutaProtegida roles={ESCRIBEN_COMPRAS}>
            <EditarProveedor />
          </RutaProtegida>
        ),
      },
      {
        path: '/compras/contratos',
        element: (
          <RutaProtegida roles={LEEN_COMPRAS}>
            <ListaContratosCompra />
          </RutaProtegida>
        ),
      },
      {
        path: '/compras/contratos/nuevo',
        element: (
          <RutaProtegida roles={ESCRIBEN_COMPRAS}>
            <NuevoContratoCompra />
          </RutaProtegida>
        ),
      },
      {
        path: '/construccion/constructoras',
        element: (
          <RutaProtegida roles={LEEN_CONSTRUCCION}>
            <ListaConstructoras />
          </RutaProtegida>
        ),
      },
      {
        path: '/construccion/constructoras/nueva',
        element: (
          <RutaProtegida roles={ESCRIBEN_CONSTRUCCION}>
            <NuevaConstructora />
          </RutaProtegida>
        ),
      },
      {
        path: '/construccion/constructoras/:id/editar',
        element: (
          <RutaProtegida roles={ESCRIBEN_CONSTRUCCION}>
            <EditarConstructora />
          </RutaProtegida>
        ),
      },
      {
        path: '/construccion/proyectos',
        element: (
          <RutaProtegida roles={LEEN_CONSTRUCCION}>
            <ListaProyectos />
          </RutaProtegida>
        ),
      },
      {
        path: '/construccion/proyectos/nuevo',
        element: (
          <RutaProtegida roles={ESCRIBEN_CONSTRUCCION}>
            <NuevoProyecto />
          </RutaProtegida>
        ),
      },
      // Cada botón según el rol (spec 018, §5).
      {
        path: '/construccion/proyectos/:id',
        element: (
          <RutaProtegida roles={LEEN_CONSTRUCCION}>
            <DetalleProyecto />
          </RutaProtegida>
        ),
      },
      {
        path: '/asistente/documentos',
        element: (
          <RutaProtegida roles={ADMINISTRAN_ASISTENTE}>
            <ListaDocumentosAgente />
          </RutaProtegida>
        ),
      },
      { path: '*', element: <NoEncontrada /> },
    ],
  },
])

export function App() {
  return <RouterProvider router={enrutador} />
}
