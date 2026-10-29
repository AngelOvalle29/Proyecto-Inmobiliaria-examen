import { zodResolver } from '@hookform/resolvers/zod'
import { useState } from 'react'
import {
  Controller,
  useForm,
  type DefaultValues,
  type FieldValues,
  type Path,
} from 'react-hook-form'
import type { z } from 'zod'

import { leerErrorApi } from '../../api/errores'
import { cn } from '../../lib/utils'
import { Button } from '../ui/button'
import { Input } from '../ui/input'
import { Label } from '../ui/label'
import { Select } from '../ui/select'
import { CampoRelacion, type Opcion, type ResultadoBusqueda } from './CampoRelacion'

interface CampoBase<V> {
  /** Igual que el campo de la API: así su error de validación cae aquí. */
  nombre: Path<V> & string
  etiqueta: string
  ayuda?: string
  /** Si devuelve false, el campo no se muestra ni se envía (regla 12). */
  visibleSi?: (valores: V) => boolean
  /** Al cambiar ese otro campo, este se vacía: la ciudad depende del país (regla 12). */
  dependeDe?: Path<V> & string
}

/** Un campo del formulario, declarado por la pantalla (spec 010, §6). */
export type CampoFormulario<V> =
  | (CampoBase<V> & { tipo: 'texto' | 'numero' | 'area' })
  | (CampoBase<V> & { tipo: 'booleano' })
  | (CampoBase<V> & { tipo: 'seleccion'; opciones: Opcion[] })
  | (CampoBase<V> & {
      tipo: 'relacion'
      /** Hook de búsqueda en la API; recibe el texto y los valores actuales. */
      buscar: (texto: string, valores: V) => ResultadoBusqueda
      /** Qué decir mientras falta el campo del que depende. */
      marcador?: string
    })

interface Props<V extends FieldValues> {
  campos: CampoFormulario<V>[]
  /** Valida el formato en el navegador. Las reglas de negocio las valida la API. */
  esquema: z.ZodType<V, V>
  valoresIniciales: DefaultValues<V>
  /** Llama a la mutación (mutateAsync). Si falla, el error se muestra aquí. */
  alEnviar: (valores: V) => Promise<unknown>
  textoEnviar: string
}

/**
 * Formulario genérico de todas las entidades (spec 010, reglas 8, 11 y 12).
 * La pantalla declara sus campos y su esquema de Zod; este componente los
 * dibuja, valida, oculta lo que no aplica, vacía lo que depende de otro campo y
 * pone cada error de la API junto a su campo.
 */
