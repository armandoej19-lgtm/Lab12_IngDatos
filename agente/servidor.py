"""Servicio web del agente: la API que usa la página y la página misma.

    GET  /api/eventos   programa completo, leído de PostgreSQL
    POST /api/agente    {"pregunta": "..."} -> respuesta del agente con sus tablas
    GET  /              página de UniConferencias
    GET  /asistente     conversación con el agente (se abre con el botón flotante)

Uso:
    python -m agente.servidor               # http://localhost:8000
    python -m agente.servidor --puerto 8080
"""

import argparse
import logging
import re
import threading
import unicodedata
from contextlib import asynccontextmanager, contextmanager
from dataclasses import asdict
from pathlib import Path
from typing import Annotated
from uuid import UUID

import psycopg
import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, StringConstraints

from pipeline import bd

from . import Agente, Almacen, Modelo, ModeloNoDisponible, SinDatos
from .consulta import Consulta

log = logging.getLogger("uvicorn.error")    # el registro que Uvicorn muestra en la consola

PAGINA = Path(__file__).resolve().parents[1] / "UniConferencias"
EXTENSIONES_DE_PAGINA = {".html", ".css", ".js", ".ico", ".png", ".jpg", ".svg", ".webp"}

# Solo se asigna un campus cuando aparece mencionado explícitamente en los
# datos descriptivos del evento. No se deduce a partir del nombre del salón.
# Las variantes se comparan después de quitar acentos, puntos y diferencias
# entre mayúsculas/minúsculas.
ALIAS_CAMPUS = {
    "IIT": ("iit", "i i t", "instituto de ingenieria y tecnologia"),
    "ICSA": ("icsa", "i c s a", "instituto de ciencias sociales y administracion"),
    "ICB": ("icb", "i c b", "instituto de ciencias biomedicas"),
    "IADA": ("iada", "i a d a", "instituto de arquitectura diseno y arte"),
    "CU": ("campus cu", "ciudad universitaria"),
    "CUAUH": ("cuauh", "cuauhtemoc", "campus cuauhtemoc"),
}


def normalizar_texto(texto: str) -> str:
    """Quita acentos y puntuación para reconocer variantes de una mención."""
    texto = unicodedata.normalize("NFKD", texto.casefold())
    texto = "".join(caracter for caracter in texto if not unicodedata.combining(caracter))
    return re.sub(r"[^a-z0-9]+", " ", texto).strip()




def campus_explicito(evento):
    """
    Obtiene el campus del evento siguiendo este orden:
    1. Título y actividad.
    2. Institución.
    3. Ponente y maestro de ceremonias.
    4. Prefijo del salón o ubicación.

    Si hay información contradictoria en una misma prioridad,
    devuelve No especificado.
    """

    def buscar_campus(campos):
        texto = " ".join(
            str(evento.get(campo) or "")
            for campo in campos
        )

        texto = f" {normalizar_texto(texto)} "

        encontrados = set()

        for campus, alias in ALIAS_CAMPUS.items():
            for variante in alias:
                variante_normalizada = normalizar_texto(variante)

                if f" {variante_normalizada} " in texto:
                    encontrados.add(campus)
                    break

        return encontrados

    # Prioridad 1: título y actividad.
    campus_evento = buscar_campus([
        "titulo",
        "actividad"
    ])

    if len(campus_evento) == 1:
        return next(iter(campus_evento))

    if len(campus_evento) > 1:
        return "No especificado"

    # Prioridad 2: institución.
    campus_institucion = buscar_campus([
        "empresa_institucion"
    ])

    if len(campus_institucion) == 1:
        return next(iter(campus_institucion))

    if len(campus_institucion) > 1:
        return "No especificado"

    # Prioridad 3: ponente y maestro de ceremonias.
    campus_personal = buscar_campus([
        "ponente",
        "maestro_ceremonias"
    ])

    if len(campus_personal) == 1:
        return next(iter(campus_personal))

    if len(campus_personal) > 1:
        return "No especificado"

    # Prioridad 4: identificar el campus mediante el prefijo del salón.
    salon = (
        evento.get("salon")
        or evento.get("ubicacion")
        or ""
    )

    salon_normalizado = normalizar_texto(str(salon))
    primera_palabra = salon_normalizado.split(" ")[0] if salon_normalizado else ""

    if primera_palabra == "cuauh":
        return "CUAUH"

    if primera_palabra == "cu":
        return "CU"

    return "No especificado"




class Pregunta(BaseModel):
    pregunta: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
    sesion: UUID | None = None      # agrupa las preguntas de una misma visita


class ArchivosDePagina(StaticFiles):
    """Sirve la página y nada más: la carpeta también tiene archivos que no son para el navegador."""

    async def get_response(self, path: str, scope):
        if path not in ("", ".") and Path(path).suffix.lower() not in EXTENSIONES_DE_PAGINA:
            raise HTTPException(status_code=404)
        return await super().get_response(path, scope)


