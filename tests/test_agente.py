"""Pruebas del agente.

El modelo de Ollama se sustituye por uno falso: aquí se prueba lo que hace el
programa con sus respuestas (validar filtros, buscar, ordenar y registrar), no
la calidad del modelo. Las pruebas que usan `conn` necesitan PostgreSQL y se
omiten si no está disponible.

Eventos válidos de los datos de muestra, por id_evento:
    1 Conferencia  dom 20  10:00-12:00  virtual     Introducción a sensores
    2 Curso        lun 21 al vie 25  09:00-13:00    Diseño de circuitos
    3 Concurso     lun 21  09:00-11:00  presencial  Inauguración
    4 Concurso     mar 22  15:00-17:00  presencial  Concurso de Programación
    5 Taller       mié 23  16:00-18:00  presencial  Torneo 3x3
    6 Ponencia     jue 24  11:00-12:00  virtual     Industria 4.0
"""

from datetime import date, time

import psycopg
import pytest

from agente import Agente, Almacen, SinDatos
from agente.agente import destacados, formatear_listado, nombra, ordenar_por_similitud
from agente.consulta import Consulta, a_hora, desde_modelo, emparentadas, esquema, sin_acentos, variantes
from main import ejecutar

ACTIVIDADES = ["Conferencia", "Conferencia magistral", "Taller", "Concurso", "Deportiva"]
FECHAS = [date(2026, 9, 21), date(2026, 9, 22)]


class ModeloFalso:
    """Devuelve filtros fijos y vectores que solo dependen de unas palabras clave.

    filtros: lo que "interpreta" de cualquier pregunta.
    afines:  números de los candidatos que "elige" cuando se le pide filtrar por tema.
    """
    chat = "modelo-falso"
    embeddings = "embeddings-falsos"
    PALABRAS = ["sensor", "circuito", "programacion", "torneo", "industria"]

    def __init__(self, filtros: dict | None = None, afines: list[int] | None = None):
        self.filtros = filtros or {}
        self.afines = afines or []
        self.candidatos = None      # lista que recibió para filtrar por tema
        self.datos_recibidos = None  # datos que recibió para redactar

    def interpretar(self, sistema, usuario, esquema):
        if "relacionados" in esquema["properties"]:
            self.candidatos = usuario
            return {"relacionados": self.afines}
        return self.filtros

    def redactar(self, sistema, usuario):
        self.datos_recibidos = usuario
        return "Respuesta de prueba."

    def vectorizar(self, textos):
        return [[float(palabra in sin_acentos(texto)) for palabra in self.PALABRAS] for texto in textos]


@pytest.fixture
def conn(rutas_muestra, tmp_path, url_bd):
    """Conexión a una base con los datos de muestra ya cargados por el pipeline."""
    assert ejecutar(*rutas_muestra, tmp_path / "out", url_bd) == 0
    with psycopg.connect(url_bd, autocommit=True) as conexion:
        yield conexion


def _agente(conn, afines=None, **filtros) -> Agente:
    agente = Agente(Almacen(conn), ModeloFalso(filtros, afines))
    agente.preparar()
    return agente


def _ids(respuesta) -> list[int]:
    return [e["id_evento"] for e in respuesta.eventos]


def _consulta(pregunta: str, **datos) -> Consulta:
    return desde_modelo(datos, pregunta, ACTIVIDADES, FECHAS, hora_min=time(8))


# --- Consulta: validación de lo que devuelve el modelo ----------------------
def test_consulta_normaliza_valores_del_modelo():
    consulta = _consulta("¿Qué conferencias virtuales de robótica hay el martes de 10 a 12?",
                         actividad="conferencia", modalidad="Virtual", fecha="2026-09-22",
                         hora_desde="10", hora_hasta="12:00", tema=" robótica ")
    assert consulta == Consulta("Conferencia", "virtual", date(2026, 9, 22), time(10), time(12), "robótica")
    assert consulta.como_dict()["hora_desde"] == "10:00"


