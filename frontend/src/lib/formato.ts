/**
 * Formato de montos y fechas para mostrar (spec 010, regla 9). Toda pantalla
 * usa estas funciones: nunca se concatena un símbolo de moneda a mano.
 */

/**
 * Un monto con su moneda: formatearMoneda('150000.00', 'USD') → "US$150,000.00".
 *
 * La API envía los montos como texto ("150000.00") para no perder precisión
 * (spec 001); aquí se convierten solo para mostrarlos.
 */
export function formatearMoneda(monto: string | number, codigoMoneda: string): string {
  const valor = typeof monto === 'string' ? Number(monto) : monto
  return new Intl.NumberFormat('es-GT', {
    style: 'currency',
    currency: codigoMoneda,
  }).format(valor)
}

/**
 * Una fecha como dd/mm/aaaa. Acepta "2026-10-05" (fecha sola) o una fecha y
 * hora ISO ("2026-10-05T14:30:00Z").
 *
 * La fecha sola se arma a mano: new Date("2026-10-05") la toma como medianoche
 * UTC, y en Guatemala (UTC−6) se mostraría el 4 de octubre.
 */
export function formatearFecha(valor: string): string {
  const soloFecha = /^(\d{4})-(\d{2})-(\d{2})$/.exec(valor)
  if (soloFecha) {
    const [, anio, mes, dia] = soloFecha
    return `${dia}/${mes}/${anio}`
  }
  return new Date(valor).toLocaleDateString('es-GT', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
  })
}
