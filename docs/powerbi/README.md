# Power BI

Power BI lee cuatro vistas del esquema `bi` de PostgreSQL, en modelo estrella
(spec 021, §4). Las crea la migración `reportes/0001_vistas_bi`, así que existen
en toda base migrada: local y Neon.

| Vista | Grano | Clave |
|---|---|---|
| `bi.dim_tiempo` | Un día | `fecha_id` (entero AAAAMMDD) |
| `bi.dim_geografia` | Una ciudad, con su país | `ciudad_id` |
| `bi.dim_propiedad` | Un bien: propiedad sin unidades o unidad de un edificio | `bien_clave` (`PROPIEDAD-12`, `UNIDAD-5`) |
| `bi.hechos_ventas` | Un contrato de venta no anulado | `contrato_id` |

Relaciones, todas de muchos a uno desde `hechos_ventas`:
- `hechos_ventas.fecha_id` → `dim_tiempo.fecha_id`
- `hechos_ventas.bien_clave` → `dim_propiedad.bien_clave`
- `hechos_ventas.ciudad_id` → `dim_geografia.ciudad_id`

Los montos van en su moneda (`neto`, con `moneda`) y en dólares (`neto_usd`),
con la tasa guardada al firmar. Para sumar entre monedas use `neto_usd`. Estado
y ciudad de la propiedad son los actuales, no los de la fecha de la venta.

## Conectar Power BI Desktop a Neon

1. **Rol de solo lectura:** el administrador de la base corre
   `crear_lector.sql` en el SQL Editor de Neon, con una contraseña propia, y
   la pasa por privado. Una sola vez.
2. En Power BI Desktop: *Obtener datos → Base de datos PostgreSQL*.
   - **Servidor:** el host de Neon (`ep-…neon.tech`), sin `postgres://` ni puerto.
   - **Base de datos:** la de `DATABASE_URL` en Render (Neon la llama `neondb` por defecto).
   - **Modo:** Importar.
   - **Credenciales:** *Base de datos*, usuario `powerbi_reader`.
   - **Cifrado:** deje la conexión cifrada (SSL). Neon la exige; no se desactiva
     la validación del certificado para que funcione.
3. Marque las cuatro vistas de `bi` y cárguelas.
4. Revise las tres relaciones de arriba en la vista de modelo.

Neon suspende la base cuando no se usa: la primera actualización puede tardar
unos segundos mientras despierta.

El tablero se guarda en `docs/powerbi/inmobiliaria.pbix`, con una página
comercial: ventas por mes, país, ciudad y tipo de propiedad, en USD y por
cantidad de contratos.
