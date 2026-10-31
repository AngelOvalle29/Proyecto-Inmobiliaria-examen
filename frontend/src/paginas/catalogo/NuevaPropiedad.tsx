import { useNavigate } from 'react-router'
import { z } from 'zod'

import { useTiposPropiedad } from '../../api/catalogo/consultas'
import { useCrearPropiedad } from '../../api/catalogo/mutaciones'
import { useBuscarCiudades, useMonedas, usePaises } from '../../api/core/consultas'
import {
  FormularioDatos,
  type CampoFormulario,
} from '../../componentes/comunes/FormularioDatos'

// Solo el formato del número. Que sea mayor que cero es una regla de negocio
// (regla 4 de la spec 003) y la valida la API: su error aparece junto al campo.
const numero = z
  .string()
  .regex(/^\d+(\.\d{1,2})?$/, 'Escriba un número, con hasta dos decimales.')

const esquema = z.object({
  nombre: z.string().min(1, 'Escriba el nombre.').max(150),
  tipo_id: z.string().min(1, 'Elija el tipo.'),
  // El país no se guarda en la propiedad (es el de la ciudad): solo sirve
  // para buscar la ciudad dentro de él.
  pais: z.string().min(1, 'Elija el país.'),
  ciudad_id: z.string().min(1, 'Busque y elija la ciudad.'),
  direccion: z.string().min(1, 'Escriba la dirección.').max(255),
  area_m2: numero,
  // Opcional y oculta para un terreno, que no tiene construcción.
  area_construida_m2: numero.or(z.literal('')).optional(),
  precio_lista: numero,
  moneda_id: z.string().min(1, 'Elija la moneda.'),
  es_publica: z.boolean(),
  descripcion: z.string(),
})

type Datos = z.infer<typeof esquema>

/** Hook de búsqueda de la ciudad: dentro del país elegido (spec 010, reglas 11 y 12). */
function useOpcionesCiudad(texto: string, valores: Datos) {
  const pais = valores.pais ? Number(valores.pais) : undefined
  const consulta = useBuscarCiudades(texto, pais)
  return {
    opciones: (consulta.data ?? []).map((ciudad) => ({
      valor: String(ciudad.id),
      etiqueta: ciudad.region ? `${ciudad.nombre} (${ciudad.region})` : ciudad.nombre,
    })),
    cargando: consulta.isFetching,
  }
}

/** Ejemplo de formulario (spec 010, §5): crear una propiedad. */
export function NuevaPropiedad() {
  const navegar = useNavigate()
  const crear = useCrearPropiedad()
  const tipos = useTiposPropiedad()
  const paises = usePaises()
  const monedas = useMonedas()

  // El tipo "Terreno" lo crea la migración 0002 del catálogo con ese nombre.
  const idTerreno = tipos.data?.find((tipo) => tipo.nombre === 'Terreno')?.id

  const campos: CampoFormulario<Datos>[] = [
    { nombre: 'nombre', etiqueta: 'Nombre', tipo: 'texto' },
    {
      nombre: 'tipo_id',
      etiqueta: 'Tipo',
      tipo: 'seleccion',
      opciones: (tipos.data ?? []).map((tipo) => ({
        valor: String(tipo.id),
        etiqueta: tipo.nombre,
      })),
    },
    {
      nombre: 'pais',
      etiqueta: 'País',
      tipo: 'seleccion',
      opciones: (paises.data ?? []).map((pais) => ({
        valor: String(pais.id),
        etiqueta: pais.nombre,
      })),
    },
    {
      nombre: 'ciudad_id',
      etiqueta: 'Ciudad',
      tipo: 'relacion',
      dependeDe: 'pais',
      marcador: 'Primero elija el país',
      buscar: useOpcionesCiudad,
    },
    { nombre: 'direccion', etiqueta: 'Dirección', tipo: 'texto' },
    { nombre: 'area_m2', etiqueta: 'Área del terreno (m²)', tipo: 'numero' },
    {
      nombre: 'area_construida_m2',
      etiqueta: 'Área construida (m²)',
      tipo: 'numero',
      ayuda: 'Opcional.',
      visibleSi: (valores) => valores.tipo_id !== String(idTerreno),
    },
    {
      nombre: 'moneda_id',
      etiqueta: 'Moneda',
      tipo: 'seleccion',
      opciones: (monedas.data ?? []).map((moneda) => ({
        valor: String(moneda.id),
        etiqueta: `${moneda.codigo} · ${moneda.nombre}`,
      })),
    },
    { nombre: 'precio_lista', etiqueta: 'Precio de lista', tipo: 'numero' },
    {
      nombre: 'descripcion',
      etiqueta: 'Descripción',
      tipo: 'area',
      ayuda: 'Opcional.',
    },
    {
      nombre: 'es_publica',
      etiqueta: 'Mostrar en la consulta pública',
      tipo: 'booleano',
    },
  ]

  /** Del formulario (todo texto) a lo que espera la API (ids numéricos). */
  const guardar = async (datos: Datos) => {
    const creada = await crear.mutateAsync({
      nombre: datos.nombre,
      tipo_id: Number(datos.tipo_id),
      ciudad_id: Number(datos.ciudad_id),
      direccion: datos.direccion,
      area_m2: datos.area_m2,
      area_construida_m2: datos.area_construida_m2 || null,
      precio_lista: datos.precio_lista,
      moneda_id: Number(datos.moneda_id),
      es_publica: datos.es_publica,
      descripcion: datos.descripcion,
    })
    // Se muestra en la lista, ya con el código que le asignó el backend.
    navegar(`/catalogo/propiedades?buscar=${creada.codigo ?? ''}`)
  }

  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-2xl font-semibold">Nueva propiedad</h1>
      <FormularioDatos
        campos={campos}
        esquema={esquema}
        valoresIniciales={{
          nombre: '',
          tipo_id: '',
          pais: '',
          ciudad_id: '',
          direccion: '',
          area_m2: '',
          area_construida_m2: '',
          precio_lista: '',
          moneda_id: '',
          es_publica: false,
          descripcion: '',
        }}
        alEnviar={guardar}
        textoEnviar="Crear propiedad"
      />
    </div>
  )
}
