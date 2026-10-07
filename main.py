from fastapi import FastAPI, HTTPException
from fastapi.middileware.cors import CORSMiddleware
from pydantic import BaseModel

from orquestador import generar_diagnostico_riego

app = FastAPI(
    title ="API B.A.W.í Backend"
    description="Motor de cálculo y lógica difusa para ecosistema de riego agrícola"
    version = 1.0

app.add.middleware(
    CORSMiddleware,
    allow_origins=["*"]
)


)