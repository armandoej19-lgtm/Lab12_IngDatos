'''

IMPORTS & LIBRARIES

'''

import pandas as pd


from pathlib import Path

'''

DICIONARY OF COLS

'''

cols_n_dtypes = {

    # define all columns before read the xlsx {col:dtype}
    "actividad":"str",

    "fecha_inicio":{"date":"YYYY-MM-DD"},

    "fecha_fin":{"date":"YYYY-MM-DD"},

    "hora_inicio":{"time":"%H:%M"},

    "hora_fin":{"time":"%H:%M"},

    "tipo":"str",

    "salon":"str",

    "titulo":"str",

    "ponente":"str",

    "empresa/institucion":"str",

    "maestro de ceremonias":"str",

    "enlace":{"str":"https\://"}

}



'''

PATHS & VARS

'''

BK_PATH =     '/'  # route

LOGS =        '/'  # route (log: tracking)

DEST =        '/'  #





'''

STAGE 1: LOAD

'''

def cargar_datos():

    try:
        # Busca automáticamente el Excel de entrada junto al archivo .py.
        carpeta_script = Path(__file__).resolve().parent
        nombre_diccionario = "Diccionario_Datos_Semana_Ingenieria.xlsx"

        archivos_excel = [
            ruta for ruta in carpeta_script.iterdir()
            if ruta.is_file()
            and ruta.suffix.lower() in [".xlsx", ".xls"]
            and ruta.name.lower() != nombre_diccionario.lower()
            and "procesado" not in ruta.stem.lower()
            and "rechazado" not in ruta.stem.lower()
        ]

        if not archivos_excel:
            raise FileNotFoundError(
                f"No se encontró un Excel de datos en {carpeta_script}. "
                "Coloca el archivo de entrada junto al .py."
            )

        if len(archivos_excel) > 1:
            nombres = "\\n".join(f"- {ruta.name}" for ruta in archivos_excel)
            raise ValueError(
                "Hay varios Excel posibles como entrada:\\n"
                f"{nombres}\\n"
                "Deja únicamente el Excel de datos en esa carpeta para "
                "que el pipeline pueda elegirlo automáticamente."
            )

        archivo = archivos_excel[0]
        df = pd.read_excel(archivo)

        print("Archivo cargado automáticamente:", archivo.name)
        return df

    except Exception as error:
        print("Error durante la carga:", error)
        return None


df = cargar_datos()



'''

STAGE 2: LOAD VALIDATION

'''

def validar_carga(df):

    try:

        if df is None:

            print("Error: no se pudieron cargar los datos.")

            return False



        if df.empty:

            print("Error: el archivo no contiene registros.")

            return False



        if len(df.columns) == 0:

            print("Error: el archivo no contiene columnas.")

            return False



        print("Validación de carga exitosa.")

        print("Número de registros:", df.shape[0])

        print("Número de columnas:", df.shape[1])



        print("\nPrimeros registros:")

        print(df.head())



        return True



    except Exception as error:

        print("Error durante la validación:", error)

        return False





'''

PIPELINE EXECUTION

'''

df = cargar_datos()



if validar_carga(df):

    print("La carga está lista para continuar con la siguiente etapa.")

else:

    print("No se puede continuar con el pipeline.")





