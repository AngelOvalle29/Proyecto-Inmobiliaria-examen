# 002 · Despliegue en producción e integración continua

| Campo | Valor |
|---|---|
| **Número** | 002 |
| **Estado** | Borrador |
| **Autor** | Equipo |
| **Revisor** | Por asignar |
| **Fecha** | 2026-10-08 |
| **Apps afectadas** | `config`, infraestructura |
| **Rama** | `feature/002-despliegue` |
| **Pull request** | — |

---

## 1. Problema

El enunciado es explícito: **los sistemas no desplegados no serán revisados**.
El despliegue vale 1 punto directo, pero su ausencia pone en riesgo los 15.

El error típico es dejarlo para el final, cuando ya no hay tiempo de resolver
problemas de configuración. Esta spec monta producción cuando el sistema
todavía es mínimo, para que los errores se descubran ahora y no en noviembre.

## 2. Alcance

**Incluye:**
- Backend desplegado en Railway: API, worker de Celery, PostgreSQL y RabbitMQ
- Frontend desplegado en Vercel
- Variables de entorno y secretos configurados en ambos proveedores
- `Dockerfile` de producción para el backend
- `docker-compose.yml` para desarrollo local
- Flujo de GitHub Actions con calidad y pruebas en cada pull request
- Endpoint de salud público
- Despliegue automático al fusionar a `main`

**No incluye:**
- Dominio propio (se usan los subdominios de Railway y Vercel)
- Monitoreo avanzado ni alertas
- Respaldos fuera de los automáticos de Railway

## 3. Decisión de proveedor

**Railway para el backend, Vercel para el frontend.**

Se compararon cuatro rutas:

| Opción | Costo mensual | Esfuerzo de montaje | Mantenimiento |
|---|---|---|---|
| **Railway + Vercel** | ~$15–20 | 1–2 horas | Ninguno |
| Hetzner + Coolify | ~€11 | Medio día | Bajo |
| Hetzner + Docker Compose | ~€6 | 1 día | Continuo |
| Render administrado | ~$43 | 2 horas | Ninguno |
| Oracle Cloud capa gratuita | $0 | 1 día | Continuo, con riesgo |

**Railway gana por el criterio correcto para este proyecto.** El despliegue
vale 1 punto de 15; los otros 14 están en el agente de IA, la mensajería, la
auditoría y la reportería. Cada hora dedicada a administrar un servidor es una
hora que no se invierte en lo que sí se evalúa. Unos $15 al mes entre cuatro
personas son alrededor de Q35 cada uno.

**Se descartó Render** porque su plan gratuito no sirve (las bases de datos
expiran a los 30 días, los servicios se apagan tras 15 minutos de inactividad
y no hay trabajadores en segundo plano, así que no habría Celery) y su plan de
pago sale cerca de $43 al mes sin siquiera incluir RabbitMQ.

**Se descartó la capa gratuita de Oracle Cloud** pese a ser generosa (2 OCPU
ARM y 12 GB de memoria) porque reclama las instancias que permanezcan inactivas
y la disponibilidad de ese tipo de instancia es históricamente escasa. El
riesgo de encontrar el sistema caído el día de la defensa no compensa el
ahorro.

**La decisión es reversible.** Todo corre en contenedores, así que migrar a
Hetzner o a Oracle es cuestión de levantar el mismo `docker-compose.yml` en un
servidor. Esa portabilidad es parte de la decisión, no un accidente.

## 4. Arquitectura de despliegue

```
                  ┌──────────────┐
   Navegador ────▶│    Vercel    │  React estático, HTTPS, CDN
                  └──────┬───────┘
                         │ llamadas a la API
                         ▼
                  ┌──────────────────────────────────┐
                  │           Railway                │
                  │                                  │
                  │  ┌────────────┐  ┌────────────┐  │
                  │  │   api      │  │  worker    │  │
                  │  │  Django    │  │  Celery    │  │
                  │  │ gunicorn   │  │            │  │
                  │  └─────┬──────┘  └─────┬──────┘  │
                  │        │               │         │
                  │  ┌─────▼───────────────▼──────┐  │
                  │  │  PostgreSQL + pgvector     │  │
                  │  └────────────────────────────┘  │
                  │  ┌────────────────────────────┐  │
                  │  │        RabbitMQ            │  │
                  │  └────────────────────────────┘  │
                  └──────────────────────────────────┘
```

