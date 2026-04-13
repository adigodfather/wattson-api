/* ============================================================
   ZYNAPSE – Frontend Logic v2
   ============================================================ */

// ---- CONFIG ----
// Dacă rulezi local: http://localhost:8000
// Dacă ai deploy pe Render, schimbă URL-ul de mai jos sau
// seteazî variabila de mediu ZYNAPSE_API_URL în localStorage.
const API_URL = localStorage.getItem('ZYNAPSE_API_URL') || 'http://localhost:8000';

document.addEventListener('DOMContentLoaded', () => {
  document.getElementById('api-url-display').textContent = API_URL;
  initUpload();
  initHeatingToggle();
  addRoom(); // o cameră default
});

// ---- NAVEGARE PAȘI ----
let currentStep = 1;

function goStep(n) {
  if (n > currentStep && !validateStep(currentStep)) return;
  const prev = document.getElementById(`step-${currentStep}`);
  const next = document.getElementById(`step-${n}`);
  if (!next) return;

  prev.classList.add('hidden');
  next.classList.remove('hidden');

  // update indicatori
  for (let i = 1; i <= 5; i++) {
    const ind = document.getElementById(`step-ind-${i}`);
    ind.classList.remove('active', 'done');
    if (i < n) ind.classList.add('done');
    if (i === n) ind.classList.add('active');
  }

  currentStep = n;
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

function validateStep(step) {
  if (step === 1) {
    const pid = document.getElementById('project_id').value.trim();
    if (!pid) { alert('Introduceți numele proiectului.'); return false; }
  }
  if (step === 2) {
    const area = document.getElementById('total_area').value;
    const vol = document.getElementById('total_volume').value;
    if (!area || area <= 0) { alert('Introduceți suprafața utilă totală.'); return false; }
    if (!vol || vol <= 0) { alert('Introduceți volumul total.'); return false; }
  }
  if (step === 4) {
    const rooms = gatherRooms();
    if (rooms.length === 0) { alert('Adăugați cel puțin o cameră.'); return false; }
  }
  return true;
}

// ---- UPLOAD FIȘIERE ----
let uploadedFiles = [];

function initUpload() {
  const area = document.getElementById('upload-area');
  const input = document.getElementById('file-input');

  area.addEventListener('click', () => input.click());
  input.addEventListener('change', () => handleFiles(input.files));

  area.addEventListener('dragover', e => { e.preventDefault(); area.classList.add('drag-over'); });
  area.addEventListener('dragleave', () => area.classList.remove('drag-over'));
  area.addEventListener('drop', e => {
    e.preventDefault();
    area.classList.remove('drag-over');
    handleFiles(e.dataTransfer.files);
  });
}

function handleFiles(files) {
  Array.from(files).forEach(f => {
    if (!uploadedFiles.find(u => u.name === f.name)) uploadedFiles.push(f);
  });
  renderFileList();
}

function renderFileList() {
  const list = document.getElementById('file-list');
  list.innerHTML = uploadedFiles.map((f, i) => `
    <div class="file-item">
      <span class="file-icon">📄</span>
      <span>${f.name}</span>
      <span class="file-size">${(f.size / 1024).toFixed(0)} KB</span>
      <span class="file-remove" onclick="removeFile(${i})">✕</span>
    </div>
  `).join('');
}

function removeFile(i) {
  uploadedFiles.splice(i, 1);
  renderFileList();
}

// ---- PDC PHASE TOGGLE ----
function initHeatingToggle() {
  const hType = document.getElementById('heating_type');
  hType.addEventListener('change', () => {
    const pdcGroup = document.getElementById('pdc-phase-group');
    const isPdc = hType.value.startsWith('pdc') || hType.value === 'geothermal';
    pdcGroup.style.display = isPdc ? '' : 'none';
  });
  hType.dispatchEvent(new Event('change'));
}

// ---- CAMERE ----
let roomCounter = 0;

function addRoom() {
  roomCounter++;
  const id = roomCounter;
  const list = document.getElementById('rooms-list');

  const div = document.createElement('div');
  div.className = 'room-item';
  div.id = `room-${id}`;
  div.innerHTML = `
    <div class="room-header">
      <span>Camera ${id}</span>
      <span class="room-remove" onclick="removeRoom(${id})">✕ Șterge</span>
    </div>
    <div class="room-grid">
      <div class="form-group">
        <label>Nume *</label>
        <input type="text" class="r-name" placeholder="ex: Living" />
      </div>
      <div class="form-group">
        <label>Nivel</label>
        <input type="text" class="r-level" placeholder="ex: Parter" />
      </div>
      <div class="form-group">
        <label>Suprafață (m²) *</label>
        <input type="number" class="r-area" placeholder="ex: 28" min="1" step="0.1" />
      </div>
      <div class="form-group">
        <label>Înălțime (m) *</label>
        <input type="number" class="r-height" placeholder="ex: 2.7" min="1" step="0.05" />
      </div>
      <div class="form-group">
        <label>Parapet fereastră (m)</label>
        <input type="number" class="r-sill" placeholder="ex: 0.9" min="0" step="0.05" />
      </div>
      <div class="form-group">
        <label>Funcțiune *</label>
        <select class="r-function">
          <option value="day">Zi (living, dining, birou)</option>
          <option value="night">Noapte (dormitor)</option>
          <option value="circulation">Circulație (hol, scară)</option>
          <option value="bathroom">Baie / WC</option>
          <option value="kitchen">Bucătărie</option>
          <option value="technical/storage">Tehnică / Depozit</option>
          <option value="other">Alt tip</option>
        </select>
      </div>
      <div class="form-group" style="justify-content:flex-end; gap:10px; flex-direction:row; align-items:center;">
        <label class="checkbox-label">
          <input type="checkbox" class="r-tv" /> TV
        </label>
        <label class="checkbox-label">
          <input type="checkbox" class="r-nightstands" /> Noptiere
        </label>
      </div>
    </div>
  `;
  list.appendChild(div);
}

function removeRoom(id) {
  const el = document.getElementById(`room-${id}`);
  if (el) el.remove();
}

function gatherRooms() {
  const rooms = [];
  document.querySelectorAll('.room-item').forEach(el => {
    const name = el.querySelector('.r-name').value.trim();
    const area = parseFloat(el.querySelector('.r-area').value);
    const height = parseFloat(el.querySelector('.r-height').value);
    const func = el.querySelector('.r-function').value;
    if (!name || isNaN(area) || isNaN(height)) return;

    const sill = parseFloat(el.querySelector('.r-sill').value);
    rooms.push({
      name,
      level: el.querySelector('.r-level').value.trim() || null,
      area_m2: area,
      height_m: height,
      window_sill_height_m: isNaN(sill) ? null : sill,
      function: func,
      has_tv: el.querySelector('.r-tv').checked,
      has_nightstands: el.querySelector('.r-nightstands').checked,
    });
  });
  return rooms;
}

// ---- SUBMIT ----
async function submitProject() {
  if (!validateStep(4)) return;

  const rooms = gatherRooms();
  const heatingType = document.getElementById('heating_type').value;
  const isPdc = heatingType.startsWith('pdc') || heatingType === 'geothermal';

  const payload = {
    project_id: document.getElementById('project_id').value.trim(),
    building: {
      type: document.getElementById('building_type').value,
      levels: document.getElementById('building_levels').value,
      climate_zone: document.getElementById('climate_zone').value,
      insulation_level: document.getElementById('insulation_level').value,
      main_entrance: document.getElementById('main_entrance').value.trim() || null,
      total_area_m2: parseFloat(document.getElementById('total_area').value),
      total_volume_m3: parseFloat(document.getElementById('total_volume').value),
    },
    heating: {
      type: heatingType,
      pdc_phase: isPdc ? document.getElementById('pdc_phase').value : null,
      has_acm_boiler: document.getElementById('has_acm_boiler').checked,
      has_ventilation: document.getElementById('has_ventilation').checked,
      has_hrv: document.getElementById('has_hrv').checked,
    },
    has_floor_heating: document.getElementById('has_floor_heating').checked,
    rooms,
  };

  goStep(5);
  document.getElementById('loading').classList.remove('hidden');
  document.getElementById('results').classList.add('hidden');
  document.getElementById('error-box').classList.add('hidden');

  try {
    const res = await fetch(`${API_URL}/calc-electric`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `HTTP ${res.status}`);
    }

    const data = await res.json();
    document.getElementById('loading').classList.add('hidden');
    renderResults(data, payload);
    document.getElementById('results').classList.remove('hidden');

  } catch (e) {
    document.getElementById('loading').classList.add('hidden');
    const box = document.getElementById('error-box');
    box.textContent = `Eroare la calculul proiectului: ${e.message}`;
    box.classList.remove('hidden');
  }
}

