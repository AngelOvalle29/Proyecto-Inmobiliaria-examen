import { Card, CardContent, CardHeader, CardTitle } from '../../componentes/ui/card'
import { EstadoServicio } from '../estado/EstadoServicio'

/** Primera pantalla después de entrar (spec 010, §5). */
export function Inicio() {
  return (
    <div className="flex max-w-2xl flex-col gap-4">
      <h1 className="text-2xl font-semibold">Inicio</h1>
      <Card>
        <CardHeader>
          <CardTitle>Estado del sistema</CardTitle>
        </CardHeader>
        <CardContent>
          <EstadoServicio />
        </CardContent>
      </Card>
    </div>
  )
}
