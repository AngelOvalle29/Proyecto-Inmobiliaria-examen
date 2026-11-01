import { useNavigate } from 'react-router'
import { z } from 'zod'

import { useCrearAgente } from '../../api/crm/mutaciones'
import { useOpcionesUsuarioAgente } from '../../api/usuarios/consultas'
import {
  FormularioDatos,
  type CampoFormulario,
} from '../../componentes/comunes/FormularioDatos'
import { fechaDeHoy } from '../../lib/formato'

// Solo el formato: el rango de 0 a 100 lo valida la API (spec 004, regla 3).
const esquema = z.object({
  usuario: z.string().min(1, 'Busque y elija el usuario.'),
  porcentaje_comision: z
    .string()
    .regex(/^\d+(\.\d{1,2})?$/, 'Escriba un número, con hasta dos decimales.'),
  fecha_ingreso: z.string().min(1, 'Elija la fecha de ingreso.'),
})

type Datos = z.infer<typeof esquema>

const CAMPOS: CampoFormulario<Datos>[] = [
  {
    nombre: 'usuario',
    etiqueta: 'Usuario',
    tipo: 'relacion',
    ayuda: 'Solo usuarios activos con rol de agente.',
    buscar: useOpcionesUsuarioAgente,
  },
  {
    nombre: 'porcentaje_comision',
    etiqueta: 'Comisión (%)',
    tipo: 'numero',
    ayuda: 'Entre 0 y 100, con dos decimales.',
  },
  { nombre: 'fecha_ingreso', etiqueta: 'Fecha de ingreso', tipo: 'fecha' },
]

/**
 * Crea el perfil comercial de un usuario que ya existe (spec 004, regla 1). La
 * lista incluye a quienes ya son agentes, porque `usuarios` no conoce `crm`
 * (spec 013): elegir a uno responde 409 USUARIO_YA_ES_AGENTE, que sale arriba
 * del formulario.
 */
export function NuevoAgente() {
  const navegar = useNavigate()
  const crear = useCrearAgente()

  const guardar = async (datos: Datos) => {
    const agente = await crear.mutateAsync({
      usuario: Number(datos.usuario),
      porcentaje_comision: datos.porcentaje_comision,
      fecha_ingreso: datos.fecha_ingreso,
    })
    navegar(`/crm/agentes?buscar=${agente.codigo ?? ''}`)
  }

  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-2xl font-semibold">Nuevo agente</h1>
      <FormularioDatos
        campos={CAMPOS}
        esquema={esquema}
        valoresIniciales={{
          usuario: '',
          porcentaje_comision: '',
          fecha_ingreso: fechaDeHoy(),
        }}
        alEnviar={guardar}
        textoEnviar="Crear agente"
      />
    </div>
  )
}
