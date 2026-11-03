import { useMutation, useQueryClient } from '@tanstack/react-query'

import { clienteApi } from '../cliente'
import type { components } from '../tipos.generados'
import type {
  Constructora,
  PagoConstructora,
  Proyecto,
  ProyectoDetalle,
} from './consultas'

export type DatosConstructora = components['schemas']['ConstructoraEntrada']
export type DatosEditarConstructora =
  components['schemas']['PatchedConstructoraEntrada']
export type DatosProyecto = components['schemas']['ProyectoEntrada']
export type DatosEditarProyecto = components['schemas']['PatchedProyectoEdicion']
export type DatosAvance = components['schemas']['Avance']
export type DatosProgramarPago = components['schemas']['ProgramarPago']
export type DatosPagar = components['schemas']['Pagar']

/**
 * Después de escribir se invalida todo lo de construcción: listas, detalle del
 * proyecto y sus pagos empiezan con ['construccion'] (spec 018, §6). Los pagos
 * usan esta: cambian el comprometido y el disponible del detalle.
 */
function useInvalidarConstruccion() {
  const clienteConsultas = useQueryClient()
  return () => clienteConsultas.invalidateQueries({ queryKey: ['construccion'] })
}

/**
 * Lo que cambia el estado de una propiedad invalida además el catálogo
 * completo, como useInvalidarVenta (spec 018, §6): la ficha y las unidades
 * tienen sus propias claves, y finalizar cambia también las unidades
 * (spec 017, regla 15).
 */
function useInvalidarProyectoYCatalogo() {
  const clienteConsultas = useQueryClient()
  return () =>
    Promise.all(
      ['construccion', 'catalogo'].map((dominio) =>
        clienteConsultas.invalidateQueries({ queryKey: [dominio] }),
      ),
    )
}

/** POST /constructoras/: el backend asigna el código CST-0001 (spec 006, regla 8). */
export function useCrearConstructora() {
  const invalidar = useInvalidarConstruccion()
  return useMutation({
    mutationFn: async (datos: DatosConstructora) =>
      (await clienteApi.post<Constructora>('/constructoras/', datos)).data,
    onSuccess: invalidar,
  })
}

/** PATCH /constructoras/{id}/: solo lo que cambia. */
export function useEditarConstructora() {
  const invalidar = useInvalidarConstruccion()
  return useMutation({
    mutationFn: async ({ id, ...datos }: DatosEditarConstructora & { id: number }) =>
      (await clienteApi.patch<Constructora>(`/constructoras/${id}/`, datos)).data,
    onSuccess: invalidar,
  })
}

/**
 * DELETE /constructoras/{id}/: borrado lógico. Responde 409 si la constructora
 * tiene un proyecto activo (spec 017, regla 23).
 */
export function useDesactivarConstructora() {
  const invalidar = useInvalidarConstruccion()
  return useMutation({
    mutationFn: async (id: number) => {
      await clienteApi.delete(`/constructoras/${id}/`)
    },
    onSuccess: invalidar,
  })
}

/**
 * POST /proyectos-construccion/: nace PLANIFICADO y no toca la propiedad hasta
 * iniciarse (spec 017, regla 12). Que la propiedad esté adquirida y sin otra
 * obra activa lo revisa la API.
 */
export function useCrearProyecto() {
  const invalidar = useInvalidarConstruccion()
  return useMutation({
    mutationFn: async (datos: DatosProyecto) =>
      (await clienteApi.post<Proyecto>('/proyectos-construccion/', datos)).data,
    onSuccess: invalidar,
  })
}

/**
 * PATCH /proyectos-construccion/{id}/ (regla 17): un proyecto activo cambia
 * nombre, fin estimado y presupuesto; uno finalizado, solo el presupuesto. Se
 * envía solo lo que el estado admite: la API rechaza cualquier otro campo,
 * aunque no cambie.
 */