// ---- RENDER RESULTS ----
let lastResult = null;
let lastPayload = null;

function renderResults(data, payload) {
  lastResult = data;
  lastPayload = payload;

  document.getElementById('result-project-id').textContent = data.project_id;

  // Summary cards
  const circuits_all = data.circuits_all || [];
  const te_ct = data.circuits_te_ct || [];
  const teg = data.circuits_teg || [];
  const hc = data.heating_circuits || {};

  const pdcKw = hc.pdc ? hc.pdc.power_kw_thermal : 0;
  const zoneLabel = { I: '−12°C', II: '−15°C', III: '−18°C', IV: '−21°C', V: '−25°C' };

  document.getElementById('result-summary').innerHTML = `
    <div class="summary-card">
      <div class="value">${data.climate_zone}</div>
      <div class="label">Zona Climatică (${zoneLabel[data.climate_zone] || ''})</div>
    </div>
    <div class="summary-card">
      <div class="value">${pdcKw > 0 ? pdcKw + ' kW' : '—'}</div>
      <div class="label">Putere PDC</div>
    </div>
    <div class="summary-card">
      <div class="value">${te_ct.length}</div>
      <div class="label">Circuite TE-CT</div>
    </div>
    <div class="summary-card">
      <div class="value">${teg.length}</div>
      <div class="label">Circuite TEG</div>
    </div>
    <div class="summary-card">
      <div class="value">${circuits_all.length}</div>
      <div class="label">Total Circuite</div>
    </div>
    <div class="summary-card">
      <div class="value">${(data.rooms || []).length}</div>
      <div class="label">Camere procesate</div>
    </div>
  `;

  // Tab PDC & Incalzire
  const hLabels = {
    pdc_air_water: 'PDC aer-apă', pdc_air_air: 'PDC aer-aer',
    gas_boiler: 'Centrală gaz', electric_boiler: 'Centrală electrică',
    geothermal: 'Geotermală', none: 'Fără',
  };
  let pdcHtml = `<h3 style="margin-bottom:16px; color:var(--accent-2)">Circuite Instalație Termică</h3>`;
  pdcHtml += renderCircuitTable([hc.pdc, hc.boiler, hc.pump, hc.ventilation].filter(Boolean));
  document.getElementById('tab-pdc').innerHTML = pdcHtml;

  // Tab TE-CT
  document.getElementById('tab-tect').innerHTML =
    `<h3 style="margin-bottom:16px; color:var(--accent-2)">Tablou Electric – Camera Tehnică (TE-CT)</h3>` +
    renderCircuitTable(te_ct);

  // Tab TEG
  document.getElementById('tab-teg').innerHTML =
    `<h3 style="margin-bottom:16px; color:var(--accent-2)">Tablou Electric General (TEG)</h3>` +
    renderCircuitTable(teg);

  // Tab Camere
  const roomsHtml = (data.rooms || []).map(r => `
    <div class="room-result-card">
      <div class="room-result-title">${r.name}${r.level ? ` – ${r.level}` : ''} <small style="color:var(--text-muted)">(${r.area_m2} m²)</small></div>
      <div class="room-result-grid">
        <div class="room-result-section">
          <h4>Prize</h4>
          <ul>
            ${(r.sockets || []).length ? r.sockets.map(s =>
              `<li>${s.type} ×${s.count} la ${s.height_m} m</li>`
            ).join('') : '<li style="color:var(--text-muted)">–</li>'}
          </ul>
        </div>
        <div class="room-result-section">
          <h4>Iluminat</h4>
          <ul>
            ${(r.lights || []).map(l => `<li>${l.type} ×${l.count}</li>`).join('')}
          </ul>
        </div>
      </div>
    </div>
  `).join('');
  document.getElementById('tab-rooms').innerHTML =
    `<h3 style="margin-bottom:16px; color:var(--accent-2)">Detalii pe Camere</h3>` + roomsHtml;

  // Tab Memoriu
  document.getElementById('tab-memoriu').innerHTML =
    `<div class="memoriu-box">${escapeHtml(data.memoriu_tehnic || '')}</div>`;

  // Tab JSON
  document.getElementById('tab-json').innerHTML =
    `<div class="json-box">${escapeHtml(JSON.stringify(data, null, 2))}</div>`;

  showTab('tab-pdc');
}

