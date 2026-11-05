# api_viajes.py — Sesión 2
# Programación Distribuida · Facultad de Telemática · Universidad de Colima
#
# Cómo correrla:
#   pip install fastapi uvicorn
#   uvicorn api_viajes:app --reload
#   http://127.0.0.1:8000/docs
#
# Los datos viven en memoria (la base de datos llega en la sesión 3).

from typing import Literal, Optional
from datetime import date
from fastapi import Body, FastAPI, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, model_validator

app = FastAPI(title="API de Viajes", version="2.0")

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

# ============================================================
# 2. DATOS EN MEMORIA
# ============================================================

viajes = {
    1: {
        "id": 1, 
        "personas": 3, 
        "destino": "Colima", 
        "presupuesto": 500.0, 
        "fecha_salida": "2024-11-15", 
        "fecha_regreso": "2024-11-18", 
        "estado": "pendiente"
    }
}
actividades = {}
siguiente = {"viaje": 2, "actividad": 1}

# ============================================================
# 3. MANEJO DE ERRORES UNIFICADO
# ============================================================

def error(codigo, mensaje, detalles=None):
    return JSONResponse(status_code=codigo, content={"error": mensaje, "detalles": detalles or []})

@app.exception_handler(HTTPException)
async def error_http(request: Request, exc: HTTPException):
    return error(exc.status_code, exc.detail)

@app.exception_handler(RequestValidationError)
async def error_validacion(request: Request, exc: RequestValidationError):
    errores = exc.errors()
    if any(e["type"] == "json_invalid" for e in errores):
        return error(400, "El cuerpo no es un JSON válido")
    detalles = [f"{'.'.join(str(x) for x in e['loc'][1:])}: {e['msg']}" for e in errores]
    return error(422, "Los datos no son válidos", detalles)

@app.exception_handler(Exception)
async def error_interno(request: Request, exc: Exception):
    return error(500, "Error interno del servidor")


def buscar_viaje(viaje_id: int):
    if viaje_id not in viajes:
        raise HTTPException(404, f"No existe el viaje {viaje_id}")
    return viajes[viaje_id]

# ============================================================
# 4. CRUD DE VIAJES 
# ============================================================

@app.get("/viajes", tags=["viajes"])
def listar_viajes():
    return list(viajes.values())

@app.get("/viajes/{viaje_id}", tags=["viajes"])
def consultar_viaje(viaje_id: int):
    return buscar_viaje(viaje_id)

@app.post("/viajes", status_code=201, tags=["viajes"])
def crear_viaje(datos: ViajeNuevo, response: Response):
    # Regla del negocio: No se puede crear un viaje al mismo destino en la misma fecha
    fecha_str = str(datos.fecha_salida)
    for v in viajes.values():
        if v["destino"].lower() == datos.destino.lower() and v["fecha_salida"] == fecha_str:
            raise HTTPException(409, f"Ya existe un viaje a {datos.destino} el {fecha_str}")
            
    # Convertimos fechas a string para que no haya problemas al guardar/imprimir
    datos_dict = datos.model_dump()
    datos_dict["fecha_salida"] = str(datos_dict["fecha_salida"])
    datos_dict["fecha_regreso"] = str(datos_dict["fecha_regreso"])
    
    nuevo = {"id": siguiente["viaje"], **datos_dict}
    viajes[nuevo["id"]] = nuevo
    siguiente["viaje"] += 1
    response.headers["Location"] = f"/viajes/{nuevo['id']}"
    return nuevo

@app.put("/viajes/{viaje_id}", tags=["viajes"])
def reemplazar_viaje(viaje_id: int, datos: ViajeNuevo):
    buscar_viaje(viaje_id)
    # Validamos regla de negocio al reemplazar también
    fecha_str = str(datos.fecha_salida)
    for v in viajes.values():
        if v["id"] != viaje_id and v["destino"].lower() == datos.destino.lower() and v["fecha_salida"] == fecha_str:
            raise HTTPException(409, f"Ya existe un viaje a {datos.destino} el {fecha_str}")
            
    datos_dict = datos.model_dump()
    datos_dict["fecha_salida"] = str(datos_dict["fecha_salida"])
    datos_dict["fecha_regreso"] = str(datos_dict["fecha_regreso"])
    
    viajes[viaje_id] = {"id": viaje_id, **datos_dict}
    return viajes[viaje_id]

@app.patch("/viajes/{viaje_id}", tags=["viajes"])
def modificar_viaje(viaje_id: int, cambios: ViajeCambios):
    viaje = buscar_viaje(viaje_id)
    cambios_dict = cambios.model_dump(exclude_unset=True)
    
    if "fecha_salida" in cambios_dict: cambios_dict["fecha_salida"] = str(cambios_dict["fecha_salida"])
    if "fecha_regreso" in cambios_dict: cambios_dict["fecha_regreso"] = str(cambios_dict["fecha_regreso"])
    
    viaje.update(cambios_dict)
    return viaje

@app.delete("/viajes/{viaje_id}", status_code=204, tags=["viajes"])
def borrar_viaje(viaje_id: int):
    buscar_viaje(viaje_id)
    del viajes[viaje_id]
    return Response(status_code=204)


# ============================================================
# 5. ENDPOINTS DE ACTIVIDADES
# ============================================================

@app.post("/viajes/{viaje_id}/actividades", status_code=201, tags=["actividades"])
def crear_actividad(viaje_id: int, datos: ActividadNueva):
    buscar_viaje(viaje_id)
    nueva = {"id": siguiente["actividad"], "viaje_id": viaje_id, **datos.model_dump()}
    actividades[nueva["id"]] = nueva
    siguiente["actividad"] += 1
    return nueva

@app.get("/viajes/{viaje_id}/actividades", tags=["actividades"])
def listar_actividades(viaje_id: int):
    buscar_viaje(viaje_id)
    return [a for a in actividades.values() if a["viaje_id"] == viaje_id]

@app.patch("/viajes/{viaje_id}/actividades/{actividad_id}", tags=["actividades"])
def modificar_actividad(viaje_id: int, actividad_id: int, datos: ActividadNueva):
    buscar_viaje(viaje_id)
    if actividad_id not in actividades or actividades[actividad_id]["viaje_id"] != viaje_id:
        raise HTTPException(404, "No existe la actividad")
    actividades[actividad_id].update(datos.model_dump())
    return actividades[actividad_id]

@app.delete("/viajes/{viaje_id}/actividades/{actividad_id}", status_code=204, tags=["actividades"])
def borrar_actividad(viaje_id: int, actividad_id: int):
    buscar_viaje(viaje_id)
    if actividad_id not in actividades or actividades[actividad_id]["viaje_id"] != viaje_id:
        raise HTTPException(404, "No existe la actividad")
    del actividades[actividad_id]
    return Response(status_code=204)


# ============================================================
# 6. DEMO: SIN VALIDACIÓN
# ============================================================

sin_validar = []

@app.post("/sin-validar/viajes", status_code=201, tags=["demo: sin validación"])
def crear_sin_validar(datos: dict = Body(...)):
    sin_validar.append(datos)
    return datos

@app.get("/sin-validar/viajes", tags=["demo: sin validación"])
def listar_sin_validar():
    return sin_validar