export function useEditarProyecto() {
  const invalidar = useInvalidarConstruccion()
  return useMutation({
    mutationFn: async ({ id, ...datos }: DatosEditarProyecto & { id: number }) =>
      (await clienteApi.patch<ProyectoDetalle>(`/proyectos-construccion/${id}/`, datos))
        .data,
    onSuccess: invalidar,
  })
}

/** Las acciones del ciclo del proyecto que no piden datos (reglas 12, 14 y 15). */
export type AccionSinDatos = 'iniciar' | 'reanudar' | 'finalizar'

/**
 * POST .../{id}/iniciar|reanudar|finalizar/. Todas pueden cambiar el estado de
 * la propiedad: iniciar la pasa a EN_CONSTRUCCION y finalizar a DISPONIBLE.
 */
export function useAccionProyecto() {
  const invalidar = useInvalidarProyectoYCatalogo()
  return useMutation({
    mutationFn: async ({ id, accion }: { id: number; accion: AccionSinDatos }) =>
      (await clienteApi.post<Proyecto>(`/proyectos-construccion/${id}/${accion}/`))
        .data,
    onSuccess: invalidar,
  })
}

/** POST .../{id}/avance/: el porcentaje nunca baja; lo revisa la API (regla 13). */
export function useRegistrarAvance() {
  const invalidar = useInvalidarConstruccion()
  return useMutation({
    mutationFn: async ({ id, ...datos }: DatosAvance & { id: number }) =>
      (await clienteApi.post<Proyecto>(`/proyectos-construccion/${id}/avance/`, datos))
        .data,
    onSuccess: invalidar,
  })
}

/**
 * POST .../{id}/suspender|cancelar/ con su motivo (reglas 14 y 16). Cancelar
 * devuelve la propiedad a ADQUIRIDA y anula los pagos programados.
 */
export function useAccionProyectoConMotivo() {
  const invalidar = useInvalidarProyectoYCatalogo()
  return useMutation({
    mutationFn: async ({
      id,
      accion,
      motivo,
    }: {
      id: number
      accion: 'suspender' | 'cancelar'
      motivo: string
    }) =>
      (
        await clienteApi.post<Proyecto>(`/proyectos-construccion/${id}/${accion}/`, {
          motivo,
        })
      ).data,
    onSuccess: invalidar,
  })
}

/**
 * POST .../{id}/pagos/: programa un pago en la moneda del proyecto (regla 20).
 * Si supera el presupuesto, la API responde 409 PRESUPUESTO_EXCEDIDO.
 */
export function useProgramarPago() {
  const invalidar = useInvalidarConstruccion()
  return useMutation({
    mutationFn: async ({
      proyecto,
      ...datos
    }: DatosProgramarPago & { proyecto: number }) =>
      (
        await clienteApi.post<PagoConstructora>(
          `/proyectos-construccion/${proyecto}/pagos/`,
          datos,
        )
      ).data,
    onSuccess: invalidar,
  })
}

/** POST /pagos-constructora/{id}/pagar/: con su fecha y su referencia (regla 21). */
export function usePagarPago() {
  const invalidar = useInvalidarConstruccion()
  return useMutation({
    mutationFn: async ({ id, ...datos }: DatosPagar & { id: number }) =>
      (
        await clienteApi.post<PagoConstructora>(
          `/pagos-constructora/${id}/pagar/`,
          datos,
        )
      ).data,
    onSuccess: invalidar,
  })
}

/** POST /pagos-constructora/{id}/anular/: con motivo; deja de comprometer (regla 19). */
export function useAnularPago() {
  const invalidar = useInvalidarConstruccion()
  return useMutation({
    mutationFn: async ({ id, motivo }: { id: number; motivo: string }) =>
      (
        await clienteApi.post<PagoConstructora>(`/pagos-constructora/${id}/anular/`, {
          motivo,
        })
      ).data,
    onSuccess: invalidar,
  })
}
