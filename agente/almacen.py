"""Acceso del agente a PostgreSQL: catálogo, búsqueda de eventos, vectores e interacciones."""

from dataclasses import dataclass
from datetime import date, time
from uuid import UUID

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from .consulta import Consulta

COLUMNAS_EVENTO = ("id_evento, actividad, fecha_inicio, fecha_fin, hora_inicio, hora_fin, tipo, "
                   "salon, titulo, ponente, empresa_institucion, maestro_ceremonias, enlace")


class SinDatos(RuntimeError):
    """La base de datos todavía no tiene el programa cargado."""


@dataclass
class Catalogo:
    """Resumen del programa: lo que el agente necesita saber antes de buscar."""
    total: int
    actividades: dict[str, int]     # {actividad: eventos}, de mayor a menor
    modalidades: dict[str, int]
    dias: dict[date, int]           # un evento de varios días cuenta en cada uno
    hora_min: time
    hora_max: time


class Almacen:
    def __init__(self, conn: psycopg.Connection):
        self.conn = conn

    def _filas(self, consulta: str, parametros=None) -> list[dict]:
        with self.conn.cursor(row_factory=dict_row) as cur:
            return cur.execute(consulta, parametros).fetchall()

    # ----------------------------------------------------------------------
    # Programa
    # ----------------------------------------------------------------------
    def catalogo(self) -> Catalogo:
        try:
            resumen = self._filas("SELECT count(*) AS total, min(hora_inicio) AS hora_min, "
                                  "max(hora_fin) AS hora_max FROM eventos")[0]
        except psycopg.errors.UndefinedTable as error:
            raise SinDatos("La base de datos no tiene las tablas del programa: "
                           "ejecuta primero el pipeline (python main.py).") from error
        if not resumen["total"]:
            raise SinDatos("La tabla de eventos está vacía: ejecuta primero el pipeline (python main.py).")

        actividades = self._filas("SELECT actividad, count(*) AS n FROM eventos GROUP BY 1 ORDER BY n DESC, 1")
        modalidades = self._filas("SELECT tipo, count(*) AS n FROM eventos GROUP BY 1 ORDER BY n DESC, 1")
        dias = self._filas(
            "SELECT dia::date AS dia, count(*) AS n "
            "FROM eventos, generate_series(fecha_inicio::timestamp, fecha_fin::timestamp, interval '1 day') AS dia "
            "GROUP BY 1 ORDER BY 1")
        return Catalogo(
            total=resumen["total"],
            actividades={f["actividad"]: f["n"] for f in actividades},
            modalidades={f["tipo"]: f["n"] for f in modalidades},
            dias={f["dia"]: f["n"] for f in dias},
            hora_min=resumen["hora_min"],
            hora_max=resumen["hora_max"],
        )

    def buscar(self, consulta: Consulta) -> list[dict]:
        """Eventos que cumplen los filtros de la consulta, en orden cronológico.

        El tema no se filtra aquí: se resuelve después con los vectores.
        """
        condiciones, parametros = ["true"], {}
        if consulta.actividad:
            # por prefijo: "Conferencia" incluye también "Conferencia magistral"
            condiciones.append("lower(actividad) LIKE lower(%(actividad)s::text) || '%%'")
            parametros["actividad"] = consulta.actividad
        if consulta.modalidad:
            condiciones.append("tipo = %(modalidad)s")
            parametros["modalidad"] = consulta.modalidad
        if consulta.fecha:
            condiciones.append("%(fecha)s BETWEEN fecha_inicio AND fecha_fin")
            parametros["fecha"] = consulta.fecha

        desde, hasta = consulta.hora_desde, consulta.hora_hasta
        if desde and hasta and desde == hasta:      # "a las 10": en curso a esa hora
            condiciones.append("hora_inicio <= %(desde)s AND hora_fin > %(desde)s")
        elif desde and hasta:                       # "entre las 10 y las 12": coincide con el intervalo
            condiciones.append("hora_inicio < %(hasta)s AND hora_fin > %(desde)s")
        elif desde:                                 # "después de las 16": empieza a esa hora o más tarde
            condiciones.append("hora_inicio >= %(desde)s")
        elif hasta:                                 # "antes de las 10": empieza antes
            condiciones.append("hora_inicio < %(hasta)s")
        if desde:
            parametros["desde"] = desde
        if hasta:
            parametros["hasta"] = hasta

        return self._filas(f"SELECT {COLUMNAS_EVENTO} FROM eventos WHERE {' AND '.join(condiciones)} "
                           "ORDER BY fecha_inicio, hora_inicio, id_evento", parametros)

    # ----------------------------------------------------------------------
    # Vectores
    # ----------------------------------------------------------------------
    def estado_vectores(self, modelo: str) -> list[dict]:
        """Cada evento con el texto que tiene vectorizado (`contenido`; nulo si no hay vector de ese modelo)."""
        return self._filas(
            "SELECT e.id_evento, e.titulo, e.actividad, v.contenido FROM eventos e "
            "LEFT JOIN agente_vectores v ON v.id_evento = e.id_evento AND v.modelo = %s "
            "ORDER BY e.id_evento", [modelo])

    def guardar_vectores(self, modelo: str, filas: list[tuple[int, str, list[float]]]) -> None:
        """filas: (id_evento, texto vectorizado, vector)."""
        with self.conn.cursor() as cur:
            cur.executemany(
                "INSERT INTO agente_vectores (id_evento, modelo, contenido, embedding) "
                "VALUES (%s, %s, %s, %s) "
                "ON CONFLICT (id_evento) DO UPDATE SET modelo = EXCLUDED.modelo, "
                "contenido = EXCLUDED.contenido, embedding = EXCLUDED.embedding, creado_en = now()",
                [(id_evento, modelo, texto, vector) for id_evento, texto, vector in filas])

    def vectores(self, modelo: str, ids: list[int]) -> dict[int, list[float]]:
        filas = self._filas("SELECT id_evento, embedding FROM agente_vectores "
                            "WHERE modelo = %s AND id_evento = ANY(%s::integer[])", [modelo, ids])
        return {f["id_evento"]: f["embedding"] for f in filas}

    # ----------------------------------------------------------------------
    # Interacciones
    # ----------------------------------------------------------------------
    def registrar(self, sesion: UUID, pregunta: str, consulta: Consulta, eventos: list[int],
                  respuesta: str, modelo: str, duracion_ms: int) -> None:
        self.conn.execute(
            "INSERT INTO agente_interacciones (sesion, pregunta, filtros, eventos, respuesta, modelo, duracion_ms) "
            "VALUES (%s, %s, %s, %s::integer[], %s, %s, %s)",
            [sesion, pregunta, Jsonb(consulta.como_dict()), eventos, respuesta, modelo, duracion_ms])
