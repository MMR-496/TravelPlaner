# 1. Usar JWT para la autenticación

- **Fecha:** 2026-11-11
- **Estado:** Aceptada

## Contexto

La API necesita saber quién hace cada petición para aplicar los roles (encargado e invitado) y los dueños de las actividades. HTTP no recuerda nada entre peticiones. Las opciones eran guardar sesiones en el servidor o entregar un token firmado que el cliente manda cada vez.

## Decisión

Usamos un token JWT firmado con HS256, que lleva el usuario y el rol y vence a los 30 minutos. El secreto se lee de la variable de entorno `JWT_SECRETO` y, si falta, la API no arranca. Las contraseñas se guardan con bcrypt, nunca en texto.

## Consecuencias

- La API no guarda sesiones: funciona igual aunque corran varias copias.
- El contenido del token se puede leer, así que no lleva nada secreto.
- Un token robado sirve hasta que vence; por eso dura solo 30 minutos.
- El rol viaja dentro del token: si a alguien le cambian el rol, el cambio no se nota hasta que su token venza.
- No hay cierre de sesión en el servidor: salir solo borra el token en la página.
