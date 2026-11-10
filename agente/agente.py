"""Agente del programa de la Semana de Ingeniería.

Cada pregunta sigue cuatro pasos:

1. Interpretar: el modelo convierte la pregunta en filtros (Consulta).
2. Recuperar: los filtros se resuelven con SQL en PostgreSQL y el tema con
   los vectores de los eventos.
3. Redactar: el modelo responde en español a partir de lo encontrado. El
   listado de eventos lo arma el programa con los datos de la base, así que
   títulos, horarios y lugares nunca dependen de lo que escriba el modelo.
4. Registrar: la interacción queda guardada en `agente_interacciones`.
"""

import logging
import time as reloj
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from uuid import UUID, uuid4

import numpy as np

from pipeline.config import DIAS_ES

from . import config
from .almacen import Almacen, Catalogo
from .consulta import Consulta, desde_modelo, esquema, palabras, sin_acentos, variantes
from .modelo import Modelo

log = logging.getLogger(__name__)

# Campos donde se busca el tema de forma literal
CAMPOS_NOMBRE = ("ponente", "empresa_institucion", "salon", "maestro_ceremonias")
CAMPOS_LITERALES = ("titulo", "actividad", *CAMPOS_NOMBRE)

INSTRUCCIONES_INTERPRETE = """\
Extraes filtros de búsqueda de preguntas sobre el programa de la Semana de Ingeniería.
Responde con un JSON con estos campos. Usa null en los que la pregunta no mencione; no inventes filtros.

- actividad: clase de actividad por la que se pregunta, en singular. Opciones: {actividades}.
- modalidad: "presencial" o "virtual".
- fecha: día por el que se pregunta. Opciones: {fechas}.
- hora_desde y hora_hasta: horario en formato de 24 horas "HH:MM".
- tema: asunto, palabra clave, persona, empresa o lugar por el que se pregunta. No repitas aquí la actividad, la modalidad, la fecha ni la hora.

Horarios (las actividades son de {hora_min} a {hora_max}, así que "la 1" es 13:00 y "las 5" es 17:00):
- "entre las 10 y las 12": hora_desde "10:00", hora_hasta "12:00".
- una sola hora, como "a las 3 de la tarde": la misma en los dos campos, hora_desde "15:00" y hora_hasta "15:00".
- "después de las 4 pm" o "a partir de las 4 pm": hora_desde "16:00", hora_hasta null.
- "antes de las 10": hora_desde null, hora_hasta "10:00".
{franjas}

Ejemplos:
{ejemplos}"""

INSTRUCCIONES_FILTRO = """\
Eliges, de una lista de actividades de un congreso de ingeniería, las que tratan sobre un tema.
Recibes el tema y una lista numerada de actividades: título y, entre paréntesis, la clase de actividad.
Responde con un JSON con los números de las actividades que tratan sobre ese tema o sobre un tema muy cercano.
- No cuenta una actividad que solo comparte el área general (ingeniería, industria, tecnología, ciencia).
- No cuenta un título que no dice de qué trata ("Pendiente", "Por confirmar", "Por definir").
- Si ninguna trata del tema, responde con una lista vacía."""

ESQUEMA_FILTRO = {
    "type": "object",
    "properties": {"relacionados": {"type": "array", "items": {"type": "integer"}}},
    "required": ["relacionados"],
}

INSTRUCCIONES_REDACTOR = """\
Eres el asistente del programa de la Semana de Ingeniería. Respondes siempre en español.
Recibes una pregunta y los datos que se encontraron en la base de datos del programa.

- Responde de forma directa, en tres frases como máximo.
- Usa solo los datos recibidos. No inventes eventos, horarios, lugares ni personas.
- Si la pregunta no trata del programa, di que solo puedes responder sobre el programa."""


@dataclass
class Respuesta:
    pregunta: str
    consulta: Consulta
    eventos: list[dict]     # resultados, ya ordenados
    texto: str              # lo que redactó el modelo
    listado: str            # eventos formateados por el programa (vacío si no aplica)

    @property
    def completa(self) -> str:
        return f"{self.texto}\n\n{self.listado}" if self.listado else self.texto


