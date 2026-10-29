/// <reference types="vite/client" />

// Variables de entorno que el frontend espera. Solo las que empiezan con VITE_
// llegan al navegador, y quedan visibles en el código compilado: nunca secretos
// (docs/frontend.md §6).
interface ImportMetaEnv {
  readonly VITE_API_URL: string
  readonly VITE_ENTORNO?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
