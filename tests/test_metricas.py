"""Pruebas de la vista de métricas en consola.

Ollama se sustituye por un cliente simulado con los mismos campos que
devuelve el real. Las pruebas que usan `conn` necesitan PostgreSQL.
"""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace as Datos

import psycopg
import pytest

from agente import Agente, Almacen
from agente.metricas import (dibujar, ficha_modelo, memoria_del_sistema, numero, reunir, seccion_memoria,
                             tamano, uso_del_agente)
from modelo_falso import ModeloFalso

GIB = 1024 ** 3


class OllamaFalso:
    """Responde como Ollama a show, list y ps."""

    def show(self, nombre):
        if nombre.startswith("bge"):
            return Datos(details=Datos(family="bert", parameter_size="566.70M", quantization_level="F16", format="gguf"),
                         capabilities=["embedding"],
                         modelinfo={"general.architecture": "bert", "general.parameter_count": 566703104,
                                    "bert.block_count": 24, "bert.context_length": 8192,
                                    "bert.embedding_length": 1024, "general.license": "mit"})
        return Datos(details=Datos(family="qwen3", parameter_size="4.0B", quantization_level="Q4_K_M", format="gguf"),
                     capabilities=["completion", "tools", "thinking"],
                     modelinfo={"general.architecture": "qwen3", "general.parameter_count": 4022468096,
                                "qwen3.block_count": 36, "qwen3.context_length": 262144,
                                "qwen3.embedding_length": 2560, "general.license": "apache-2.0"})

    def list(self):
        return Datos(models=[Datos(model="qwen3:4b", size=2497293931), Datos(model="bge-m3:latest", size=1157672605)])

    def ps(self):
        en_cuatro_minutos = datetime.now(timezone.utc) + timedelta(minutes=4)
        return Datos(models=[Datos(model="qwen3:4b", size=3 * GIB, size_vram=GIB, context_length=4096,
                                   expires_at=en_cuatro_minutos)])


class OllamaApagado:
    def show(self, nombre):
        raise ConnectionError("Failed to connect to Ollama")


@pytest.fixture
def conn(bd_con_muestra):
    with psycopg.connect(bd_con_muestra, autocommit=True) as conexion:
        yield conexion


def test_formato_de_numeros_y_tamanos():
    assert numero(4022468096) == "4,022,468,096"
    assert tamano(2497293931) == "2.33 GiB"
    assert tamano(600 * 1024 ** 2) == "600 MiB"


def test_ficha_del_modelo_de_chat():
    titulo, filas = ficha_modelo(OllamaFalso(), "qwen3:4b", "MODELO DE CHAT", contexto_en_uso=4096)
    assert titulo == "MODELO DE CHAT · qwen3:4b"
    assert dict(filas) == {
        "Parámetros": "4,022,468,096 (4.0B)",
        "Arquitectura": "qwen3, 36 capas, cuantización Q4_K_M (gguf)",
        "Contexto": "4,096 tokens por petición (el modelo admite hasta 262,144)",
        "Tamaño en disco": "2.33 GiB",
        "Capacidades": "completion, tools, thinking",
        "Licencia": "apache-2.0",
    }


def test_ficha_del_modelo_de_embeddings():
    # se pide como "bge-m3" y Ollama lo lista como "bge-m3:latest"
    filas = dict(ficha_modelo(OllamaFalso(), "bge-m3", "MODELO DE EMBEDDINGS")[1])
    assert filas["Parámetros"] == "566,703,104 (566.70M)"
    assert filas["Dimensión"] == "1,024 valores por vector"
    assert filas["Contexto"] == "hasta 8,192 tokens por texto"
    assert filas["Tamaño en disco"] == "1.08 GiB"


