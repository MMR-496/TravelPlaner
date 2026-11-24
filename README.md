# Travel Planer · API

API para planear viajes en grupo. El **encargado** crea y administra los viajes (destino, fechas, presupuesto, número de personas); cada **invitado** agrega sus propias actividades a un viaje y solo ve las suyas. Además, una IA (Gemini) sugiere qué hacer en un destino.

Proyecto final de Programación Distribuida · Facultad de Telemática · Universidad de Colima.

- **Versión:** v1.0.0 (ver [CHANGELOG.md](CHANGELOG.md))
- **Lenguaje:** Python · FastAPI (base de datos SQLite, página web en HTML + JavaScript)
- **Arquitectura:** [docs/arquitectura.md](docs/arquitectura.md)

## Cómo correrla

Todos los comandos son para **cmd de Windows** y se ejecutan desde la carpeta `app`.

1. Clonar el repositorio:
   ```
   git clone https://github.com/MMR-496/TravelPlaner.git
   cd TravelPlaner
   git checkout final
   cd app
   ```
2. Instalar dependencias:
   ```
   pip install fastapi uvicorn pyjwt bcrypt
   ```
3. Configurar las variables de entorno (ver la tabla de abajo). La API **no lee archivos `.env`**: las variables se definen con `set` en la misma ventana donde se arranca:
   ```
   set JWT_SECRETO=una-cadena-larga-y-aleatoria
   set GEMINI_API_KEY=su-clave
   ```
4. Arrancar la API:
   ```
   uvicorn api_viajes:app --reload
   ```
   Sin `JWT_SECRETO` la API no arranca (se detiene con un mensaje que lo indica).
5. En otra ventana de cmd, servir la página web:
   ```
   cd TravelPlaner\app\front
   python -m http.server 5500
   ```
6. Abrir el contrato en http://127.0.0.1:8000/docs y la página en http://127.0.0.1:5500 (usar **127.0.0.1**, no `localhost`: la página le pide a la API en `http://127.0.0.1:8000`, y esa dirección está fija en `front/index.html`).

La base de datos `viajes.db` se crea sola la primera vez y queda en la carpeta desde donde se arranca la API (por eso se corre desde `app`).

### Usuarios de prueba

Se crean automáticamente si la tabla de usuarios está vacía:

| Usuario | Clave | Rol |
|---|---|---|
| `coco` | `cocoloco` | encargado |
| `ana` | `ana12345` | encargado |
| `pancho` | `tamarindo123` | invitado |
| `pedrita` | `123tamatindo` | invitado |
| `lupe` | `lupe12345` | invitado |

También se crea un viaje de prueba (Manzanillo, id 1) para que `/viajes/1/actividades` exista desde el inicio.

### Qué puede hacer cada rol

| Operación | encargado | invitado |
|---|---|---|
| Ver viajes (`GET /viajes`, `GET /viajes/{id}`) | Sí | Sí |
| Crear, reemplazar, modificar o borrar viajes | Sí | No (403) |
| Crear actividades en un viaje | Sí | Sí |
| Ver, modificar y borrar actividades | Todas | Solo las suyas (404 si no son suyas) |
| Pedir una sugerencia a la IA | Sí | Sí |

## Variables de entorno

Están todas en [.env.example](.env.example). **Ninguna clave real va en el repositorio.**

| Variable | Para qué sirve | Obligatoria |
|---|---|---|
| `JWT_SECRETO` | Firmar los tokens de sesión. Sin ella la API no arranca. | Sí |
| `GEMINI_API_KEY` | Clave de Gemini para `POST /viajes/sugerencia`. Sin ella, ese endpoint responde 503 (solo si se usa la dirección real de Google). | Para la IA |
| `GEMINI_MODELO` | Modelo de Gemini que se usa (`gemini-flash-lite-latest` por omisión). | No |
| `EXTERNO_URL` | A dónde se manda la petición de IA (`https://generativelanguage.googleapis.com` por omisión). Para las pruebas apunta al simulador: `http://127.0.0.1:9000`. | No |
| `CORS_ORIGENES` | Páginas que pueden usar la API desde el navegador, separadas por coma y **sin espacios**. Por omisión: `http://127.0.0.1:5500` y `http://localhost:5500`. | No |

