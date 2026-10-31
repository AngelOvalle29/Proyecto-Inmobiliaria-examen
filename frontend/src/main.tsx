import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { isAxiosError } from 'axios'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

import { App } from './App'
import './index.css'
import { ProveedorSesion } from './sesion/ProveedorSesion'

// Un solo QueryClient para toda la aplicación: guarda en caché las respuestas
// de la API, así que no hace falta otro estado global (docs/frontend.md §3).
// Solo se reintenta lo que puede cambiar (sin red, un 5xx): repetir un 404 de un
// contrato ajeno solo dejaría la pantalla unos segundos más en "Cargando…".
const clienteConsultas = new QueryClient({
  defaultOptions: {
    queries: {
      retry: (fallos, error) => {
        const estado = isAxiosError(error) ? error.response?.status : undefined
        return fallos < 3 && (estado === undefined || estado >= 500)
      },
    },
  },
})

const raiz = document.getElementById('root')
if (!raiz) {
  throw new Error('No existe el elemento #root en index.html')
}

createRoot(raiz).render(
  <StrictMode>
    <QueryClientProvider client={clienteConsultas}>
      <ProveedorSesion>
        <App />
      </ProveedorSesion>
    </QueryClientProvider>
  </StrictMode>,
)
