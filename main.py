"""Ejecuta el pipeline completo desde la línea de comandos.

Uso:
    python main.py                # archivos de data/raw y base de datos de DATABASE_URL
    python main.py --agente       # al terminar, abre el chat con el agente
    python main.py --datos data/sample/programa_muestra.xlsx \
                   --diccionario data/sample/diccionario_muestra.xlsx --sin-bd
"""

import argparse
import logging
import sys
from pathlib import Path

import psycopg
from dotenv import load_dotenv

from pipeline import (almacenamiento, cargar_datos, cargar_diccionario, limpieza,
                      seleccion, transformacion, validacion_de_informacion,
                      validar_carga, validar_layout)
from pipeline import bd, config

log = logging.getLogger("pipeline")

RAIZ = Path(__file__).resolve().parent


def configurar_logs(directorio: Path) -> None:
    directorio.mkdir(parents=True, exist_ok=True)
    formato = logging.Formatter("%(asctime)s | %(levelname)-7s | %(name)s | %(message)s", "%Y-%m-%d %H:%M:%S")
    raiz = logging.getLogger()
    raiz.setLevel(logging.INFO)
    raiz.handlers.clear()
    for handler in (logging.StreamHandler(sys.stdout),
                    logging.FileHandler(directorio / config.ARCHIVO_LOG, mode="w", encoding="utf-8")):
        handler.setFormatter(formato)
        raiz.addHandler(handler)


def ejecutar(ruta_datos, ruta_diccionario, directorio_salida, url_bd: str | None = None) -> int:
    """Corre las 8 etapas. Devuelve 0 si terminó bien y 1 si se detuvo.

    url_bd: URL de PostgreSQL donde la etapa 8 guarda los resultados. Sin ella
    solo se escriben los archivos.
    """
    salida = Path(directorio_salida)
    configurar_logs(salida)

    log.info("=== ETAPA 1: CARGA ===")
    df = cargar_datos(ruta_datos)
    diccionario = cargar_diccionario(ruta_diccionario)

    log.info("=== ETAPA 2: VALIDACIÓN DE CARGA ===")
    if not validar_carga(df):
        log.error("No se puede continuar con el pipeline.")
        return 1

    log.info("=== ETAPA 3: VALIDACIÓN DE LAYOUT ===")
    layout = validar_layout(df, diccionario)
    if not layout.estructura_valida:
        log.error("No se puede continuar: el archivo no tiene la estructura esperada.")
        return 1

    log.info("=== ETAPA 4: VALIDACIÓN DE INFORMACIÓN ===")
    validacion = validacion_de_informacion(df, diccionario)

    log.info("=== ETAPA 5: LIMPIEZA ===")
    df_limpio, bitacora = limpieza(df, validacion)
    # Se valida de nuevo lo ya limpio: lo que siga incumpliendo no tuvo corrección segura
    pendientes = validacion_de_informacion(df_limpio, diccionario)

    log.info("=== ETAPA 6: SELECCIÓN ===")
    df_sel, df_rechazados = seleccion(df_limpio, pendientes, df_original=df)

    log.info("=== ETAPA 7: TRANSFORMACIÓN ===")
    df_final = transformacion(df_sel)

    log.info("=== ETAPA 8: ALMACENAMIENTO ===")
    reporte = validacion.reporte.rename(columns={"Total Errores": "Antes de limpieza"})
    reporte["Después de limpieza"] = pendientes.reporte["Total Errores"]
    reportes = {config.HOJA_REPORTE: reporte, config.HOJA_INCUMPLIMIENTOS: validacion.incumplimientos}
    try:
        almacenamiento(df_final, df_rechazados, salida, df_bitacora=bitacora,
                       reportes=reportes, url_bd=url_bd)
    except psycopg.Error as error:
        log.error("No se pudo guardar en PostgreSQL (los archivos sí se escribieron): %s", error)
        return 1
    if not url_bd:
        log.warning("Sin base de datos: los resultados quedaron solo en archivos.")

    log.info("Pipeline terminado: %d procesados, %d rechazados. Salidas en '%s'",
             len(df_final), len(df_rechazados), salida)
    return 0


def _archivo_por_defecto(patron: str) -> Path:
    """El único archivo de data/raw que cumple el patrón."""
    carpeta = RAIZ / config.DIRECTORIO_DATOS
    encontrados = sorted(carpeta.glob(patron))
    if len(encontrados) != 1:
        raise FileNotFoundError(f"Se esperaba un archivo '{patron}' en {config.DIRECTORIO_DATOS} "
                                f"y hay {len(encontrados)}: indícalo con --datos y --diccionario.")
    return encontrados[0]


def main() -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(description="Pipeline de datos de la Semana de Ingeniería")
    parser.add_argument("--datos", help=f"Excel con el programa de actividades (por defecto: el de {config.DIRECTORIO_DATOS})")
    parser.add_argument("--diccionario", help=f"Excel con el diccionario de datos y catálogos (por defecto: el de {config.DIRECTORIO_DATOS})")
    parser.add_argument("--salida", default="output", help="Carpeta de salida (por defecto: output)")
    parser.add_argument("--bd", metavar="URL", help=f"URL de PostgreSQL (por defecto: variable {config.VAR_URL_BD})")
    parser.add_argument("--sin-bd", action="store_true", help="Guardar solo en archivos, sin PostgreSQL")
    parser.add_argument("--agente", nargs="?", const="", metavar="PREGUNTA",
                        help="Al terminar, abre el chat con el agente (o responde solo PREGUNTA)")
    args = parser.parse_args()

    con_agente = args.agente is not None
    if args.sin_bd and con_agente:
        parser.error("--agente necesita la base de datos: quita --sin-bd.")
    url_bd = None if args.sin_bd else args.bd or bd.url_bd()
    if not args.sin_bd and not url_bd:
        parser.error(f"Falta la conexión a PostgreSQL: define {config.VAR_URL_BD} (ver .env.example), "
                     "usa --bd o agrega --sin-bd.")
    try:
        datos = args.datos or _archivo_por_defecto(config.PATRON_PROGRAMA)
        diccionario = args.diccionario or _archivo_por_defecto(config.PATRON_DICCIONARIO)
    except FileNotFoundError as error:
        parser.error(str(error))

    codigo = ejecutar(datos, diccionario, args.salida, url_bd)
    if codigo == 0 and con_agente:
        from agente.__main__ import conversar  # se importa aquí: el pipeline no depende de Ollama
        codigo = conversar(url_bd, args.agente or None)
    return codigo


if __name__ == "__main__":
    sys.exit(main())
