# UniConferencias — Pipeline + Página web

## Archivos
- `pipeline.py`: procesa el Excel, valida/selecciona/transforma y crea `conferencias.json`.
- `index.html`, `styles.css`, `script.js`: interfaz web, búsqueda, filtros, agenda local y enlace Outlook.
- `conferencias.json`: lo genera automáticamente el pipeline.
- `Diccionario_Datos_Semana_Ingenieria.xlsx`: diccionario que usa el pipeline (colócalo aquí).
- `archivo_datos.xlsx`: Excel de datos (debe ser el único Excel de entrada adicional en esta carpeta).

## Uso
1. Instala dependencias si hace falta: `pip install pandas openpyxl`.
2. Coloca el diccionario y el Excel de entrada en esta carpeta.
3. Ejecuta `python pipeline.py`.
4. Inicia el servidor web desde esta carpeta: `python -m http.server 8000`.
5. Abre `http://localhost:8000`.

## Nota
El Excel de entrada debe tener los encabezados esperados por el pipeline. El campo campus no está presente en el esquema actual, así que se muestra como “No especificado” hasta que se incorpore al diccionario/Excel.
