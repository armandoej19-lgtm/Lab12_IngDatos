# UniConferencias — Página web

Página del programa de la Semana de Ingeniería: búsqueda, filtros, agenda local,
enlace a Outlook y un asistente que responde preguntas sobre el programa.

## Archivos
- `index.html`, `styles.css`, `script.js`: la página.
- `Programa_32IIT_21-09.xlsx` y `Diccionario_Datos_Semana_Ingenieria.xlsx`: copias de los
  archivos de entrada. El pipeline los lee de `data/raw/`, no de aquí.

Esta carpeta ya no tiene un pipeline propio ni `conferencias.json`. Los datos salen del
único pipeline del proyecto (`python main.py`, en la raíz), que los guarda en PostgreSQL,
y la página los pide al servidor:

- `GET  /api/eventos`: el programa completo.
- `POST /api/agente` con `{"pregunta": "..."}`: la respuesta del asistente y los eventos que encontró.

## Uso
Desde la raíz del proyecto (ver el README principal para la instalación):

1. Ejecuta el pipeline: `python main.py`.
2. Inicia el servidor: `python -m agente.servidor`.
3. Abre `http://localhost:8000`.

El servidor entrega la página y la API juntas, así que no hace falta `python -m http.server`.

## Nota
El campo campus no está en el diccionario ni en el Excel, así que se muestra como
«No especificado» hasta que se incorpore.
