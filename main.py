"""Ejecuta el pipeline completo desde la línea de comandos.

Uso:
    python main.py --datos data/raw/Programa_32IIT_21-09.xlsx \
                   --diccionario data/raw/Diccionario_Datos_Semana_Ingenieria.xlsx \
                   --salida output
"""

import argparse
import logging
import sys
from pathlib import Path

from pipeline import (almacenamiento, cargar_datos, cargar_diccionario, limpieza,
                      seleccion, transformacion, validacion_de_informacion,
                      validar_carga, validar_layout)
from pipeline import config

log = logging.getLogger("pipeline")


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


def ejecutar(ruta_datos, ruta_diccionario, directorio_salida) -> int:
    """Corre las 8 etapas. Devuelve 0 si terminó bien y 1 si se detuvo."""
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
    reporte_antes = validacion_de_informacion(df, diccionario)

    log.info("=== ETAPA 5: LIMPIEZA ===")
    df_limpio, bitacora = limpieza(df)
    reporte_despues = validacion_de_informacion(df_limpio, diccionario)

    log.info("=== ETAPA 6: SELECCIÓN ===")
    df_sel, df_rechazados = seleccion(df_limpio, diccionario, df_original=df)

    log.info("=== ETAPA 7: TRANSFORMACIÓN ===")
    df_final = transformacion(df_sel)

    log.info("=== ETAPA 8: ALMACENAMIENTO ===")
    reporte = reporte_antes.rename(columns={"Total Errores": "Antes de limpieza"})
    reporte["Después de limpieza"] = reporte_despues["Total Errores"]
    almacenamiento(df_final, df_rechazados, salida, df_bitacora=bitacora,
                   reportes={"validacion": reporte})

    log.info("Pipeline terminado: %d procesados, %d rechazados. Salidas en '%s'",
             len(df_final), len(df_rechazados), salida)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Pipeline de datos de la Semana de Ingeniería")
    parser.add_argument("--datos", required=True, help="Excel con el programa de actividades")
    parser.add_argument("--diccionario", required=True, help="Excel con el diccionario de datos y catálogos")
    parser.add_argument("--salida", default="output", help="Carpeta de salida (por defecto: output)")
    args = parser.parse_args()
    return ejecutar(args.datos, args.diccionario, args.salida)


if __name__ == "__main__":
    sys.exit(main())
