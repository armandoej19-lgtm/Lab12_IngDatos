"""Acceso a PostgreSQL: conexión, esquema y carga de tablas."""

import logging
import os
from pathlib import Path

import pandas as pd
import psycopg
from psycopg import sql

from . import config

log = logging.getLogger(__name__)

ESQUEMA = Path(__file__).with_name("esquema.sql")


def url_bd() -> str | None:
    """URL de conexión tomada de la variable de entorno, o None si no está definida."""
    return os.getenv(config.VAR_URL_BD) or None


def conectar(url: str | None = None, **opciones) -> psycopg.Connection:
    """Abre una conexión con la URL indicada o, si no se pasa, con la del entorno."""
    url = url or url_bd()
    if not url:
        raise RuntimeError(f"Falta la URL de PostgreSQL: define {config.VAR_URL_BD} (ver .env.example).")
    return psycopg.connect(url, **opciones)


def crear_esquema(conn: psycopg.Connection) -> None:
    """Crea las tablas que falten. No modifica las que ya existen."""
    conn.execute(ESQUEMA.read_text(encoding="utf-8"))


def _filas(df: pd.DataFrame) -> list[list]:
    """Filas con valores nativos de Python y None en lugar de los nulos de pandas."""
    return [[None if pd.isna(valor) else valor for valor in fila]
            for fila in df.astype(object).itertuples(index=False, name=None)]


def reemplazar_tabla(conn: psycopg.Connection, tabla: str, df: pd.DataFrame) -> None:
    """Sustituye el contenido de `tabla` por el de `df` y verifica cuántas filas quedaron.

    Las columnas de `df` deben llamarse igual que las de la tabla.
    """
    nombre = sql.Identifier(tabla)
    insertar = sql.SQL("INSERT INTO {} ({}) VALUES ({})").format(
        nombre,
        sql.SQL(", ").join(map(sql.Identifier, df.columns)),
        sql.SQL(", ").join(sql.Placeholder() * len(df.columns)),
    )
    with conn.cursor() as cur:
        cur.execute(sql.SQL("DELETE FROM {}").format(nombre))
        if len(df):
            cur.executemany(insertar, _filas(df))
        guardadas = cur.execute(sql.SQL("SELECT count(*) FROM {}").format(nombre)).fetchone()[0]

    if guardadas != len(df):
        raise IOError(f"Verificación fallida en la tabla {tabla}: "
                      f"se esperaban {len(df)} filas, hay {guardadas}")
    log.info("Guardado y verificado: tabla %s (%d registros)", tabla, len(df))