#----------------------------------------------------------------------------
# ETAPA 3: VALIDACION DE LAYOUT
#----------------------------------------------------------------------------
def validar_layout(df):

    try:

        # 1.- Verificar que el DataFrame exista
        if df is None:

            print("Error: no existen datos para validar.")

            return False



        # 2.- Cargar diccionario de datos
        diccionario = pd.read_excel(

            Path(__file__).resolve().parent / "Diccionario_Datos_Semana_Ingenieria.xlsx",

            sheet_name="Diccionario"

        )



        # 3.- Obtener columnas esperadas y tipos
        columnas_esperadas = diccionario["Campo"].tolist()

        tipos_esperados = dict(zip(

            diccionario["Campo"],

            diccionario["Tipo esperado"]

        ))



        # 4.- Obtener columnas reales
        columnas_reales = df.columns.tolist()



        # 5.- Validar nombres de columnas
        columnas_faltantes = [

            col for col in columnas_esperadas

            if col not in columnas_reales

        ]



        columnas_adicionales = [

            col for col in columnas_reales

            if col not in columnas_esperadas

        ]



        # 6.- Validar tipos de datos y formatos
        errores_tipos = {}



        for col in columnas_esperadas:



            # No validar columnas que no existen
            if col not in columnas_reales:

                continue



            tipo = tipos_esperados[col]

            serie = df[col]



            # Ignorar valores nulos para la validación de tipo
            valores = serie.dropna()



            # Validación de texto
            if tipo == "str":



                incorrectos = valores[

                    ~valores.map(lambda x: isinstance(x, str))

                ]



            # Validación de fechas
            elif tipo == "date":



                fechas = pd.to_datetime(

                    valores,

                    format="%Y-%m-%d",

                    errors="coerce"

                )



                incorrectos = valores[

                    fechas.isna()

                ]



            # Validación de horas
            elif tipo == "time":



                def hora_valida(valor):

                    try:

                        if isinstance(valor, str):

                            return pd.to_datetime(

                                valor,

                                format="%H:%M",

                                errors="raise"

                            ) is not None



                        if hasattr(valor, "strftime"):

                            return valor.strftime("%H:%M") == valor.strftime("%H:%M")



                        return False



                    except:

                        return False



                incorrectos = valores[

                    ~valores.map(hora_valida)

                ]



            else:

                incorrectos = pd.Series(dtype=object)



            # Guardar errores encontrados
            if len(incorrectos) > 0:

                errores_tipos[col] = len(incorrectos)



        # 7.- Generar reporte
        print("\n========== VALIDACION DE LAYOUT ==========")



        print("\nColumnas esperadas:", len(columnas_esperadas))

        print("Columnas encontradas:", len(columnas_reales))



        # Reportar columnas faltantes
        print("\n--- Columnas faltantes ---")

        if columnas_faltantes:

            for col in columnas_faltantes:

                print("ERROR:", col)

        else:

            print("Ninguna")



        # Reportar columnas adicionales
        print("\n--- Columnas adicionales ---")

        if columnas_adicionales:

            for col in columnas_adicionales:

                print("ADVERTENCIA:", col)

        else:

            print("Ninguna")



        # Reportar incompatibilidades de tipos
        print("\n--- Errores de tipos/formato ---")

        if errores_tipos:

            for col, cantidad in errores_tipos.items():

                print(f"ERROR: {col} -> {cantidad} valores incorrectos")

        else:

            print("Ninguno")



        # 8.- Resultado final
        layout_valido = (

            len(columnas_faltantes) == 0

            and len(errores_tipos) == 0

        )



        if layout_valido:

            print("\nValidación de layout exitosa.")

            return True

        else:

            print("\nError: layout inválido.")

            return False



    except Exception as error:

        print("Error durante la validación del layout:", error)

        return False



