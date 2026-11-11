# Pipeline de datos: Semana de Ingeniería

Ficha Técnica de la Clase | Ingeniería de Datos Grupo A
------------------------------------------------------------
> Jesús Armando Esparza Jiménez       - 260974  ||
> Rebecca Araly Araiza López          - 261630  ||
> Rodrigo Aaron Vásquez Chavarría     - 264620  ||
> David Yair Martinez Nava            - 262079  ||
> Kevin Ariel Carbajal Estrada        - 260422  ||
------------------------------------------------------------

Pipeline en Python que toma el programa de actividades de la Semana de Ingeniería (Excel) y lo valida, limpia, filtra y transforma usando como referencia el diccionario de datos del evento. Al final guarda los **datos procesados** y los **registros rechazados** en PostgreSQL y en archivos Excel.

Sobre esa base de datos trabaja un **agente** con modelos locales de Ollama que responde preguntas en español sobre el programa: qué conferencias hay en un horario, cuáles se relacionan con un tema, qué tipos de actividad existen. La **página web** `UniConferencias` muestra el programa y permite preguntarle al agente.

Proyecto del *Laboratorio 12: Implementación de un Pipeline de Datos en Python*. Funciona en **Windows** y en **Fedora Linux**.

```
data/raw/*.xlsx ──> pipeline (8 etapas) ──> PostgreSQL ──> servidor web ──> página UniConferencias
                                        │                  (API + agente con Ollama)
                                        └─> output/*.xlsx
```

Hay un solo pipeline. La página no procesa datos por su cuenta: los pide al servidor, que los lee de PostgreSQL.

## Etapas

Cada etapa hace lo que le corresponde y entrega su resultado a la siguiente; ninguna repite el trabajo de otra.

| # | Etapa | Módulo | Qué hace |
|---|---|---|---|
| 1 | Carga | `pipeline/carga.py` | Lee el programa y el diccionario de datos (layout y catálogos). |
| 2 | Validación de carga | `pipeline/carga.py` | Comprueba que el archivo se leyó sin errores y que no está vacío. |
| 3 | Validación del layout | `pipeline/layout.py` | Revisa nombres de columnas, columnas requeridas y tipos de datos contra el diccionario. Si faltan columnas, se detiene. |
| 4 | Validación de información | `pipeline/validacion.py` | Identifica y registra los incumplimientos: duplicados, nulos, vacíos, formatos, rangos, catálogos y reglas entre campos. Es la única etapa que evalúa reglas. |
| 5 | Limpieza | `pipeline/limpieza.py` | Trata los problemas que marcó la etapa 4, cuando tienen corrección segura, y anota cada cambio en una bitácora. |
| 6 | Selección | `pipeline/seleccion.py` | Conserva los registros sin incumplimientos y los atributos del diseño; separa los demás con su motivo de rechazo. |
| 7 | Transformación | `pipeline/transformacion.py` | Aplica el esquema de salida: nombres estándar, tipos y formato, atributos derivados, orden e identificador. |
| 8 | Almacenamiento | `pipeline/almacenamiento.py` | Guarda por separado procesados y rechazados (con la bitácora y el reporte) en PostgreSQL y en Excel, y verifica la escritura releyendo lo guardado. |

Los parámetros del evento (rango de fechas y horas, patrón de enlaces, mapeos de limpieza, nombres de hojas y de tablas) están en `pipeline/config.py`.

## Decisiones de diseño

