# 026 · Gestión de usuarios desde el sistema

| Campo | Valor |
|---|---|
| **Número** | 026 |
| **Estado** | Implementada |
| **Autor** | Douglas Gerardo Morales Velásquez (rol A) |
| **Revisor** | Por asignar |
| **Fecha** | 2026-11-04 |
| **Apps afectadas** | `usuarios` (servicios, selectores, API) y `frontend/` (`paginas/usuarios`, menú) |
| **Rama** | `feature/026-gestion-usuarios` |
| **Pull request** | [DouGMV/Proyecto-Inmobiliaria#110](https://github.com/DouGMV/Proyecto-Inmobiliaria/pull/110) |

---

## 1. Problema

Hoy los usuarios solo se crean y se editan en el panel de Django (`/admin/`).
Para que otra persona administre cuentas hay que darle acceso a ese panel, que
permite tocar cualquier tabla de la base sin las reglas de negocio ni la
auditoría del sistema. Tampoco hay forma de que un usuario cambie su propia
contraseña.

## 2. Alcance

**Incluye:**
- Una pantalla **Usuarios**, solo para `ADMINISTRADOR`: listar con filtros,
  crear, editar, desactivar, reactivar y restablecer la contraseña.
- **Cambiar mi contraseña** para cualquier usuario con sesión.
- Auditoría de cada operación, sin guardar nunca una contraseña.

**No incluye:**
- Recuperar la contraseña por correo: no hay envío de correo (spec 020).
- Dar acceso al panel de Django (`is_staff`): sigue siendo cosa de `/admin/`.
- Crear el perfil de agente: sigue en CRM (spec 004).

## 3. Reglas de negocio

1. **Solo `ADMINISTRADOR` gestiona usuarios.** `GERENTE` sigue viendo el
   listado de activos para crear agentes (spec 013), sin escribir.
2. **Un correo, una cuenta**, sin distinguir mayúsculas (spec 001, regla 1).
   Repetirlo responde 409 `USUARIO_DUPLICADO`.
3. **La contraseña cumple los validadores del sistema** (mínimo 10
   caracteres, no común, no parecida al correo ni al nombre). Si no, 400
   `CONTRASENA_INVALIDA` con los motivos.
4. **Nadie se desactiva ni se cambia el rol a sí mismo** (409
   `OPERACION_SOBRE_SI_MISMO`): así un administrador no puede quedarse fuera
   por error.
5. **Siempre queda al menos un `ADMINISTRADOR` activo** (409
   `ULTIMO_ADMINISTRADOR`).
6. **Un superusuario es siempre `ADMINISTRADOR`** (spec 001, regla 3): su rol
   no se cambia aquí (409 `SUPERUSUARIO_ES_ADMINISTRADOR`).
7. **Un usuario con perfil de agente activo no cambia de rol ni se desactiva**
   (409 `USUARIO_CON_PERFIL_AGENTE`): primero se desactiva el agente en CRM,
   que revisa que no tenga clientes (spec 004, regla 4).
8. **Desactivar es borrado lógico** (`is_active`). El usuario no puede iniciar
   sesión, y sus tokens dejan de servir en la petición siguiente: la
   autenticación JWT rechaza a un usuario inactivo.
9. **Cambiar mi contraseña exige la actual** (400 `CONTRASENA_ACTUAL_INCORRECTA`).
10. **Auditoría:** crear, editar, desactivar, reactivar y cada cambio de
    contraseña quedan en la bitácora, con el usuario que lo hizo y la IP. La
    contraseña nunca se guarda en la bitácora, ni cifrada.
11. **Los usuarios creados aquí no entran al panel de Django** (`is_staff` en
    falso).

## 4. Modelo de datos

Sin cambios: `usuarios.Usuario` ya tiene todo lo necesario.

## 5. API

| Método | Ruta | Quién |
|---|---|---|
| GET | `/api/v1/usuarios/?estado=ACTIVOS\|INACTIVOS\|TODOS&rol=&buscar=` | `ADMINISTRADOR`, `GERENTE` (por omisión, `ACTIVOS`) |
| POST | `/api/v1/usuarios/` | `ADMINISTRADOR` |
| GET, PATCH | `/api/v1/usuarios/{id}/` · PATCH: nombre, rol, país y teléfono | `ADMINISTRADOR` |
| POST | `/api/v1/usuarios/{id}/desactivar/` y `/reactivar/` | `ADMINISTRADOR` |
| POST | `/api/v1/usuarios/{id}/restablecer-contrasena/` | `ADMINISTRADOR` |
| POST | `/api/v1/auth/cambiar-contrasena/` | Cualquier usuario con sesión |

El listado agrega `activo` a cada fila. El detalle agrega teléfono y último
acceso. El correo no se edita: identifica la cuenta y su historial.

## 6. Servicios y selectores

- `usuarios/services.py`: `crear_usuario`, `actualizar_usuario`,
  `desactivar_usuario`, `reactivar_usuario`, `restablecer_contrasena` y
  `cambiar_mi_contrasena`. Todas en `transaction.atomic`, con bloqueo de la
  fila (`select_for_update`) donde se revisan las reglas 4 a 7.
- `usuarios/selectors.py`: `listar_usuarios(estado=...)`,
  `contar_administradores_activos()` y `tiene_perfil_de_agente_activo(usuario)`.
  Este último usa la relación inversa `usuario.agente`, sin importar `crm`:
  `crm` ya depende de `usuarios` y la importación sería circular.
- Frontend: `paginas/usuarios/ListaUsuarios.tsx`, `FormularioUsuario.tsx`,
  `DialogoContrasena.tsx` y `paginas/cuenta/CambiarContrasena.tsx`; el menú
  agrega **Usuarios** (solo `ADMINISTRADOR`), y el pie del menú, **Cambiar
  contraseña**.

## 7. Auditoría

| Acción | Valores |
|---|---|
| Crear | Correo, nombre, rol, país y teléfono |
| Editar | Los campos que cambian, antes y después |
| Desactivar, reactivar | `activo` |
| Contraseña | `{"contrasena": "restablecida"}` o `"cambiada por el usuario"`, nunca el valor |

## 8. Criterios de aceptación

- [x] Un administrador crea un usuario y ese usuario inicia sesión
- [x] Un correo repetido (con otras mayúsculas) responde 409
- [x] Una contraseña débil responde 400 con los motivos
- [x] Nadie se desactiva a sí mismo ni deja el sistema sin administradores
- [x] Un usuario con perfil de agente activo no se desactiva ni cambia de rol
- [x] Un usuario desactivado no inicia sesión y su token deja de servir
- [x] `GERENTE`, `AGENTE`, `CONTABILIDAD` y `CONSULTA` reciben 403 al escribir
- [x] Cualquier usuario cambia su contraseña dando la actual
- [x] Ninguna contraseña aparece en la bitácora
- [x] `pytest`, `ruff`, `npm run lint`, `npm run typecheck` y `npm run build` pasan

## 9. Pruebas

| Nivel | Caso |
|---|---|
| Servicio | Cada regla de §3, con su error |
| API | Permisos por rol, listado por estado, crear, editar, desactivar, reactivar, restablecer y cambiar la propia contraseña |
| API | El token de un usuario desactivado responde 401 |

## 10. Decisiones y alternativas descartadas

- **Solo `ADMINISTRADOR`.** Gerencia administra el negocio, no las cuentas: si
  gerencia pudiera crear administradores, podría darse más permisos.
- **El correo no se edita.** Es el usuario de inicio de sesión y el que aparece
  en la bitácora; uno distinto es otra cuenta.
- **Restablecer escribiendo la contraseña nueva** y no por correo: el sistema
  no envía correos (spec 020, §16 del plan).
- **Sin importar `crm`.** La relación inversa evita la dependencia circular.

## 11. Trabajo con agentes de IA

**Sesión 2026-11-04 (Claude Code, rol A).** Douglas eligió esta mejora de la
lista de módulos a mejorar. El agente propuso las reglas 4 a 7, que evitan
quedarse sin administradores o dejar un agente con otro rol, e implementó la
spec completa.