function renderCircuitTable(circuits) {
  if (!circuits || circuits.length === 0) {
    return '<p style="color:var(--text-muted);padding:16px 0">Niciun circuit generat.</p>';
  }
  const rows = circuits.map(c => {
    const phaseLabel = c.phase || c.poles || '—';
    const badge = c.phase === 'trifazat'
      ? `<span class="badge badge-blue">3F</span>`
      : c.phase === 'monofazat'
        ? `<span class="badge badge-green">1F</span>`
        : '';
    return `
      <tr>
        <td><code style="color:var(--accent)">${c.id || '—'}</code></td>
        <td>${c.usage || c.device || '—'} ${badge}</td>
        <td>${c.power_kw_thermal ? c.power_kw_thermal + ' kW' : (c.power_kw ? c.power_kw + ' kW' : '—')}</td>
        <td>${c.current_a_calc ? '~' + c.current_a_calc + ' A' : '—'}</td>
        <td><strong>${c.breaker_a} A</strong></td>
        <td>${c.cable || '—'}</td>
      </tr>
    `;
  }).join('');
  return `
    <table class="circuit-table">
      <thead>
        <tr>
          <th>ID</th><th>Utilizare</th><th>Putere</th>
          <th>I calc.</th><th>Siguranță</th><th>Cablu</th>
        </tr>
      </thead>
      <tbody>${rows}</tbody>
    </table>
  `;
}

