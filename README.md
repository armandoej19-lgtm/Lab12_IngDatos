# Pipeline de datos: Semana de Ingeniería

Pipeline en Python que toma el programa de actividades de la Semana de Ingeniería (Excel) y lo valida, limpia, filtra y transforma usando como referencia el diccionario de datos del evento. Al final guarda por separado los **datos procesados** y los **registros rechazados**.

Proyecto del *Laboratorio 12: Implementación de un Pipeline de Datos en Python*.

## Etapas

| # | Etapa | Módulo | Qué hace |
|---|---|---|---|
| 1 | Carga | `pipeline/carga.py` | Lee el programa y el diccionario de datos (layout y catálogos). |
| 2 | Validación de carga | `pipeline/carga.py` | Comprueba que el archivo se leyó sin errores y que no está vacío. |
| 3 | Validación del layout | `pipeline/layout.py` | Revisa nombres de columnas, columnas requeridas y tipos de datos contra el diccionario. Si faltan columnas, se detiene. |
| 4 | Validación de información | `pipeline/validacion.py` | Cuenta los registros que incumplen cada regla: duplicados, nulos, vacíos, formatos, rangos, catálogos y reglas entre campos. |
| 5 | Limpieza | `pipeline/limpieza.py` | Corrige lo que tiene corrección segura y registra cada cambio en una bitácora. |
| 6 | Selección | `pipeline/seleccion.py` | Conserva los registros que cumplen todas las reglas y separa los demás con su motivo de rechazo. |
| 7 | Transformación | `pipeline/transformacion.py` | Aplica el esquema de salida: nombres estándar, tipos, atributos derivados, orden e identificador. |
| 8 | Almacenamiento | `pipeline/almacenamiento.py` | Guarda procesados, rechazados, bitácora y reporte, y verifica la escritura releyendo cada archivo. |

Los parámetros del evento (rango de fechas y horas, patrón de enlaces, mapeos de limpieza, nombres de hojas) están en `pipeline/config.py`.

## Decisiones de diseño

- **Las reglas se escriben una sola vez.** `reglas_por_registro()` devuelve una máscara booleana por regla. La etapa 4 la usa para el reporte y la etapa 6 para decidir qué registros se rechazan.
- **La limpieza corrige y la selección decide.** La limpieza nunca borra registros: solo corrige valores cuando la corrección es segura, por ejemplo `CUAUH` → `Concurso` o `"CUAUH A 108 - Audiovisual"` → `"CUAUH A 108"`. Lo que no se puede corregir sin adivinar, como una hora fin anterior a la hora inicio, se rechaza en la selección.
- **Nada se pierde en silencio.** Cada rechazo indica la fila del Excel, sus valores originales y el motivo. Cada corrección queda en la bitácora con su valor antes y después.

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
| `fecha_fuera_de_rango` | Fecha fuera del 20 al 25 de septiembre de 2026. |
| `hora_fuera_de_rango` | Hora fuera de 08:00 a 22:00. |
| `fecha_inicio_mayor_a_fin` / `hora_inicio_no_menor_a_fin` | Orden incorrecto entre inicio y fin. |
| `virtual_sin_enlace` / `presencial_sin_salon` | Reglas entre el tipo de evento y sus campos. |
| `titulo_vacio` | Título vacío. |
| `maestro_igual_a_ponente` | El maestro de ceremonias es la misma persona que el ponente. |
| `empresa_vacia` | Empresa / Institución con solo espacios. |

## Estructura

```
pipeline-semana-ingenieria/
├── main.py                     # ejecuta el pipeline completo (CLI)
├── pipeline/                   # una etapa por módulo
├── notebooks/Laboratorio_12.ipynb
├── scripts/generar_datos_muestra.py
├── tests/                      # pruebas con pytest
├── data/
│   ├── raw/                    # archivos reales (no se suben, ver "Datos")
│   └── sample/                 # datos sintéticos para probar
├── requirements.txt
└── requirements-dev.txt
```

## Instalación

```bash
git clone https://github.com/<usuario>/pipeline-semana-ingenieria.git
cd pipeline-semana-ingenieria
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
```

## Uso

**Con los archivos reales**: cópialos a `data/raw/` y ejecuta:

```bash
python main.py \
  --datos data/raw/Programa_32IIT_21-09.xlsx \
  --diccionario data/raw/Diccionario_Datos_Semana_Ingenieria.xlsx \
  --salida output
```

**Con los datos de muestra:**

```bash
python main.py --datos data/sample/programa_muestra.xlsx --diccionario data/sample/diccionario_muestra.xlsx
```

**Notebook:** abre `notebooks/Laboratorio_12.ipynb`. Si no encuentra los archivos reales en `data/raw/`, usa los de muestra. Para Google Colab, la primera celda trae las instrucciones para clonar el repo.

El pipeline termina con código `0` si todo salió bien, y con `1` si se detuvo en la carga o en el layout.

## Salidas (`output/`)

| Archivo | Contenido |
|---|---|
| `datos_procesados.xlsx` | Registros aceptados con el esquema final: `id_evento`, campos en snake_case, `duracion_horas`, `num_dias` y `dia_semana`. |
| `registros_rechazados.xlsx` | Registros rechazados con sus valores originales, `fila_excel` y `motivo_rechazo`. Se escribe aunque esté vacío. |
| `bitacora_limpieza.xlsx` | Cada celda corregida, con su valor original y su valor limpio. |
| `reporte_validacion.xlsx` | Errores por regla, antes y después de la limpieza. |
| `pipeline.log` | Registro de la ejecución. |

## Datos

- `data/sample/` contiene datos **sintéticos** generados con `scripts/generar_datos_muestra.py`. Incluyen a propósito casos sucios y casos que deben rechazarse. No son el programa real del evento.
- `data/raw/` está en `.gitignore`, porque el programa real incluye nombres de personas. Si tienen permiso para publicarlo, quiten esas líneas del `.gitignore`.

## Pruebas

```bash
pytest -q
```

Las pruebas cubren cada etapa y el pipeline completo con los datos de muestra. Además, GitHub Actions las corre en cada push (`.github/workflows/tests.yml`).
