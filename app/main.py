from typing import Literal, Optional
from fastapi import Body, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field

app = FastAPI(title="Travel Planer")

#LUKA
@app.post("/viajes") #-> 201 errores: 400, 422 Crear un nuevo viaje
def funcion():
    pass

#TERE
@app.get("/viajes") # -> 200 errores: - Listado de todos los viajes
def funcion():
    pass

#LUKA
@app.get("/viajes/{id_viaje}")# -> 200 errores: 404 Detalles del viaje
def funcion():
    pass

#TERE
@app.patch("/viajes/{id_viaje}") #-> 200 errores: 400, 404, 422 Editar algún elemento del viaje
def funcion():
    pass

#ELIAS
@app.delete("/viajes/{id_viaje}")
def funcion():
    pass