// ---- TABS ----
function showTab(id) {
  document.querySelectorAll('.tab-content').forEach(el => el.classList.add('hidden'));
  document.querySelectorAll('.tab').forEach(el => el.classList.remove('active'));
  document.getElementById(id).classList.remove('hidden');
  const tabs = document.querySelectorAll('.tab');
  const map = {
    'tab-pdc': 0, 'tab-tect': 1, 'tab-teg': 2,
    'tab-rooms': 3, 'tab-memoriu': 4, 'tab-json': 5,
  };
  if (map[id] !== undefined) tabs[map[id]]?.classList.add('active');
}

// ---- UTILITIES ----
function escapeHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

function copyJSON() {
  if (!lastResult) return;
  navigator.clipboard.writeText(JSON.stringify(lastResult, null, 2))
    .then(() => alert('JSON copiat în clipboard!'))
    .catch(() => alert('Nu s-a putut copia. Copiați manual din tab-ul JSON.'));
}

function downloadMemoriu() {
  if (!lastResult?.memoriu_tehnic) return;
  const blob = new Blob([lastResult.memoriu_tehnic], { type: 'text/plain;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `memoriu-${(lastResult.project_id || 'proiect').replace(/\s+/g, '_')}.txt`;
  a.click();
  URL.revokeObjectURL(url);
}

// ---- API URL OVERRIDE (din console: setApiUrl('https://...')) ----
window.setApiUrl = (url) => {
  localStorage.setItem('ZYNAPSE_API_URL', url);
  location.reload();
};
