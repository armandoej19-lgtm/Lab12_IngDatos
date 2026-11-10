const JSON_URL = "./conferencias.json";
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

let conferencias = [];
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
  let lista = conferencias.filter(c => {
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
  titleView.textContent = view==="agenda"?"Mi agenda":view==="calendario"?"Calendario de conferencias":"Conferencias disponibles";
  subtitleView.textContent = view==="agenda"?"Aquí aparecen las conferencias que guardaste.":view==="calendario"?"Eventos ordenados por fecha y hora.":"Consulta los horarios y encuentra las actividades que te interesan.";
  renderizar();
}
async function obtenerConferencias() {
  try {
    const respuesta = await fetch(JSON_URL,{cache:"no-store"});
    if (!respuesta.ok) throw new Error(`HTTP ${respuesta.status}`);
    const datos = await respuesta.json();
    if (!Array.isArray(datos)) throw new Error("El JSON debe contener una lista de conferencias.");
    conferencias = datos;
    llenarFiltros();
    statusBox.hidden = true;
    renderizar();
  } catch(error) {
    contador.textContent = "Error";
    statusBox.hidden = false;
    statusBox.innerHTML = `No se pudo cargar <code>conferencias.json</code>. Ejecuta primero <code>pipeline.py</code> y abre la página desde un servidor local. <br><small>${escapeHTML(error.message)}</small>`;
  }
}

searchInput.addEventListener("input",renderizar);
document.getElementById("search-button").addEventListener("click",renderizar);
[campusSelect,daySelect,categorySelect].forEach(el=>el.addEventListener("change",renderizar));
document.getElementById("clear-filters").addEventListener("click",()=>{
  searchInput.value=""; campusSelect.value=""; daySelect.value=""; categorySelect.value=""; renderizar();
});
document.querySelectorAll("[data-view]").forEach(b=>b.addEventListener("click",()=>cambiarVista(b.dataset.view)));
document.querySelector("[data-view-link='agenda']").addEventListener("click",()=>cambiarVista("agenda"));
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
