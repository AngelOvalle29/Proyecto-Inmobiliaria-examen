import { zodResolver } from '@hookform/resolvers/zod'
import { useForm } from 'react-hook-form'
import { Link, Navigate, useLocation, useNavigate } from 'react-router'
import { z } from 'zod'

import { leerErrorApi } from '../../api/errores'
import { useIniciarSesion } from '../../api/usuarios/mutaciones'
import { Button } from '../../componentes/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '../../componentes/ui/card'
import { Input } from '../../componentes/ui/input'
import { Label } from '../../componentes/ui/label'
import { useSesion } from '../../sesion/useSesion'

const esquema = z.object({
  email: z.email('Escriba un correo válido.'),
  password: z.string().min(1, 'Escriba la contraseña.'),
})

type Datos = z.infer<typeof esquema>

/** Inicio de sesión (spec 010, §5). */
export function Login() {
  const { estado, abrirSesion } = useSesion()
  const navegar = useNavigate()
  const ubicacion = useLocation()
  const iniciar = useIniciarSesion()
  const formulario = useForm<Datos>({ resolver: zodResolver(esquema) })

  // La ruta que se pidió antes de llegar aquí (RutaProtegida la guarda).
  const desde = (ubicacion.state as { desde?: string } | null)?.desde ?? '/'

  if (estado === 'con-sesion') {
    return <Navigate to={desde} replace />
  }

  const enviar = formulario.handleSubmit((datos) => {
    iniciar.mutate(datos, {
      onSuccess: (tokens) => {
        abrirSesion(tokens)
        navegar(desde, { replace: true })
      },
    })
  })

  const errores = formulario.formState.errors

  // Spec 022: díptico editorial. El panel óxido presenta el sistema y la
  // tarjeta blanca lleva el formulario; en el teléfono quedan uno sobre otro.
  return (
    <div className="grid w-full max-w-4xl overflow-hidden rounded-2xl md:grid-cols-2">
      <section className="flex flex-col justify-between gap-10 bg-oxido p-8 text-crema md:p-10">
        <p className="font-mono text-xs tracking-etiqueta uppercase">Inmobiliaria</p>
        <div className="flex flex-col gap-4">
          <h1 className="font-editorial text-5xl leading-none md:text-6xl">
            Sistema de Gestión Inmobiliaria
          </h1>
          <p className="text-lg leading-snug text-crema/85">
            Propiedades, clientes, contratos y reportes de la agencia en un solo lugar.
          </p>
        </div>
      </section>
      <Card className="rounded-none border-0">
        <CardHeader>
          <CardTitle>Iniciar sesión</CardTitle>
          <p className="text-sm text-tenue">Inicie sesión para continuar.</p>
        </CardHeader>
        <CardContent>
          <form onSubmit={enviar} className="flex flex-col gap-4" noValidate>
            {iniciar.isError && (
              <p role="alert" className="rounded-md bg-red-50 p-3 text-sm text-red-700">
                {leerErrorApi(iniciar.error).mensaje}
              </p>
            )}
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="email">Correo</Label>
              <Input
                id="email"
                type="email"
                autoComplete="username"
                aria-invalid={errores.email ? true : undefined}
                {...formulario.register('email')}
              />
              {errores.email && (
                <p className="text-xs text-red-600">{errores.email.message}</p>
              )}
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="password">Contraseña</Label>
              <Input
                id="password"
                type="password"
                autoComplete="current-password"
                aria-invalid={errores.password ? true : undefined}
                {...formulario.register('password')}
              />
              {errores.password && (
                <p className="text-xs text-red-600">{errores.password.message}</p>
              )}
            </div>
            <Button type="submit" disabled={iniciar.isPending}>
              {iniciar.isPending ? 'Entrando…' : 'Entrar'}
            </Button>
          </form>
          {/* Spec 018, §5: un visitante sin cuenta encuentra el asistente. */}
          <p className="mt-4 text-center text-sm text-tenue">
            ¿Tiene una pregunta sobre nuestras propiedades?{' '}
            <Link
              className="text-oxido underline-offset-4 hover:underline"
              to="/asistente"
            >
              Consulte al asistente
            </Link>
          </p>
        </CardContent>
      </Card>
    </div>
  )
}
