import axios from 'axios'

/**
 * Cliente HTTP único del frontend (docs/frontend.md §2). Ningún componente llama
 * a la API directamente: todo pasa por los hooks de TanStack Query de
 * src/api/<dominio>/, que usan este cliente.
 */
export const clienteApi = axios.create({
  baseURL: import.meta.env.VITE_API_URL,
  // En el plan gratuito, Render tarda alrededor de un minuto en despertar la API
  // (spec 002, §5.8). Con menos tiempo, la primera petición fallaría siempre.
  timeout: 90_000,
})
