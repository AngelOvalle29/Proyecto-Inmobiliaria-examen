import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

import { App } from './App'
import './index.css'
import { FaltaConfiguracion } from './paginas/errores/FaltaConfiguracion'
import { ProveedorSesion } from './sesion/ProveedorSesion'

// Un solo QueryClient para toda la aplicación: guarda en caché las respuestas
// de la API, así que no hace falta otro estado global (docs/frontend.md §3).
const clienteConsultas = new QueryClient()

const raiz = document.getElementById('root')
if (!raiz) {
  throw new Error('No existe el elemento #root en index.html')
}

// Sin la dirección de la API no se arranca la aplicación: se explica qué falta,
// en vez de dejar que el login falle sin decir por qué.
if (!import.meta.env.VITE_API_URL) {
  createRoot(raiz).render(<FaltaConfiguracion />)
} else {
  createRoot(raiz).render(
    <StrictMode>
      <QueryClientProvider client={clienteConsultas}>
        <ProveedorSesion>
          <App />
        </ProveedorSesion>
      </QueryClientProvider>
    </StrictMode>,
  )
}
