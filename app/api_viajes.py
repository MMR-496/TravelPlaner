# api_viajes.py — Sesión 3
# Programación Distribuida · Facultad de Telemática · Universidad de Colima
#
# Cómo correrla:
#   pip install fastapi uvicorn
#   uvicorn api_viajes:app --reload
#   http://127.0.0.1:8000/docs
#
# Los datos viven en un archivo SQLite (viajes.db), así que
# sobreviven cuando se reinicia la API.
# Regla de oro: toda consulta lleva parámetros (?), nunca texto pegado.

import json
import os
import urllib.request
import urllib.error
import sqlite3
from datetime import datetime, timedelta, timezone, date
from typing import Literal, Optional

import bcrypt
import jwt
from fastapi import Body, Depends, FastAPI, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field, model_validator

app = FastAPI(title="API de Viajes", version="5.0")

# ============================================================
# 1. MODELOS Y VALIDACIONES
# ============================================================

ESTADOS = Literal["pendiente", "en curso", "completado"]


class ViajeNuevo(BaseModel):
    personas: int = Field(..., gt=0, le=10, examples=[3])
    destino: str = Field(..., min_length=3, max_length=50, examples=["Manzanillo"])
    presupuesto: float = Field(..., gt=0, examples=[1500.50])
    fecha_salida: date = Field(..., examples=["2024-12-25"])
    fecha_regreso: date = Field(..., examples=["2024-12-30"])
    estado: ESTADOS = Field(default="pendiente")

    @model_validator(mode="after")
    def validar_fechas(self):
        if self.fecha_regreso < self.fecha_salida:
            raise ValueError("La fecha de regreso no puede ser anterior a la fecha de salida")
        return self


class Viaje(ViajeNuevo):
    # Lo que la API devuelve: un viaje con su id
    id: int


class ViajeCambios(BaseModel):
    personas: Optional[int] = Field(None, gt=0, le=10)
    destino: Optional[str] = Field(None, min_length=3, max_length=50)
    presupuesto: Optional[float] = Field(None, gt=0)
    fecha_salida: Optional[date] = None
    fecha_regreso: Optional[date] = None
    estado: Optional[ESTADOS] = None


class ActividadNueva(BaseModel):
    nombre: str = Field(..., min_length=2, max_length=50, examples=["Visitar la playa"])
    hora: str = Field(..., pattern=r"^\d{2}:\d{2}$", examples=["10:30"])

class Actividad(ActividadNueva):
    id: int
    viaje_id: int
    usuario: str


class ErrorRespuesta(BaseModel):
    # Formato único de todos los errores de la API
    error: str = Field(..., examples=["No existe el viaje 99"])
    detalles: list[str] = Field(default=[], examples=[[]])

class Credenciales(BaseModel):
    usuario: str = Field(..., examples=["ana"])
    clave: str = Field(..., max_length=72, examples=["ana12345"])   # bcrypt usa hasta 72 bytes


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expira_en_segundos: int


# Errores que se muestran en el contrato (/docs)
E400 = {400: {"model": ErrorRespuesta, "description": "El cuerpo no es un JSON válido"}}
E404 = {404: {"model": ErrorRespuesta, "description": "No existe el recurso"}}
E409 = {409: {"model": ErrorRespuesta, "description": "Ya existe un viaje al mismo destino en esa fecha"}}
E422 = {422: {"model": ErrorRespuesta, "description": "Los datos no son válidos"}}
E401 = {401: {"model": ErrorRespuesta, "description": "Falta el token, es falso o ya expiró"}}
E403 = {403: {"model": ErrorRespuesta, "description": "Tu rol no tiene permiso para esta operación"}}

# ============================================================
# 2. BASE DE DATOS (SQLite)
# ============================================================

ARCHIVO_BD = "viajes.db"

SECRETO = "clave-no-tan-secreta-123-tamarindo"
MINUTOS_TOKEN = 30

def conectar():
    con = sqlite3.connect(ARCHIVO_BD)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con