## Ejemplos de uso

Entrar y obtener el token:
```
curl -X POST http://127.0.0.1:8000/login -H "Content-Type: application/json" -d "{\"usuario\": \"ana\", \"clave\": \"ana12345\"}"
```
La respuesta trae `access_token`; el token dura 30 minutos. Para usarlo en cmd: `set TOKEN=el-token-que-regresó`.

Crear un viaje (solo el encargado):
```
curl -X POST http://127.0.0.1:8000/viajes -H "Authorization: Bearer %TOKEN%" -H "Content-Type: application/json" -d "{\"personas\": 3, \"destino\": \"Manzanillo\", \"presupuesto\": 1500.50, \"fecha_salida\": \"2026-12-25\", \"fecha_regreso\": \"2026-12-30\"}"
```

Agregar una actividad al viaje 1 (el dueño sale del token, no del cuerpo):
```
curl -X POST http://127.0.0.1:8000/viajes/1/actividades -H "Authorization: Bearer %TOKEN%" -H "Content-Type: application/json" -d "{\"nombre\": \"Visitar la playa\", \"hora\": \"10:30\"}"
```

Pedir una sugerencia a la IA:
```
curl -X POST http://127.0.0.1:8000/viajes/sugerencia -H "Authorization: Bearer %TOKEN%" -H "Content-Type: application/json" -d "{\"destino\": \"Comala, Colima\"}"
```
Responde algo como `{"tipo": "pueblo", "sugerencia": "..."}`; `tipo` es `playa`, `ciudad`, `naturaleza` o `pueblo`.

## Contrato y errores

- Contrato OpenAPI: http://127.0.0.1:8000/docs (el JSON está en `/openapi.json`)
- Errores: todos responden `{"error": "...", "detalles": [...]}`. Ver [docs/errores.md](docs/errores.md).

## Cómo probarla

Se usan tres ventanas de cmd, todas en la carpeta `app`:

```
:: Ventana 1: el simulador de fallas del servicio externo (puerto 9000)
python simulador.py

:: Ventana 2: la API apuntando al simulador (en vez de a Google)
set JWT_SECRETO=una-cadena-larga-y-aleatoria
set EXTERNO_URL=http://127.0.0.1:9000
uvicorn api_viajes:app

:: Ventana 3: las pruebas (el archivo prueba.json describe qué probar)
python probar_api.py
```

La primera vez la prueba 15 (persistencia) queda pendiente: reiniciar la API (Ctrl+C y volver a arrancarla) y correr `python probar_api.py` otra vez. El reporte se guarda en un archivo `reporte_U3S6_<matrícula>.txt`.

Otros scripts: `probar_ia.py` (qué hace la API cuando la IA tarda, falla o responde basura) y `probar_gemini.py` (revisa que `GEMINI_API_KEY` funcione y qué modelo conviene).

Resultado de la versión v1.0.0: 28 de 28 pruebas pasadas

## Anatomía de mi API

