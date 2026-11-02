# Guía de defensa: bloque B (CRM, ventas, arrendamientos y reportes comerciales)

Para preparar la defensa oral. Cada integrante debe poder explicar cualquier
parte del sistema (`docs/requisitos.md` §10), así que sirve también al resto del
equipo.

**Cómo usarla:** tapa cada respuesta e intenta decirla con tus palabras, y abre
el archivo que se indica. Si solo puedes repetirla, todavía no la entendiste.

---

## 1. El sistema en un minuto

Un ERP para una agencia inmobiliaria. El bloque B cubre desde que aparece un
cliente hasta que paga:

```
Cliente → Cotización → Contrato de venta → Cuotas → Pagos
                       Contrato de arrendamiento → Pagos de renta
```

Cada app sigue las mismas capas:

| Capa | Archivo | Qué hace |
|---|---|---|
| HTTP | `views.py`, `serializers.py` | Valida la entrada, llama y formatea la salida |
| Escrituras | `services.py` | Reglas de negocio y transacciones |
| Lecturas | `selectors.py` | Consultas, filtros y agregaciones |
| Datos | `models.py` | Campos y constraints |

**Por qué así:** una regla vive en un solo lugar. Las pantallas, los reportes y
el agente reutilizan el mismo selector y no pueden contradecirse.

---

## 2. Recorrido de una venta

**Abre:** `apps/crm/services.py` y `apps/ventas/services.py`.

1. **Cotizar.** El precio sale de la lista del bien y el total es precio menos
   descuento, calculado por el servicio. Nace en `BORRADOR`.
2. **Enviar:** pasa a `ENVIADA`.
3. **Aprobar:** pasa a `APROBADA` y el bien a `RESERVADA`. Si otro lo reservó
   antes, falla.
4. **Firmar:** `firmar_contrato`. El bien pasa a `VENDIDA`, y se guardan la tasa
   al dólar, el monto en dólares y la comisión.
   - **Contado:** nace `LIQUIDADO`, sin cuotas.
   - **Financiado:** nace `VIGENTE` y genera sus cuotas.
5. **Pagar:** `registrar_pago_cuota`. Puede ser parcial. Al pagar la última
   cuota, el contrato pasa a `LIQUIDADO`.

**Anular** solo se puede con un contrato vigente sin pagos, y el bien vuelve a
`DISPONIBLE`. Con pagos no, porque habría que devolver dinero y eso está fuera
de alcance.

### Ejemplo con la demo: CV-00001
Monto Q 820,000, enganche Q 164,000, 60 cuotas, 8.5 % anual.

- Saldo: 820,000 − 164,000 = **656,000**
- Tasa mensual: 8.5 / 12 / 100 = 0.0070833
- Cuota fija: `P · i / (1 − (1 + i)^−n)` = **13,458.84**
- Primera cuota: interés 656,000 · 0.0070833 = **4,646.67**; capital 13,458.84 −
  4,646.67 = **8,812.17**

Al principio se debe mucho, así que la cuota es casi todo interés. Al final es
casi todo capital. Es el sistema francés.

**La última cuota es distinta** (13,459.23 en esta demo): su capital es
exactamente lo que falta, para que el redondeo no deje centavos sueltos.

---

## 3. Recorrido de un arrendamiento

**Abre:** `apps/arrendamientos/services.py`.

1. **Firmar:** se generan de una vez todos los pagos de renta, y el bien pasa a
   `ARRENDADA`.
2. **Cobrar:** `registrar_pago_renta`. Se paga completo y una sola vez.
3. **Recargo:** `calcular_recargo`. Si se paga después del vencimiento más los
   días de gracia, se cobra renta · porcentaje. El último día de gracia todavía
   no tiene recargo.