def test_consulta_descarta_valores_fuera_del_catalogo():
    consulta = _consulta("¿Qué hay?", actividad="Hackatón", modalidad="híbrido", fecha="2026-12-01",
                         hora_desde="25:00", hora_hasta="tarde", tema="null")
    assert consulta.vacia
    assert _consulta("hola").vacia


def test_consulta_solo_acepta_la_actividad_si_la_pregunta_la_nombra():
    # el modelo dedujo "Concurso" de la palabra "torneo": ese filtro escondería el evento buscado
    deducida = _consulta("¿Dónde es el torneo de ajedrez?", actividad="Concurso", tema="torneo de ajedrez")
    assert (deducida.actividad, deducida.tema) == (None, "torneo de ajedrez")
    assert _consulta("¿Qué concursos hay?", actividad="Concurso").actividad == "Concurso"
    assert _consulta("¿Qué talleres hay?", actividad="Taller").actividad == "Taller"
    assert _consulta("¿Qué actividades presenciales hay?", actividad="Conferencia").actividad is None


def test_consulta_convierte_el_tema_en_actividad_si_es_una_clase():
    consulta = _consulta("¿Qué deportes hay?", tema="deportes")
    assert (consulta.actividad, consulta.tema) == ("Deportiva", None)
    assert _consulta("¿Hay algo de drones?", tema="drones").tema == "drones"


def test_consulta_ordena_el_horario_y_pasa_a_la_tarde_las_horas_tempranas():
    invertido = _consulta("de 12 a 10", hora_desde="12:00", hora_hasta="10:00")
    assert (invertido.hora_desde, invertido.hora_hasta) == (time(10), time(12))
    # el programa empieza a las 8: "la 1" solo puede ser la 1 de la tarde
    tarde = _consulta("entre las 9 y la 1", hora_desde="9", hora_hasta="1")
    assert (tarde.hora_desde, tarde.hora_hasta) == (time(9), time(13))


@pytest.mark.parametrize("valor, esperado", [("10", time(10)), ("9:30", time(9, 30)), ("09:30:00", time(9, 30)),
                                             ("24:00", None), ("diez", None), (None, None), (10, None)])
def test_a_hora(valor, esperado):
    assert a_hora(valor) == esperado


def test_esquema_limita_la_salida_al_catalogo():
    propiedades = esquema(ACTIVIDADES, FECHAS)["properties"]
    assert propiedades["actividad"]["enum"] == [*ACTIVIDADES, None]
    assert propiedades["fecha"]["enum"] == ["2026-09-21", "2026-09-22", None]


@pytest.mark.parametrize("a, b, son_variantes, estan_emparentadas", [
    ("sensor", "sensores", True, True),
    ("dron", "drones", True, True),
    ("ia", "ia", True, True),
    ("deportes", "deportiva", False, True),
    ("medicina", "medicion", False, True),      # por esto el tema se compara con la regla estricta
    ("video", "videojuegos", False, False),
    ("curso", "concurso", False, False),
    ("presenciales", "presentacion", False, False),
])
def test_comparacion_de_palabras(a, b, son_variantes, estan_emparentadas):
    assert variantes(a, b) is son_variantes
    assert emparentadas(a, b) is estan_emparentadas


# --- Búsqueda por tema ------------------------------------------------------
def _evento(id_evento, titulo, ponente=None, empresa=None):
    return {"id_evento": id_evento, "titulo": titulo, "actividad": "Conferencia", "ponente": ponente,
            "empresa_institucion": empresa, "salon": None, "maestro_ceremonias": None}


def test_nombra_ignora_acentos_plurales_y_palabras_vacias():
    evento = _evento(1, "Usos de la IA en los Sensores Ópticos", ponente="Dra. María Pérez", empresa="UACJ")
    assert nombra("sensor óptico", evento)
    assert nombra("IA", evento)                         # palabra completa, no parte de otra
    assert nombra("la doctora maria perez", evento)
    assert not nombra("sensores de presión", evento)    # deben estar todas las palabras
    assert not nombra("ingeniería", _evento(2, "Usos de la IA"))
    assert not nombra("de la", evento)                  # sin palabras con contenido no hay coincidencia
    assert nombra("maria perez", evento, campos=("ponente",))
    assert not nombra("sensores", evento, campos=("ponente",))