def validacion_de_informacion(df):



    def fechas_invalidas(col):

      fechas_invalidas_fecha_inicio = pd.to_datetime(

      df[col], format="%Y-%m-%d", errors='coerce'

      ).isna()



      return fechas_invalidas_fecha_inicio



    def rango_fecha(col):

      fecha_inicio_valido = pd.to_datetime('2026-09-20')

      fecha_fin_valido = pd.to_datetime('2026-09-25')



      fechas_df = pd.to_datetime(df[col], format='mixed', errors='coerce')

      fechas_fuera_de_rango = fechas_df.notna() & ((fechas_df < fecha_inicio_valido) | (fechas_df > fecha_fin_valido))

      return fechas_fuera_de_rango



    def horas_validacion(col):

      return pd.to_datetime(

        df[col], format="%H:%M", errors='coerce'

    ).isna()



    def rango_horas(col):

      hora_inicio_rango1 = pd.to_datetime('08:00')

      hora_fin_rango2 = pd.to_datetime('22:00')



      horas_df = pd.to_datetime(df[col], format='mixed', errors='coerce')

      horas_fuera_de_rango = horas_df.notna() & ((horas_df < hora_inicio_rango1) | (horas_df > hora_fin_rango2))

      return horas_fuera_de_rango







    #-------------------------------------------------------------------------------------
    errores = {}

    #1.- Hay valores duplicados
    errores['Cantidad_duplicados'] = df.duplicated().sum()



    #2.- hay valores nulos
    columnas_nulos = [col for col in df.columns if col not in ["Enlace", "Ponente", "Empresa / Institución", "Maestro de ceremonias"]]

    errores['Cantidad_nulos'] = df[columnas_nulos].isnull().sum().sum()



    #3.- hay valores vacios
    errores["Vacios"] = sum(

        (df[col].astype(str).str.strip() == "").sum() for col in df.columns

    )



    #4.- verificar catálogo permitido
    cat_actividades = pd.read_excel(

        "Diccionario_Datos_Semana_Ingenieria.xlsx", sheet_name="Catalogo Actividad"

    )

    lista_actividades = cat_actividades["Actividad permitida"].str.lower().tolist()

    errores['actividades'] = (~df['Actividad'].str.lower().isin(lista_actividades)).sum()



    #5.- verificar formato de fechas y hora
    #-- fechas
    errores['formato_fecha'] = fechas_invalidas('Fecha inicio').sum() + fechas_invalidas('Fecha fin').sum()



    #-----------------
    #-- horas
    errores['formato_hora'] = horas_validacion('Hora inicio').sum() +  horas_validacion('Hora fin').sum()



    #6.- verificar formato de enlace
    patron_teams = r'^https\://(events\\.)?teams\\.microsoft\\.com/.\*$'



    enlaces_invalidos = df['Enlace'].notna() & ~df['Enlace'].astype(str).str.match(patron_teams)

    errores['enlaces_invalidos'] =   enlaces_invalidos.sum()



    es_virtual = df['Tipo'].astype(str).str.lower().str.strip() == 'virtual'

    enlace_vacio =df['Enlace'].isna() | df['Enlace'].astype(str).str.strip() == ''

    enlace_virtual_vacio =  es_virtual & enlace_vacio

    errores['enlaces_vacios'] =   enlace_virtual_vacio.sum()





    #7.- validación de rangos de fecha y hora
    # ------------------- fechas
    errores['fecha_rango'] = rango_fecha('Fecha inicio').sum() + rango_fecha('Fecha fin').sum()

    # ------------------- horas
    errores['horas_rango'] = rango_horas('Hora inicio').sum() + rango_horas('Hora fin').sum()





    # 8-fecha inicio<= fecha fin & Hora inicio < Hora fin
    f_inicio = pd.to_datetime(df["Fecha inicio"], errors="coerce")

    f_fin = pd.to_datetime(df["Fecha fin"], errors="coerce")

    errores["error_orden_fechas"] = (f_inicio > f_fin).sum()



    h_inicio = pd.to_datetime(df["Hora inicio"], format="%H:%M", errors="coerce")

    h_fin = pd.to_datetime(df["Hora fin"], format="%H:%M", errors="coerce")

    errores["error_orden_horas"] = (h_inicio >= h_fin).sum()



    #9.- Tipo (presencial o virtual)
    tipo_permitido = ['presencial', 'virtual']

    errores['Tipo'] =  (~df["Tipo"].astype(str).str.lower().str.strip().isin(tipo_permitido)).sum()





    #10.- Clases
    clases = pd.read_excel(Path(__file__).resolve().parent / 'Diccionario_Datos_Semana_Ingenieria.xlsx', sheet_name='Catálogo Salon')

    lista_salones = clases['Lugar'].astype(str).str.strip().tolist()



    salon_valido = df["Salón"].notna() & (df["Salón"].astype(str).str.strip() != "") & (df["Salón"].astype(str).str.strip() != "—")



    salon_no_en_catalogo = salon_valido & (~df["Salón"].astype(str).str.strip().isin(lista_salones))



    errores['clases_salon'] = salon_no_en_catalogo.sum()



    #11.- reglas del salón
    es_presencial = df["Tipo"].astype(str).str.strip().str.lower() == "presencial"

    salon_vacio = (

      df["Salón"].isna()

      | (df["Salón"].astype(str).str.strip() == "")

      | (df["Salón"].astype(str).str.strip().str.lower() == "nan")

  )

    errores['salon_presencial'] = (es_presencial & salon_vacio).sum()



    #12.- titulo
    titulo_vacio = (df['Título'].isna() | df['Título'].astype(str).str.strip() == '').sum()

    errores['titulo_vacio'] = titulo_vacio



    #13.- Ponente
    maestro_txt = df['Maestro de ceremonias'].astype(str).str.lower().str.strip()

    ponente_txt = df['Ponente'].astype(str).str.strip().str.lower()



    coincidencia_ponentes = (

        (ponente_txt != "")

        & (ponente_txt != "nan")

        & (maestro_txt != "")

        & (maestro_txt != "nan")

        & (ponente_txt == maestro_txt)

    )



    errores['maestro_igual_ponente'] = coincidencia_ponentes.sum()





    #14.- Empresa / institución
    errores['empresas_vacias'] =  (df['Empresa / Institución'].astype(str).str.strip() == '').sum()



    return errores







resultados = validacion_de_informacion(df)

df_errores = pd.DataFrame(list(resultados.items()), columns=['Validación', 'Total Errores'])



print(df_errores)



