# Convenciones de trabajo

El enunciado evalúa el proceso de ramas, pull requests y la legibilidad del
historial, y advierte que **no se debe hacer a última hora**. Un historial con
40 commits del día anterior a la entrega es evidencia en contra.

Estas convenciones son de cumplimiento obligatorio desde el primer commit.

---

## 1. Ramas

| Rama | Propósito |
|---|---|
| `main` | Solo código desplegado en producción. Nadie hace commit directo. |
| `develop` | Rama de integración y rama por defecto del repositorio. Nadie hace commit directo. |
| `feature/*` | Funcionalidad nueva |
| `fix/*` | Corrección de errores |
| `docs/*` | Solo documentación |
| `chore/*` | Configuración, dependencias, infraestructura |

**Nombres:** `feature/NNN-descripcion-corta`, donde `NNN` es el número de la
spec que implementa.

```
feature/003-crud-propiedades
feature/011-exportador-excel
fix/042-calculo-mora-cuotas
docs/001-manual-tecnico
```

Las ramas salen de `develop` y regresan a `develop`. A `main` solo llegan
fusiones desde `develop` cuando se va a desplegar.

**Nadie hace commit directo a `main` ni a `develop`.** GitHub no lo impide en
este repositorio, así que se cumple con las reglas internas de la sección 1.1.

### 1.1 Reglas internas de trabajo

El repositorio es privado y en el plan gratuito de GitHub las ramas privadas
no se pueden proteger. El equipo decidió (2026-10-21) no cambiar de plan y
trabajar con estas reglas. **Nada técnico las hace cumplir: dependen de cada
integrante**, y el historial deja ver si se respetaron.

1. **Nunca se sube nada directo a `main` ni a `develop`**: ni con `git push`, ni
   desde la web de GitHub. Al editar un archivo en la web, elegir
   *"Create a new branch for this commit and start a pull request"*, nunca
   *"Commit directly to the develop branch"*.
2. **Todo entra por pull request**, con la plantilla de la sección 3.
3. **Lo aprueba otro integrante** con el botón *Approve* de GitHub, no con un
   comentario. Si el cambio toca apps de otro integrante, aprueba el dueño
   (sección 4).
4. **Fusiona el autor, solo después de la aprobación.** Nadie fusiona un pull
   request sin aprobar, ni el suyo ni el de otro.
5. **Mientras GitHub Actions no se ejecute**, las verificaciones se corren a
   mano. El autor las corre desde `backend/` y pega el resultado en el pull
   request, y quien revisa las vuelve a correr en su máquina antes de aprobar:

   ```bash
   ruff format --check . && ruff check . && python manage.py makemigrations --check --dry-run && pytest
   ```

6. **Se fusiona con *"Create a merge commit"*.** No se usa *squash* ni
   *rebase*: los commits de cada incremento son la evidencia del proceso y deben
   quedar en el historial.
7. **Después de fusionar se borra la rama**, con el botón que ofrece GitHub.
8. **Nunca `git push --force`** sobre `main` ni `develop`. Si alguien sube algo
   directo por error, no se reescribe el historial: se avisa al equipo y se
   sigue con la regla desde el siguiente cambio.
9. **A `main` solo llega un pull request de `develop` a `main`**, cuando se va a
   desplegar. Lo abre el responsable del despliegue (rol A) y lo aprueba otro
   integrante.

---

## 2. Commits

Formato **Conventional Commits**, con descripción en español:

```
<tipo>(<alcance>): <descripción en imperativo>

[cuerpo opcional, explicando el porqué]

[referencias opcionales]
```

**Tipos:** `feat`, `fix`, `docs`, `refactor`, `test`, `chore`, `perf`.

**Alcance:** la app afectada (`catalogo`, `ventas`, `ia`, `reportes`…).

```
feat(catalogo): agregar CRUD de propiedades con filtros por ciudad y tipo
fix(ventas): corregir cálculo de mora cuando la cuota es parcial
test(arrendamientos): cubrir cálculo de ocupación con unidades mixtas
docs(arquitectura): documentar la capa de selectores
refactor(reportes): extraer el exportador de Excel a una clase genérica
```

