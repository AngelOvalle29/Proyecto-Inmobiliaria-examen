import { useMutation, useQueryClient } from '@tanstack/react-query'

import { clienteApi } from '../cliente'
import type { components } from '../tipos.generados'
import type {
  Avaluo,
  DocumentoOficial,
  Propiedad,
  TipoPropiedad,
  Unidad,
} from './consultas'

type CambiarEstado = components['schemas']['CambiarEstado']
type DescargaDocumento = components['schemas']['DescargaDocumento']

/**
 * Lo que se envía para crear una propiedad: los campos escribibles del esquema.
 * Los de solo lectura (id, código, estado, resúmenes) los pone el backend.
 */
export type DatosNuevaPropiedad = Pick<
  Propiedad,
  | 'nombre'
  | 'tipo_id'
  | 'ciudad_id'
  | 'direccion'
  | 'area_m2'
  | 'area_construida_m2'
  | 'precio_lista'
  | 'moneda_id'
  | 'es_publica'
  | 'descripcion'
>

/**
 * Después de escribir, se invalidan las consultas de propiedades: TanStack
 * Query las vuelve a pedir y la lista se actualiza sin recargar la página.
 */
function useInvalidarPropiedades() {
  const clienteConsultas = useQueryClient()
  return () =>
    clienteConsultas.invalidateQueries({ queryKey: ['catalogo', 'propiedades'] })
}

/** POST /propiedades/: el backend asigna el código PROP-NNNNN (spec 003). */
export function useCrearPropiedad() {
  const invalidar = useInvalidarPropiedades()
  return useMutation({
    mutationFn: async (datos: DatosNuevaPropiedad) =>
      (await clienteApi.post<Propiedad>('/propiedades/', datos)).data,
    onSuccess: invalidar,
  })
}

/**
 * PATCH /propiedades/{id}/. El estado no va aquí: tiene su propia acción
 * (spec 003, regla 7).
 */
export function useActualizarPropiedad() {
  const invalidar = useInvalidarPropiedades()
  return useMutation({
    mutationFn: async ({ id, ...datos }: DatosNuevaPropiedad & { id: number }) =>
      (await clienteApi.patch<Propiedad>(`/propiedades/${id}/`, datos)).data,
    onSuccess: invalidar,
  })
}

/**
 * POST /{recurso}/{id}/cambiar-estado/ con el estado nuevo y el motivo. La
 * propiedad y la unidad tienen la misma acción con la misma entrada (spec 003),
 * así que un solo hook sirve para las dos (spec 014, regla 4). Se invalida
 * todo el catálogo: la lista, la ficha y las unidades.
 */
export function useCambiarEstado(recurso: 'propiedades' | 'unidades') {
  const clienteConsultas = useQueryClient()
  return useMutation({
    mutationFn: async ({ id, ...datos }: CambiarEstado & { id: number }) =>
      (await clienteApi.post(`/${recurso}/${id}/cambiar-estado/`, datos)).data,
    onSuccess: () => clienteConsultas.invalidateQueries({ queryKey: ['catalogo'] }),
  })
}

/** DELETE /propiedades/{id}/: borrado lógico (spec 003, regla 6). */
export function useDesactivarPropiedad() {
  const invalidar = useInvalidarPropiedades()
  return useMutation({
    mutationFn: async (id: number) => {
      await clienteApi.delete(`/propiedades/${id}/`)
    },
    onSuccess: invalidar,
  })
}

/** Los campos escribibles de una unidad; la propiedad sale de la URL. */
export type DatosUnidad = Pick<
  Unidad,
  | 'codigo'
  | 'nivel'
  | 'area_m2'
  | 'habitaciones'
  | 'banos'
  | 'precio_lista'
  | 'moneda_id'
>

function useInvalidarUnidades() {
  const clienteConsultas = useQueryClient()
  return () =>
    clienteConsultas.invalidateQueries({ queryKey: ['catalogo', 'unidades'] })
}

/** POST /propiedades/{id}/unidades/. Un código repetido en la propiedad da 409. */
export function useCrearUnidad(propiedad: number) {
  const invalidar = useInvalidarUnidades()
  return useMutation({
    mutationFn: async (datos: DatosUnidad) =>
      (await clienteApi.post<Unidad>(`/propiedades/${propiedad}/unidades/`, datos))
        .data,
    onSuccess: invalidar,
  })
}

/** PATCH /unidades/{id}/. Como en la propiedad, el estado tiene su propia acción. */
export function useActualizarUnidad() {
  const invalidar = useInvalidarUnidades()
  return useMutation({
    mutationFn: async ({ id, ...datos }: DatosUnidad & { id: number }) =>
      (await clienteApi.patch<Unidad>(`/unidades/${id}/`, datos)).data,
    onSuccess: invalidar,
  })
}

/** DELETE /unidades/{id}/: borrado lógico. */
export function useDesactivarUnidad() {
  const invalidar = useInvalidarUnidades()
  return useMutation({
    mutationFn: async (id: number) => {
      await clienteApi.delete(`/unidades/${id}/`)
    },
    onSuccess: invalidar,
  })
}

/** Lo que se envía para registrar un avalúo; el documento es opcional. */
export type DatosAvaluo = Pick<
  Avaluo,
  'fecha' | 'valor' | 'moneda_id' | 'perito' | 'metodologia' | 'observaciones'
> & { documento_id?: number | null }

/**
 * Invalida las consultas del catálogo con esas claves. Los avalúos invalidan
 * también los documentos: un documento que respalda un avalúo ya no se puede
 * desactivar.
 */
function useInvalidar(...claves: string[]) {
  const clienteConsultas = useQueryClient()
  return () =>
    Promise.all(
      claves.map((clave) =>
        clienteConsultas.invalidateQueries({ queryKey: ['catalogo', clave] }),
      ),
    )
}

