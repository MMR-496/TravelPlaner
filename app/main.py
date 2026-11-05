from typing import Literal, Optional
from fastapi import Body, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field
from datetime import date

app = FastAPI(title="Travel Planer")

#Almacenamiento temporal
VIAJES = []

#Esquema para visualizar viajes (GET)
class Viaje(BaseModel):
    id : int
    personas : int #Cuántas personas planean ir 
    destino : str #A dónde van a ir
    presupuesto : float #Presupuesto total del grupo/persona
    fecha_salida : date #Cuando emprenden su viaje
    fecha_regreso : date #Cuándo regresan a casa
    estado : str #El viaje está pendiente, en curso o completado

#Esquema para crar viajes (POST)
class ViajeCreate(BaseModel):
    personas : int = Field(ge=1, lt=20 )
    destino : str
    presupuesto : float = Field(gt=0)
    fecha_salida : date = Field(ge=date.today())
    fecha_regreso : date = Field(ge=date.today())
    estado : str = Field(min_length=7)

# gt greater than (>)
# ge greater than or equal (>=)
# lt less than (<)
# le less than or equal (<=)

#Esquema para actualizar (PATCH/PUT)
class ViajeUpdate(BaseModel):
    personas : int
    destino : str
    presupuesto : float
    fecha_salida : date
    fecha_regreso : date
    estado : str

#LUKA
@app.post("/viajes", tags=["Viajes"]) #-> 201 errores: 400, 422 Crear un nuevo viaje
def create_viaje(viaje: ViajeCreate):
    VIAJES.append(viaje.model_dump())
    return VIAJES

#TERE
@app.get("/viajes", tags=["Viajes"]) # -> 200 errores: - Listado de todos los viajes
def funcion():
    pass

#LUKA
@app.get("/viajes/{id_viaje}", tags=["Viajes"])# -> 200 errores: 404 Detalles del viaje
def funcion():
    pass

#TERE
@app.patch("/viajes/{id_viaje}", tags=["Viajes"]) #-> 200 errores: 400, 404, 422 Editar algún elemento del viaje
def funcion():
    pass

#ELIAS
@app.delete("/viajes/{id_viaje}", tags=["Viajes"])
def funcion():
    pass