def limpieza(df, errores):

  import numpy as np

  lista_errores_criticos = []

  lista_filas_rellenar = []

  errores = errores.set_index('Validación')['Total Errores'].to_dict()

  # Eliminar duplicados
  if errores['Cantidad_duplicados'] > 0:

    df = df.drop_duplicates()



  # Asignación de filas con nulos automáticamente
  columnas_si_nulos = ['Maestro de ceremonias', 'Empresa / Institución', 'Ponente']



  if errores['Cantidad_nulos'] > 0:

    columnas_no_deben_llevar_nulos = [col for col in df.columns if col not in columnas_si_nulos]

    for col in columnas_no_deben_llevar_nulos:

      columna_tipo = df[col].dtype

      if columna_tipo == 'object':

        filas_a_rellenar= df[df[col].isna()].copy()

        if len(filas_a_rellenar) > 0:

          lista_filas_rellenar.append(filas_a_rellenar)



        df[col] = df[col].fillna('Por asignar')

      else:

        filas_con_errores = df[df[col].isna()].copy()



        if len(filas_con_errores) > 0:

          lista_errores_criticos.append(filas_con_errores)



          df = df.dropna(subset=[col])



  # limpiando valores vacios
  if errores['Vacios'] > 0:

    columnas = df.columns

    df = df.replace(r'^\s\*$', np.nan, regex=True)

    columnas_no_deben_llevar_nulos = [col for col in df.columns if col not in columnas_si_nulos]



    for col in columnas_no_deben_llevar_nulos:

      columna_tipo = df[col].dtype

      if columna_tipo == 'object':

        filas_a_rellenar = df[df[col].isna()].copy()

        if len(filas_a_rellenar) > 0:

          lista_filas_rellenar.append(filas_a_rellenar)

        df[col] = df[col].fillna('Por asignar')



      else:

        filas_con_errores = df[df[col].isna()].copy()

        if len(filas_con_errores) > 0:

          lista_errores_criticos.append(filas_con_errores)



        df= df.dropna(subset=[col])



  #----- limpieza en actividades
  df['Actividad'] = df['Actividad'].replace(

      {'FOSEEI': 'Ponencia', 'CUAUH': 'Concurso', 'CENALTEC': 'Curso'}

  )



  # Formato de fecha y hora
  columnas_fecha = ['Fecha inicio', 'Fecha fin']



  if errores['formato_fecha'] > 0:

    for col in columnas_fecha:

      fechas_convertidas = pd.to_datetime(df[col], format='mixed', errors='coerce')

      fechas_invalidas = fechas_convertidas.isna()

      filas_con_errores = df[fechas_invalidas].copy()

      if len(filas_con_errores) > 0:

        lista_errores_criticos.append(filas_con_errores)

        df =df.dropna(subset=[col])

      df[col] = fechas_convertidas



  columnas_hora = ['Hora inicio', 'Hora fin']

  if errores['formato_hora'] > 0:

    for col in columnas_hora:

      horas_convertidas = pd.to_datetime(df[col], format = 'mixed', errors='coerce')

      horas_invalidas = horas_convertidas.isna()

      filas_con_errores = df[horas_invalidas].copy()



      if len(filas_con_errores)> 0:

        lista_errores_criticos.append(filas_con_errores)

        df = df.dropna(subset=[col])

        horas_convertidas = pd.to_datetime(df[col], format='mixed', errors='coerce')

      df[col] = horas_convertidas.dt.time



  #----- limpieza en enlace inválido
  patron_teams = r'^https\://(events\\.)?teams\\.microsoft\\.com/.\*$'

  enlaces_invalidos = df['Enlace'].notna() & ~df['Enlace'].astype(str).str.match(patron_teams)

  df.loc[enlaces_invalidos, 'Enlace'] = None





  #Enlaces vacios
  if errores['enlaces_vacios'] > 0:

    df['Enlace'] = df['Enlace'].replace(r'^\s\*$', np.nan, regex=True)



    es_presencial = df['Tipo'].astype(str).str.lower().str.strip() == 'presencial'

    enlace_vacio = df['Enlace'].isna()

    enlaces_incorrectos = (~es_presencial) & enlace_vacio

    filas_errores = df[enlaces_incorrectos]

    if len(filas_errores) > 0:

      lista_filas_rellenar.append(filas_errores)

    df.loc[enlaces_incorrectos, 'Enlace'] = 'Enlace por confirmar'





  # fecha_rango y horas_rango
  if errores['fecha_rango'] > 0:



    fecha_inicio_valido = pd.to_datetime('2026-09-20')

    fecha_fin_valido = pd.to_datetime('2026-09-25')



    fechas_df_inicio = pd.to_datetime(df['Fecha inicio'], format='mixed', errors='coerce')

    fechas_df_fin = pd.to_datetime(df['Fecha fin'], format='mixed', errors='coerce')

    fuera_rango_inicio = fechas_df_inicio.notna() & ((fechas_df_inicio < fecha_inicio_valido) | (fechas_df_inicio > fecha_fin_valido))

    fuera_rango_fin = fechas_df_fin.notna() & ((fechas_df_fin < fecha_inicio_valido) | (fechas_df_fin > fecha_fin_valido))

    fechas_error_rango = fuera_rango_inicio | fuera_rango_fin



    filas_con_errores = df[fechas_error_rango].copy()



    if len(filas_con_errores)> 0:

      lista_errores_criticos.append(filas_con_errores)



      df = df[~fechas_error_rango].copy()



  # -------------------------
  if errores['horas_rango'] > 0:

    hora_inicio_valido = pd.to_datetime('08:00').time()

    hora_fin_valido = pd.to_datetime('22:00').time()



    horas_inicio_dt = pd.to_datetime(df['Hora inicio'], format='mixed', errors='coerce')

    horas_fin_dt = pd.to_datetime(df['Hora fin'], format='mixed', errors='coerce')



    horas_inicio_time = horas_inicio_dt.dt.time

    horas_fin_time = horas_fin_dt.dt.time



    inicio_fuera_de_rango = horas_inicio_time.notna() & ((horas_inicio_time < hora_inicio_valido) | (horas_inicio_time > hora_fin_valido))

    fin_fuera_de_rango = horas_fin_time.notna() & ((horas_fin_time < hora_inicio_valido) | (horas_fin_time > hora_fin_valido))



    horas_error_rango = inicio_fuera_de_rango | fin_fuera_de_rango



    filas_error_rango = df[horas_error_rango].copy()



    if len(filas_error_rango) > 0:

        lista_errores_criticos.append(filas_error_rango)

        df = df[~horas_error_rango].copy()



  # la lógica de inicio < fin en fechas y hora
  if errores['error_orden_fechas'] > 0:

    f_inicio = pd.to_datetime(df["Fecha inicio"], errors="coerce")

    f_fin = pd.to_datetime(df["Fecha fin"], errors="coerce")



    ambas_validas = f_inicio.notna() & f_fin.notna()

    fechas_logica_incorrecta = ambas_validas & (f_inicio > f_fin)

    filas_error = df[fechas_logica_incorrecta].copy()



    if len(filas_error) > 0:

      lista_errores_criticos.append(filas_error)



    df = df[~fechas_logica_incorrecta].copy()

  # -------------------
  if errores['error_orden_horas'] > 0:

    h_inicio = pd.to_datetime(df["Hora inicio"], format="mixed", errors="coerce")

    h_fin = pd.to_datetime(df["Hora fin"], format="mixed", errors="coerce")



    ambas_validas = h_inicio.notna() & h_fin.notna()

    horas_invalidas = ambas_validas & (h_inicio >= h_fin)

    filas_errores = df[horas_invalidas].copy()

    if len(filas_errores) > 0:

      lista_errores_criticos.append(filas_errores)



    df = df[~horas_invalidas].copy()



  # Error de tipo
  if errores['Tipo'] > 0:

    categorias_validas = ['presencial', 'virtual']



    tipo_normalizado = df['Tipo'].astype(str).str.lower().str.strip()



    es_valido = tipo_normalizado.isin(categorias_validas)

    es_invalido = ~es_valido



    filas_errores_tipo = df[es_invalido].copy()



    if len(filas_errores_tipo) > 0:

        lista_errores_criticos.append(filas_errores_tipo)



    df.loc[es_valido, 'Tipo'] = tipo_normalizado[es_valido].str.capitalize()







  #---- limpieza en clases
  if errores['clases_salon'] > 0:



    patron_maestro = r'^(E 102|Y1 101|Y1 208|B 116|CU C 124|CU D3 202|CU A 101|H1 102|PLAZA DE LA FRATERNIDAD|CUAUH A 108|CU D2 210|ESTACIONAMIENTO ADMINISTRATIVO|Cancha de Pádel|Z 101|CUAUH Explanada|Z 105|Y1 202|C 101|CU D2 102|PLAZA CULTURAL|ESTACIONAMIENTO DE MAESTROS).\*$'

    # Aplicar el reemplazo con regex únicamente en las filas donde 'Salón' no sea nulo
    mask_salon_no_nulo = df['Salón'].notna()

    df.loc[mask_salon_no_nulo, 'Salón'] = df.loc[mask_salon_no_nulo, 'Salón'].str.replace(patron_maestro, r'\1', regex=True)

    df.loc[df['Salón'].str.contains('CANCHA DE BASQUET', case=False, na=False), 'Salón'] = 'Cancha de Basketball'

    df.loc[df['Salón'].str.contains('J2', case=False, na=False), 'Salón'] = 'J2 103'

    df.loc[df['Salón'].str.contains('PLAZA DE LA FRATERNIDAD', case=False, na=False), 'Salón'] = 'Plaza de la Fraternidad'

    df.loc[df['Salón'].str.contains('ESTACIONAMIENTO ADMINISTRATIVO', case=False, na=False), 'Salón'] = 'Estacionamiento Administrativo'

    df.loc[df['Salón'].str.contains('CANCHA Cancha de Pádel', case=False, na=False), 'Salón'] = 'Cancha de Pádel'

    df.loc[df['Salón'].str.contains('PLAZA CULTURAL', case=False, na=False), 'Salón'] = 'Plaza Cultural'

    df.loc[df['Salón'].str.contains('ESTACIONAMIENTO DE MAESTROS', case=False, na=False), 'Salón'] = 'Estacionamiento Maestros'



    clases = pd.read_excel(Path(__file__).resolve().parent / 'Diccionario_Datos_Semana_Ingenieria.xlsx', sheet_name='Catálogo Salon')

    lista_salones = clases['Lugar'].astype(str).str.strip().tolist()



    salon_valido = df["Salón"].notna() & (df["Salón"].astype(str).str.strip() != "") & (df["Salón"].astype(str).str.strip() != "—")



    salon_no_en_catalogo = salon_valido & (~df["Salón"].astype(str).str.strip().isin(lista_salones))

    filas_con_errores = df[salon_no_en_catalogo].copy()



    if len(filas_con_errores) > 0:

      lista_errores_criticos.append(filas_con_errores)



    df = df[~salon_no_en_catalogo].copy()





    #salones presenciales
    if errores['salon_presencial'] > 0:

      es_presencial = df["Tipo"].astype(str).str.strip().str.lower() == "presencial"

      salon_vacio = (

      df["Salón"].isna()

      | (df["Salón"].astype(str).str.strip() == "")

      | (df["Salón"].astype(str).str.strip().str.lower() == "nan")

      )



      salones_invalidos = es_presencial & salon_vacio

      filas_invalidas = df[salones_invalidos].copy()



      if len(filas_invalidas) > 0:

        lista_errores_criticos.append(filas_invalidas)



      df = df[~salones_invalidos].copy





    # título vacío
    if errores['titulo_vacio'] > 0:

      titulo_texto = df['Título'].astype(str).str.strip().str.lower()

      titulos_errores = (df['Título'].isna() | titulo_texto== '' | titulo_texto=='nan')

      filas_error = df[titulos_errores].copy()



      if len(filas_error) > 0:

        lista_errores_criticos.append(filas_error)



      df = df[~titulos_errores].copy()



    #------ Limpieza por maestro es igual a ponente
    if errores['maestro_igual_ponente'] > 0:

      df.loc[df['Ponente'].astype(str).str.strip() == df['Maestro de ceremonias'].astype(str).str.strip(), 'Maestro de ceremonias'] = None



    # empresas vacias
    if errores['empresas_vacias'] > 0:

      empresa_texto = df['Empresa / Institución'].astype(str).str.lower().str.strip()

      empresas_vacias = (df['Empresa / Institución'].notna()) & (empresa_texto == '')

      filas_errores = df[empresas_vacias].copy()

      if len(filas_errores) > 0:

        lista_filas_rellenar.append(filas_errores)

      df = df[~empresas_vacias].copy()





    return df, lista_errores_criticos, lista_filas_rellenar





