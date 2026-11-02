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

/** Hoy en la hora local, como aaaa-mm-dd: el valor de un campo de fecha. */
export function fechaDeHoy(): string {
  return aTextoDeFecha(new Date())
}

function aTextoDeFecha(fecha: Date): string {
  const mes = String(fecha.getMonth() + 1).padStart(2, '0')
  const dia = String(fecha.getDate()).padStart(2, '0')
  return `${fecha.getFullYear()}-${mes}-${dia}`
}

export type EstadoVencimiento = 'vencido' | 'por-vencer' | 'vigente'

/**
 * Si un documento está vencido, vence en los próximos 30 días o sigue vigente
 * (spec 014, regla 7). Se calcula con la fecha de hoy al mostrarlo, como la
 * mora de ventas. Las fechas aaaa-mm-dd se comparan como texto: en ese
 * formato, el orden del texto es el de las fechas. Sin fecha de vencimiento,
 * el documento no vence.
 */
export function estadoVencimiento(
  vencimiento: string | null | undefined,
): EstadoVencimiento {
  if (!vencimiento) {
    return 'vigente'
  }
  const hoy = new Date()
  const enTreintaDias = new Date(hoy.getFullYear(), hoy.getMonth(), hoy.getDate() + 30)
  if (vencimiento < aTextoDeFecha(hoy)) {
    return 'vencido'
  }
  if (vencimiento <= aTextoDeFecha(enTreintaDias)) {
    return 'por-vencer'
  }
  return 'vigente'
}
