"""Consulta estructurada: los filtros que el modelo extrae de una pregunta.

El modelo devuelve un JSON restringido por `esquema()`. Aun así, cada campo se
valida aquí contra el catálogo real: lo que no sea válido se descarta en lugar
de convertirse en un filtro inventado.
"""

import re
import unicodedata
from dataclasses import dataclass, fields
from datetime import date, time

MODALIDADES = ("presencial", "virtual")
_SIN_VALOR = {"", "null", "none", "ninguno", "ninguna", "n/a"}
_HORA = re.compile(r"^(\d{1,2})(?:[:.](\d{2}))?(?::\d{2})?$")


def sin_acentos(texto: str) -> str:
    """Minúsculas y sin acentos, para comparar textos escritos de formas distintas."""
    plano = unicodedata.normalize("NFKD", str(texto))
    return "".join(c for c in plano if not unicodedata.combining(c)).lower().strip()


def palabras(texto: str) -> list[str]:
    """Palabras de un texto, en minúsculas y sin acentos."""
    return re.findall(r"[a-z0-9]+", sin_acentos(texto))


def _comun(a: str, b: str) -> int:
    """Número de letras iniciales que comparten dos palabras."""
    return next((i for i, (x, y) in enumerate(zip(a, b)) if x != y), min(len(a), len(b)))


def variantes(a: str, b: str) -> bool:
    """True si son la misma palabra salvo la terminación: sensor/sensores, dron/drones."""
    corta = min(len(a), len(b))
    return a == b or (corta >= 4 and _comun(a, b) == corta and abs(len(a) - len(b)) <= 2)


def emparentadas(a: str, b: str) -> bool:
    """True si comparten raíz, aunque cambie más que la terminación: deportes/deportiva.

    Deben coincidir al menos 6 letras iniciales y la mayor parte de la palabra
    más corta, para no unir "presenciales" con "presentación".
    """
    comun = _comun(a, b)
    return variantes(a, b) or (comun >= 6 and comun >= 0.7 * min(len(a), len(b)))


@dataclass(frozen=True)
class Consulta:
    actividad: str | None = None    # clase de actividad del catálogo
    modalidad: str | None = None    # presencial | virtual (columna `tipo`)
    fecha: date | None = None
    hora_desde: time | None = None
    hora_hasta: time | None = None
    tema: str | None = None         # se resuelve con la búsqueda por vectores

    @property
    def vacia(self) -> bool:
        """Sin filtros ni tema: la pregunta es general sobre el programa."""
        return all(getattr(self, campo.name) is None for campo in fields(self))

    def como_dict(self) -> dict:
        """Versión serializable (para guardar en la bitácora de interacciones)."""
        return {
            "actividad": self.actividad,
            "modalidad": self.modalidad,
            "fecha": self.fecha.isoformat() if self.fecha else None,
            "hora_desde": f"{self.hora_desde:%H:%M}" if self.hora_desde else None,
            "hora_hasta": f"{self.hora_hasta:%H:%M}" if self.hora_hasta else None,
            "tema": self.tema,
        }

    def descripcion(self) -> str:
        """Los filtros en palabras, para explicar qué se buscó."""
        partes = []
        if self.actividad:
            partes.append(f"actividad {self.actividad}")
        if self.modalidad:
            partes.append(f"modalidad {self.modalidad}")
        if self.fecha:
            partes.append(f"día {self.fecha.isoformat()}")
        if self.hora_desde and self.hora_hasta:
            if self.hora_desde == self.hora_hasta:
                partes.append(f"a las {self.hora_desde:%H:%M}")
            else:
                partes.append(f"entre las {self.hora_desde:%H:%M} y las {self.hora_hasta:%H:%M}")
        elif self.hora_desde:
            partes.append(f"a partir de las {self.hora_desde:%H:%M}")
        elif self.hora_hasta:
            partes.append(f"antes de las {self.hora_hasta:%H:%M}")
        if self.tema:
            partes.append(f"tema «{self.tema}»")
        return ", ".join(partes) if partes else "sin filtros"