# --------------------------------------------------------------------------
# Formato
# --------------------------------------------------------------------------
def dia_largo(fecha: date) -> str:
    """'lunes 21 de septiembre'"""
    return f"{DIAS_ES[fecha.weekday()].lower()} {fecha.day} de {config.MESES[fecha.month - 1]}"


def dia_corto(fecha: date) -> str:
    """'lun 21 sep'"""
    return f"{sin_acentos(DIAS_ES[fecha.weekday()])[:3]} {fecha.day} {config.MESES[fecha.month - 1][:3]}"


def _cuando(evento: dict, dia: Callable[[date], str]) -> str:
    fechas = dia(evento["fecha_inicio"])
    if evento["fecha_fin"] != evento["fecha_inicio"]:
        fechas += f" al {dia(evento['fecha_fin'])}"
    return f"{fechas}, {evento['hora_inicio']:%H:%M}-{evento['hora_fin']:%H:%M}"


def _lugar(evento: dict) -> str:
    return evento["salon"] or evento["tipo"]


def _frase_evento(evento: dict, con_presentador: bool = False) -> str:
    """Un evento en una línea, como lo recibe el modelo para redactar."""
    dias = dia_largo(evento["fecha_inicio"])
    if evento["fecha_fin"] != evento["fecha_inicio"]:
        dias = f"todos los días del {dias} al {dia_largo(evento['fecha_fin'])}"
    frase = (f"- «{evento['titulo']}»: {evento['actividad']}, {dias}, "
             f"de {evento['hora_inicio']:%H:%M} a {evento['hora_fin']:%H:%M}, {_lugar(evento)}")
    if evento["ponente"]:
        frase += f", ponente {evento['ponente']}"
    if con_presentador and evento["maestro_ceremonias"]:
        frase += f", presenta {evento['maestro_ceremonias']}"
    return frase


def formatear_listado(eventos: list[dict], total: int | None = None) -> str:
    """Listado numerado de eventos, con los datos tal como están en la base."""
    lineas = []
    for numero, e in enumerate(eventos, start=1):
        lineas.append(f"{numero:>2}. {_cuando(e, dia_corto)} | {e['actividad']} | {_lugar(e)}")
        persona = " - ".join(v for v in (e["ponente"], e["empresa_institucion"]) if v)
        lineas.append(f"    {e['titulo']}" + (f" ({persona})" if persona else ""))
        if e["enlace"]:
            lineas.append(f"    {e['enlace']}")
    if total and total > len(eventos):
        lineas.append(f"(Se muestran {len(eventos)} de {total}. Acota la pregunta por día, horario o tema para ver el resto.)")
    return "\n".join(lineas)


def _conteos(conteos: dict) -> str:
    return ", ".join(f"{nombre} ({n})" for nombre, n in conteos.items())


# --------------------------------------------------------------------------
# Búsqueda por tema
# --------------------------------------------------------------------------
def texto_evento(evento: dict) -> str:
    """Texto que se vectoriza de cada evento: el título y la clase de actividad describen su tema."""
    return f"{evento['titulo']} ({evento['actividad']})"


def nombra(tema: str, evento: dict, campos: tuple[str, ...] = CAMPOS_LITERALES) -> bool:
    """True si el evento menciona en `campos` todas las palabras del tema (o su plural)."""
    buscadas = [p for p in palabras(tema) if p not in config.PALABRAS_VACIAS]
    presentes = palabras(" ".join(evento[campo] or "" for campo in campos))
    return bool(buscadas) and all(any(variantes(b, p) for p in presentes) for b in buscadas)


def ordenar_por_similitud(vector_tema: list[float], eventos: list[dict],
                          vectores: dict[int, list[float]]) -> list[tuple[dict, float]]:
    """(evento, similitud coseno con el tema), del más al menos parecido. Sin vector, la similitud es 0."""
    tema = np.asarray(vector_tema, dtype=float)
    tema /= np.linalg.norm(tema) or 1.0
    puntuados = []
    for evento in eventos:
        vector = vectores.get(evento["id_evento"])
        similitud = 0.0
        if vector is not None:
            vector = np.asarray(vector, dtype=float)
            similitud = float(vector @ tema / (np.linalg.norm(vector) or 1.0))
        puntuados.append((evento, similitud))
    return sorted(puntuados, key=lambda par: par[1], reverse=True)


