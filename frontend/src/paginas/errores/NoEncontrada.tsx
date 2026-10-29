import { Link } from 'react-router'

/** Ruta que no existe en el frontend. */
export function NoEncontrada() {
  return (
    <div className="flex flex-col gap-2">
      <h1 className="text-2xl font-semibold">Página no encontrada</h1>
      <Link to="/" className="text-sm underline">
        Volver al inicio
      </Link>
    </div>
  )
}
