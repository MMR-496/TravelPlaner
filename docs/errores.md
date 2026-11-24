# Catálogo de errores

Todos los errores responden con el mismo formato:

```json
{"error": "Mensaje para el usuario", "detalles": ["detalle por campo, si aplica"]}
```

| Código | Cuándo | Ejemplo de mensaje |
|---|---|---|
| 400 | El cuerpo no es un JSON válido, o un `PATCH` no trae ningún campo para modificar | "El cuerpo no es un JSON válido" · "No se envió ningún campo para modificar" |
| 401 | Usuario o clave incorrectos en `/login`; falta el token, es falso o ya expiró (estas respuestas llevan `WWW-Authenticate: Bearer`) | "Usuario o clave incorrectos" · "El token ya expiró: inicia sesión otra vez" |
| 403 | Un invitado intenta lo que solo hace el encargado (crear, reemplazar, modificar o borrar viajes) | "Tu rol (invitado) no puede hacer esto: solo el encargado" |
| 404 | El viaje o la actividad no existe, o la actividad es de otro invitado (no se confirma que exista) | "No existe el viaje 99" · "No existe la actividad" |
| 409 | Ya hay un viaje al mismo destino y fecha de salida, o se agrega una actividad a un viaje completado | "Ya existe un viaje a Manzanillo el 2026-12-20" · "El viaje ya está completado: no se pueden agregar actividades" |
| 422 | Los datos no cumplen las reglas (tipo, formato, rango, fecha de regreso anterior a la de salida) | "Los datos no son válidos" + un detalle por campo |
| 500 | Falla inesperada de la API | "Error interno del servidor" |
| 502 | Gemini respondió un error, algo ilegible o con la forma equivocada, o no se pudo conectar | "La IA respondió algo inesperado." · "La IA no está disponible (respondió 400). Intenta más tarde." |
| 503 | Falta configurar la clave de la IA | "Falta configurar la variable de entorno GEMINI_API_KEY" |
| 504 | Gemini no respondió en 8 segundos | "La IA tardó demasiado en responder. Intenta en un momento." |

Nota sobre el 422: cuando falla la validación de un campo, `detalles` trae una línea por campo (por ejemplo `personas: Input should be greater than 0`). Si falla la regla de fechas en un `PATCH`, el mensaje va en `error` y `detalles` queda vacío.