- **Las reglas se escriben y se evalúan en un solo lugar.** `validacion_de_informacion()` devuelve una máscara booleana por regla, el resumen de totales y el detalle por registro. La limpieza y la selección trabajan con ese resultado; no vuelven a revisar los datos por su cuenta.
- **La limpieza trata, la selección decide.** La limpieza nunca borra registros: corrige lo que la validación marcó cuando la corrección es segura, por ejemplo `CUAUH` → `Concurso` o `"CUAUH A 108 - Audiovisual"` → `"CUAUH A 108"`. Después se valida de nuevo, y lo que siga incumpliendo (como una hora fin anterior a la hora inicio, que no se puede corregir sin adivinar) lo separa la selección.
- **Nada se pierde en silencio.** Cada incumplimiento queda registrado con su fila del Excel. Cada corrección queda en la bitácora con su valor antes y después. Cada rechazo indica la fila, sus valores originales y el motivo.
- **La base de datos es neutral.** Las tablas del programa solo usan tipos estándar de PostgreSQL y no dependen del agente: cualquier aplicación puede consultarlas. Lo que es propio del agente vive en dos tablas aparte.
- **Los datos los pone la base, no el modelo.** El modelo interpreta la pregunta y redacta una respuesta breve, pero los eventos se buscan con SQL y tanto el listado como las cifras los escribe el programa. Un título, un horario, un salón o un total nunca dependen de lo que escriba el modelo.

### Reglas de validación

| Regla | Descripción |
|---|---|
| `duplicados` | Registro idéntico a uno anterior. |
| `nulos` | Falta un campo obligatorio. Solo son opcionales Ponente, Empresa / Institución, Maestro de ceremonias y Enlace. |
| `vacios` | Celda con texto vacío o solo espacios. |
| `actividad_fuera_de_catalogo` | Actividad que no aparece en *Catalogo Actividad*. |
| `tipo_invalido` | Tipo distinto de `presencial` / `virtual`. |
| `salon_fuera_de_catalogo` | Salón que no aparece en *Catálogo Salon*. |
| `formato_fecha` / `formato_hora` | Fecha distinta de `YYYY-MM-DD`, u hora distinta de `HH:MM`. |
| `enlace_invalido` | Enlace que no es de Microsoft Teams. |
| `espacios_sobrantes` | Texto con espacios al inicio, al final o repetidos. |
| `fecha_fuera_de_rango` | Fecha fuera del 20 al 25 de septiembre de 2026. |
| `hora_fuera_de_rango` | Hora fuera de 08:00 a 22:00. |
| `fecha_inicio_mayor_a_fin` / `hora_inicio_no_menor_a_fin` | Orden incorrecto entre inicio y fin. |
| `virtual_sin_enlace` / `presencial_sin_salon` | Reglas entre el tipo de evento y sus campos. |
| `maestro_igual_a_ponente` | El maestro de ceremonias es la misma persona que el ponente. |

Un título vacío o una empresa con solo espacios no tienen regla propia: ya los cubren `nulos` y `vacios`.

Qué hace la limpieza con cada problema: quita los espacios de más y deja en nulo el texto vacío (`vacios`, `espacios_sobrantes`); cambia el nombre de sede por la actividad del catálogo (`actividad_fuera_de_catalogo`); deja el salón con su nombre de catálogo (`salon_fuera_de_catalogo`); anula el enlace que no es de Teams (`enlace_invalido`) y el maestro de ceremonias repetido (`maestro_igual_a_ponente`). Las demás reglas no tienen corrección segura.

## Estructura

```
pipeline-semana-ingenieria/
├── main.py                     # ejecuta el pipeline completo (CLI)
├── pipeline/                   # una etapa por módulo
│   ├── bd.py                   # conexión y carga en PostgreSQL
│   └── esquema.sql             # tablas de la base de datos
├── agente/                     # agente de preguntas y respuestas (Ollama)
│   └── servidor.py             # API web del agente; también sirve la página
├── UniConferencias/            # página web (HTML, CSS y JavaScript)
├── scripts/
│   ├── crear_bd.py             # crea el rol y la base de datos
│   └── generar_datos_muestra.py
├── tests/                      # pruebas con pytest
├── data/
│   ├── raw/                    # archivos reales (no se suben, ver "Datos")
│   └── sample/                 # datos sintéticos para probar
├── .env.example                # plantilla de la configuración local
├── requirements.txt
└── requirements-dev.txt
```

## Instalación

Requisitos: Python 3.10 o superior, PostgreSQL 14 o superior y, para el agente, Ollama. Los pasos 1 y 2 cambian según el sistema; del 3 en adelante son iguales.