```
Anatomía de mi API · lista de revisión (43 de 43)

0 · Cliente (2/2)
  [x] Mi proyecto tiene un cliente que consume la API: una página, una app o un script.
  [x] Puedo hacer una acción en el cliente y mostrar la petición y la respuesta en la pestaña Red (F12).
  En la presentación: Abran su front y hagan una acción en vivo. Con F12 → Red, muestren la petición que salió y la respuesta que llegó.

1 · Petición HTTP (3/3)
  [x] Mis rutas nombran cosas (/tareas, /tareas/7), no acciones (/crearTarea).
  [x] Cada operación usa el método correcto: GET lee, POST crea, PUT o PATCH modifica, DELETE borra.
  [x] Tengo la ficha de endpoints: método, ruta, qué recibe y qué responde.
  En la presentación: Muestren su ficha de endpoints o /docs y expliquen en una frase qué hace cada ruta.

2 · CORS (3/3)
  [x] Configuré CORS con una lista de orígenes, no con *.
  [x] Authorization y Content-Type están en los encabezados permitidos.
  [x] CORS va antes de revisar el token.
  En la presentación: Abran su front desde su origen (por ejemplo, el puerto 5500) con F12 abierto: la consola sin errores de CORS.

3 · Autenticación (3/3)
  [x] Las contraseñas se guardan con hash (bcrypt o password_hash).
  [x] El login regresa un token JWT con vencimiento.
  [x] Sin token, o con un token alterado, la API responde 401.
  En la presentación: Hagan una petición a una ruta protegida sin token (401) y luego con token (200).

4 · Autorización (2/2)
  [x] Hay al menos dos roles y una acción que un rol no puede hacer (403).
  [x] Las consultas de recursos propios filtran por el usuario del token (WHERE id = ? AND usuario = ?).
  En la presentación: Con el usuario A pidan un recurso del usuario B: debe responder 404. Con un rol sin permiso intenten borrar: 403.

5 · Validación (3/3)
  [x] Valido campos obligatorios, tipo, formato y rango.
  [x] Un dato inválido responde 422 y dice qué campo falló.
  [x] Un duplicado o una regla rota responde 409.
  En la presentación: Manden un dato inválido desde su front y muestren que el error aparece en el campo correcto.

6 · Endpoint / controlador (2/2)
  [x] Tengo el CRUD completo de mi recurso principal.
  [x] Cada operación responde con su código: 200, 201, 204 o 404.
  En la presentación: Recorran el CRUD de su recurso principal en /docs, Postman o su front.

7 · Servicio / lógica de negocio (2/2)
  [x] Identifico al menos una regla de negocio propia de mi proyecto.
  [x] La regla está en una función aparte, no revuelta con el manejo de HTTP.
  En la presentación: Expliquen su regla de negocio y muestren el caso en que dice que no (409).

7b · Integraciones externas (5/5)
  [x] Mi API consume al menos un servicio externo.
  [x] La llamada tiene un tiempo máximo de espera (timeout).
  [x] Si el servicio falla o tarda, responde 502 o 504 con un mensaje claro.
  [x] La clave del servicio está en una variable de entorno.
  [x] Puedo explicar en qué caso se usaría SOAP en lugar de REST (por ejemplo, el SAT).
  En la presentación: Muestren la integración funcionando y luego la falla controlada: sin clave (503) o con el servicio caído (502 o 504).

8 · Persistencia (2/2)
  [x] Los datos se guardan en una base de datos y sobreviven al reinicio.
  [x] Todas mis consultas usan parámetros (?), ninguna pega datos al texto del SQL.
  En la presentación: Reinicien la API en vivo y muestren que los datos siguen ahí. Enseñen una de sus consultas con ?.

9 · Respuesta HTTP (2/2)
  [x] Todos mis errores salen en JSON con el mismo formato: {"error": ..., "detalles": [...]}.
  [x] Ningún error muestra trazas, rutas de archivos ni SQL.
  En la presentación: Provoquen dos errores distintos y muestren que ambos llegan con el mismo formato JSON.

Configuración base (3/3)
  [x] Secretos y claves (JWT, IA, base de datos) se leen de variables de entorno, no están escritos en el código.
  [x] En mi repositorio de GitHub no hay ninguna clave.
  [x] Mi README dice qué variables hay que configurar.
  En la presentación: Muestren dónde lee su código las variables de entorno y busquen en vivo en su repositorio que no haya ninguna clave.

Pruebas automáticas (2/2)
  [x] Tengo pruebas automáticas (probar_api.py, una colección de Postman o similar).
  [x] Las pruebas pasan antes de entregar.
  En la presentación: Corran sus pruebas en vivo y comenten el resultado.

Documentación (6/6)
  [x] Mi README explica qué es, cómo correrla en pocos pasos, qué variables configurar y cómo probarla.
  [x] Mi API publica su contrato (OpenAPI en /docs u openapi.yaml).
  [x] Tengo .env.example con las variables de entorno, sin valores secretos.
  [x] Tengo docs/arquitectura.md con el diagrama C4 de contenedores: página, API, base de datos y servicio externo.
  [x] Tengo CHANGELOG.md con lo que trae la versión v1.0.0.
  [x] Recomendado: 2 decisiones explicadas (ADR) en docs/decisiones/ y el catálogo de errores en docs/errores.md.
  En la presentación: Abran su repositorio en GitHub: el README y el diagrama de arquitectura. Con el diagrama expliquen qué parte de su sistema está distribuida y cómo se comunican las piezas.

Timeout e idempotencia (2/2)
  [x] Sé qué operaciones de mi API se pueden repetir sin riesgo y cuáles no.
  [x] Si reintento llamadas externas, solo es ante fallas pasajeras (429, 5xx o timeout).
  En la presentación: Expliquen qué pasaría en su proyecto si el usuario le da doble clic a "Guardar".

Seguridad en capas (1/1)
  [x] Puedo decir qué riesgo del OWASP API Top 10 evita cada capa de mi API.
  En la presentación: Cierren la presentación con la tabla “riesgo → cómo lo evita mi API”.

```

