"""Etapa 8: Almacenamiento.

Guarda los datos procesados, los registros rechazados, la bitácora de limpieza
y el reporte de validación en dos destinos:

- Archivos Excel en la carpeta de salida.
- PostgreSQL: tablas neutrales que puede consultar cualquier aplicación y de
  las que lee el agente. La carga es una sola transacción que reemplaza el
  contenido anterior: o se guardan todas las tablas o ninguna.

En ambos destinos se verifica la escritura releyendo lo guardado.
"""

import logging
from datetime import time
from pathlib import Path

import pandas as pd

from . import bd, config

log = logging.getLogger(__name__)


# --------------------------------------------------------------------------
# Archivos
# --------------------------------------------------------------------------
def _guardar_y_verificar(df: pd.DataFrame, ruta: Path) -> Path:
    df.to_excel(ruta, index=False)
    leido = pd.read_excel(ruta)
    if leido.shape != df.shape or list(leido.columns) != [str(c) for c in df.columns]:
        raise IOError(f"Verificación fallida en {ruta.name}: "
                      f"se esperaba {df.shape}, se leyó {leido.shape}")
    log.info("Guardado y verificado: %s (%d registros)", ruta.name, len(df))
    return ruta


def _guardar_archivos(df_procesados, df_rechazados, directorio: Path, df_bitacora, reportes) -> dict[str, Path]:
    rutas = {
        "procesados": _guardar_y_verificar(df_procesados, directorio / config.ARCHIVO_PROCESADOS),
        "rechazados": _guardar_y_verificar(df_rechazados, directorio / config.ARCHIVO_RECHAZADOS),
    }
    if df_bitacora is not None:
        rutas["bitacora"] = _guardar_y_verificar(df_bitacora, directorio / config.ARCHIVO_BITACORA)

    if reportes:
        ruta = directorio / config.ARCHIVO_REPORTE
        with pd.ExcelWriter(ruta) as writer:
            for hoja, reporte in reportes.items():
                reporte.to_excel(writer, sheet_name=hoja, index=False)
        if set(pd.ExcelFile(ruta).sheet_names) != set(reportes):
            raise IOError(f"Verificación fallida en {ruta.name}")
        log.info("Guardado y verificado: %s", ruta.name)
        rutas["reporte"] = ruta

    return rutas


# --------------------------------------------------------------------------
# PostgreSQL
# --------------------------------------------------------------------------
def _como_texto(df: pd.DataFrame, columnas: list[str]) -> pd.DataFrame:
    """Pasa `columnas` a texto conservando los nulos (valores originales de cualquier tipo)."""
    df = df.copy()
    df[columnas] = df[columnas].astype("string")
    return df


def _tablas(df_procesados, df_rechazados, df_bitacora, reportes) -> dict[str, pd.DataFrame]:
    """Adapta cada salida del pipeline a las columnas y tipos de su tabla."""
    eventos = df_procesados.copy()
    for col in ("fecha_inicio", "fecha_fin"):
        eventos[col] = eventos[col].dt.date
    for col in ("hora_inicio", "hora_fin"):
        eventos[col] = eventos[col].map(time.fromisoformat)

    # Se guardan solo las columnas del layout: las adicionales del Excel quedan en el archivo
    rechazados = df_rechazados.reindex(columns=["fila_excel", *config.COLUMNAS, "motivo_rechazo"])
    rechazados = _como_texto(rechazados, config.COLUMNAS).rename(columns=config.RENOMBRAR)

    if df_bitacora is None:
        df_bitacora = pd.DataFrame(columns=["fila_excel", "columna", "valor_original", "valor_limpio"])
    bitacora = _como_texto(df_bitacora, ["valor_original", "valor_limpio"])

    reporte = (reportes or {}).get(config.HOJA_REPORTE)
    if reporte is None:
        reporte = pd.DataFrame(columns=list(config.RENOMBRAR_REPORTE))
    reporte = reporte.rename(columns=config.RENOMBRAR_REPORTE)

    return {
        config.TABLA_EVENTOS: eventos,
        config.TABLA_RECHAZADOS: rechazados,
        config.TABLA_BITACORA: bitacora,
        config.TABLA_REPORTE: reporte,
    }


def _guardar_en_postgres(url_bd: str, tablas: dict[str, pd.DataFrame]) -> None:
    with bd.conectar(url_bd) as conn:  # confirma al salir; si algo falla, deshace todo
        bd.crear_esquema(conn)
        for tabla, df in tablas.items():
            bd.reemplazar_tabla(conn, tabla, df)
    log.info("Carga confirmada en PostgreSQL: %d tablas", len(tablas))


# --------------------------------------------------------------------------
# ETAPA 8: ALMACENAMIENTO
# --------------------------------------------------------------------------
def almacenamiento(df_procesados: pd.DataFrame, df_rechazados: pd.DataFrame,
                   directorio, df_bitacora: pd.DataFrame | None = None,
                   reportes: dict[str, pd.DataFrame] | None = None,
                   url_bd: str | None = None) -> dict[str, Path]:
    """Escribe las salidas en `directorio` y, si se indica `url_bd`, en PostgreSQL.

    Devuelve las rutas de los archivos verificados. El archivo y la tabla de
    rechazados se escriben aunque estén vacíos, para dejar constancia de que la
    etapa se ejecutó. Los archivos se escriben primero: si la base de datos
    falla, los resultados no se pierden.
    """
    directorio = Path(directorio)
    directorio.mkdir(parents=True, exist_ok=True)

    rutas = _guardar_archivos(df_procesados, df_rechazados, directorio, df_bitacora, reportes)
    if url_bd:
        _guardar_en_postgres(url_bd, _tablas(df_procesados, df_rechazados, df_bitacora, reportes))
    return rutas