### 1. Programas

**Windows** (PowerShell):

```powershell
winget install PostgreSQL.PostgreSQL.17
winget install Ollama.Ollama
```

El instalador de PostgreSQL pide una clave para el superusuario `postgres`: hay que anotarla para el paso 3.

**Fedora:**

```bash
sudo dnf install -y python3 python3-pip postgresql-server
sudo postgresql-setup --initdb
sudo systemctl enable --now postgresql
curl -fsSL https://ollama.com/install.sh | sh
```

En Fedora, PostgreSQL identifica por defecto las conexiones locales con el usuario del sistema (`ident`) y no acepta claves. Se cambia a autenticación con clave y se le pone una al superusuario:

```bash
sudo sed -i -E 's/^(host\s+all\s+all\s+\S+\s+)ident\s*$/\1scram-sha-256/' /var/lib/pgsql/data/pg_hba.conf
sudo systemctl restart postgresql
sudo -u postgres psql -c "ALTER USER postgres PASSWORD 'una_clave_para_postgres'"
```

### 2. Entorno de Python

```bash
git clone https://github.com/<usuario>/pipeline-semana-ingenieria.git
cd pipeline-semana-ingenieria
python -m venv .venv               # en Fedora: python3 -m venv .venv
source .venv/bin/activate          # en Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
```

En Windows se instala pandas 2.x: *Smart App Control* de Windows 11 bloquea un binario de pandas 3.1. En Linux se usa la versión más reciente.

### 3. Base de datos

Copia `.env.example` como `.env` y completa dos datos: en `DATABASE_URL`, el usuario, la clave y la base que usará el proyecto (se crean en este paso); en `POSTGRES_PASSWORD`, la clave del superusuario del paso 1. Después:

```bash
python scripts/crear_bd.py
```

Las tablas no hay que crearlas: la etapa 8 las crea la primera vez a partir de `pipeline/esquema.sql`.

### 4. Modelos del agente

Son locales y de uso libre; se descargan una sola vez (3.7 GB en total):

```bash
ollama pull qwen3:4b
ollama pull bge-m3
```

`qwen3:4b` (Apache 2.0) interpreta las preguntas y redacta; `bge-m3` (MIT) genera los vectores. Funcionan con tarjeta gráfica o solo con procesador. Con 8 GB de RAM conviene cerrar otros programas: el modelo de chat ocupa unos 2.5 GB.

## Uso

**Pipeline con los archivos reales.** Cópialos a `data/raw/` y ejecuta:

```bash
python main.py
```

Sin argumentos toma de `data/raw/` el archivo `Programa*.xlsx` y el `Diccionario*.xlsx`, y guarda en la base de `DATABASE_URL`. También se pueden indicar:

```bash
python main.py --datos data/raw/Programa_32IIT_21-09.xlsx --diccionario data/raw/Diccionario_Datos_Semana_Ingenieria.xlsx --salida output
```

**Pipeline con los datos de muestra, sin base de datos:**

```bash
python main.py --datos data/sample/programa_muestra.xlsx --diccionario data/sample/diccionario_muestra.xlsx --sin-bd
```

El pipeline termina con código `0` si todo salió bien, y con `1` si se detuvo en la carga, en el layout o al guardar en PostgreSQL.

**Agente.** Responde cuando el pipeline ya terminó, porque lee lo que guardó la etapa 8:

```bash
python main.py --agente
```

```bash
python -m agente
```

```bash
python -m agente "¿Qué conferencias hay entre las 10 y las 12?"
```

El primero ejecuta el pipeline y abre la conversación; el segundo conversa sobre lo que ya está en la base; el tercero responde una sola pregunta. Ejemplo:

