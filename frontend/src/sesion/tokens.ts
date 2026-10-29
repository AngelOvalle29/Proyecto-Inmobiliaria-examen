/**
 * Dónde viven los tokens JWT (spec 010, regla 4; docs/frontend.md §5).
 *
 * - El de acceso, en una variable del módulo: se pierde al recargar la página,
 *   y así nunca queda escrito en el navegador.
 * - El de refresco, en localStorage: es lo que permite seguir dentro después de
 *   recargar. El riesgo de guardarlo ahí está explicado en la §10 de la spec.
 */

const CLAVE_REFRESCO = 'inmobiliaria.refresco'

let tokenAcceso: string | null = null

export function obtenerAcceso(): string | null {
  return tokenAcceso
}

export function guardarAcceso(token: string): void {
  tokenAcceso = token
}

export function obtenerRefresco(): string | null {
  // localStorage puede no estar disponible (modo privado estricto): sin él, no
  // hay sesión que recordar, pero la aplicación no debe romperse.
  try {
    return localStorage.getItem(CLAVE_REFRESCO)
  } catch {
    return null
  }
}

export function guardarTokens(acceso: string, refresco: string): void {
  tokenAcceso = acceso
  try {
    localStorage.setItem(CLAVE_REFRESCO, refresco)
  } catch {
    // Sin localStorage, la sesión dura hasta recargar la página.
  }
}

export function borrarTokens(): void {
  tokenAcceso = null
  try {
    localStorage.removeItem(CLAVE_REFRESCO)
  } catch {
    // Nada que borrar.
  }
}