def test_memoria_de_los_modelos_cargados():
    filas = dict(seccion_memoria(OllamaFalso(), ["qwen3:4b", "bge-m3"])[1])
    assert filas["qwen3:4b"] == "3.00 GiB (2.00 GiB en RAM y 1.00 GiB en GPU) · contexto de 4,096 · se libera en 4 min"
    assert filas["bge-m3"] == "no está cargado (se carga al usarlo)"
    assert "RAM del sistema" in filas


def test_memoria_del_sistema():
    total, disponible = memoria_del_sistema()
    assert 0 < disponible <= total


def test_uso_del_agente_suma_los_tokens_de_cada_pregunta(conn):
    agente = Agente(Almacen(conn), ModeloFalso({"actividad": "Concurso"}))
    agente.preparar()
    agente.preguntar("¿Qué concursos hay?")
    agente.preguntar("¿Y qué concursos hay el martes?")

    # el modelo simulado gasta 100 + 50 tokens de entrada y 10 + 20 de salida por pregunta
    guardados = conn.execute("SELECT tokens_entrada, tokens_salida FROM agente_interacciones").fetchall()
    assert guardados == [(150, 30), (150, 30)]

    titulo, filas = uso_del_agente(conn)
    datos = dict(filas)
    assert titulo == "USO DEL AGENTE"
    assert datos["Preguntas"] == "2 en 1 conversación (hoy: 2)"
    assert datos["Tokens leídos"] == "300 (promedio de 150 por pregunta)"
    assert datos["Tokens generados"] == "60 (promedio de 30 por pregunta)"
    assert "Tokens" not in datos                       # todas las preguntas tienen sus tokens
    ultima = filas[-2][1]                               # las últimas preguntas van de la más reciente a la más antigua
    assert "150 leídos, 30 generados" in ultima and "¿Y qué concursos hay el martes?" in ultima


def test_uso_del_agente_sin_preguntas(conn):
    assert uso_del_agente(conn) == ("USO DEL AGENTE", [("Preguntas", "ninguna todavía")])


def test_uso_del_agente_actualiza_una_base_con_el_esquema_anterior(conn):
    conn.execute("ALTER TABLE agente_interacciones DROP COLUMN tokens_entrada, DROP COLUMN tokens_salida")
    conn.execute("INSERT INTO agente_interacciones (sesion, pregunta, filtros, eventos, respuesta, modelo, duracion_ms) "
                 "VALUES (gen_random_uuid(), 'pregunta antigua', '{}', '{}', 'respuesta', 'modelo', 2000)")
    datos = dict(uso_del_agente(conn)[1])
    assert datos["Tokens"] == "registrados en 0 de 1 preguntas (las anteriores no los guardaban)"
    assert datos["Tiempo por pregunta"] == "mediana de 2.0 s · promedio de 2.0 s"


def test_la_vista_se_muestra_aunque_falten_ollama_y_postgresql():
    secciones = dict(reunir(OllamaApagado(), "qwen3:4b", "bge-m3", conn=None))
    assert secciones["MODELOS"] == [("Ollama", "no responde: inícialo y vuelve a intentar")]
    assert secciones["USO DEL AGENTE"] == [("PostgreSQL", "sin conexión: revisa DATABASE_URL en .env")]
    assert "MEMORIA" in secciones


def test_la_vista_avisa_si_el_pipeline_no_se_ha_ejecutado(url_bd):
    with psycopg.connect(url_bd, autocommit=True) as conexion:
        secciones = dict(reunir(OllamaFalso(), "qwen3:4b", "bge-m3", conexion))
    assert secciones["USO DEL AGENTE"] == [("PostgreSQL", "sin tablas: ejecuta primero el pipeline (python main.py)")]
    assert "MODELO DE CHAT · qwen3:4b" in secciones


def test_dibujar_alinea_las_etiquetas():
    vista = dibujar([("MODELO", [("Parámetros", "4.0B"), ("Arquitectura", "qwen3")])], "Métricas")
    assert vista.splitlines() == ["Métricas", "========", "", "MODELO", "  Parámetros    4.0B", "  Arquitectura  qwen3"]