def destacados(candidatos: list[tuple[dict, float]],
               minimo: float = config.SIMILITUD_MINIMA,
               margen: float = config.MARGEN_SIMILITUD) -> list[dict]:
    """Candidatos que casi igualan al más parecido y superan la similitud mínima."""
    if not candidatos:
        return []
    corte = max(minimo, candidatos[0][1] - margen)
    return [evento for evento, similitud in candidatos if similitud >= corte]


# --------------------------------------------------------------------------
# Agente
# --------------------------------------------------------------------------
class Agente:
    def __init__(self, almacen: Almacen, modelo: Modelo, sesion: UUID | None = None):
        self.almacen = almacen
        self.modelo = modelo
        self.sesion = sesion or uuid4()

    def preparar(self) -> int:
        """Comprueba que hay datos y genera los vectores que falten. Devuelve cuántos generó.

        Un vector falta si el evento no lo tiene, si es de otro modelo de
        embeddings o si se calculó con un texto distinto del actual.
        """
        self.almacen.catalogo()
        pendientes = [e for e in self.almacen.estado_vectores(self.modelo.embeddings)
                      if e["contenido"] != texto_evento(e)]
        for inicio in range(0, len(pendientes), config.LOTE_EMBEDDINGS):
            lote = pendientes[inicio:inicio + config.LOTE_EMBEDDINGS]
            textos = [texto_evento(e) for e in lote]
            vectores = self.modelo.vectorizar(textos)
            self.almacen.guardar_vectores(
                self.modelo.embeddings,
                [(e["id_evento"], texto, vector) for e, texto, vector in zip(lote, textos, vectores)])
            log.debug("Vectores generados: %d de %d", inicio + len(lote), len(pendientes))
        return len(pendientes)

    def preguntar(self, pregunta: str) -> Respuesta:
        """Responde una pregunta y la deja registrada."""
        inicio = reloj.perf_counter()
        catalogo = self.almacen.catalogo()
        consulta = self._interpretar(pregunta, catalogo)

        if consulta.vacia:
            respuesta = self._responder_resumen(pregunta, consulta, catalogo)
        else:
            respuesta = self._responder_busqueda(pregunta, consulta)

        self.almacen.registrar(
            self.sesion, pregunta, consulta, [e["id_evento"] for e in respuesta.eventos],
            respuesta.completa, self.modelo.chat, int((reloj.perf_counter() - inicio) * 1000))
        return respuesta

    # ----------------------------------------------------------------------
    # 1. Interpretar
    # ----------------------------------------------------------------------
    def _interpretar(self, pregunta: str, catalogo: Catalogo) -> Consulta:
        actividades, fechas = list(catalogo.actividades), list(catalogo.dias)
        instrucciones = INSTRUCCIONES_INTERPRETE.format(
            actividades=", ".join(actividades),
            fechas=", ".join(f"{f.isoformat()} ({dia_largo(f)})" for f in fechas),
            hora_min=f"{catalogo.hora_min:%H:%M}",
            hora_max=f"{catalogo.hora_max:%H:%M}",
            franjas="\n".join(f'- "en la {franja}": hora_desde "{desde}", hora_hasta "{hasta}".'
                              for franja, (desde, hasta) in config.FRANJAS.items()),
            ejemplos=_ejemplos(actividades, fechas),
        )
        datos = self.modelo.interpretar(instrucciones, f"Pregunta: {pregunta}", esquema(actividades, fechas))
        consulta = desde_modelo(datos, pregunta, actividades, fechas, catalogo.hora_min)
        log.debug("Pregunta interpretada: %s", consulta.descripcion())
        return consulta

    # ----------------------------------------------------------------------
    # 2. Recuperar
    # ----------------------------------------------------------------------
    def _por_tema(self, tema: str, eventos: list[dict]) -> list[dict]:
        """Eventos relacionados con el tema: primero los que lo nombran, después los afines.

        Los que nombran el tema entran siempre. Si el tema es una persona,
        empresa o lugar del programa, con ellos basta. Si no, se añaden los
        afines: los eventos cuyo vector está entre los más parecidos al tema y
        que el modelo confirma que tratan de él.
        """
        vectores = self.almacen.vectores(self.modelo.embeddings, [e["id_evento"] for e in eventos])
        ordenados = ordenar_por_similitud(self.modelo.vectorizar([tema])[0], eventos, vectores)
        nombrados = [evento for evento, _ in ordenados if nombra(tema, evento)]
        if any(nombra(tema, evento, CAMPOS_NOMBRE) for evento in nombrados):
            return nombrados

        # Sin nada que nombre el tema se exige además una similitud mínima: así una
        # pregunta sobre algo que no está en el programa no devuelve eventos al azar.
        minimo = 0.0 if nombrados else config.SIMILITUD_MINIMA
        ya_incluidos = {evento["id_evento"] for evento in nombrados}
        candidatos = [evento for evento in destacados(ordenados, minimo)
                      if evento["id_evento"] not in ya_incluidos][:config.CANDIDATOS_POR_TEMA]
        return nombrados + self._afines(tema, candidatos, hay_nombrados=bool(nombrados))

    def _afines(self, tema: str, candidatos: list[dict], hay_nombrados: bool) -> list[dict]:
        """De los candidatos, los que el modelo considera que tratan del tema."""
        if not candidatos:
            return []
        lista = "\n".join(f"{numero}. {texto_evento(evento)}" for numero, evento in enumerate(candidatos, 1))
        datos = self.modelo.interpretar(INSTRUCCIONES_FILTRO, f"Tema: {tema}\nActividades:\n{lista}", ESQUEMA_FILTRO)
        numeros = datos.get("relacionados")
        numeros = set(numeros) if isinstance(numeros, list) else set()
        elegidos = [evento for numero, evento in enumerate(candidatos, 1) if numero in numeros]
        # Si el modelo no elige ninguno y nada nombra el tema, deciden los vectores:
        # los candidatos ya son los más parecidos y superan la similitud mínima.
        return elegidos or ([] if hay_nombrados else candidatos)

    # ----------------------------------------------------------------------
    # 3. Redactar
    # ----------------------------------------------------------------------
    def _responder_resumen(self, pregunta, consulta, catalogo: Catalogo) -> Respuesta:
        """Pregunta general (sin filtros): se responde con el resumen del programa.

        Las cifras las muestra el programa debajo del texto, igual que el
        listado de eventos: el modelo no tiene que copiarlas ni contarlas.
        """
        dias = list(catalogo.dias)
        periodo = (f"{catalogo.total} eventos, del {dia_largo(dias[0])} al {dia_largo(dias[-1])} de {dias[-1].year}, "
                   f"entre las {catalogo.hora_min:%H:%M} y las {catalogo.hora_max:%H:%M}")
        cifras = "\n".join([
            f"Tipos de actividad ({len(catalogo.actividades)}): {_conteos(catalogo.actividades)}",
            f"Modalidad: {_conteos(catalogo.modalidades)}",
            "Eventos por día (los de varios días cuentan en cada uno): "
            + _conteos({dia_largo(d): n for d, n in catalogo.dias.items()}),
        ])
        datos = (f"Pregunta: {pregunta}\n\nPrograma: {periodo}.\n{cifras}\n\n"
                 "Debajo de tu respuesta se mostrarán estas cifras completas: no las copies todas. "
                 "Responde a la pregunta en dos o tres frases.")
        texto = self.modelo.redactar(INSTRUCCIONES_REDACTOR, datos) or f"El programa tiene {periodo}."
        return Respuesta(pregunta, consulta, [], texto, cifras)

    def _responder_busqueda(self, pregunta, consulta: Consulta) -> Respuesta:
        eventos = self.almacen.buscar(consulta)
        literales = 0
        if consulta.tema and eventos:
            eventos = self._por_tema(consulta.tema, eventos)
            literales = sum(nombra(consulta.tema, e) for e in eventos)

        if not eventos:
            texto = f"No encontré actividades con estas características: {consulta.descripcion()}."
            return Respuesta(pregunta, consulta, [], texto, "")

        ejemplos = eventos[:config.EVENTOS_PARA_MODELO]
        orden = "del más al menos relacionado con el tema" if consulta.tema else "en orden cronológico"
        datos = [
            f"Pregunta: {pregunta}",
            "",
            f"Búsqueda realizada: {consulta.descripcion()}. Todas las fechas son de {eventos[0]['fecha_inicio'].year}.",
            f"Eventos encontrados: {len(eventos)}.",
            "Por actividad: " + _conteos(Counter(e["actividad"] for e in eventos)) + ".",
            # con un día fijo todos ocurren ese día: el de inicio solo confundiría
            *(["Por día de inicio: " + _conteos(Counter(dia_largo(e["fecha_inicio"]) for e in eventos)) + "."]
              if not consulta.fecha else []),
            *([f"De ellos, {literales} nombran «{consulta.tema}»; los demás tratan temas afines."]
              if 0 < literales < len(eventos) else []),
            ("Los eventos" if len(ejemplos) == len(eventos) else f"Los primeros {len(ejemplos)} eventos") + f", {orden}:",
            *(_frase_evento(e, con_presentador=bool(consulta.tema)) for e in ejemplos),
            "",
            "El listado completo, con horarios y lugares, aparece debajo de la respuesta. "
            "Responde a la pregunta en dos o tres frases: di cuántos eventos se encontraron y menciona "
            "como máximo dos títulos. No enumeres los eventos ni menciones estas indicaciones.",
        ]
        texto = (self.modelo.redactar(INSTRUCCIONES_REDACTOR, "\n".join(datos))
                 or f"Encontré {len(eventos)} eventos ({consulta.descripcion()}).")
        mostrados = eventos[:config.MAX_LISTADO]
        return Respuesta(pregunta, consulta, mostrados, texto, formatear_listado(mostrados, len(eventos)))