/** POST /propiedades/{id}/avaluos/. Un avalúo no se edita (spec 011, regla 3). */
export function useRegistrarAvaluo(propiedad: number) {
  const invalidar = useInvalidar('avaluos', 'documentos')
  return useMutation({
    mutationFn: async (datos: DatosAvaluo) =>
      (await clienteApi.post<Avaluo>(`/propiedades/${propiedad}/avaluos/`, datos)).data,
    onSuccess: invalidar,
  })
}

/** DELETE /avaluos/{id}/: borrado lógico. */
export function useDesactivarAvaluo() {
  const invalidar = useInvalidar('avaluos', 'documentos')
  return useMutation({
    mutationFn: async (id: number) => {
      await clienteApi.delete(`/avaluos/${id}/`)
    },
    onSuccess: invalidar,
  })
}

/** Los datos de un documento que se pueden editar después de subirlo. */
export type DatosDocumento = Pick<
  DocumentoOficial,
  'nombre' | 'fecha_emision' | 'fecha_vencimiento' | 'emisor'
>

/** Lo que se sube: el archivo, su tipo y sus datos. */
export type DatosSubirDocumento = DatosDocumento & {
  archivo: File
  tipo: DocumentoOficial['tipo']
}

/**
 * POST /propiedades/{id}/documentos/ como multipart/form-data (spec 014,
 * regla 5): un archivo no viaja en JSON. Con FormData, axios pone el
 * Content-Type y el separador de las partes por su cuenta.
 */
export function useSubirDocumento(propiedad: number) {
  const invalidar = useInvalidar('documentos')
  return useMutation({
    mutationFn: async (datos: DatosSubirDocumento) => {
      const formulario = new FormData()
      formulario.append('archivo', datos.archivo)
      formulario.append('tipo', datos.tipo)
      formulario.append('nombre', datos.nombre)
      formulario.append('fecha_emision', datos.fecha_emision)
      // Sin vencimiento, la parte no se envía: la API lo guarda vacío.
      if (datos.fecha_vencimiento) {
        formulario.append('fecha_vencimiento', datos.fecha_vencimiento)
      }
      formulario.append('emisor', datos.emisor)
      return (
        await clienteApi.post<DocumentoOficial>(
          `/propiedades/${propiedad}/documentos/`,
          formulario,
        )
      ).data
    },
    onSuccess: invalidar,
  })
}

/** PATCH /documentos/{id}/. El archivo y el tipo no se cambian (spec 011, regla 7). */
export function useActualizarDocumento() {
  const invalidar = useInvalidar('documentos')
  return useMutation({
    mutationFn: async ({ id, ...datos }: DatosDocumento & { id: number }) =>
      (await clienteApi.patch<DocumentoOficial>(`/documentos/${id}/`, datos)).data,
    onSuccess: invalidar,
  })
}

/** DELETE /documentos/{id}/. Si respalda un avalúo activo, la API responde 409. */
export function useDesactivarDocumento() {
  const invalidar = useInvalidar('documentos')
  return useMutation({
    mutationFn: async (id: number) => {
      await clienteApi.delete(`/documentos/${id}/`)
    },
    onSuccess: invalidar,
  })
}

/**
 * Descargar un documento (spec 014, regla 6). Es una mutación y no una
 * consulta a propósito: la URL firmada vence a los 5 minutos, así que se pide
 * en cada clic y nunca se guarda en la caché.
 *
 * La pestaña se abre antes de pedir la URL: el navegador solo deja abrir
 * ventanas durante el clic, y después de esperar a la API ya no lo considera
 * parte del clic.
 */
export function useDescargarDocumento() {
  return useMutation({
    mutationFn: async (id: number) => {
      const ventana = window.open('', '_blank')
      try {
        const { url } = (
          await clienteApi.get<DescargaDocumento>(`/documentos/${id}/descarga/`)
        ).data
        if (ventana) {
          // La pestaña nueva no debe poder controlar a esta.
          ventana.opener = null
          ventana.location.href = url
        } else {
          // El navegador bloqueó la pestaña nueva: se abre en esta, y con
          // Atrás se vuelve a la ficha.
          window.location.assign(url)
        }
      } catch (error) {
        ventana?.close()
        throw error
      }
    },
  })
}

/** Los campos escribibles de un tipo de propiedad. */
export type DatosTipoPropiedad = Pick<
  TipoPropiedad,
  'nombre' | 'descripcion' | 'requiere_unidades'
>

/** POST /tipos-propiedad/. Solo el administrador (spec 003, regla 8). */
export function useCrearTipoPropiedad() {
  const invalidar = useInvalidar('tipos-propiedad')
  return useMutation({
    mutationFn: async (datos: DatosTipoPropiedad) =>
      (await clienteApi.post<TipoPropiedad>('/tipos-propiedad/', datos)).data,
    onSuccess: invalidar,
  })
}

/** PATCH /tipos-propiedad/{id}/. */
export function useActualizarTipoPropiedad() {
  const invalidar = useInvalidar('tipos-propiedad')
  return useMutation({
    mutationFn: async ({ id, ...datos }: DatosTipoPropiedad & { id: number }) =>
      (await clienteApi.patch<TipoPropiedad>(`/tipos-propiedad/${id}/`, datos)).data,
    onSuccess: invalidar,
  })
}

/** DELETE /tipos-propiedad/{id}/: borrado lógico. */
export function useDesactivarTipoPropiedad() {
  const invalidar = useInvalidar('tipos-propiedad')
  return useMutation({
    mutationFn: async (id: number) => {
      await clienteApi.delete(`/tipos-propiedad/${id}/`)
    },
    onSuccess: invalidar,
  })
}
