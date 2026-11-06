"""Pruebas de cada etapa con los datos sintéticos de scripts/generar_datos_muestra.py.

En los datos de muestra, las filas 0-5 son válidas (algunas tras limpieza)
y las filas 6-12 deben rechazarse.
"""

import pandas as pd
import pytest

from main import ejecutar
from pipeline import (almacenamiento, cargar_datos, limpieza, seleccion,
                      transformacion, validacion_de_informacion, validar_carga,
                      validar_layout)

FILAS_VALIDAS = 6
FILAS_RECHAZADAS = 7


# --- Etapas 1 y 2 ---------------------------------------------------------
def test_carga_y_validacion(df):
    assert validar_carga(df)
    assert df.shape == (FILAS_VALIDAS + FILAS_RECHAZADAS, 12)


def test_carga_rechaza_archivo_inexistente_o_no_excel(tmp_path):
    assert cargar_datos(tmp_path / "no_existe.xlsx") is None
    csv = tmp_path / "datos.csv"
    csv.write_text("a,b\n1,2\n")
    assert cargar_datos(csv) is None
    assert not validar_carga(None)
    assert not validar_carga(pd.DataFrame(columns=["a"]))


# --- Etapa 3 ----------------------------------------------------------------
def test_layout_valido(df, diccionario):
    assert validar_layout(df, diccionario).valido


def test_layout_detecta_columna_faltante_y_adicional(df, diccionario):
    resultado = validar_layout(df.drop(columns=["Tipo"]).assign(Extra=1), diccionario)
    assert resultado.columnas_faltantes == ["Tipo"]
    assert resultado.columnas_adicionales == ["Extra"]
    assert not resultado.estructura_valida


# --- Etapa 4 ----------------------------------------------------------------
def test_validacion_detecta_incumplimientos(df, diccionario):
    errores = validacion_de_informacion(df, diccionario).set_index("Validación")["Total Errores"]
    assert errores["duplicados"] == 1
    assert errores["fecha_fuera_de_rango"] == 1
    assert errores["hora_inicio_no_menor_a_fin"] == 1
    assert errores["virtual_sin_enlace"] == 1
    assert errores["enlace_invalido"] == 1
    assert errores["maestro_igual_a_ponente"] == 1


# --- Etapa 5 ----------------------------------------------------------------
def test_limpieza_corrige_sin_eliminar_registros(df):
    limpio, bitacora = limpieza(df)
    assert len(limpio) == len(df)
    assert limpio.loc[2, "Actividad"] == "Concurso"            # CUAUH -> Concurso
    assert limpio.loc[2, "Salón"] == "CUAUH A 108"             # se recorta la descripción
    assert limpio.loc[4, "Salón"] == "Cancha de Basketball"
    assert limpio.loc[3, "Título"] == "Concurso de Programación"
    assert limpio.loc[3, "Tipo"] == "presencial"
    assert pd.isna(limpio.loc[3, "Maestro de ceremonias"])    # era igual al ponente
    assert pd.isna(limpio.loc[4, "Enlace"])                    # enlace que no es de Teams
    assert pd.isna(limpio.loc[5, "Empresa / Institución"])     # solo espacios
    assert not bitacora.empty


# --- Etapa 6 ----------------------------------------------------------------
def test_seleccion_separa_aceptados_y_rechazados(df, diccionario):
    limpio, _ = limpieza(df)
    sel, rech = seleccion(limpio, diccionario, df_original=df)
    assert len(sel) == FILAS_VALIDAS
    assert len(rech) == FILAS_RECHAZADAS
    assert rech["motivo_rechazo"].str.len().gt(0).all()
    assert rech.loc[rech["fila_excel"] == 9, "motivo_rechazo"].item() == "fecha_fuera_de_rango"
    # los rechazados conservan el valor original del Excel
    assert "Hackatón" in rech["Actividad"].tolist()


def test_datos_limpios_cumplen_todas_las_reglas(df, diccionario):
    limpio, _ = limpieza(df)
    sel, _ = seleccion(limpio, diccionario)
    errores = validacion_de_informacion(sel, diccionario)
    assert errores["Total Errores"].sum() == 0


# --- Etapa 7 ----------------------------------------------------------------
def test_transformacion_aplica_esquema(df, diccionario):
    limpio, _ = limpieza(df)
    sel, _ = seleccion(limpio, diccionario)
    final = transformacion(sel)
    assert final.columns[0] == "id_evento"
    assert {"fecha_inicio", "hora_inicio", "salon", "duracion_horas", "num_dias", "dia_semana"} <= set(final.columns)
    assert pd.api.types.is_datetime64_any_dtype(final["fecha_inicio"])
    assert final["fecha_inicio"].is_monotonic_increasing
    primera = final.iloc[0]
    assert (primera["duracion_horas"], primera["dia_semana"]) == (2.0, "Domingo")
    assert pd.isna(primera["salon"])                            # virtual: '—' -> nulo


# --- Etapa 8 ----------------------------------------------------------------
def test_almacenamiento_guarda_y_verifica(tmp_path):
    procesados = pd.DataFrame({"a": [1, 2]})
    rechazados = pd.DataFrame(columns=["a", "motivo_rechazo"])  # vacío también se guarda
    rutas = almacenamiento(procesados, rechazados, tmp_path)
    assert rutas["procesados"].exists() and rutas["rechazados"].exists()
    assert len(pd.read_excel(rutas["procesados"])) == 2


# --- Pipeline completo -----------------------------------------------------
def test_pipeline_completo(rutas_muestra, tmp_path):
    datos, dicc = rutas_muestra
    assert ejecutar(datos, dicc, tmp_path / "out") == 0
    assert len(pd.read_excel(tmp_path / "out" / "datos_procesados.xlsx")) == FILAS_VALIDAS
    assert len(pd.read_excel(tmp_path / "out" / "registros_rechazados.xlsx")) == FILAS_RECHAZADAS


@pytest.mark.parametrize("columna", ["Actividad", "Fecha inicio", "Enlace"])
def test_pipeline_se_detiene_si_falta_una_columna(rutas_muestra, tmp_path, columna):
    datos, dicc = rutas_muestra
    roto = tmp_path / "roto.xlsx"
    pd.read_excel(datos).drop(columns=[columna]).to_excel(roto, index=False)
    assert ejecutar(roto, dicc, tmp_path / "out") == 1