4. **Terminar**, de tres formas:
   - **Renovar:** crea un contrato nuevo que empieza al día siguiente del fin
     del anterior. El anterior queda `RENOVADO` y el bien sigue `ARRENDADA`.
   - **Rescindir:** el inquilino se va antes. Se cancelan los pagos que vencen
     después de esa fecha, y los anteriores se siguen debiendo.
   - **Finalizar:** solo si la fecha de fin ya pasó. Pasa a `VENCIDO` y el bien
     vuelve a `DISPONIBLE`.

**Mora contra recargo:** son cosas distintas. Una renta está en mora desde el
día siguiente al vencimiento. La gracia solo decide si se cobra recargo.

---

## 4. Preguntas probables

### Arquitectura

**¿Por qué una vista no puede hacer `Model.objects.filter`?**
Porque las consultas viven en `selectors.py`. Si la cartera se aplicara en cada
vista, bastaría olvidarla una vez para exponer datos ajenos.

**¿Por qué no usan señales de Django?**
Son difíciles de rastrear: la escritura pasa sin que se vea en el código que la
provoca. `registrar_auditoria` se llama de forma explícita en cada servicio.

**¿Por qué la auditoría no abre su propia transacción?**
Porque debe caer dentro de la del servicio. Si la operación falla y se revierte,
su registro también. Nunca queda una operación sin registro, ni un registro de
algo que no ocurrió.

**¿Qué hace `transaction.atomic`?**
Agrupa las escrituras: se guardan todas o ninguna. Firmar toca el bien, el
contrato, las cuotas y la auditoría. Si algo falla, no queda un bien vendido sin
contrato.

**¿Qué hace `select_for_update`?**
Bloquea la fila hasta el fin de la transacción. Si llegan dos pagos a la vez, el
segundo espera y lee el saldo que dejó el primero. Sin eso, los dos leerían el
mismo saldo y podrían pagar de más.

**¿Por qué bloquear primero el contrato y después la cuota?**
Para mantener siempre el mismo orden. Si dos operaciones bloquearan en orden
inverso, cada una esperaría a la otra (deadlock).

### Reglas de negocio

**¿Por qué `en_mora` no es un campo?**
Porque depende de la fecha de hoy. Guardado, habría que actualizarlo cada día y
podría quedar desactualizado. Calculado, nunca se equivoca.

**¿Por qué los montos usan `Decimal` y no `float`?**
`float` no representa exactamente valores como 0.1, y los errores se acumulan.
Con dinero se necesitan centavos exactos. También se redondea con `ROUND_HALF_UP`.

**¿Por qué se guarda la tasa de cambio en cada contrato y pago?**
Porque las tasas cambian. Si un reporte convirtiera con la de hoy, el pasado
cambiaría cada día. Se guarda la tasa de la fecha de la operación.

**¿Por qué se guarda la comisión?**
Si después cambia el porcentaje del agente, ese contrato no debe cambiar. Con
cotización, la comisión es del agente que cotizó, aunque el cliente se haya
reasignado.

**¿Por qué solo una cotización aprobada por bien?**
Aprobar exige que el bien esté `DISPONIBLE` y lo pasa a `RESERVADA`, dentro de un
bloqueo de su fila. La segunda aprobación encuentra el bien reservado y falla.

**¿Por qué no se borran contratos?**
Por trazabilidad: es borrado lógico con `activo`, y anular es un estado. Los
registros se conservan.

### Permisos

**¿Qué pasa si un agente pide un cliente ajeno?**
Responde **404, no 403**. Un 403 confirmaría que ese cliente existe. Toda la
regla está en `listar_clientes_visibles`: el agente solo ve su cartera, y los
contratos y cotizaciones parten de ese selector.

**¿Cómo funciona `TieneRol`?**
Cada vista declara `roles_por_metodo`. Un `GET` no declarado queda para
cualquier usuario autenticado. Una escritura no declarada se rechaza con 403:
olvidarla deja la puerta cerrada, no abierta.