def consultar(sql, parametros=()):
    """Para SELECT. Devuelve una lista de diccionarios."""
    con = conectar()
    try:
        filas = con.execute(sql, parametros).fetchall()
    finally:
        con.close()

    resultado = []
    for fila in filas:
        resultado.append(dict(fila))
    return resultado


def ejecutar(sql, parametros=()):
    """Para INSERT, UPDATE y DELETE. Devuelve el id de la última fila insertada."""
    con = conectar()
    try:
        cursor = con.execute(sql, parametros)
        con.commit()
        return cursor.lastrowid
    finally:
        con.close()


def crear_tablas():
    con = conectar()
    try:
        # UNIQUE: la base de datos también hace cumplir la regla del 409
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS viajes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                personas INTEGER NOT NULL,
                destino TEXT NOT NULL COLLATE NOCASE,
                presupuesto REAL NOT NULL,
                fecha_salida TEXT NOT NULL,
                fecha_regreso TEXT NOT NULL,
                estado TEXT NOT NULL,
                UNIQUE (destino, fecha_salida)
            )
            """
        )
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS actividades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                viaje_id INTEGER NOT NULL,
                nombre TEXT NOT NULL,
                usuario TEXT NOT NULL,
                hora TEXT NOT NULL,
                FOREIGN KEY (viaje_id) REFERENCES viajes (id) ON DELETE CASCADE
            )
            """
        )

        con.execute(
            """
            CREATE TABLE IF NOT EXISTS usuarios (
                    usuario TEXT PRIMARY KEY,
                    clave_hash TEXT NOT NULL,
                    rol TEXT NOT NULL)
            """
        )

        con.execute(
            """
            CREATE TABLE IF NOT EXISTS sin_validar (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                datos TEXT NOT NULL
            )
            """
        )
        #Se crean usuarios de prueba
        cantidad = con.execute("SELECT COUNT(*) FROM usuarios").fetchone()[0]
        if cantidad == 0:
            usuarios_prueba = [
                ("coco", "cocoloco", "encargado"),
                ("pancho", "tamarindo123", "invitado"),
                ("ana", "ana12345", "encargado"),
                ("pedrita", "123tamatindo", "invitado"),
                ("lupe", "lupe12345", "invitado")
            ]
            for usuario, clave, rol in usuarios_prueba:
                clave_hash = bcrypt.hashpw(clave.encode(), bcrypt.gensalt()).decode()
                con.execute(
                    "INSERT INTO usuarios (usuario, clave_hash, rol) VALUES (?, ?, ?)",
                    (usuario, clave_hash, rol),
                )

        cantidad_viajes = con.execute("SELECT COUNT(*) FROM viajes").fetchone()[0]
        if cantidad_viajes == 0:
            con.execute(
                "INSERT INTO viajes (personas, destino, presupuesto, fecha_salida, fecha_regreso, estado) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (2, "Manzanillo", 3000.0, "2026-12-20", "2026-12-23", "pendiente"),
            )  
        con.commit()
    finally:
        con.close()


crear_tablas()

# --- CONFIGURACIÓN DE LA IA ---
IA_URL = os.environ.get("EXTERNO_URL", "https://generativelanguage.googleapis.com").rstrip("/")
IA_MODELO = os.environ.get("GEMINI_MODELO", "gemini-flash-lite-latest")
IA_CLAVE = os.environ.get("GEMINI_API_KEY", "")

