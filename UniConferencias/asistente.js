// Conversación con el agente. Cada respuesta trae un texto y las tablas con los datos de las actividades.
const API_AGENTE = "/api/agente";
const CLAVE_CONVERSACION = "uniconferencias-conversacion";
const CLAVE_SESION = "uniconferencias-sesion";
const COLUMNAS_ANCHAS = new Set(["Título"]);
const COLUMNAS_SIN_CORTE = new Set(["Día", "Horario", "Eventos"]);

const mensajes = document.getElementById("chat-messages");
const formulario = document.getElementById("chat-form");
const entrada = document.getElementById("question");
const boton = document.getElementById("ask-button");
const intro = document.getElementById("chat-intro");
const nueva = document.getElementById("chat-new");

// La conversación se conserva mientras la pestaña siga abierta, aunque se vuelva al programa
let conversacion = leer(CLAVE_CONVERSACION, []);

function leer(clave, porDefecto) {
  try { return JSON.parse(sessionStorage.getItem(clave)) ?? porDefecto; }
  catch { return porDefecto; }
}
function guardar(clave, valor) {
  try { sessionStorage.setItem(clave, JSON.stringify(valor)); } catch { /* sin almacenamiento disponible */ }
}
function sesion() {
  // Agrupa las preguntas de esta conversación en el historial del agente
  let id = leer(CLAVE_SESION, null);
  if (!id && window.crypto && crypto.randomUUID) {
    id = crypto.randomUUID();
    guardar(CLAVE_SESION, id);
  }
  return id || undefined;
}
// Todo el contenido se inserta como texto: ni lo que escribe el modelo ni los datos se interpretan como HTML
function crear(etiqueta, clase, texto) {
  const elemento = document.createElement(etiqueta);
  if (clase) elemento.className = clase;
  if (texto !== undefined) elemento.textContent = texto;
  return elemento;
}

function crearTabla(tabla) {
  const figura = crear("figure", "chat-table");
  figura.appendChild(crear("figcaption", "", tabla.titulo));
  const elementoTabla = crear("table");
  const encabezado = elementoTabla.createTHead().insertRow();
  tabla.columnas.forEach(columna => {
    const celda = crear("th", "", columna);
    celda.scope = "col";
    encabezado.appendChild(celda);
  });
  const cuerpo = elementoTabla.createTBody();
  tabla.filas.forEach(fila => {
    const renglon = cuerpo.insertRow();
    fila.forEach((valor, i) => {
      const columna = tabla.columnas[i];
      const celda = renglon.insertCell();
      if (COLUMNAS_ANCHAS.has(columna)) celda.className = "wide";
      if (COLUMNAS_SIN_CORTE.has(columna)) celda.className = "nowrap";
      if (columna === "Enlace" && valor.startsWith("https://")) {
        const enlace = crear("a", "", "Unirse ↗");
        enlace.href = valor;
        enlace.target = "_blank";
        enlace.rel = "noopener noreferrer";
        celda.appendChild(enlace);
      } else {
        celda.textContent = valor;
      }
    });
  });
  const desplazable = crear("div", "chat-table-scroll");
  desplazable.appendChild(elementoTabla);
  figura.appendChild(desplazable);
  if (tabla.nota) figura.appendChild(crear("p", "chat-table-note", tabla.nota));
  return figura;
}
function mostrarPregunta(texto) {
  mensajes.appendChild(crear("div", "chat-message user", texto));
}
function mostrarRespuesta(datos) {
  const mensaje = crear("div", "chat-message agent");
  mensaje.appendChild(crear("p", "chat-text", datos.respuesta));
  (datos.tablas || []).forEach(tabla => mensaje.appendChild(crearTabla(tabla)));
  if (datos.busqueda) mensaje.appendChild(crear("p", "chat-meta", `Búsqueda: ${datos.busqueda}`));
  mensajes.appendChild(mensaje);
  return mensaje;
}
function conConversacion(hay) {
  intro.hidden = hay;
  nueva.hidden = !hay;
}

async function preguntar(pregunta) {
  conConversacion(true);
  mostrarPregunta(pregunta);
  const espera = crear("div", "chat-message agent waiting", "Buscando en el programa…");
  mensajes.appendChild(espera);
  espera.scrollIntoView({behavior: "smooth", block: "end"});
  boton.disabled = true;
  entrada.disabled = true;
  try {
    const respuesta = await fetch(API_AGENTE, {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({pregunta, sesion: sesion()})
    });
    const datos = await respuesta.json().catch(() => ({}));
    if (!respuesta.ok) throw new Error(typeof datos.detail === "string" ? datos.detail : `HTTP ${respuesta.status}`);
    espera.remove();
    const mostrado = {respuesta: datos.respuesta, tablas: datos.tablas, busqueda: datos.busqueda};
    mostrarRespuesta(mostrado).scrollIntoView({behavior: "smooth", block: "start"});
    conversacion.push({pregunta, respuesta: mostrado});
    guardar(CLAVE_CONVERSACION, conversacion.slice(-20));
  } catch (error) {
    espera.remove();
    const aviso = crear("div", "chat-message agent error", `El asistente no pudo responder: ${error.message}`);
    mensajes.appendChild(aviso);
    aviso.scrollIntoView({behavior: "smooth", block: "end"});
  } finally {
    boton.disabled = false;
    entrada.disabled = false;
    entrada.focus();
  }
}

formulario.addEventListener("submit", evento => {
  evento.preventDefault();
  const pregunta = entrada.value.trim();
  if (!pregunta || boton.disabled) return;
  entrada.value = "";
  preguntar(pregunta);
});
document.getElementById("chat-suggestions").addEventListener("click", evento => {
  const sugerencia = evento.target.closest(".chip");
  if (sugerencia && !boton.disabled) preguntar(sugerencia.textContent);
});
nueva.addEventListener("click", () => {
  conversacion = [];
  sessionStorage.removeItem(CLAVE_CONVERSACION);
  sessionStorage.removeItem(CLAVE_SESION);
  mensajes.replaceChildren();
  conConversacion(false);
  entrada.focus();
});

conversacion.forEach(turno => {
  mostrarPregunta(turno.pregunta);
  mostrarRespuesta(turno.respuesta);
});
conConversacion(conversacion.length > 0);
entrada.focus();