## REST y SOAP en mi proyecto

Si Travel Planer reservara vuelos u hoteles de verdad, podría necesitar un proveedor de reservas que solo ofrezca SOAP (los sistemas de reservas de aerolíneas y hoteles suelen tenerlo). Iría como una integración externa, en la misma capa que hoy ocupa Gemini (la función `preguntar_a_la_ia` y el endpoint `POST /viajes/sugerencia`): una función que reciba el destino y las fechas del viaje en JSON, arme el sobre XML que pide el proveedor, lo mande con un POST y un tiempo máximo de espera, lea la respuesta XML y la regrese como JSON. Los errores se traducirían igual que ahora: 504 si tarda, 502 si responde un error o algo ilegible, 503 si falta la configuración. La página web nunca vería XML.

## Equipo y reflexiones

| Integrante | Qué hizo |
|---|---|
| Mayte Muñoz (`MMR-496`) | Proyecto base, modelos y alta de viajes; base de datos SQLite; login con JWT y roles; página web y CORS; ajustes finales de la API y endpoints restantes en la página. |
| Teresa Torres (`aTeresaTorres`) | [Completar] |
| Elias (`Elias735`) | Apoyo en la implementación y pruebas de autenticación con JWT, roles y control de acceso y manejo de errores y pruebas |

**Mayte Muñoz Rosales:** Personalmente, lo más complicado fue la cuestión de la conexión con la IA, me costó bastante entender lo que estaba pasando y la configuración para que pudiera funcionar. Si esto fuera un proyecto para una empresa dedicaría más tiempo en la seguridad, si bien creo que cumplimos con lo básico, hay muchas posibilidades de ataques ciberneticos

**Ana Teresa Torres Barajas:** Lo que más me costó fue entender cómo funcionaba el flujo de CORS y el manejo de errores con timeout de la IA. Si este proyecto fuera de una empresa, usaría un gestor de secretos en la nube en lugar de variables de entorno locales, y probablemente implementaría pruebas unitarias con pytest desde el primer día.

**Elías:** Lo que más me costó fue comprender la autenticación con JWT y cómo controlar los permisos de cada usuario para evitar que pudiera acceder a información de otros. También fue complicado entender cómo manejar los errores cuando la IA no responde correctamente. Si este proyecto fuera para una empresa, dedicaría más tiempo a las pruebas automatizadas, la seguridad y la protección de los datos de los usuarios.
