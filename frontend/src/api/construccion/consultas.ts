import { keepPreviousData, useQuery } from '@tanstack/react-query'

import { clienteApi } from '../cliente'
import type { components, operations } from '../tipos.generados'

export type Constructora = components['schemas']['Constructora']
export type Proyecto = components['schemas']['Proyecto']
export type ProyectoDetalle = components['schemas']['ProyectoDetalle']
export type EstadoProyecto = components['schemas']['EstadoProyectoEnum']
export type PagoConstructora = components['schemas']['Pago']
export type EstadoPago = components['schemas']['EstadoPagoConstructoraEnum']
export type TipoPago = components['schemas']['TipoPagoConstructoraEnum']
type PaginaConstructoras = components['schemas']['PaginatedConstructoraList']
type PaginaProyectos = components['schemas']['PaginatedProyectoList']
type PaginaPagos = components['schemas']['PaginatedPagoList']

/** Filtros que acepta GET /constructoras/, tal como los documenta el esquema. */
export type FiltrosConstructoras = NonNullable<
  operations['v1_constructoras_list']['parameters']['query']
>

/** Filtros que acepta GET /proyectos-construccion/. */
export type FiltrosProyectos = NonNullable<
  operations['v1_proyectos_construccion_list']['parameters']['query']
>

/** Etiqueta de cada estado de un proyecto (spec 017, reglas 9 a 16). */
export const ETIQUETAS_ESTADO_PROYECTO: Record<EstadoProyecto, string> = {
  PLANIFICADO: 'Planificado',
  EN_EJECUCION: 'En ejecución',
  SUSPENDIDO: 'Suspendido',
  FINALIZADO: 'Finalizado',
  CANCELADO: 'Cancelado',
}

/** Etiqueta de cada estado de un pago a constructora (spec 017, regla 21). */
export const ETIQUETAS_ESTADO_PAGO: Record<EstadoPago, string> = {
  PROGRAMADO: 'Programado',
  PAGADO: 'Pagado',
  ANULADO: 'Anulado',
}

/** Etiqueta de cada tipo de pago (spec 017, reglas 20 y 21). */
export const ETIQUETAS_TIPO_PAGO: Record<TipoPago, string> = {
  ANTICIPO: 'Anticipo',
  AVANCE: 'Avance',
  FINIQUITO: 'Finiquito',
  EXTRA: 'Extra',
}

/**
 * Un proyecto activo todavía puede avanzar (spec 017, regla 10): admite
 * cancelarse y editar sus tres campos (regla 17). Es la misma lista que
 * ESTADOS_ACTIVOS del backend.
 */
export const ESTADOS_ACTIVOS: EstadoProyecto[] = [
  'PLANIFICADO',
  'EN_EJECUCION',
  'SUSPENDIDO',
]

/**
 * Una página de constructoras activas con sus filtros (spec 018, §5).
 * calificacion_min deja fuera las que todavía no tienen calificación: así lo
 * resuelve la API.
 */
export function useConstructoras(filtros: FiltrosConstructoras) {
  return useQuery({
    queryKey: ['construccion', 'constructoras', filtros],
    queryFn: async () =>
      (
        await clienteApi.get<PaginaConstructoras>('/constructoras/', {
          params: filtros,
        })
      ).data,
    placeholderData: keepPreviousData,
  })
}

/** Una constructora, para su formulario de edición. */
export function useConstructora(id: number) {
  return useQuery({
    queryKey: ['construccion', 'constructoras', 'detalle', id],
    queryFn: async () =>
      (await clienteApi.get<Constructora>(`/constructoras/${id}/`)).data,
  })
}

/** Constructoras activas que coinciden con el texto, para CampoRelacion. */
export function useOpcionesConstructora(texto: string) {
  const consulta = useConstructoras({ buscar: texto || undefined })
  return {
    opciones: (consulta.data?.results ?? []).map((constructora) => ({
      valor: String(constructora.id),
      etiqueta: `${constructora.codigo ?? ''} · ${constructora.nombre}`,
    })),
    cargando: consulta.isFetching,
  }
}

/** Una página de proyectos con su filtro de estado (spec 018, §5). */
export function useProyectos(filtros: FiltrosProyectos) {
  return useQuery({
    queryKey: ['construccion', 'proyectos', filtros],
    queryFn: async () =>
      (
        await clienteApi.get<PaginaProyectos>('/proyectos-construccion/', {
          params: filtros,
        })
      ).data,
    placeholderData: keepPreviousData,
  })
}

/**
 * Un proyecto con total_comprometido y disponible, que calcula la API
 * (spec 017, §5). La pantalla los muestra tal cual, sin sumar los pagos
 * (spec 018, §4).
 */
export function useProyecto(id: number) {
  return useQuery({
    queryKey: ['construccion', 'proyectos', 'detalle', id],
    queryFn: async () =>
      (await clienteApi.get<ProyectoDetalle>(`/proyectos-construccion/${id}/`)).data,
  })
}

/** Una página de los pagos de un proyecto, para la tabla de su detalle. */
export function usePagosDeProyecto(proyecto: number, pagina: number) {
  return useQuery({
    queryKey: ['construccion', 'pagos', proyecto, pagina],
    queryFn: async () =>
      (
        await clienteApi.get<PaginaPagos>(
          `/proyectos-construccion/${proyecto}/pagos/`,
          {
            params: { page: pagina },
          },
        )
      ).data,
    placeholderData: keepPreviousData,
  })
}
