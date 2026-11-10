"""Pruebas del servicio web: la API que usa la página de UniConferencias.

El modelo se sustituye por uno simulado. Las pruebas que usan `cliente`
necesitan PostgreSQL y se omiten si no está disponible.
"""

import psycopg
import pytest
from fastapi.testclient import TestClient

from agente.servidor import crear_app
from modelo_falso import ModeloFalso

CAMPOS_DE_LA_PAGINA = {"id", "titulo", "ponente", "campus", "ubicacion", "fecha", "fechaFin",
                       "horaInicio", "horaFin", "area", "tipo", "descripcion", "enlace"}


def _cliente(url_bd, **filtros) -> TestClient:
    return TestClient(crear_app(url_bd, modelo=ModeloFalso(filtros)))


@pytest.fixture
def cliente(bd_con_muestra):
    return _cliente(bd_con_muestra)


def test_eventos_devuelve_el_programa_con_los_campos_de_la_pagina(cliente):
    eventos = cliente.get("/api/eventos").json()
    assert len(eventos) == 6
    assert all(set(evento) == CAMPOS_DE_LA_PAGINA for evento in eventos)
    assert eventos[0] == {
        "id": 1, "titulo": "Introducción a sensores", "ponente": "Ponente A", "campus": "No especificado",
        "ubicacion": "Virtual", "fecha": "2026-09-20", "fechaFin": "2026-09-20",
        "horaInicio": "10:00", "horaFin": "12:00", "area": "Conferencia", "tipo": "virtual",
        "descripcion": "Institución: UACJ · Maestro de ceremonias: Maestro A",
        "enlace": "https://teams.microsoft.com/meet/000000",
    }
    presencial = eventos[1]
    assert (presencial["ubicacion"], presencial["enlace"], presencial["fechaFin"]) == ("W 102", "", "2026-09-25")


def test_agente_responde_con_texto_y_eventos(bd_con_muestra):
    cliente = _cliente(bd_con_muestra, hora_desde="10:00", hora_hasta="12:00")
    respuesta = cliente.post("/api/agente", json={"pregunta": "¿Qué hay entre las 10 y las 12?"})
    assert respuesta.status_code == 200
    datos = respuesta.json()
    assert datos["respuesta"] == "Respuesta de prueba."
    assert datos["busqueda"] == "entre las 10:00 y las 12:00"
    assert datos["filtros"]["hora_desde"] == "10:00"
    assert [evento["id"] for evento in datos["eventos"]] == [1, 2, 3, 6]
    assert (datos["total"], datos["detalle"]) == (4, "")


def test_agente_en_pregunta_general_devuelve_las_cifras(cliente):
    datos = cliente.post("/api/agente", json={"pregunta": "¿Qué tipos de actividad hay?"}).json()
    assert datos["eventos"] == [] and datos["total"] == 0
    assert "Tipos de actividad (5)" in datos["detalle"]


def test_agente_registra_la_sesion_de_la_pagina(bd_con_muestra):
    sesion = "0b0f6c1e-7a52-4b1e-9d5e-3c1f2a4b5c6d"
    _cliente(bd_con_muestra).post("/api/agente", json={"pregunta": "hola", "sesion": sesion})
    with psycopg.connect(bd_con_muestra) as conn:
        guardada = conn.execute("SELECT sesion::text, pregunta FROM agente_interacciones").fetchone()
    assert guardada == (sesion, "hola")


@pytest.mark.parametrize("cuerpo", [{}, {"pregunta": "   "}, {"pregunta": "x" * 501},
                                    {"pregunta": "hola", "sesion": "no-es-un-uuid"}])
def test_agente_rechaza_peticiones_invalidas(cliente, cuerpo):
    assert cliente.post("/api/agente", json=cuerpo).status_code == 422


def test_sirve_la_pagina_pero_no_otros_archivos_de_la_carpeta(cliente):
    inicio = cliente.get("/")
    assert inicio.status_code == 200 and "UniConferencias" in inicio.text
    assert cliente.get("/script.js").status_code == 200
    assert cliente.get("/Programa_32IIT_21-09.xlsx").status_code == 404
    assert cliente.get("/README.txt").status_code == 404


def test_sin_base_de_datos_responde_503_con_explicacion():
    cliente = _cliente("postgresql://nadie@127.0.0.1:1/nada?connect_timeout=2")
    respuesta = cliente.get("/api/eventos")
    assert respuesta.status_code == 503
    assert "No se pudo conectar a PostgreSQL" in respuesta.json()["detail"]


def test_sin_pipeline_ejecutado_responde_503_con_explicacion(url_bd):
    cliente = _cliente(url_bd)     # esquema vacío: el pipeline todavía no ha creado las tablas
    assert "ejecuta primero el pipeline" in cliente.get("/api/eventos").json()["detail"]
    respuesta = cliente.post("/api/agente", json={"pregunta": "hola"})
    assert respuesta.status_code == 503 and "ejecuta primero el pipeline" in respuesta.json()["detail"]