export function FormularioDatos<V extends FieldValues>({
  campos,
  esquema,
  valoresIniciales,
  alEnviar,
  textoEnviar,
}: Props<V>) {
  const formulario = useForm<V>({
    resolver: zodResolver(esquema),
    defaultValues: valoresIniciales,
  })
  const [errorGeneral, setErrorGeneral] = useState<string | null>(null)
  // watch() devuelve todos los valores y vuelve a dibujar el formulario cuando
  // cambian: es lo que permite visibleSi y dependeDe. oxlint avisa que no se
  // lleva con el React Compiler, que este proyecto no usa (vite.config.ts).
  // oxlint-disable-next-line react/incompatible-library
  const valores = formulario.watch()
  const visibles = campos.filter((campo) => campo.visibleSi?.(valores) ?? true)

  /** Vacía los campos que dependen del que acaba de cambiar. */
  const vaciarDependientes = (nombre: string) => {
    for (const campo of campos) {
      if (campo.dependeDe === nombre) {
        formulario.setValue(campo.nombre, '' as V[typeof campo.nombre])
      }
    }
  }

  const enviar = formulario.handleSubmit(async (datos) => {
    setErrorGeneral(null)
    // Un campo oculto no se envía (regla 12).
    const aEnviar = { ...datos }
    for (const campo of campos) {
      if (!visibles.includes(campo)) {
        delete aEnviar[campo.nombre]
      }
    }
    try {
      await alEnviar(aEnviar)
    } catch (excepcion) {
      mostrarErrorApi(excepcion)
    }
  })

  /**
   * Regla 8: cada error de `detalles` va junto a su campo; lo que no
   * corresponde a ningún campo visible (un 409, un 403) va arriba.
   */
  const mostrarErrorApi = (excepcion: unknown) => {
    const error = leerErrorApi(excepcion)
    let quedoSinCampo = true
    for (const [nombre, mensajes] of Object.entries(error.detalles)) {
      const campo = visibles.find((visible) => visible.nombre === nombre)
      if (campo) {
        const mensaje = Array.isArray(mensajes) ? String(mensajes[0]) : String(mensajes)
        formulario.setError(campo.nombre, { message: mensaje })
        quedoSinCampo = false
      }
    }
    if (quedoSinCampo) {
      setErrorGeneral(error.mensaje)
    }
  }

  const errores = formulario.formState.errors

  return (
    <form onSubmit={enviar} className="flex max-w-2xl flex-col gap-4" noValidate>
      {errorGeneral && (
        <p role="alert" className="rounded-md bg-red-50 p-3 text-sm text-red-700">
          {errorGeneral}
        </p>
      )}

      {visibles.map((campo) => {
        const error = errores[campo.nombre]?.message
        const id = `campo-${campo.nombre}`
        const invalido = error ? true : undefined

        if (campo.tipo === 'booleano') {
          return (
            <label key={campo.nombre} className="flex items-center gap-2 text-sm">
              <input type="checkbox" {...formulario.register(campo.nombre)} />
              {campo.etiqueta}
            </label>
          )
        }

        let control
        if (campo.tipo === 'seleccion') {
          control = (
            <Select
              id={id}
              aria-invalid={invalido}
              {...formulario.register(campo.nombre, {
                onChange: () => vaciarDependientes(campo.nombre),
              })}
            >
              <option value="">Elija una opción</option>
              {campo.opciones.map((opcion) => (
                <option key={opcion.valor} value={opcion.valor}>
                  {opcion.etiqueta}
                </option>
              ))}
            </Select>
          )
        } else if (campo.tipo === 'relacion') {
          const falta = campo.dependeDe !== undefined && !valores[campo.dependeDe]
          control = (
            <Controller
              control={formulario.control}
              name={campo.nombre}
              render={({ field }) => (
                <CampoRelacion
                  // Al cambiar el campo del que depende, la key cambia y React
                  // crea el campo de nuevo, vacío (regla 12).
                  key={campo.dependeDe ? String(valores[campo.dependeDe]) : undefined}
                  id={id}
                  valor={String(field.value ?? '')}
                  alElegir={(valor) => {
                    field.onChange(valor)
                    vaciarDependientes(campo.nombre)
                  }}
                  buscar={(texto) => campo.buscar(texto, valores)}
                  deshabilitado={falta}
                  marcador={falta ? campo.marcador : undefined}
                  invalido={invalido}
                />
              )}
            />
          )
        } else if (campo.tipo === 'area') {
          control = (
            <textarea
              id={id}
              rows={3}
              aria-invalid={invalido}
              className={cn(
                'w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-400',
                error && 'border-red-500',
              )}
              {...formulario.register(campo.nombre)}
            />
          )
        } else {
          control = (
            <Input
              id={id}
              inputMode={campo.tipo === 'numero' ? 'decimal' : undefined}
              aria-invalid={invalido}
              {...formulario.register(campo.nombre)}
            />
          )
        }

        return (
          <div key={campo.nombre} className="flex flex-col gap-1.5">
            <Label htmlFor={id}>{campo.etiqueta}</Label>
            {control}
            {campo.ayuda && !error && (
              <p className="text-xs text-slate-500">{campo.ayuda}</p>
            )}
            {error && <p className="text-xs text-red-600">{String(error)}</p>}
          </div>
        )
      })}

      <div>
        <Button type="submit" disabled={formulario.formState.isSubmitting}>
          {formulario.formState.isSubmitting ? 'Guardando…' : textoEnviar}
        </Button>
      </div>
    </form>
  )
}
