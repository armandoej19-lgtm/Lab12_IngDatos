"""Genera datos SINTÉTICOS de muestra en data/sample/.

Sirven para probar el pipeline sin los archivos reales. Imitan la estructura
del programa y del diccionario, e incluyen a propósito casos sucios y casos
que deben rechazarse.

Uso:
    python scripts/generar_datos_muestra.py
"""

from pathlib import Path

import pandas as pd

COLUMNAS = [
    "Actividad", "Fecha inicio", "Fecha fin", "Hora inicio", "Hora fin",
    "Tipo", "Salón", "Título", "Ponente", "Empresa / Institución",
    "Maestro de ceremonias", "Enlace",
]
TEAMS = "https://teams.microsoft.com/meet/000000"


def programa_muestra() -> pd.DataFrame:
    filas = [
        # --- registros válidos ---
        ["Conferencia", "2026-09-20", "2026-09-20", "10:00", "12:00", "virtual", "—",
         "Introducción a sensores", "Ponente A", "UACJ", "Maestro A", TEAMS],
        ["Curso", "2026-09-21", "2026-09-25", "09:00", "13:00", "presencial", "W 102",
         "Diseño de circuitos", "Ponente B", "UACJ", "Maestro B", None],
        # --- sucios pero corregibles en la limpieza ---
        ["CUAUH", "2026-09-21", "2026-09-21", "09:00", "11:00", "presencial", "CUAUH A 108 - Audiovisual",
         "Inauguración", "Ponente C", "UACJ", "Maestro C", None],
        ["Concurso", "2026-09-22", "2026-09-22", "15:00", "17:00", "Presencial", "B1 101",
         "Concurso de  Programación  ", "Ponente D", "UACJ", "Ponente D", None],
        ["Taller", "2026-09-23", "2026-09-23", "16:00", "18:00", "presencial", "CANCHA DE BASQUET/FUTBOLITO",
         "Torneo 3x3", None, "UACJ", "Maestro E", "https://zoom.us/j/123"],
        ["Ponencia", "2026-09-24", "2026-09-24", "11:00", "12:00", "virtual", "—",
         "Industria 4.0", "Ponente F", "   ", None, TEAMS],
        # --- deben rechazarse ---
        ["Curso", "2026-09-21", "2026-09-25", "09:00", "13:00", "presencial", "W 102",
         "Diseño de circuitos", "Ponente B", "UACJ", "Maestro B", None],          # duplicado
        ["Taller", "2026-09-28", "2026-09-28", "10:00", "12:00", "presencial", "W 102",
         "Taller fuera de fecha", "Ponente G", "UACJ", "Maestro G", None],        # fecha fuera de rango
        ["Conferencia", "2026-09-22", "2026-09-22", "15:00", "14:00", "virtual", "—",
         "Hora invertida", "Ponente H", "UACJ", "Maestro H", TEAMS],              # hora inicio >= fin
        ["Conferencia", "2026-09-23", "2026-09-23", "10:00", "11:00", "virtual", "—",
         "Virtual sin enlace", "Ponente I", "UACJ", "Maestro I", None],           # virtual sin enlace
        ["Hackatón", "2026-09-24", "2026-09-24", "08:00", "20:00", "presencial", "B1 101",
         "Actividad fuera de catálogo", "Ponente J", "UACJ", "Maestro J", None],  # actividad no permitida
        ["Curso", "2026-09-25", "2026-09-25", "07:00", "09:00", "presencial", "Salón inexistente",
         "Muy temprano", "Ponente K", "UACJ", "Maestro K", None],                 # hora y salón inválidos
        ["Conferencia", "2026-09-25", "2026-09-25", "10:00", "11:00", "híbrido", "W 102",
         None, "Ponente L", "UACJ", "Maestro L", None],                           # tipo inválido y sin título
    ]
    return pd.DataFrame(filas, columns=COLUMNAS)


def diccionario_muestra() -> dict[str, pd.DataFrame]:
    tipos = ["str", "date", "date", "time", "time", "str", "str", "str", "str", "str", "str", "str"]
    return {
        "Diccionario": pd.DataFrame({"Campo": COLUMNAS, "Tipo esperado": tipos}),
        "Catalogo Actividad": pd.DataFrame({"Actividad permitida": [
            "Conferencia", "Curso", "Concurso", "Ponencia", "Taller", "Deportiva", "Cultural"]}),
        "Catálogo Salon": pd.DataFrame({"Lugar": [
            "W 102", "B1 101", "CUAUH A 108", "Cancha de Basketball", "J2 103", "Plaza Cultural"]}),
    }


def escribir(directorio: Path) -> tuple[Path, Path]:
    directorio.mkdir(parents=True, exist_ok=True)
    ruta_datos = directorio / "programa_muestra.xlsx"
    ruta_dicc = directorio / "diccionario_muestra.xlsx"
    programa_muestra().to_excel(ruta_datos, index=False)
    with pd.ExcelWriter(ruta_dicc) as writer:
        for hoja, df in diccionario_muestra().items():
            df.to_excel(writer, sheet_name=hoja, index=False)
    return ruta_datos, ruta_dicc


if __name__ == "__main__":
    raiz = Path(__file__).resolve().parents[1]
    for ruta in escribir(raiz / "data" / "sample"):
        print("Generado:", ruta.relative_to(raiz))
