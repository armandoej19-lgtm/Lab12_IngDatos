// La página se sirve desde el mismo servidor que la API (python -m agente.servidor).
const API_EVENTOS = "/api/eventos";
const API_AGENTE = "/api/agente";

const contenedor = document.getElementById("conferencias-container");
const contador = document.getElementById("results-count");
const statusBox = document.getElementById("status");
const searchInput = document.getElementById("search");
const campusSelect = document.getElementById("campus");
const daySelect = document.getElementById("day");
const categorySelect = document.getElementById("category");
const titleView = document.getElementById("view-title");
const subtitleView = document.getElementById("view-subtitle");
const agendaBadge = document.getElementById("agenda-badge");
const questionInput = document.getElementById("question");
const askButton = document.getElementById("ask-button");
const answerBox = document.getElementById("assistant-answer");
const answerText = document.getElementById("assistant-text");
const answerDetail = document.getElementById("assistant-detail");
const answerSearch = document.getElementById("assistant-search");
const answerClear = document.getElementById("assistant-clear");

const VISTAS = {
  conferencias: ["Conferencias disponibles", "Consulta los horarios y encuentra las actividades que te interesan."],
  calendario: ["Calendario de conferencias", "Eventos ordenados por fecha y hora."],
  agenda: ["Mi agenda", "Aquí aparecen las conferencias que guardaste."],
  asistente: ["Resultados del asistente", "Eventos que encontró el asistente para tu pregunta."]
};

let conferencias = [];
let resultadosAsistente = [];
let vistaActual = "conferencias";
let agenda = cargarAgenda();

function cargarAgenda() {
  try { return JSON.parse(localStorage.getItem("uniconferencias-agenda") || "[]"); }
  catch { return []; }
}
function guardarAgenda() {
  localStorage.setItem("uniconferencias-agenda", JSON.stringify(agenda));
  agendaBadge.textContent = agenda.length;
}
function fechaLocal(iso) {
  if (!iso) return "Fecha por confirmar";
  const [y,m,d] = iso.split("-").map(Number);
  return new Date(y, m-1, d).toLocaleDateString("es-MX",{weekday:"long",day:"numeric",month:"long",year:"numeric"});
}
function diaISO(iso) {
  if (!iso) return "";
  const [y,m,d] = iso.split("-").map(Number);
  return new Date(y,m-1,d).toLocaleDateString("es-MX",{weekday:"long"}).toLowerCase();
}
function escapeHTML(value) {
  return String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
}
function idEnAgenda(id) { return agenda.some(item => String(item) === String(id)); }

function llenarFiltros() {
  const campus = [...new Set(conferencias.map(c=>c.campus).filter(Boolean))].sort();
  const areas = [...new Set(conferencias.map(c=>c.area).filter(Boolean))].sort();
  campus.forEach(v => campusSelect.add(new Option(v,v)));
  areas.forEach(v => categorySelect.add(new Option(v,v)));
}
function crearTarjeta(c) {
  const article = document.createElement("article");
  article.className = "conference-row";
  const enAgenda = idEnAgenda(c.id);
  const enlaceOutlook = crearEnlaceOutlook(c);
  article.innerHTML = `
    <div class="conference-info">
      <span class="category-tag">${escapeHTML(c.area || "General")}</span>
      <h3>${escapeHTML(c.titulo)}</h3>
      <p class="speaker">Ponente: ${escapeHTML(c.ponente || "Por confirmar")}</p>
      ${c.descripcion ? `<p class="description">${escapeHTML(c.descripcion)}</p>` : ""}
    </div>
    <div class="location-info"><strong>${escapeHTML(c.campus || "Campus no especificado")}</strong><span>${escapeHTML(c.ubicacion || "Ubicación por confirmar")}</span></div>
    <div class="time-info"><strong>${escapeHTML(c.horaInicio || "--:--")} – ${escapeHTML(c.horaFin || "--:--")}</strong><span>${escapeHTML(fechaLocal(c.fecha))}</span></div>
    <div class="actions">
      <button class="agenda-button ${enAgenda?"saved":""}" data-agenda="${escapeHTML(c.id)}">${enAgenda?"✓ En mi agenda":"+ Mi agenda"}</button>
      ${c.enlace ? `<a class="join-button" href="${escapeHTML(c.enlace)}" target="_blank" rel="noopener noreferrer">Unirse en Teams ↗</a>` : ""}
      ${enlaceOutlook ? `<a class="outlook-button" href="${enlaceOutlook}" target="_blank" rel="noopener noreferrer">Outlook ↗</a>` : ""}
    </div>`;
  return article;
}
function crearEnlaceOutlook(c) {
  if (!c.fecha || !c.horaInicio || !c.horaFin) return "";
  const params = new URLSearchParams({
    subject: c.titulo || "Conferencia universitaria",
    startdt: `${c.fecha}T${c.horaInicio}:00`,
    enddt: `${c.fecha}T${c.horaFin}:00`,
    location: `${c.campus || ""} - ${c.ubicacion || ""}`,
    body: `Ponente: ${c.ponente || "Por confirmar"}\nÁrea: ${c.area || ""}\n${c.descripcion || ""}`
  });
  return `https://outlook.office.com/calendar/0/deeplink/compose?${params.toString()}`;
}
function renderizar() {
  const texto = searchInput.value.trim().toLocaleLowerCase("es");
  const campus = campusSelect.value;
  const dia = daySelect.value;
  const area = categorySelect.value;
  // En la vista del asistente se parte de lo que él encontró, en su orden (lo más relacionado primero)
  const base = vistaActual === "asistente" ? resultadosAsistente : conferencias;
  let lista = base.filter(c => {
    const combinado = [c.titulo,c.ponente,c.area,c.descripcion,c.ubicacion,c.campus].join(" ").toLocaleLowerCase("es");
    return (!texto || combinado.includes(texto)) &&
      (!campus || c.campus === campus) &&
      (!dia || diaISO(c.fecha) === dia) &&
      (!area || c.area === area);
  });
  if (vistaActual === "agenda") lista = lista.filter(c=>idEnAgenda(c.id));
  if (vistaActual === "calendario") lista.sort((a,b)=>(a.fecha+a.horaInicio).localeCompare(b.fecha+b.horaInicio));
  contenedor.replaceChildren();
  lista.forEach(c=>contenedor.appendChild(crearTarjeta(c)));
  contador.textContent = `${lista.length} ${lista.length===1?"conferencia":"conferencias"}`;
  statusBox.hidden = lista.length > 0;
  statusBox.textContent = vistaActual==="agenda" && !lista.length ? "Tu agenda está vacía. Agrega conferencias con el botón «+ Mi agenda»." : "No hay conferencias que coincidan con los filtros.";
}
function cambiarVista(view) {
  vistaActual = view;
  document.querySelectorAll("[data-view]").forEach(b=>b.classList.toggle("active",b.dataset.view===view));
  [titleView.textContent, subtitleView.textContent] = VISTAS[view];
  renderizar();
}
function limpiarFiltros() {
  searchInput.value=""; campusSelect.value=""; daySelect.value=""; categorySelect.value="";
}
async function obtenerConferencias() {
  try {
    const respuesta = await fetch(API_EVENTOS,{cache:"no-store"});
    const datos = await respuesta.json().catch(()=>null);
    if (!respuesta.ok) throw new Error(datos && typeof datos.detail === "string" ? datos.detail : `HTTP ${respuesta.status}`);
    if (!Array.isArray(datos)) throw new Error("La respuesta debe ser una lista de conferencias.");
    conferencias = datos;
    llenarFiltros();
    statusBox.hidden = true;
    renderizar();
  } catch(error) {
    contador.textContent = "Error";
    statusBox.hidden = false;
    statusBox.innerHTML = `No se pudo cargar el programa. Inicia el servidor con <code>python -m agente.servidor</code> y abre <code>http://localhost:8000</code>.<br><small>${escapeHTML(error.message)}</small>`;
  }
}

