-- Esquema de la base de datos del programa de la Semana de Ingeniería.
--
-- Tablas neutrales (las puede consumir cualquier aplicación):
--     eventos, registros_rechazados, bitacora_limpieza, reporte_validacion,
--     incumplimientos_validacion
-- Tablas del agente (ninguna otra aplicación las necesita):
--     agente_vectores, agente_interacciones
--
-- Solo usa tipos estándar de PostgreSQL, sin extensiones. Los nombres van sin
-- esquema para que se creen en el search_path de la conexión.

-- --------------------------------------------------------------------------
-- Tablas neutrales: las reemplaza la etapa 8 del pipeline en cada ejecución
-- --------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS eventos (
    id_evento           integer PRIMARY KEY,
    actividad           text NOT NULL,
    fecha_inicio        date NOT NULL,
    fecha_fin           date NOT NULL,
    hora_inicio         time NOT NULL,
    hora_fin            time NOT NULL,
    tipo                text NOT NULL,
    salon               text,
    titulo              text NOT NULL,
    ponente             text,
    empresa_institucion text,
    maestro_ceremonias  text,
    enlace              text,
    duracion_horas      numeric(5, 2) NOT NULL,
    num_dias            integer NOT NULL,
    dia_semana          text NOT NULL,
    cargado_en          timestamptz NOT NULL DEFAULT now()
);
COMMENT ON TABLE eventos IS 'Actividades aceptadas por el pipeline, con el esquema final.';
COMMENT ON COLUMN eventos.tipo IS 'Modalidad: presencial o virtual.';
COMMENT ON COLUMN eventos.salon IS 'Lugar físico; nulo en eventos virtuales.';
COMMENT ON COLUMN eventos.hora_inicio IS 'Horario diario: se repite cada día entre fecha_inicio y fecha_fin.';

CREATE TABLE IF NOT EXISTS registros_rechazados (
    fila_excel          integer NOT NULL,
    actividad           text,
    fecha_inicio        text,
    fecha_fin           text,
    hora_inicio         text,
    hora_fin            text,
    tipo                text,
    salon               text,
    titulo              text,
    ponente             text,
    empresa_institucion text,
    maestro_ceremonias  text,
    enlace              text,
    motivo_rechazo      text NOT NULL,
    cargado_en          timestamptz NOT NULL DEFAULT now()
);
COMMENT ON TABLE registros_rechazados IS
    'Registros que incumplen alguna regla. Conservan el valor original del Excel, por eso todo es texto.';

CREATE TABLE IF NOT EXISTS bitacora_limpieza (
    fila_excel     integer NOT NULL,
    columna        text NOT NULL,
    valor_original text,
    valor_limpio   text,
    cargado_en     timestamptz NOT NULL DEFAULT now()
);
COMMENT ON TABLE bitacora_limpieza IS 'Cada celda que corrigió la etapa de limpieza, antes y después.';

CREATE TABLE IF NOT EXISTS reporte_validacion (
    validacion          text PRIMARY KEY,
    antes_de_limpieza   integer NOT NULL,
    despues_de_limpieza integer NOT NULL,
    cargado_en          timestamptz NOT NULL DEFAULT now()
);
COMMENT ON TABLE reporte_validacion IS 'Registros que incumplen cada regla, antes y después de la limpieza.';

CREATE TABLE IF NOT EXISTS incumplimientos_validacion (
    fila_excel integer NOT NULL,
    regla      text NOT NULL,
    cargado_en timestamptz NOT NULL DEFAULT now()
);
COMMENT ON TABLE incumplimientos_validacion IS
    'Detalle de la validación de los datos originales: una fila por cada regla que incumple cada registro.';

-- --------------------------------------------------------------------------
-- Tablas del agente
-- --------------------------------------------------------------------------
-- Los vectores se borran junto con su evento: tras cada carga el agente los regenera.
CREATE TABLE IF NOT EXISTS agente_vectores (
    id_evento integer PRIMARY KEY REFERENCES eventos (id_evento) ON DELETE CASCADE,
    modelo    text NOT NULL,
    contenido text NOT NULL,
    embedding real[] NOT NULL,
    creado_en timestamptz NOT NULL DEFAULT now()
);
COMMENT ON TABLE agente_vectores IS 'Vector (embedding) de cada evento para la búsqueda por tema.';
COMMENT ON COLUMN agente_vectores.modelo IS 'Modelo de embeddings que generó el vector.';
COMMENT ON COLUMN agente_vectores.contenido IS 'Texto del evento que se vectorizó.';

CREATE TABLE IF NOT EXISTS agente_interacciones (
    id_interaccion bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    sesion         uuid NOT NULL,
    pregunta       text NOT NULL,
    filtros        jsonb NOT NULL,
    eventos        integer[] NOT NULL,
    respuesta      text NOT NULL,
    modelo         text NOT NULL,
    duracion_ms    integer NOT NULL,
    creado_en      timestamptz NOT NULL DEFAULT now()
);
COMMENT ON TABLE agente_interacciones IS 'Historial de preguntas y respuestas del agente.';
COMMENT ON COLUMN agente_interacciones.sesion IS 'Agrupa las preguntas de una misma conversación.';
COMMENT ON COLUMN agente_interacciones.filtros IS 'Filtros que el modelo extrajo de la pregunta.';
COMMENT ON COLUMN agente_interacciones.eventos IS
    'id_evento de los resultados mostrados. Sin llave foránea: los ids cambian en cada carga.';
