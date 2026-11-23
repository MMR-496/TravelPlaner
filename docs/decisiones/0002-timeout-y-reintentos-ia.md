# 2. Tiempo máximo y un reintento al llamar a la IA

- **Fecha:** 2026-11-13
- **Estado:** Aceptada

## Contexto

Las sugerencias dependen de Gemini, un servicio externo que puede tardar, fallar o responder algo inesperado. Sin protección, la API se quedaría esperando y el usuario vería una página cargando sin fin. Al conectar la página web se vio que la IA real tarda más que el simulador, así que el tiempo máximo se subió de su valor inicial a 9 segundos y en la versión final quedó en 8.

## Decisión

Cada llamada espera como máximo 8 segundos y se intenta hasta 2 veces (el original y un reintento), solo ante errores 5xx o si no se puede conectar. Si tarda más del tiempo máximo no se reintenta: se responde 504. Un error 4xx o una respuesta ilegible responden 502 sin reintentar. Además, la respuesta de la IA se revisa antes de entregarla: el `tipo` debe ser `playa`, `ciudad`, `naturaleza` o `pueblo`, y la sugerencia no puede venir vacía.

## Consecuencias

- En el peor caso el usuario espera cerca de 16 segundos (un intento que tarda casi 8 s y falla con 5xx, más un reintento de 8 s) y recibe un mensaje que la página puede mostrar.
- Una sugerencia puede perderse si la IA está caída; el usuario la vuelve a pedir después.
- Reintentar es seguro porque pedir una sugerencia no cambia nada en nuestra base de datos.
- No se reintenta un 429 (límite de uso de la clave): responde 502.
