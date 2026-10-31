import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  // Tailwind genera solo las clases que aparecen en el código (spec 010).
  plugins: [react(), tailwindcss()],
})