def preguntar_a_la_ia(instruccion: str) -> dict:
    """Le pregunta a Gemini y regresa el JSON. Protege la API de caídas y reintenta si falla temporalmente."""
    if not IA_CLAVE and "googleapis.com" in IA_URL:
        raise HTTPException(503, "Falta configurar la variable de entorno GEMINI_API_KEY")
    
    cuerpo = {
        "contents": [{"parts": [{"text": instruccion}]}],
        "generationConfig": {"responseMimeType": "application/json", "temperature": 0}
    }
    
    # Intentaremos hasta 2 veces (el original + 1 reintento)
    max_intentos = 2 
    
    for intento in range(max_intentos):
        req = urllib.request.Request(
            f"{IA_URL}/v1beta/models/{IA_MODELO}:generateContent",
            data=json.dumps(cuerpo).encode(),
            method="POST",
            headers={"Content-Type": "application/json", "x-goog-api-key": IA_CLAVE}
        )
        
        try:
            # EL TIMEOUT: máximo 5 segundos esperando a Google
            with urllib.request.urlopen(req, timeout=5) as r:
                respuesta = json.loads(r.read())
            return json.loads(respuesta["candidates"][0]["content"]["parts"][0]["text"])
        
        except TimeoutError:
            # Si hay timeout, NO reintentamos, ya perdimos mucho tiempo.
            raise HTTPException(504, "La IA tardó demasiado en responder. Intenta en un momento.")
            
        except urllib.error.HTTPError as e:
            # Si es un error del servidor (500-599), hay oportunidad de reintentar
            if 500 <= e.code < 600 and intento < (max_intentos - 1):
                continue # Salta al siguiente intento del bucle
            # Si es un 400 (error del cliente) o ya nos quedamos sin intentos, nos rendimos
            raise HTTPException(502, f"La IA no está disponible (respondió {e.code}). Intenta más tarde.")
            
        except urllib.error.URLError as e:
            if isinstance(e.reason, TimeoutError):
                raise HTTPException(504, "La IA tardó demasiado en responder.")
            if intento < (max_intentos - 1):
                continue
            raise HTTPException(502, "No se pudo conectar con la IA.")
            
        except (ValueError, KeyError, IndexError, TypeError):
            raise HTTPException(502, "La IA respondió algo que no entendemos.")

# ============================================================
# 3. MANEJO DE ERRORES UNIFICADO
# ============================================================


def error(codigo, mensaje, detalles=None):
    if detalles is None:
        detalles = []
    return JSONResponse(status_code=codigo, content={"error": mensaje, "detalles": detalles})


@app.exception_handler(HTTPException)
async def error_http(request: Request, exc: HTTPException):
    return error(exc.status_code, exc.detail)


@app.exception_handler(RequestValidationError)
async def error_validacion(request: Request, exc: RequestValidationError):
    errores = exc.errors()

    for e in errores:
        if e["type"] == "json_invalid":
            return error(400, "El cuerpo no es un JSON válido")

    detalles = []
    for e in errores:
        # loc[0] es "body", "path" o "query"; lo quitamos para que sea más claro
        campo = ".".join(str(parte) for parte in e["loc"][1:])
        detalles.append(f"{campo}: {e['msg']}")
    return error(422, "Los datos no son válidos", detalles)


@app.exception_handler(Exception)
async def error_interno(request: Request, exc: Exception):
    return error(500, "Error interno del servidor")


def buscar_viaje(viaje_id: int):
    filas = consultar("SELECT * FROM viajes WHERE id = ?", (viaje_id,))
    if len(filas) == 0:
        raise HTTPException(404, f"No existe el viaje {viaje_id}")
    return filas[0]


def buscar_actividad(viaje_id: int, actividad_id: int, yo: dict):
    if yo["rol"] == "encargado":
        filas = consultar(
            "SELECT * FROM actividades WHERE id = ? AND viaje_id = ?",
            (actividad_id, viaje_id),
        )
    else:
        filas = consultar(
            "SELECT * FROM actividades WHERE id = ? AND viaje_id = ? AND usuario = ?",
            (actividad_id, viaje_id, yo["usuario"]),
        )
    if len(filas) == 0:
        # 404 y no 403: no confirmamos que exista
        raise HTTPException(404, "No existe la actividad")
    return filas[0]

# ============================================================
# 4. AUTENTICACIÓN: ¿QUIÉN ERES?  (login -> token -> verificar el token en cada petición)
# ============================================================

@app.post("/login", response_model=Token, responses=E401,
          tags=["sesión"], summary="Entrar: cambia usuario y clave por un token")