def test_similitud_ordena_y_destaca_los_mas_parecidos():
    eventos = [_evento(1, "Hidrología"), _evento(2, "Redes neuronales"), _evento(3, "Aprendizaje automático"),
               _evento(4, "Sin vector")]
    vectores = {1: [0.0, 1.0], 2: [0.8, 0.6], 3: [1.0, 0.1]}
    ordenados = ordenar_por_similitud([1.0, 0.0], eventos, vectores)
    assert [e["id_evento"] for e, _ in ordenados] == [3, 2, 1, 4]
    assert ordenados[0][1] == pytest.approx(0.995, abs=1e-3) and ordenados[3][1] == 0.0

    assert [e["id_evento"] for e in destacados(ordenados, minimo=0.5, margen=0.25)] == [3, 2]
    assert [e["id_evento"] for e in destacados(ordenados, minimo=0.5, margen=0.05)] == [3]
    assert destacados(ordenados, minimo=0.999, margen=0.05) == []   # nada alcanza el mínimo
    assert destacados([]) == []


def test_listado_avisa_cuando_no_muestra_todo():
    evento = {"actividad": "Taller", "fecha_inicio": date(2026, 9, 21), "fecha_fin": date(2026, 9, 21),
              "hora_inicio": time(9), "hora_fin": time(10, 30), "tipo": "presencial", "salon": "W 102",
              "titulo": "Soldadura", "ponente": "Ponente A", "empresa_institucion": "UACJ", "enlace": None}
    listado = formatear_listado([evento], total=4)
    assert "lun 21 sep, 09:00-10:30 | Taller | W 102" in listado
    assert "Soldadura (Ponente A - UACJ)" in listado
    assert "Se muestran 1 de 4" in listado


# --- Agente completo (PostgreSQL + modelo falso) ----------------------------
def test_preparar_genera_los_vectores_una_sola_vez(conn):
    agente = Agente(Almacen(conn), ModeloFalso())
    assert agente.preparar() == 6
    assert agente.preparar() == 0
    contenido = conn.execute("SELECT contenido, modelo, cardinality(embedding) FROM agente_vectores "
                             "WHERE id_evento = 2").fetchone()
    assert contenido == ("Diseño de circuitos (Curso)", "embeddings-falsos", 5)

    # con otro modelo de embeddings los vectores se regeneran
    agente.modelo.embeddings = "otros-embeddings"
    assert agente.preparar() == 6
    assert conn.execute("SELECT DISTINCT modelo FROM agente_vectores").fetchall() == [("otros-embeddings",)]


def test_pregunta_por_horario(conn):
    todas = _agente(conn, hora_desde="10:00", hora_hasta="12:00").preguntar("¿Qué hay entre las 10 y las 12?")
    assert _ids(todas) == [1, 2, 3, 6]          # coinciden con el intervalo; el curso cuenta por su horario diario
    assert "Introducción a sensores" in todas.listado

    conferencias = _agente(conn, actividad="Conferencia", hora_desde="10:00", hora_hasta="12:00").preguntar(
        "¿Qué conferencias hay entre las 10 y las 12?")
    assert _ids(conferencias) == [1]


def test_pregunta_por_hora_dia_y_modalidad(conn):
    assert _ids(_agente(conn, hora_desde="16:00").preguntar("¿Qué hay después de las 4?")) == [5]
    assert _ids(_agente(conn, hora_hasta="10:00").preguntar("¿Qué hay antes de las 10?")) == [2, 3]
    assert _ids(_agente(conn, hora_desde="15:00", hora_hasta="15:00").preguntar("¿Qué hay a las 3?")) == [4]
    assert _ids(_agente(conn, fecha="2026-09-23").preguntar("¿Qué hay el miércoles?")) == [2, 5]  # el curso dura toda la semana
    assert _ids(_agente(conn, modalidad="virtual").preguntar("¿Qué actividades virtuales hay?")) == [1, 6]


