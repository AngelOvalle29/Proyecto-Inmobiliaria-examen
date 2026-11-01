/**
 * Se muestra en lugar de la aplicación cuando falta VITE_API_URL. Sin esa
 * variable, Axios manda cada petición a la propia página y el login falla sin
 * explicar por qué (lo notó B al probar en local).
 */
export function FaltaConfiguracion() {
  return (
    <main className="mx-auto flex max-w-xl flex-col gap-3 p-6 text-sm">
      <h1 className="text-xl font-semibold">Falta configurar la dirección de la API</h1>
      <p>
        La variable <code>VITE_API_URL</code> está vacía, así que el frontend no sabe a
        qué API conectarse.
      </p>
      <ul className="list-disc space-y-1 pl-5">
        <li>
          <strong>En desarrollo:</strong> copie <code>frontend/.env.example</code> a{' '}
          <code>frontend/.env.local</code> y vuelva a iniciar <code>npm run dev</code>.
        </li>
        <li>
          <strong>En Vercel:</strong> agréguela en{' '}
          <em>Settings → Environment Variables</em>, de tipo <em>Config</em>, terminada
          en <code>/api/v1</code>, y vuelva a desplegar.
        </li>
      </ul>
    </main>
  )
}