def login(c: Credenciales):
    with conectar() as con:
        fila = con.execute("SELECT * FROM usuarios WHERE usuario = ?", (c.usuario,)).fetchone()
    # Mismo mensaje si no existe el usuario o si la clave está mal: no le digas al atacante cuál falló
    if fila is None or not bcrypt.checkpw(c.clave.encode(), fila["clave_hash"].encode()):
        raise HTTPException(401, "Usuario o clave incorrectos")
    ahora = datetime.now(timezone.utc)
    datos = {"sub": fila["usuario"], "rol": fila["rol"],           # lo que el token "dice" de ti
             "iat": ahora, "exp": ahora + timedelta(minutes=MINUTOS_TOKEN)}
    token = jwt.encode(datos, SECRETO, algorithm="HS256")          # firmado con la clave del servidor
    return {"access_token": token, "token_type": "bearer", "expira_en_segundos": MINUTOS_TOKEN * 60}


bearer = HTTPBearer(auto_error=False)   # lee el encabezado  Authorization: Bearer <token>
SIN_SESION = {"WWW-Authenticate": "Bearer"}


def usuario_actual(cred: HTTPAuthorizationCredentials = Depends(bearer)) -> dict:
    if cred is None:
        raise HTTPException(401, "Falta el token: inicia sesión en POST /login", headers=SIN_SESION)
    try:
        datos = jwt.decode(cred.credentials, SECRETO, algorithms=["HS256"])   # revisa firma y expiración
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "El token ya expiró: inicia sesión otra vez", headers=SIN_SESION)
    except jwt.InvalidTokenError:
        raise HTTPException(401, "El token no es válido (¿lo modificaste?)", headers=SIN_SESION)
    return {"usuario": datos["sub"], "rol": datos["rol"]}


# ============================================================
# 5. AUTORIZACIÓN: ¿QUÉ PUEDES HACER?  (rol -> 403)
# ============================================================

def solo_encargado(yo: dict = Depends(usuario_actual)) -> dict:
    if yo["rol"] != "encargado":
        raise HTTPException(403, f"Tu rol ({yo['rol']}) no puede hacer esto: solo el encargado")
    return yo


@app.get("/yo", tags=["sesión"], responses=E401, summary="¿Quién dice el token que soy?")
def quien_soy(yo: dict = Depends(usuario_actual)):
    return yo



# ============================================================
# 6. CRUD DE VIAJES
# ============================================================


@app.get("/viajes", response_model=list[Viaje], responses={**E401}, tags=["viajes"])
def listar_viajes(yo: dict = Depends(usuario_actual)):
    return consultar("SELECT * FROM viajes")


@app.get("/viajes/{viaje_id}", response_model=Viaje, responses={**E401, **E404, **E422}, tags=["viajes"])
def consultar_viaje(viaje_id: int, yo: dict = Depends(usuario_actual)):
    return buscar_viaje(viaje_id)

@app.post(
    "/viajes",
    status_code=201,
    response_model=Viaje,
    responses={**E400, **E409, **E422},
    tags=["viajes"],
)
def crear_viaje(datos: ViajeNuevo, response: Response, yo: dict = Depends(solo_encargado)):
    try:
        nuevo_id = ejecutar(
            "INSERT INTO viajes (personas, destino, presupuesto, fecha_salida, fecha_regreso, estado) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                datos.personas,
                datos.destino,
                datos.presupuesto,
                datos.fecha_salida.isoformat(),
                datos.fecha_regreso.isoformat(),
                datos.estado,
            ),
        )
    except sqlite3.IntegrityError:
        # Regla del negocio: mismo destino y misma fecha de salida
        raise HTTPException(
            409, f"Ya existe un viaje a {datos.destino} el {datos.fecha_salida.isoformat()}"
        )

    response.headers["Location"] = f"/viajes/{nuevo_id}"
    return buscar_viaje(nuevo_id)


