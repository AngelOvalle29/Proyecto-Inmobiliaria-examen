import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

import { App } from './App'
import './index.css'
import { ProveedorSesion } from './sesion/ProveedorSesion'

// Un solo QueryClient para toda la aplicación: guarda en caché las respuestas
// de la API, así que no hace falta otro estado global (docs/frontend.md §3).
const clienteConsultas = new QueryClient()

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