**Reglas:**
- Un commit, un cambio lógico. Nada de "varios arreglos".
- Descripción en imperativo: "agregar", no "agregado" ni "agregando".
- Máximo 72 caracteres en la primera línea.
- El cuerpo explica **por qué**, no **qué**. El diff ya dice qué.
- Nunca `WIP`, `cambios`, `fix`, `.` ni `asdf`.
- **Cada integrante hace sus propios commits con su propia cuenta.** No se
  comparten credenciales de GitHub.

---

## 3. Pull requests

Toda rama entra por pull request. Sin excepciones.

**Plantilla:**

```markdown
## Qué hace
Resumen en dos o tres líneas.

## Spec
Implementa `specs/003-crud-propiedades.md`

## Cambios
- Modelo `Propiedad` con sus constraints
- Servicios de creación y actualización, con auditoría
- Selectores con filtros por ciudad, tipo y rango de precio
- Endpoints bajo /api/v1/propiedades/
- Pruebas de servicios y de API

## Cómo probarlo
1. `python manage.py migrate`
2. `python manage.py seed_demo`
3. `GET /api/v1/propiedades/?ciudad=1&precio_max=200000`

## Pendientes
Nada, o lo que quede fuera del alcance de esta spec.
```

**Requisitos para fusionar:**
- [ ] Enlaza una spec aprobada
- [ ] `ruff check` y `ruff format --check` pasan
- [ ] `pytest` pasa
- [ ] El resultado de las verificaciones está pegado en el PR (sección 1.1,
      regla 5, mientras GitHub Actions no se ejecute)
- [ ] Hay pruebas de la lógica nueva
- [ ] Los endpoints de escritura registran auditoría
- [ ] Aprobado por **otro integrante** del equipo con el botón *Approve*
- [ ] Sin secretos ni credenciales en el diff
- [ ] `CLAUDE.md` y `AGENTS.md` siguen sincronizados si alguno cambió

**La revisión no es un trámite.** Quien aprueba debe poder explicar el código en
la defensa oral, porque la defensa es individual y el catedrático puede
preguntar sobre cualquier módulo.

---

## 4. Reparto y conflictos

Cada integrante es dueño de sus apps (ver `docs/roadmap.md`), pero puede revisar
y corregir cualquier parte. Si un cambio toca apps de otro integrante, se marca
en el pull request y esa persona debe ser quien lo apruebe.

Para reducir conflictos de fusión:
- Fusionar `develop` a la rama propia con frecuencia, no solo al final.
- Ramas de vida corta: menos de 3 días.
- Migraciones: coordinar antes de generar, para evitar números duplicados.

---

## 5. Uso de agentes de IA

Está permitido y es parte de lo que el curso pide evidenciar, pero con reglas:

- **Los commits los hace el estudiante**, no el agente. El estudiante revisa,
  entiende y asume el código.
- **Prohibido el vibecoding:** aceptar código sin leerlo ni entenderlo.
- Antes de hacer commit de algo generado, el estudiante debe poder responder:
  ¿qué hace cada función?, ¿por qué está en esta capa?, ¿qué pasa si falla?
- Si no puede responder eso, **no hace el commit**. Pide una explicación o lo
  reescribe.
- Las sesiones de trabajo con el agente que produjeron decisiones relevantes se
  resumen en la spec correspondiente. Esa es la evidencia del proceso.

---

## 6. Ritmo de trabajo

- **Reunión semanal** del equipo, con acta breve en `docs/bitacora/`.
- **Commits distribuidos en el tiempo.** El historial debe mostrar trabajo
  continuo, no ráfagas.
- **Despliegue temprano.** Un sistema no desplegado no se revisa; el despliegue
  debe funcionar desde la fase 1, aunque el sistema aún sea mínimo.
- **Defensa cruzada.** Antes de la entrega, cada integrante explica al equipo un
  módulo que **no** programó. Es el mejor ensayo posible.

---

## 7. Mensajes y archivos prohibidos en el repositorio

- Archivos `.env` con valores reales
- Credenciales, llaves de API, cadenas de conexión
- Archivos de base de datos
- Carpetas `.venv/`, `node_modules/`, `__pycache__/`
- Archivos de configuración personal del editor
- Documentos oficiales con datos de personas reales

Todo esto va en `.gitignore`. Si algo se sube por error, **rotar la credencial
inmediatamente**; borrarla en un commit posterior no la elimina del historial.
