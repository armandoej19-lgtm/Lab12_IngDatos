"""Parámetros del pipeline.

Todas las reglas que dependen del evento (fechas, horarios, catálogos fijos,
patrones) viven aquí para no repetirlas entre etapas.
"""

# --------------------------------------------------------------------------
# Layout de entrada (nombres tal como vienen en el Excel del programa)
# --------------------------------------------------------------------------
COLUMNAS = [
    "Actividad", "Fecha inicio", "Fecha fin", "Hora inicio", "Hora fin",
    "Tipo", "Salón", "Título", "Ponente", "Empresa / Institución",
    "Maestro de ceremonias", "Enlace",
]

# Campos que pueden venir vacíos sin invalidar el registro
COLUMNAS_OPCIONALES = [
    "Ponente", "Empresa / Institución", "Maestro de ceremonias", "Enlace",
]
COLUMNAS_OBLIGATORIAS = [c for c in COLUMNAS if c not in COLUMNAS_OPCIONALES]

# Atributos que se conservan en la etapa de selección
COLUMNAS_SELECCIONADAS = list(COLUMNAS)

# --------------------------------------------------------------------------
# Esquema de salida (diseño del pipeline)
# --------------------------------------------------------------------------
RENOMBRAR = {
    "Actividad": "actividad",
    "Fecha inicio": "fecha_inicio",
    "Fecha fin": "fecha_fin",
    "Hora inicio": "hora_inicio",
    "Hora fin": "hora_fin",
    "Tipo": "tipo",
    "Salón": "salon",
    "Título": "titulo",
    "Ponente": "ponente",
    "Empresa / Institución": "empresa_institucion",
    "Maestro de ceremonias": "maestro_ceremonias",
    "Enlace": "enlace",
}

DIAS_ES = {0: "Lunes", 1: "Martes", 2: "Miércoles", 3: "Jueves",
           4: "Viernes", 5: "Sábado", 6: "Domingo"}

# --------------------------------------------------------------------------
# Reglas del evento
# --------------------------------------------------------------------------
FECHA_MIN = "2026-09-20"
FECHA_MAX = "2026-09-25"
HORA_MIN = "08:00"
HORA_MAX = "22:00"

TIPOS_PERMITIDOS = ["presencial", "virtual"]
SIN_SALON = "—"  # marcador usado en eventos virtuales

PATRON_TEAMS = r"^https://(events\.)?teams\.microsoft\.com/.*$"

# --------------------------------------------------------------------------
# Correcciones de la etapa de limpieza
# --------------------------------------------------------------------------
MAPEO_ACTIVIDAD = {
    "FOSEEI": "Ponencia",
    "CUAUH": "Concurso",
    "CENALTEC": "Curso",
}

# Recorta descripciones extra del salón y deja solo el código: "CUAUH A 108 - Audiovisual" -> "CUAUH A 108"
PATRON_SALON = (
    r"^(E 102|Y1 101|Y1 208|B 116|CU C 124|CU D3 202|CU A 101|H1 102|"
    r"PLAZA DE LA FRATERNIDAD|CUAUH A 108|CU D2 210|ESTACIONAMIENTO ADMINISTRATIVO|"
    r"Cancha de Pádel|Z 101|CUAUH Explanada|Z 105|Y1 202|C 101|CU D2 102|"
    r"PLAZA CULTURAL|ESTACIONAMIENTO DE MAESTROS).*$"
)

# (texto que contiene el salón, nombre en el catálogo); se aplican en orden
MAPEO_SALON = [
    ("CANCHA DE BASQUET", "Cancha de Basketball"),
    ("J2", "J2 103"),
    ("PLAZA DE LA FRATERNIDAD", "Plaza de la Fraternidad"),
    ("ESTACIONAMIENTO ADMINISTRATIVO", "Estacionamiento Administrativo"),
    ("CANCHA Cancha de Pádel", "Cancha de Pádel"),
    ("PLAZA CULTURAL", "Plaza Cultural"),
    ("ESTACIONAMIENTO DE MAESTROS", "Estacionamiento Maestros"),
]

# --------------------------------------------------------------------------
# Diccionario de datos (nombres de hojas y columnas del Excel)
# --------------------------------------------------------------------------
HOJA_DICCIONARIO = "Diccionario"
HOJA_ACTIVIDADES = "Catalogo Actividad"
HOJA_SALONES = "Catálogo Salon"

COL_CAMPO = "Campo"
COL_TIPO_ESPERADO = "Tipo esperado"
COL_ACTIVIDAD_PERMITIDA = "Actividad permitida"
COL_LUGAR = "Lugar"

# --------------------------------------------------------------------------
# Entradas por defecto (cuando no se indican en la línea de comandos)
# --------------------------------------------------------------------------
DIRECTORIO_DATOS = "data/raw"
PATRON_PROGRAMA = "Programa*.xlsx"
PATRON_DICCIONARIO = "Diccionario*.xlsx"

# --------------------------------------------------------------------------
# Base de datos (PostgreSQL)
# --------------------------------------------------------------------------
VAR_URL_BD = "DATABASE_URL"  # variable de entorno con la URL de conexión

TABLA_EVENTOS = "eventos"
TABLA_RECHAZADOS = "registros_rechazados"
TABLA_BITACORA = "bitacora_limpieza"
TABLA_REPORTE = "reporte_validacion"
TABLA_INCUMPLIMIENTOS = "incumplimientos_validacion"

# Hojas del reporte de validación: el resumen por regla y el detalle por registro.
# Los encabezados del resumen se renombran a las columnas de su tabla.
HOJA_REPORTE = "validacion"
HOJA_INCUMPLIMIENTOS = "incumplimientos"
RENOMBRAR_REPORTE = {
    "Validación": "validacion",
    "Antes de limpieza": "antes_de_limpieza",
    "Después de limpieza": "despues_de_limpieza",
}

# --------------------------------------------------------------------------
# Salidas en archivos
# --------------------------------------------------------------------------
ARCHIVO_PROCESADOS = "datos_procesados.xlsx"
ARCHIVO_RECHAZADOS = "registros_rechazados.xlsx"
ARCHIVO_BITACORA = "bitacora_limpieza.xlsx"
ARCHIVO_REPORTE = "reporte_validacion.xlsx"
ARCHIVO_LOG = "pipeline.log"