#datos regresados e impresos
df, errores_criticos, filas_rellenar = limpieza(df, df_errores)

resultados = validacion_de_informacion(df)

df_errores = pd.DataFrame(list(resultados.items()), columns=['Validación', 'Total Errores'])

print(df_errores)

print("-----"*10)

print(f"Errores críticos \n{errores_criticos}")

print()

print(f"filas a rellenar \n{filas_rellenar}")





#----------------------------------------------------------------------------
# ETAPA 6: SELECCION
#----------------------------------------------------------------------------
# Atributos necesarios para el proyecto (quita los que su diseño no use)
COLUMNAS_SELECCIONADAS = [

    "Actividad", "Fecha inicio", "Fecha fin", "Hora inicio", "Hora fin",

    "Tipo", "Salón", "Título", "Ponente", "Empresa / Institución",

    "Maestro de ceremonias", "Enlace"

]

OBLIGATORIAS = ["Actividad", "Fecha inicio", "Fecha fin",

                "Hora inicio", "Hora fin", "Tipo", "Título"]



def seleccion(df):

    try:

        if df is None or df.empty:

            print("Error: no hay datos para seleccionar.")

            return None, None



        f_ini = pd.to_datetime(df["Fecha inicio"], format="%Y-%m-%d", errors="coerce")

        f_fin = pd.to_datetime(df["Fecha fin"], format="%Y-%m-%d", errors="coerce")

        h_ini = pd.to_datetime(df["Hora inicio"].astype(str).str[:5], format="%H:%M", errors="coerce")

        h_fin = pd.to_datetime(df["Hora fin"].astype(str).str[:5], format="%H:%M", errors="coerce")

        tipo = df["Tipo"].astype(str).str.strip().str.lower()



        # Reglas que debe cumplir un registro para conservarse
        reglas = {

            "duplicado": df.duplicated(),

            "campo obligatorio vacio": df[OBLIGATORIAS].isna().any(axis=1),

            "fecha fuera de rango": ~(f_ini.between("2026-09-20", "2026-09-25")

                                      & f_fin.between("2026-09-20", "2026-09-25")),

            "fecha inicio > fecha fin": f_ini > f_fin,

            "hora inicio >= hora fin": h_ini >= h_fin,

            "virtual sin enlace": (tipo == "virtual") & df["Enlace"].isna(),

            "presencial sin salon": (tipo == "presencial") & df["Salón"].isna(),

        }



        # Registrar el motivo de rechazo de cada registro
        motivo = pd.Series("", index=df.index)

        for nombre, mask in reglas.items():

            motivo[mask] = motivo[mask] + nombre + "; "



        es_rechazado = motivo != ""



        df_sel = df.loc[~es_rechazado, COLUMNAS_SELECCIONADAS].reset_index(drop=True)

        df_rechazados = df.loc[es_rechazado].copy()

        df_rechazados["motivo_rechazo"] = motivo[es_rechazado].str.rstrip("; ")

        df_rechazados = df_rechazados.reset_index(drop=True)



        print("\n========== SELECCION ==========")

        print("Registros recibidos:  ", len(df))

        print("Registros aceptados:  ", len(df_sel))

        print("Registros rechazados: ", len(df_rechazados))

        print("Atributos conservados:", len(df_sel.columns))



        return df_sel, df_rechazados



    except Exception as error:

        print("Error durante la selección:", error)

        return None, None