@app.put(
    "/viajes/{viaje_id}",
    response_model=Viaje,
    responses={**E400, **E404, **E409, **E422},
    tags=["viajes"],
)
def reemplazar_viaje(viaje_id: int, datos: ViajeNuevo, yo: dict = Depends(solo_encargado)):
    buscar_viaje(viaje_id)

    try:
        ejecutar(
            "UPDATE viajes SET personas = ?, destino = ?, presupuesto = ?, "
            "fecha_salida = ?, fecha_regreso = ?, estado = ? WHERE id = ?",
            (
                datos.personas,
                datos.destino,
                datos.presupuesto,
                datos.fecha_salida.isoformat(),
                datos.fecha_regreso.isoformat(),
                datos.estado,
                viaje_id,
            ),
        )
    except sqlite3.IntegrityError:
        raise HTTPException(
            409, f"Ya existe un viaje a {datos.destino} el {datos.fecha_salida.isoformat()}"
        )

    return buscar_viaje(viaje_id)


@app.patch(
    "/viajes/{viaje_id}",
    response_model=Viaje,
    responses={**E400, **E404, **E409, **E422},
    tags=["viajes"],
)
def modificar_viaje(viaje_id: int, cambios: ViajeCambios, yo: dict = Depends(solo_encargado)):
    viaje = buscar_viaje(viaje_id)

    # Solo los campos que el cliente mandó
    cambios_dict = cambios.model_dump(exclude_unset=True, exclude_none=True)

    # Las fechas se guardan como texto "AAAA-MM-DD"
    if "fecha_salida" in cambios_dict:
        cambios_dict["fecha_salida"] = cambios_dict["fecha_salida"].isoformat()
    if "fecha_regreso" in cambios_dict:
        cambios_dict["fecha_regreso"] = cambios_dict["fecha_regreso"].isoformat()

    # Mezclamos el viaje guardado con los cambios
    viaje.update(cambios_dict)

    # Con el PATCH también hay que revisar que las fechas tengan sentido
    if viaje["fecha_regreso"] < viaje["fecha_salida"]:
        raise HTTPException(422, "La fecha de regreso no puede ser anterior a la fecha de salida")

    try:
        ejecutar(
            "UPDATE viajes SET personas = ?, destino = ?, presupuesto = ?, "
            "fecha_salida = ?, fecha_regreso = ?, estado = ? WHERE id = ?",
            (
                viaje["personas"],
                viaje["destino"],
                viaje["presupuesto"],
                viaje["fecha_salida"],
                viaje["fecha_regreso"],
                viaje["estado"],
                viaje_id,
            ),
        )
    except sqlite3.IntegrityError:
        raise HTTPException(
            409, f"Ya existe un viaje a {viaje['destino']} el {viaje['fecha_salida']}"
        )

    return buscar_viaje(viaje_id)


@app.delete(
    "/viajes/{viaje_id}",
    status_code=204,
    responses={**E404, **E422},
    tags=["viajes"],
)
def borrar_viaje(viaje_id: int, yo: dict = Depends(solo_encargado)):
    buscar_viaje(viaje_id)
    # Sus actividades se borran solas (ON DELETE CASCADE)
    ejecutar("DELETE FROM viajes WHERE id = ?", (viaje_id,))
    return Response(status_code=204)


# ============================================================
# 5. ENDPOINTS DE ACTIVIDADES
# ============================================================

@app.post(
    "/viajes/{viaje_id}/actividades",
    status_code=201,
    response_model=Actividad,
    responses={**E400, **E401, **E404, **E422},
    tags=["actividades"],
)
def crear_actividad(viaje_id: int, datos: ActividadNueva, response: Response, yo: dict = Depends(usuario_actual)):
    buscar_viaje(viaje_id)
    nuevo_id = ejecutar(
        "INSERT INTO actividades (viaje_id, usuario, nombre, hora) VALUES (?, ?, ?, ?)",
        (viaje_id, yo["usuario"], datos.nombre, datos.hora),
    )
    response.headers["Location"] = f"/viajes/{viaje_id}/actividades/{nuevo_id}"
    return buscar_actividad(viaje_id, nuevo_id, yo)


@app.get(
    "/viajes/{viaje_id}/actividades",
    response_model=list[Actividad],
    responses={**E401, **E404, **E422},
    tags=["actividades"],
)
def listar_actividades(viaje_id: int, yo: dict = Depends(usuario_actual)):
    buscar_viaje(viaje_id)
    if yo["rol"] == "encargado":
        return consultar(
            "SELECT * FROM actividades WHERE viaje_id = ? ORDER BY id",
            (viaje_id,),
        )
    return consultar(
        "SELECT * FROM actividades WHERE viaje_id = ? AND usuario = ? ORDER BY id",
        (viaje_id, yo["usuario"]),
    )


