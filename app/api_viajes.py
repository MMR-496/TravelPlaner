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
import sqlite3
from datetime import date
from typing import Literal, Optional

from fastapi import Body, FastAPI, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, model_validator

app = FastAPI(title="API de Viajes", version="3.0")

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


class ErrorRespuesta(BaseModel):
    # Formato único de todos los errores de la API
    error: str = Field(..., examples=["No existe el viaje 99"])
    detalles: list[str] = Field(default=[], examples=[[]])


# Errores que se muestran en el contrato (/docs)
E400 = {400: {"model": ErrorRespuesta, "description": "El cuerpo no es un JSON válido"}}
E404 = {404: {"model": ErrorRespuesta, "description": "No existe el recurso"}}
E409 = {409: {"model": ErrorRespuesta, "description": "Ya existe un viaje al mismo destino en esa fecha"}}
E422 = {422: {"model": ErrorRespuesta, "description": "Los datos no son válidos"}}

# ============================================================
# 2. BASE DE DATOS (SQLite)
# ============================================================

ARCHIVO_BD = "viajes.db"


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
                hora TEXT NOT NULL,
                FOREIGN KEY (viaje_id) REFERENCES viajes (id) ON DELETE CASCADE
            )
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
        con.commit()
    finally:
        con.close()


crear_tablas()

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


def buscar_actividad(viaje_id: int, actividad_id: int):
    filas = consultar(
        "SELECT * FROM actividades WHERE id = ? AND viaje_id = ?",
        (actividad_id, viaje_id),
    )
    if len(filas) == 0:
        raise HTTPException(404, "No existe la actividad")
    return filas[0]


# ============================================================
# 4. CRUD DE VIAJES
# ============================================================


@app.get("/viajes", response_model=list[Viaje], tags=["viajes"])
def listar_viajes():
    return consultar("SELECT * FROM viajes")


@app.get("/viajes/{viaje_id}", response_model=Viaje, responses={**E404, **E422}, tags=["viajes"])
def consultar_viaje(viaje_id: int):
    return buscar_viaje(viaje_id)


@app.post(
    "/viajes",
    status_code=201,
    response_model=Viaje,
    responses={**E400, **E409, **E422},
    tags=["viajes"],
)
def crear_viaje(datos: ViajeNuevo, response: Response):
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
def reemplazar_viaje(viaje_id: int, datos: ViajeNuevo):
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
def modificar_viaje(viaje_id: int, cambios: ViajeCambios):
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
def borrar_viaje(viaje_id: int):
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
    responses={**E400, **E404, **E422},
    tags=["actividades"],
)
def crear_actividad(viaje_id: int, datos: ActividadNueva):
    buscar_viaje(viaje_id)
    nuevo_id = ejecutar(
        "INSERT INTO actividades (viaje_id, nombre, hora) VALUES (?, ?, ?)",
        (viaje_id, datos.nombre, datos.hora),
    )
    return buscar_actividad(viaje_id, nuevo_id)


@app.get(
    "/viajes/{viaje_id}/actividades",
    response_model=list[Actividad],
    responses={**E404, **E422},
    tags=["actividades"],
)
def listar_actividades(viaje_id: int):
    buscar_viaje(viaje_id)
    return consultar("SELECT * FROM actividades WHERE viaje_id = ?", (viaje_id,))


@app.patch(
    "/viajes/{viaje_id}/actividades/{actividad_id}",
    response_model=Actividad,
    responses={**E400, **E404, **E422},
    tags=["actividades"],
)
def modificar_actividad(viaje_id: int, actividad_id: int, datos: ActividadNueva):
    buscar_viaje(viaje_id)
    buscar_actividad(viaje_id, actividad_id)
    ejecutar(
        "UPDATE actividades SET nombre = ?, hora = ? WHERE id = ? AND viaje_id = ?",
        (datos.nombre, datos.hora, actividad_id, viaje_id),
    )
    return buscar_actividad(viaje_id, actividad_id)


@app.delete(
    "/viajes/{viaje_id}/actividades/{actividad_id}",
    status_code=204,
    responses={**E404, **E422},
    tags=["actividades"],
)
def borrar_actividad(viaje_id: int, actividad_id: int):
    buscar_viaje(viaje_id)
    buscar_actividad(viaje_id, actividad_id)
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