```
> ¿Qué conferencias están relacionadas con inteligencia artificial?
Se encontraron 6 eventos relacionados con inteligencia artificial. Los títulos más relevantes son:
«Detección de estrés por medio de video con inteligencia artificial» y «Inteligencia Artificial:
Reto y Oportunidad del Siglo XXI».

 1. lun 21 sep, 13:00-15:30 | Conferencia | H 101
    Detección de estrés por medio de video con inteligencia artificial (Ing. ... - UACJ)
 2. jue 24 sep, 09:30-11:00 | Conferencia magistral | B 116
    Inteligencia Artificial: Reto y Oportunidad del Siglo XXI (... - UNAM)
 ...

[Búsqueda: actividad Conferencia, tema «inteligencia artificial»]
```

La última línea muestra cómo se entendió la pregunta, para poder reformularla si no era eso.

**Página web.** Con el pipeline ya ejecutado, inicia el servidor y abre `http://localhost:8000`:

```bash
python -m agente.servidor
```

El servidor entrega la página y la API juntas. Al arrancar deja listo el agente (comprueba Ollama y genera los vectores que falten); si Ollama o PostgreSQL no están disponibles, la página lo indica. La primera pregunta después de un rato sin uso tarda más, porque Ollama vuelve a cargar el modelo en memoria. Para usar otro puerto: `python -m agente.servidor --puerto 8080`.

| Ruta | Qué devuelve |
|---|---|
| `GET /api/eventos` | El programa completo, con los campos que usa la página. |
| `POST /api/agente` | Recibe `{"pregunta": "..."}` y devuelve `respuesta` (texto del agente), `busqueda` (cómo se entendió), `eventos` (los encontrados, hasta 30), `total` y `detalle` (las cifras del programa, en preguntas generales). |
| `GET /docs` | Documentación interactiva de la API. |

```bash
curl -X POST http://localhost:8000/api/agente -H "Content-Type: application/json" -d '{"pregunta": "que talleres hay el martes"}'
```

La petición debe ir en UTF-8. La página y cualquier programa lo hacen así; desde la terminal de Windows los acentos se envían en otra codificación y el servidor responde con un error 400.

## Salidas

### Base de datos (PostgreSQL)

Cada ejecución reemplaza el contenido de las cinco tablas del programa en una sola transacción: o se guardan todas o ninguna.

| Tabla | Contenido |
|---|---|
| `eventos` | Registros aceptados con el esquema final: `id_evento`, fechas (`date`), horas (`time`), `tipo`, `salon`, `titulo`, `ponente`, `duracion_horas`, `num_dias`, `dia_semana`. |
| `registros_rechazados` | Registros rechazados con sus valores originales (texto), `fila_excel` y `motivo_rechazo`. |
| `bitacora_limpieza` | Cada celda corregida, con su valor original y su valor limpio. |
| `reporte_validacion` | Errores por regla, antes y después de la limpieza. |
| `incumplimientos_validacion` | Detalle de la validación de los datos originales: una fila por cada regla que incumple cada registro. |
| `agente_vectores` | Vector (embedding) del título y la clase de actividad de cada evento, guardado como `real[]`. Se borra con su evento y el agente lo regenera al iniciar. |
| `agente_interacciones` | Historial del agente: pregunta, filtros que interpretó, eventos mostrados, respuesta, modelo y duración. No se borra al recargar el programa. |

Las cinco primeras son neutrales: no requieren extensiones y sirven a cualquier aplicación. La página web es una de ellas: lee `eventos` a través de la API. Por ejemplo:

```sql
SELECT titulo, hora_inicio, hora_fin, salon
FROM eventos
WHERE actividad = 'Conferencia' AND hora_inicio < '12:00' AND hora_fin > '10:00'
ORDER BY fecha_inicio, hora_inicio;
```

### Archivos (`output/`)

| Archivo | Contenido |
|---|---|
| `datos_procesados.xlsx` | Lo mismo que la tabla `eventos`. |
| `registros_rechazados.xlsx` | Registros rechazados con todas las columnas del Excel original. Se escribe aunque esté vacío. |
| `bitacora_limpieza.xlsx` | Cada celda corregida, con su valor original y su valor limpio. |
| `reporte_validacion.xlsx` | Dos hojas: `validacion`, con los errores por regla antes y después de la limpieza, e `incumplimientos`, con el detalle por fila del Excel. |
| `pipeline.log` | Registro de la ejecución. |