def test_tema_nombrado_en_el_titulo_no_necesita_al_modelo(conn):
    agente = _agente(conn, tema="circuitos")
    respuesta = agente.preguntar("¿Hay algo de circuitos?")
    assert _ids(respuesta) == [2]
    assert agente.modelo.candidatos is None             # ningún otro evento se le parece: no hay qué filtrar

    filtrada = _agente(conn, actividad="Taller", tema="circuitos").preguntar("¿Qué talleres hay de circuitos?")
    assert _ids(filtrada) == [] and "No encontré" in filtrada.texto


def test_tema_que_es_una_persona_devuelve_solo_sus_eventos(conn):
    assert _ids(_agente(conn, tema="Ponente B").preguntar("¿Qué da el Ponente B?")) == [2]


def test_tema_afin_lo_proponen_los_vectores_y_lo_confirma_el_modelo(conn):
    # ningún evento nombra "industria" y "sensores" a la vez: los vectores proponen el 1 y el 6
    agente = _agente(conn, afines=[2], tema="industria de sensores")
    respuesta = agente.preguntar("¿Qué hay sobre la industria de sensores?")
    assert "1. Introducción a sensores (Conferencia)\n2. Industria 4.0 (Ponencia)" in agente.modelo.candidatos
    assert _ids(respuesta) == [6]                       # el modelo eligió el segundo candidato

    # si el modelo no elige ninguno, deciden los vectores
    assert _ids(_agente(conn, tema="industria de sensores").preguntar("¿Y de la industria de sensores?")) == [1, 6]


def test_tema_ausente_del_programa_no_devuelve_eventos(conn):
    agente = _agente(conn, afines=[1, 2], tema="astronomía")
    respuesta = agente.preguntar("¿Hay algo de astronomía?")
    assert _ids(respuesta) == [] and "No encontré" in respuesta.texto
    assert agente.modelo.candidatos is None             # ningún vector se parece lo suficiente


def test_pregunta_general_responde_con_el_resumen(conn):
    agente = _agente(conn)
    respuesta = agente.preguntar("¿Qué tipos de actividad hay?")
    assert respuesta.eventos == [] and respuesta.texto == "Respuesta de prueba."
    # las cifras las muestra el programa; el modelo las recibe para redactar
    assert "Tipos de actividad (5): Concurso (2), Conferencia (1)" in respuesta.listado
    assert "Modalidad: presencial (4), virtual (2)" in respuesta.listado
    assert respuesta.listado in agente.modelo.datos_recibidos


def test_sin_resultados_no_llama_al_modelo(conn):
    agente = _agente(conn, actividad="Taller", fecha="2026-09-20")
    respuesta = agente.preguntar("¿Qué talleres hay el domingo?")
    assert respuesta.eventos == [] and agente.modelo.datos_recibidos is None
    assert respuesta.completa == "No encontré actividades con estas características: actividad Taller, día 2026-09-20."


def test_cada_pregunta_queda_registrada(conn):
    agente = _agente(conn, actividad="Concurso")
    respuesta = agente.preguntar("¿Qué concursos hay?")
    fila = conn.execute("SELECT sesion, pregunta, filtros, eventos, respuesta, modelo FROM agente_interacciones").fetchone()
    assert fila == (agente.sesion, "¿Qué concursos hay?", respuesta.consulta.como_dict(), [3, 4],
                    respuesta.completa, "modelo-falso")


def test_agente_avisa_si_el_pipeline_no_se_ha_ejecutado(url_bd):
    with psycopg.connect(url_bd, autocommit=True) as conexion:
        with pytest.raises(SinDatos):
            Agente(Almacen(conexion), ModeloFalso()).preparar()