Cuatro servicios, no cinco: **Redis se omite al inicio**. Celery usa RabbitMQ
como broker y, mientras no se necesite consultar el resultado de las tareas, el
backend de resultados sobra. Si más adelante hace falta cache, se agrega.

## 5. Servicios en Railway

| Servicio | Origen | Comando |
|---|---|---|
| `api` | Repositorio, carpeta `backend/` | `gunicorn config.wsgi --bind 0.0.0.0:$PORT` |
| `worker` | Mismo repositorio y Dockerfile | `celery -A config worker -l info` |
| `postgres` | Plantilla de Railway | — |
| `rabbitmq` | Plantilla de Railway | — |

La extensión pgvector se habilita con una migración de Django
(`CREATE EXTENSION IF NOT EXISTS vector`), no a mano, para que el entorno sea
reproducible.

**Variables de entorno en Railway:** las mismas de `.env.example`, con
`DEBUG=False`, `DJANGO_SETTINGS_MODULE=config.settings.prod` y
`ALLOWED_HOSTS` apuntando al dominio de Railway. Las cadenas de conexión de
PostgreSQL y RabbitMQ se referencian con las variables que Railway inyecta
entre servicios, nunca copiadas a mano.

**Límite de gasto:** configurarlo desde el primer día. Railway cobra por uso y
un bucle infinito en una tarea de Celery puede generar una sorpresa. Con el
tope puesto, el servicio se detiene en lugar de seguir cobrando.

## 6. Vercel

- Proyecto apuntando a la carpeta `frontend/`
- Comando de compilación `npm run build`, salida en `dist/`
- Variable `VITE_API_URL` con la URL pública de Railway
- Despliegue automático: cada pull request genera una vista previa, cada fusión
  a `main` actualiza producción

El plan Hobby es gratuito y está restringido a uso personal y no comercial, lo
cual un proyecto académico cumple.

## 7. Integración continua

Flujo en `.github/workflows/ci.yml`, ejecutado en cada pull request a `develop`
y a `main`:

1. Levanta PostgreSQL como servicio del flujo
2. Instala dependencias del backend
3. Corre `ruff check` y `ruff format --check`
4. Corre `pytest` con cobertura
5. Instala dependencias del frontend, corre `lint`, `typecheck` y `build`

**Un pull request con el flujo en rojo no se fusiona.** Configurar esto como
verificación obligatoria en la protección de ramas de GitHub.

## 8. Criterios de aceptación

- [ ] `https://<proyecto>.up.railway.app/api/v1/health/` responde 200
- [ ] `https://<proyecto>.vercel.app` carga el frontend
- [ ] El frontend desplegado consume la API desplegada sin errores de CORS
- [ ] `/api/docs/` es accesible en producción
- [ ] El worker de Celery aparece conectado a RabbitMQ en los registros
- [ ] Las migraciones corren automáticamente en cada despliegue
- [ ] `DEBUG` es `False` en producción y no se filtran trazas de error
- [ ] Los archivos estáticos del panel de administración se sirven correctamente
- [ ] El flujo de GitHub Actions corre en cada pull request y bloquea la fusión
      si falla
- [ ] Una fusión a `main` despliega automáticamente en Railway y en Vercel
- [ ] El límite de gasto está configurado en Railway
- [ ] No hay ninguna credencial en el repositorio

## 9. Pruebas

| Nivel | Caso |
|---|---|
| Humo | El endpoint de salud responde desde fuera de la red del equipo |
| Humo | Login contra la API desplegada devuelve tokens |
| Integración | Una tarea encolada se ejecuta en el worker desplegado |
| CI | Un pull request con una prueba fallando queda bloqueado |
| CI | Un pull request con un error de formato queda bloqueado |

## 10. Decisiones y alternativas descartadas

Ver la sección 3. Para la defensa oral conviene poder explicar:

- Por qué una plataforma administrada y no un servidor propio: el tiempo del
  equipo se invierte en los componentes evaluados, y la portabilidad se
  conserva con contenedores.
- Por qué el frontend va en un proveedor distinto al backend: son artefactos
  distintos (archivos estáticos frente a procesos permanentes) y separarlos
  deja el frontend gratuito, con CDN global.
- Por qué se omite Redis: RabbitMQ ya sirve como broker de Celery y el backend
  de resultados no se necesita todavía. Agregar un servicio que no se usa es
  costo y superficie de fallo sin beneficio.

## 11. Trabajo con agentes de IA

Por completar durante la implementación.