df_sel, df_rechazados = seleccion(df)

print(df_sel.head())

print(df_rechazados)



#----------------------------------------------------------------------------
# ETAPA 7: TRANSFORMACION
#----------------------------------------------------------------------------
DIAS_ES = {0: "Lunes", 1: "Martes", 2: "Miércoles", 3: "Jueves",

           4: "Viernes", 5: "Sábado", 6: "Domingo"}



def transformacion(df):

    try:

        if df is None or df.empty:

            print("Error: no hay datos para transformar.")

            return None



        df_t = df.copy()



        # 1.- Renombrar columnas con los nombres del diseño (cols_n_dtypes, etapa 1)
        df_t.columns = list(cols_n_dtypes.keys())



        # 2.- Convertir tipos según el diseño
        df_t["fecha_inicio"] = pd.to_datetime(df_t["fecha_inicio"], format="%Y-%m-%d")

        df_t["fecha_fin"] = pd.to_datetime(df_t["fecha_fin"], format="%Y-%m-%d")

        h_ini = pd.to_datetime(df_t["hora_inicio"].astype(str).str[:5], format="%H:%M")

        h_fin = pd.to_datetime(df_t["hora_fin"].astype(str).str[:5], format="%H:%M")

        df_t["hora_inicio"] = h_ini.dt.strftime("%H:%M")

        df_t["hora_fin"] = h_fin.dt.strftime("%H:%M")

        df_t["tipo"] = df_t["tipo"].str.strip().str.lower()



        # 3.- Salón de eventos virtuales: '—' pasa a nulo
        df_t.loc[df_t["salon"].astype(str).str.strip() == "—", "salon"] = None



        # 4.- Atributos derivados
        df_t["duracion_horas"] = ((h_fin - h_ini).dt.total_seconds() / 3600).round(2)

        df_t["num_dias"] = (df_t["fecha_fin"] - df_t["fecha_inicio"]).dt.days + 1

        df_t["dia_semana"] = df_t["fecha_inicio"].dt.dayofweek.map(DIAS_ES)



        # 5.- Ordenar cronológicamente y asignar id
        df_t = df_t.sort_values(["fecha_inicio", "hora_inicio"]).reset_index(drop=True)

        df_t.insert(0, "id_evento", range(1, len(df_t) + 1))



        print("\n========== TRANSFORMACION ==========")

        print("Registros:", len(df_t))

        print("Columnas finales:", df_t.columns.tolist())



        return df_t



    except Exception as error:

        print("Error durante la transformación:", error)

        return None