@app.get(
    "/viajes/{viaje_id}/actividades/{actividad_id}",
    response_model=Actividad,
    responses={**E401, **E404, **E422},
    tags=["actividades"],
)
def consultar_actividad(viaje_id: int, actividad_id: int, yo: dict = Depends(usuario_actual)):
    buscar_viaje(viaje_id)
    return buscar_actividad(viaje_id, actividad_id, yo)


@app.patch(
    "/viajes/{viaje_id}/actividades/{actividad_id}",
    response_model=Actividad,
    responses={**E400, **E401, **E404, **E422},
    tags=["actividades"],
)
def modificar_actividad(viaje_id: int, actividad_id: int, datos: ActividadNueva, yo: dict = Depends(usuario_actual)):
    buscar_viaje(viaje_id)
    buscar_actividad(viaje_id, actividad_id, yo)
    ejecutar(
        "UPDATE actividades SET nombre = ?, hora = ? WHERE id = ? AND viaje_id = ?",
        (datos.nombre, datos.hora, actividad_id, viaje_id),
    )
    return buscar_actividad(viaje_id, actividad_id, yo)


@app.delete(
    "/viajes/{viaje_id}/actividades/{actividad_id}",
    status_code=204,
    responses={**E401, **E404, **E422},
    tags=["actividades"],
)
def borrar_actividad(viaje_id: int, actividad_id: int, yo: dict = Depends(usuario_actual)):
    buscar_viaje(viaje_id)
    buscar_actividad(viaje_id, actividad_id, yo)
    ejecutar(
        "DELETE FROM actividades WHERE id = ? AND viaje_id = ?",
        (actividad_id, viaje_id),
    )
    return Response(status_code=204)

# ============================================================
# 6. DEMO: SIN VALIDACIÓN
# ============================================================


@app.post("/sin-validar/viajes", status_code=201, tags=["demo: sin validación"])
def crear_sin_validar(datos: dict = Body(...)):
    # Se guarda el JSON tal cual, como texto
    ejecutar("INSERT INTO sin_validar (datos) VALUES (?)", (json.dumps(datos),))
    return datos


@app.get("/sin-validar/viajes", tags=["demo: sin validación"])
def listar_sin_validar():
    filas = consultar("SELECT datos FROM sin_validar")
    resultado = []
    for fila in filas:
        resultado.append(json.loads(fila["datos"]))
    return resultado

# --- ENDPOINT DE SUGERENCIA CON IA ---
from pydantic import BaseModel, Field

INSTRUCCION_IA = (
    "Eres un agente de viajes en México. Para el destino que te doy, "
    "responde SOLO un JSON con la forma "
    '{"tipo": "playa" | "ciudad" | "naturaleza" | "pueblo", '
    '"sugerencia": "una actividad recomendada, máximo 20 palabras en español"}.\n'
    "Destino: "
)

class EntradaViajeSugerencia(BaseModel):
    destino: str = Field(..., min_length=2, max_length=300, examples=["Comala, Colima"])

@app.post("/viajes/sugerencia", tags=["IA"])
def viajes_sugerencia(datos: EntradaViajeSugerencia, yo: dict = Depends(usuario_actual)):
    # 1. Mandamos el destino a la IA
    ia = preguntar_a_la_ia(INSTRUCCION_IA + datos.destino)
    
    # 2. NUNCA confíes en la IA: validamos que de verdad devolvió lo que pedimos
    if not isinstance(ia, dict) or ia.get("tipo") not in ("playa", "ciudad", "naturaleza", "pueblo"):
        raise HTTPException(502, "La IA respondió algo inesperado.")
        
    # 3. Regresamos la respuesta limpia
    return {
        "tipo": ia["tipo"],
        "sugerencia": str(ia.get("sugerencia", ""))[:200]
    }