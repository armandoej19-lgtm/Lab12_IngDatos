"""Parámetros del agente: modelos locales de Ollama y reglas de búsqueda."""

# --------------------------------------------------------------------------
# Modelos (locales y de uso libre; se pueden cambiar con variables de entorno)
# --------------------------------------------------------------------------
VAR_MODELO = "AGENTE_MODELO"
VAR_MODELO_EMBEDDINGS = "AGENTE_MODELO_EMBEDDINGS"

MODELO = "qwen3:4b"                # interpreta la pregunta y redacta la respuesta (Apache 2.0)
MODELO_EMBEDDINGS = "bge-m3"       # vectores multilingües para la búsqueda por tema (MIT)

TEMPERATURA = 0                    # respuestas repetibles
TOKENS_CONTEXTO = 4096
TOKENS_RESPUESTA = 300             # la respuesta es breve: el listado lo arma el programa
LOTE_EMBEDDINGS = 32               # eventos que se vectorizan por llamada

# --------------------------------------------------------------------------
# Búsqueda
# --------------------------------------------------------------------------
MAX_LISTADO = 30                   # eventos que se muestran en la respuesta
EVENTOS_PARA_MODELO = 4            # eventos de ejemplo que recibe el modelo para redactar
CANDIDATOS_POR_TEMA = 15           # máximo de eventos afines que revisa el modelo

# Un evento es candidato a "afín" si su similitud con el tema casi iguala a la del
# más parecido. Si ningún evento nombra el tema, además debe superar un mínimo.
# Son valores medidos con bge-m3; con otro modelo de embeddings hay que volver a medirlos.
MARGEN_SIMILITUD = 0.05
SIMILITUD_MINIMA = 0.48

# Palabras que no cuentan al buscar el tema de forma literal
PALABRAS_VACIAS = {"a", "al", "con", "de", "del", "el", "en", "la", "las", "los", "o", "para", "por",
                   "sobre", "un", "una", "y", "dr", "dra", "doctor", "doctora", "ing", "lic", "mtro", "mtra"}

# Franjas del día que el modelo usa al interpretar "en la mañana", "en la tarde", "en la noche"
FRANJAS = {"mañana": ("08:00", "12:00"), "tarde": ("12:00", "19:00"), "noche": ("19:00", "22:00")}

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
         "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