def _ejemplos(actividades: list[str], fechas: list[date]) -> str:
    """Ejemplos de pregunta -> JSON armados con valores reales del catálogo."""
    actividad = actividades[0]
    plural = sin_acentos(actividad) + "s"
    fecha_a, fecha_b = fechas[len(fechas) // 2], fechas[min(1, len(fechas) - 1)]
    dia_a, dia_b = (DIAS_ES[f.weekday()].lower() for f in (fecha_a, fecha_b))
    tarde = config.FRANJAS["tarde"]

    def caso(pregunta: str, **filtros) -> str:
        campos = Consulta().como_dict() | filtros
        valores = ", ".join(f'"{campo}": ' + ("null" if valor is None else f'"{valor}"')
                            for campo, valor in campos.items())
        return f"Pregunta: {pregunta}\n{{{valores}}}"

    return "\n".join([
        caso(f"¿Qué {plural} hay entre las 10 y las 12?", actividad=actividad, hora_desde="10:00", hora_hasta="12:00"),
        caso(f"¿Qué {plural} están relacionadas con inteligencia artificial?", actividad=actividad,
             tema="inteligencia artificial"),
        caso("¿Qué tipos de actividad hay?"),
        caso("Hola, ¿qué puedes hacer?"),
        caso(f"¿Qué actividades virtuales hay el {dia_a}?", modalidad="virtual", fecha=fecha_a.isoformat()),
        caso("¿Cuántos eventos presenciales hay en la tarde?", modalidad="presencial",
             hora_desde=tarde[0], hora_hasta=tarde[1]),
        caso(f"¿Qué actividades hay el {dia_b}?", fecha=fecha_b.isoformat()),
        caso(f"¿Qué pláticas hay sobre energía solar el {dia_a} entre las 9 y la 1?", fecha=fecha_a.isoformat(),
             hora_desde="09:00", hora_hasta="13:00", tema="energía solar"),
        caso(f"¿Qué hay el {dia_b} a las 9?", fecha=fecha_b.isoformat(), hora_desde="09:00", hora_hasta="09:00"),
        caso("¿Hay algo de robótica después de las 4 pm?", hora_desde="16:00", tema="robótica"),
        caso("¿Dónde es el torneo de ajedrez?", tema="torneo de ajedrez"),
        caso("¿Qué da el Dr. Juan Pérez?", tema="Dr. Juan Pérez"),
    ])