def para_web(evento: dict) -> dict:
    """Un evento con los nombres de campo que usa la página."""
    detalles = [f"{etiqueta}: {evento[campo]}"
                for etiqueta, campo in (("Institución", "empresa_institucion"),
                                        ("Maestro de ceremonias", "maestro_ceremonias"))
                if evento[campo]]
    virtual = str(evento.get("tipo") or "").strip().casefold() == "virtual"
    return {
        "id": evento["id_evento"],
        "titulo": evento["titulo"],
        "ponente": evento["ponente"] or "Por confirmar",
        "campus": "Virtual" if virtual else campus_explicito(evento),
        "ubicacion": "Virtual" if virtual else (evento["salon"] or "Por confirmar"),
        "fecha": evento["fecha_inicio"].isoformat(),
        "fechaFin": evento["fecha_fin"].isoformat(),
        "horaInicio": f"{evento['hora_inicio']:%H:%M}",
        "horaFin": f"{evento['hora_fin']:%H:%M}",
        "area": evento["actividad"],
        "tipo": evento["tipo"],
        "descripcion": " · ".join(detalles),
        "enlace": evento["enlace"] or "",
    }
    

def crear_app(url_bd: str | None = None, modelo=None) -> FastAPI:
    """Crea la aplicación.

    url_bd: URL de PostgreSQL (por defecto, la de DATABASE_URL).
    modelo: cliente del modelo; si no se pasa se usa Ollama. Sirve para las pruebas.
    """
    estado = {"modelo": modelo, "verificado": False}
    turno = threading.Lock()    # el modelo local atiende una pregunta a la vez

    @contextmanager
    def conexion():
        try:
            conn = bd.conectar(url_bd, autocommit=True, connect_timeout=5)
        except (RuntimeError, psycopg.OperationalError) as error:
            raise HTTPException(status_code=503, detail=f"No se pudo conectar a PostgreSQL: {error}") from error
        with conn:
            yield conn

    def agente_listo(conn, sesion: UUID | None) -> Agente:
        """Agente con Ollama verificado y los vectores al día (por si el pipeline se volvió a ejecutar)."""
        if estado["modelo"] is None:
            estado["modelo"] = Modelo()
        if not estado["verificado"]:
            estado["modelo"].verificar()
            estado["verificado"] = True
        agente = Agente(Almacen(conn), estado["modelo"], sesion)
        agente.preparar()
        return agente

    def precargar() -> None:
        """Deja el agente listo desde el arranque, para que la primera pregunta no espere a los vectores."""
        try:
            with bd.conectar(url_bd, autocommit=True, connect_timeout=5) as conn, turno:
                agente_listo(conn, None)
            log.info("Agente listo (%s).", estado["modelo"].chat)
        except (RuntimeError, psycopg.Error) as error:
            # Sin base de datos o sin Ollama la página se sirve igual; se reintenta en la primera pregunta
            log.warning("El agente todavía no está disponible: %s", error)

    @asynccontextmanager
    async def al_arrancar(app: FastAPI):
        threading.Thread(target=precargar, daemon=True).start()
        yield

    app = FastAPI(title="UniConferencias", description="Programa de la Semana de Ingeniería y su asistente.",
                  lifespan=al_arrancar)

    @app.exception_handler(ModeloNoDisponible)
    @app.exception_handler(SinDatos)
    def no_disponible(request: Request, error: Exception) -> JSONResponse:
        return JSONResponse(status_code=503, content={"detail": str(error)})

    @app.exception_handler(psycopg.errors.UndefinedTable)
    def sin_tablas(request: Request, error: Exception) -> JSONResponse:
        return JSONResponse(status_code=503, content={
            "detail": "La base de datos no tiene las tablas del programa: ejecuta primero el pipeline (python main.py)."})

    @app.get("/api/eventos", summary="Programa completo")
    def eventos() -> list[dict]:
        with conexion() as conn:
            return [para_web(evento) for evento in Almacen(conn).buscar(Consulta())]

    @app.post("/api/agente", summary="Pregunta al agente")
    def preguntar(cuerpo: Pregunta) -> dict:
        with conexion() as conn, turno:
            respuesta = agente_listo(conn, cuerpo.sesion).preguntar(cuerpo.pregunta)
        return {
            "respuesta": respuesta.texto,
            "busqueda": respuesta.consulta.descripcion(),
            "filtros": respuesta.consulta.como_dict(),
            "total": respuesta.total,
            # la información de las actividades va siempre en tablas: {titulo, columnas, filas, nota}
            "tablas": [asdict(tabla) for tabla in respuesta.tablas],
            "eventos": [para_web(evento) for evento in respuesta.eventos],
        }

    @app.get("/asistente", include_in_schema=False)
    def asistente() -> FileResponse:
        """Página de la conversación con el agente; se abre con el botón flotante de la página principal."""
        return FileResponse(PAGINA / "asistente.html")

    app.mount("/", ArchivosDePagina(directory=PAGINA, html=True), name="pagina")
    return app


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(prog="python -m agente.servidor",
                                     description="Página de UniConferencias y API del agente")
    parser.add_argument("--host", default="127.0.0.1", help="Dirección donde escucha (por defecto: solo esta máquina)")
    parser.add_argument("--puerto", type=int, default=8000)
    parser.add_argument("--bd", metavar="URL", help="URL de PostgreSQL (por defecto: variable DATABASE_URL)")
    args = parser.parse_args()
    uvicorn.run(crear_app(args.bd), host=args.host, port=args.puerto)


if __name__ == "__main__":
    main()