df_final = transformacion(df_sel)

print(df_final.head())

#----------------------------------------------------------------------------
# EXPORTACION PARA LA PAGINA WEB (conferencias.json)
#----------------------------------------------------------------------------
import json

def exportar_conferencias_web(df):
    """Exporta los registros aceptados a conferencias.json para UniConferencias."""
    if df is None or df.empty:
        print("No se generó conferencias.json: no hay conferencias aceptadas.")
        return

    def texto(valor, default=""):
        return default if pd.isna(valor) else str(valor).strip()

    datos_web = []
    for _, fila in df.iterrows():
        fecha_valor = fila.get("fecha_inicio")
        fecha = fecha_valor.strftime("%Y-%m-%d") if hasattr(fecha_valor, "strftime") else str(fecha_valor)[:10]

        institucion = texto(fila.get("empresa/institucion"))
        maestro = texto(fila.get("maestro de ceremonias")
        )
        descripcion = []
        if institucion:
            descripcion.append(f"Institución: {institucion}")
        if maestro:
            descripcion.append(f"Maestro de ceremonias: {maestro}")
        if texto(fila.get("enlace")):
            descripcion.append(f"Enlace: {texto(fila.get('enlace'))}")

        datos_web.append({
            "id": int(fila.get("id_evento", len(datos_web) + 1)),
            "titulo": texto(fila.get("titulo"), "Conferencia sin título"),
            "ponente": texto(fila.get("ponente"), "Por confirmar"),
            "campus": "No especificado",
            "ubicacion": texto(fila.get("salon"), "Por confirmar"),
            "fecha": fecha,
            "fechaFin": (fila.get("fecha_fin").strftime("%Y-%m-%d")
                         if hasattr(fila.get("fecha_fin"), "strftime")
                         else str(fila.get("fecha_fin"))[:10]),
            "horaInicio": texto(fila.get("hora_inicio"))[:5],
            "horaFin": texto(fila.get("hora_fin"))[:5],
            "area": texto(fila.get("actividad"), "General"),
            "tipo": texto(fila.get("tipo"), "Presencial"),
            "descripcion": " · ".join(descripcion),
            "enlace": texto(fila.get("enlace"))
        })

    ruta_json = Path(__file__).resolve().parent / "conferencias.json"
    with ruta_json.open("w", encoding="utf-8") as archivo:
        json.dump(datos_web, archivo, ensure_ascii=False, indent=2)

    print(f"JSON web generado: {ruta_json} | {len(datos_web)} conferencias")