## Agente

Cada pregunta sigue cuatro pasos (`agente/agente.py`):

1. **Interpretar.** El modelo convierte la pregunta en filtros: actividad, modalidad, día, horario y tema. Su salida está restringida a los valores que existen en la base y después se valida: la actividad solo cuenta si la pregunta la nombra, y una hora anterior al inicio del programa se entiende como de la tarde («la 1» es 13:00).
2. **Recuperar.** Los filtros se resuelven con SQL sobre `eventos`. El tema se busca de dos formas: entran siempre los eventos que lo nombran (en el título, la actividad, el ponente, la empresa o el salón), y se añaden los afines, que son los más parecidos según sus vectores cuando el modelo confirma que tratan de eso.
3. **Redactar.** El modelo escribe dos o tres frases a partir de lo encontrado. Debajo, el programa muestra el listado de eventos o las cifras del programa, tomados de la base.
4. **Registrar.** La interacción se guarda en `agente_interacciones`.

| Pregunta | Cómo se resuelve |
|---|---|
| ¿Qué conferencias hay entre las 10 y las 12? | Actividad `Conferencia` y eventos cuyo horario coincide con ese intervalo. |
| ¿Qué conferencias están relacionadas con inteligencia artificial? | Actividad `Conferencia` y búsqueda del tema. |
| ¿Qué tipos de actividad hay? | Sin filtros: resumen del programa (eventos por actividad, modalidad y día). |
| ¿Qué talleres virtuales hay el martes por la tarde? | Actividad, modalidad, día y franja horaria combinados. |
| ¿Qué da el Dr. …? ¿Dónde es el torneo de …? | El tema es un nombre: solo los eventos que lo nombran. |

Cómo se interpreta el horario: «entre las 10 y las 12» devuelve los eventos que coinciden con ese intervalo aunque empiecen antes o terminen después; «a las 10», los que están en curso a esa hora; «después de las 4», los que empiezan a esa hora o más tarde; «antes de las 10», los que empiezan antes. Una actividad de varios días cuenta en cada uno de ellos, y «conferencias» incluye las conferencias magistrales.

Límites conocidos:

- La búsqueda de temas afines es aproximada y prefiere quedarse corta: puede omitir un evento relacionado que no nombre el tema (con «videojuegos» no aparece el «Torneo de E-GAMES»). Si un tema no está en el programa, responde que no encontró actividades.
- El texto que redacta el modelo puede tener imprecisiones de redacción; los datos fiables son los del listado.
- Cada pregunta se responde por separado: el agente no recuerda la anterior.

Los modelos y los límites de búsqueda están en `agente/config.py`. Los modelos también se pueden cambiar en `.env` con `AGENTE_MODELO` y `AGENTE_MODELO_EMBEDDINGS`; si cambia el de embeddings, el agente regenera los vectores al iniciar y conviene volver a medir los umbrales de similitud.

## Datos

- `data/sample/` contiene datos **sintéticos** generados con `scripts/generar_datos_muestra.py`. Incluyen a propósito casos sucios y casos que deben rechazarse. No son el programa real del evento.
- `data/raw/` está en `.gitignore`, porque el programa real incluye nombres de personas. Si tienen permiso para publicarlo, quiten esas líneas del `.gitignore`.
- `.env` tampoco se sube: contiene las claves de la base de datos.

## Pruebas

```bash
pytest -q
```

Las pruebas cubren cada etapa, el pipeline completo con los datos de muestra, el agente y su servicio web (con un modelo simulado, para probar la lógica del programa sin depender de Ollama). Las que necesitan PostgreSQL usan la base de `DATABASE_URL` dentro de un esquema temporal que se borra al terminar, así que no tocan las tablas reales; si no hay base de datos disponible, se omiten.

GitHub Actions las corre en cada push en un contenedor de Fedora, en Windows y en Ubuntu (`.github/workflows/tests.yml`).