**Si el frontend oculta un botón, ¿ya está protegido?**
No. Ocultar es comodidad. Quien protege es el backend, que valida cada petición.

### Frontend

**¿Por qué no hay `fetch` en los componentes?**
Todo pasa por TanStack Query, que maneja caché, recarga y estados de carga.

**¿De dónde salen los tipos?**
Se generan del esquema OpenAPI con `npm run gen:api`. Si la API cambia, el
compilador avisa.

### Reportes (`apps/reportes/selectors_comerciales.py`)

**¿Por qué usan subconsultas en R02 y R04?**
Con varios `join`, cada cotización se multiplicaría por cada contrato y los
totales saldrían inflados. Cada total se calcula aparte.

**¿Cómo pagina R10 cuotas y rentas juntas?**
Con `union`: son dos consultas con las mismas columnas que PostgreSQL une como
una lista, y el `LIMIT` se aplica en SQL. Nunca se cargan todas en memoria.

**¿Por qué no se suman monedas distintas?**
Porque sumar quetzales con pesos no significa nada. Los totales van por moneda,
y los consolidados usan los dólares guardados.

**¿Por qué el saldo cuenta cuotas futuras pero no rentas futuras?**
La deuda de una venta se firmó completa. Un mes de renta futuro todavía no se
debe: solo se deben las rentas vencidas.

**¿Por qué R11 filtra `contrato__estado=VIGENTE`?**
Porque un filtro en SQL no pasa por `CuotaPago.en_mora()`. Las cuotas de un
contrato anulado siguen en `PENDIENTE`, y sin ese filtro aparecerían como deuda.
La regla está en dos lugares a propósito, y hay que recordarlo.

**¿Por qué "Sin dato" y no 0?**
Una venta sin cotización tiene descuento desconocido, no descuento cero. Y una
conversión sin cotizaciones no existe. Presentarlo como 0 sería mentir.

**¿Cómo está protegida la cartera en los totales?**
Los selectores parten de los de cada app, que ya filtran por cartera, antes de
contar y sumar. No basta con ocultar filas si el total sigue incluyéndolas.

**¿Por qué R03 no tiene tiempos por etapa?**
Se recortó en la spec 021 por plazo. Los eventos están en la bitácora, y en la
demo todas las transiciones ocurren en el mismo instante.

---

## 5. Dónde están las cosas

| Tema | Archivo |
|---|---|
| Cartera | `apps/crm/selectors.py`, `listar_clientes_visibles` |
| Cuotas | `apps/ventas/services.py`, `calcular_cuotas` |
| Pago de cuota | `apps/ventas/services.py`, `registrar_pago_cuota` |
| Mora | `apps/ventas/models.py` y `apps/arrendamientos/models.py`, `en_mora` |
| Recargo | `apps/arrendamientos/services.py`, `calcular_recargo` |
| Permisos | `apps/usuarios/permissions.py`, `TieneRol` |
| Auditoría | `apps/auditoria/services.py`, `registrar_auditoria` |
| Errores | `apps/core/exceptions.py`, `ErrorDominio` |
| Reportes comerciales | `apps/reportes/selectors_comerciales.py` |
| Reglas | `specs/004`, `specs/007`, `specs/008`, `specs/012` y `specs/021` |

---

## 6. Antes de la defensa

- [ ] Explicar el recorrido de una venta sin mirar.
- [ ] Calcular a mano la primera cuota del ejemplo.
- [ ] Abrir `registrar_pago_cuota` y explicarlo línea por línea.
- [ ] Explicar por qué 404 y no 403.
- [ ] Explicar una consulta de R10 o R11.
- [ ] Mostrar en vivo: cotizar, aprobar, firmar y pagar, con `A-103` o `A-203`.
- [ ] Explicar lo que hizo un agente de IA y qué decidiste tú (la §11 de cada spec).
- [ ] Repasar las partes de tus compañeros: catálogo, IA, reportes y mensajería.