exportar_conferencias_web(df_final)






import os



def almacenamiento(df_procesado, df_rechazados, ruta_procesados="datos_procesados.xlsx", ruta_rechazados="registros_rechazados.xlsx"):

    try:

        print("\n Almacenamiento")

        if df_procesado is None or df_procesado.empty:

            print("Advertencia: No hay datos procesados para guardar.")

        else:

            df_procesado.to_excel(ruta_procesados, index=False)



            if os.path.exists(ruta_procesados):

                print(f"✓ Éxito: Datos procesados guardados y verificados en '{ruta_procesados}' ({len(df_procesado)} registros).")

            else:

                print(f"✗ Error: No se pudo verificar la creación del archivo '{ruta_procesados}'.")



        if df_rechazados is None or df_rechazados.empty:

            print("Información: No hay registros rechazados que almacenar.")

        else:

            df_rechazados.to_excel(ruta_rechazados, index=False)



            if os.path.exists(ruta_rechazados):

                print(f"✓ Éxito: Registros rechazados guardados y verificados en '{ruta_rechazados}' ({len(df_rechazados)} registros).")

            else:

                print(f"✗ Error: No se pudo verificar la creación del archivo '{ruta_rechazados}'.")



    except Exception as error:

        print("Error crítico durante el almacenamiento:", error)



almacenamiento(df_final, df_rechazados,
              ruta_procesados=str(Path(__file__).resolve().parent / "datos_procesados.xlsx"),
              ruta_rechazados=str(Path(__file__).resolve().parent / "registros_rechazados.xlsx"))