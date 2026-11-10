"""Pruebas de la carga en PostgreSQL (etapa 8).

Las que usan la fixture `url_bd` se omiten si no hay base de datos disponible.
"""

from datetime import date, time
from decimal import Decimal
from uuid import uuid4

import pandas as pd
import psycopg

from main import ejecutar

FILAS_VALIDAS = 6
FILAS_RECHAZADAS = 7


def _contar(conn, tabla: str) -> int:
    return conn.execute(f"SELECT count(*) FROM {tabla}").fetchone()[0]


def test_pipeline_guarda_todas_las_salidas(rutas_muestra, tmp_path, url_bd):
    datos, dicc = rutas_muestra
    assert ejecutar(datos, dicc, tmp_path / "out", url_bd) == 0

    with psycopg.connect(url_bd) as conn:
        assert _contar(conn, "eventos") == FILAS_VALIDAS
        assert _contar(conn, "registros_rechazados") == FILAS_RECHAZADAS
        assert _contar(conn, "bitacora_limpieza") == len(pd.read_excel(tmp_path / "out" / "bitacora_limpieza.xlsx"))
        assert _contar(conn, "reporte_validacion") == len(pd.read_excel(tmp_path / "out" / "reporte_validacion.xlsx"))

        # tipos nativos: fecha, hora, numérico y nulo en el salón de un evento virtual
        primero = conn.execute("SELECT actividad, fecha_inicio, hora_inicio, hora_fin, salon, duracion_horas, dia_semana "
                               "FROM eventos ORDER BY id_evento LIMIT 1").fetchone()
        assert primero == ("Conferencia", date(2026, 9, 20), time(10), time(12), None, Decimal("2.00"), "Domingo")

        # los rechazados conservan el valor original y su motivo
        rechazado = conn.execute("SELECT actividad, fecha_inicio, motivo_rechazo FROM registros_rechazados "
                                 "WHERE fila_excel = 9").fetchone()
        assert rechazado == ("Taller", "2026-09-28", "fecha_fuera_de_rango")

        duplicados = conn.execute("SELECT antes_de_limpieza FROM reporte_validacion "
                                  "WHERE validacion = 'duplicados'").fetchone()
        assert duplicados == (1,)


def test_recarga_reemplaza_los_datos_y_conserva_las_interacciones(rutas_muestra, tmp_path, url_bd):
    datos, dicc = rutas_muestra
    assert ejecutar(datos, dicc, tmp_path / "out", url_bd) == 0

    with psycopg.connect(url_bd) as conn:
        conn.execute("INSERT INTO agente_vectores (id_evento, modelo, contenido, embedding) "
                     "VALUES (1, 'modelo', 'texto', '{0.1, 0.2}')")
        conn.execute("INSERT INTO agente_interacciones (sesion, pregunta, filtros, eventos, respuesta, modelo, duracion_ms) "
                     "VALUES (%s, 'pregunta', '{}', '{1}', 'respuesta', 'modelo', 10)", [uuid4()])

    assert ejecutar(datos, dicc, tmp_path / "out", url_bd) == 0

    with psycopg.connect(url_bd) as conn:
        assert _contar(conn, "eventos") == FILAS_VALIDAS           # no se duplican
        assert _contar(conn, "registros_rechazados") == FILAS_RECHAZADAS
        assert _contar(conn, "agente_vectores") == 0               # se borran con su evento
        assert _contar(conn, "agente_interacciones") == 1          # el historial se conserva


def test_pipeline_devuelve_1_si_no_puede_conectarse(rutas_muestra, tmp_path):
    datos, dicc = rutas_muestra
    sin_servidor = "postgresql://nadie@127.0.0.1:1/nada?connect_timeout=2"
    assert ejecutar(datos, dicc, tmp_path / "out", sin_servidor) == 1
    # los archivos se escriben antes: el resultado no se pierde
    assert len(pd.read_excel(tmp_path / "out" / "datos_procesados.xlsx")) == FILAS_VALIDAS
