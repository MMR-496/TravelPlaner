# Changelog

Todos los cambios importantes de este proyecto se documentan en este archivo.

El formato se basa en [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) y el proyecto usa [Versionado Semántico](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-11-23

### Agregado

- CRUD de viajes (`GET`, `POST`, `PUT`, `PATCH`, `DELETE`) con validación (422) y formato de error único `{"error", "detalles"}`; JSON roto o vacío responde 400.
- Reglas de validación: de 1 a 10 personas, destino de 3 a 50 caracteres, presupuesto mayor que 0, fecha de regreso no anterior a la de salida y estado `pendiente`, `en curso` o `completado`.
- Persistencia en SQLite (`viajes.db`): los datos sobreviven a un reinicio. No se repite un viaje al mismo destino y fecha de salida (409).
- Login con JWT (30 minutos) y contraseñas con bcrypt; `GET /yo` dice quién es el dueño del token.
- Roles `encargado` e `invitado`: solo el encargado crea, reemplaza, modifica o borra viajes (403).
- Actividades de un viaje (`/viajes/{id}/actividades`) con dueño: el invitado ve, modifica y borra solo las suyas (404 si no son suyas); el encargado ve todas. A un viaje completado no se le agregan actividades (409).
- Sugerencias de viaje con Gemini (`POST /viajes/sugerencia`): tiempo máximo de espera de 8 s, un reintento ante fallas del servicio y errores 502, 503 y 504 en el mismo formato. La respuesta de la IA se valida antes de entregarla.
- CORS configurado con una lista de orígenes (`CORS_ORIGENES`).
- Página web (`app/front/index.html`): login, alta, edición y borrado de viajes y de actividades, sugerencias de la IA y un registro de lo que la página le pide a la API.
- Contrato OpenAPI en `/docs`, con los códigos de error de cada ruta.
- Encabezado `Location` en las respuestas 201 y `WWW-Authenticate: Bearer` en las 401.
- Pruebas automáticas (`probar_api.py`, 28 pruebas) y herramientas de prueba de la IA (`simulador.py`, `probar_ia.py`, `probar_gemini.py`, `prueba.json`).
- Documentación: README, `.env.example`, arquitectura (modelo C4), catálogo de errores y decisiones de arquitectura.

### Cambiado

- El secreto de los tokens ya no está escrito en el código: se lee de la variable de entorno `JWT_SECRETO` y, si falta, la API no arranca.
- El tiempo máximo de espera a la IA subió a 9 s al conectar la página (la IA real tarda más que el simulador) y quedó en 8 s en esta versión.
- Los usuarios solo pueden tener rol `encargado` o `invitado` (restricción en la base de datos).
- Se quitó de la API la tabla `sin_validar`, que ya no se usaba.

### Seguridad

- Las claves (`JWT_SECRETO`, `GEMINI_API_KEY`) salen de variables de entorno y `.env` está en `.gitignore`.
- El secreto de tokens anterior sigue visible en el historial de git: no volver a usarlo.

### Pendiente

- Dejar de versionar `app/viajes.db` (la API la vuelve a crear sola) y agregarla a `.gitignore`.
- Quitar los usuarios de prueba, que tienen claves conocidas, antes de cualquier uso real, y agregar una forma de registrar usuarios.
- Quitar los espacios del valor por omisión de `CORS_ORIGENES` en `api_viajes.py`: con el espacio después de la coma, `http://localhost:5500` no queda permitido (hoy solo funciona la página abierta en `127.0.0.1:5500`).
- Los viajes no tienen dueño: cualquier usuario con sesión ve todos. Decidir si cada quien debe ver solo los suyos.
- Que la dirección de la API en la página (`http://127.0.0.1:8000`) se pueda configurar.
- Cambiar SQLite por un servidor de base de datos si varias copias de la API corren al mismo tiempo.

### Historial de pull requests

Cómo se llegó a esta versión:

| PR | Qué trajo | Autor | Fecha |
|---|---|---|---|
| [#1](https://github.com/MMR-496/TravelPlaner/pull/1) Valida POST y PUT de viajes | Validaciones de entrada para crear y reemplazar viajes | aTeresaTorres | 2026-11-04 |
| [#2](https://github.com/MMR-496/TravelPlaner/pull/2) Persistencia y contrato | Base de datos SQLite y contrato OpenAPI | MMR-496 | 2026-11-06 |
| [#3](https://github.com/MMR-496/TravelPlaner/pull/3) Login y roles | Autenticación con token, rol `invitado` y usuarios de prueba | MMR-496 | 2026-11-11 |
| [#4](https://github.com/MMR-496/TravelPlaner/pull/4) Integración de Gemini | Sugerencias de viaje con IA, simulador y pruebas de la IA | aTeresaTorres | 2026-11-13 |
| [#5](https://github.com/MMR-496/TravelPlaner/pull/5) Front y CORS | Página web, CORS y ajustes de pruebas y tiempos | MMR-496 | 2026-11-18 |
| Commit `07cd922` en `final` | Correcciones generales de la API y endpoints restantes en la página | MMR-496 | 2026-11-23 |