// ---------------------------------------------------------------- Asistente
function sesionAsistente() {
  // Agrupa las preguntas de esta visita en el historial del agente
  let sesion = sessionStorage.getItem("uniconferencias-sesion");
  if (!sesion && window.crypto && crypto.randomUUID) {
    sesion = crypto.randomUUID();
    sessionStorage.setItem("uniconferencias-sesion", sesion);
  }
  return sesion || undefined;
}
async function preguntarAsistente(pregunta) {
  askButton.disabled = true;
  askButton.textContent = "Buscando…";
  answerBox.hidden = false;
  answerText.textContent = "El asistente está buscando en el programa…";
  answerDetail.hidden = true;
  answerSearch.textContent = "";
  answerClear.hidden = true;
  try {
    const respuesta = await fetch(API_AGENTE, {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({pregunta, sesion: sesionAsistente()})
    });
    const datos = await respuesta.json().catch(()=>({}));
    if (!respuesta.ok) throw new Error(typeof datos.detail === "string" ? datos.detail : `HTTP ${respuesta.status}`);

    // El texto es del modelo: se muestra como texto, nunca como HTML
    answerText.textContent = datos.respuesta;
    answerDetail.textContent = datos.detalle || "";
    answerDetail.hidden = !datos.detalle;
    const mostrados = datos.eventos.length;
    answerSearch.textContent = `Búsqueda: ${datos.busqueda}` + (datos.total > mostrados ? ` · se muestran ${mostrados} de ${datos.total}` : "");
    if (mostrados) {
      resultadosAsistente = datos.eventos;
      answerClear.hidden = false;
      limpiarFiltros();
      cambiarVista("asistente");
    } else if (vistaActual === "asistente") {
      cambiarVista("conferencias");
    }
  } catch(error) {
    answerText.textContent = `El asistente no pudo responder: ${error.message}`;
  } finally {
    askButton.disabled = false;
    askButton.textContent = "Preguntar";
  }
}

searchInput.addEventListener("input",renderizar);
document.getElementById("search-button").addEventListener("click",renderizar);
[campusSelect,daySelect,categorySelect].forEach(el=>el.addEventListener("change",renderizar));
document.getElementById("clear-filters").addEventListener("click",()=>{ limpiarFiltros(); renderizar(); });
document.querySelectorAll("[data-view]").forEach(b=>b.addEventListener("click",()=>cambiarVista(b.dataset.view)));
document.querySelector("[data-view-link='agenda']").addEventListener("click",()=>cambiarVista("agenda"));
document.getElementById("assistant-form").addEventListener("submit",e=>{
  e.preventDefault();
  const pregunta = questionInput.value.trim();
  if (pregunta) preguntarAsistente(pregunta);
});
answerClear.addEventListener("click",()=>{ answerBox.hidden = true; cambiarVista("conferencias"); });
contenedor.addEventListener("click",e=>{
  const button=e.target.closest("[data-agenda]");
  if(!button)return;
  const id=button.dataset.agenda;
  if(idEnAgenda(id)) agenda=agenda.filter(x=>String(x)!==String(id));
  else agenda.push(id);
  guardarAgenda(); renderizar();
});
guardarAgenda();
obtenerConferencias();