def esquema(actividades: list[str], fechas: list[date]) -> dict:
    """JSON Schema que restringe la salida del modelo a valores del catálogo."""
    hora = {"type": ["string", "null"]}
    propiedades = {
        "actividad": {"enum": [*actividades, None]},
        "modalidad": {"enum": [*MODALIDADES, None]},
        "fecha": {"enum": [*(f.isoformat() for f in fechas), None]},
        "hora_desde": hora,
        "hora_hasta": hora,
        "tema": {"type": ["string", "null"]},
    }
    return {"type": "object", "properties": propiedades, "required": list(propiedades)}


def _texto(valor) -> str | None:
    if not isinstance(valor, str) or sin_acentos(valor) in _SIN_VALOR:
        return None
    return valor.strip()


def a_hora(valor, hora_min: time | None = None) -> time | None:
    """Acepta '10', '9:30', '09:30' o '09:30:00'; cualquier otra cosa se descarta.

    hora_min: hora a la que empieza el programa. Una hora anterior solo puede
    ser de la tarde, así que "la 1" se entiende como las 13:00.
    """
    coincidencia = _HORA.match(_texto(valor) or "")
    if not coincidencia:
        return None
    horas, minutos = int(coincidencia[1]), int(coincidencia[2] or 0)
    if horas >= 24 or minutos >= 60:
        return None
    hora = time(horas, minutos)
    if hora_min and hora < hora_min and horas < 12:
        hora = time(horas + 12, minutos)
    return hora


def _a_fecha(valor, fechas: list[date]) -> date | None:
    try:
        fecha = date.fromisoformat(_texto(valor) or "")
    except ValueError:
        return None
    return fecha if fecha in fechas else None


def _del_catalogo(valor, opciones) -> str | None:
    """La opción del catálogo que coincide con `valor` sin importar mayúsculas ni acentos."""
    buscado = sin_acentos(_texto(valor) or "")
    return next((opcion for opcion in opciones if sin_acentos(opcion) == buscado), None)


def _nombrada(actividad: str | None, pregunta: str) -> str | None:
    """La actividad solo vale como filtro si la pregunta la nombra.

    Evita que el modelo la deduzca de otra palabra ("torneo" -> Concurso,
    "plática" -> Ponencia) y deje fuera justo los eventos que se buscaban.
    """
    if actividad and any(emparentadas(palabras(actividad)[0], p) for p in palabras(pregunta)):
        return actividad
    return None


def _actividad_del_tema(tema: str, actividades: list[str]) -> str | None:
    """Si el tema es en realidad una clase de actividad ("deportes" -> Deportiva), devuelve cuál."""
    partes = palabras(tema)
    if len(partes) != 1:
        return None
    return next((a for a in actividades if emparentadas(palabras(a)[0], partes[0])), None)


def desde_modelo(datos: dict, pregunta: str, actividades: list[str], fechas: list[date],
                 hora_min: time | None = None) -> Consulta:
    """Convierte el JSON del modelo en una Consulta válida."""
    desde, hasta = a_hora(datos.get("hora_desde"), hora_min), a_hora(datos.get("hora_hasta"), hora_min)
    if desde and hasta and desde > hasta:
        desde, hasta = hasta, desde
    actividad = _nombrada(_del_catalogo(datos.get("actividad"), actividades), pregunta)
    tema = _texto(datos.get("tema"))
    if tema and not actividad and (como_actividad := _actividad_del_tema(tema, actividades)):
        actividad, tema = como_actividad, None
    return Consulta(
        actividad=actividad,
        modalidad=_del_catalogo(datos.get("modalidad"), MODALIDADES),
        fecha=_a_fecha(datos.get("fecha"), fechas),
        hora_desde=desde,
        hora_hasta=hasta,
        tema=tema,
    )
