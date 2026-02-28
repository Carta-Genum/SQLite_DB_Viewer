/**
 * Spatial Transcriptomics DB Viewer — Client
 *
 * State-driven SPA: all data fetched from /api/* endpoints,
 * rendered into the DOM. No framework dependencies.
 */

// ---- State ----

const S = {
  db: null,
  table: null,
  filters: {},
  search: '',
  sort: null,
  dir: 'asc',
  page: 1,
  dbMeta: {},
  facets: {},       // {col: {values: [...], numeric: bool}}
  selected: new Set(),  // row IDs currently checked for export
  theme: localStorage.getItem('stdb-theme') || 'dark',
};

let searchTimeout = null;

// ---- Init ----

async function init() {
  applyTheme(S.theme);

  document.getElementById('portInfo').textContent = location.host;

  const resp = await fetch('/api/databases');
  S.dbMeta = await resp.json();
  const dbNames = Object.keys(S.dbMeta);
  if (!dbNames.length) return;

  // Database selector
  const sel = document.getElementById('dbSelect');
  for (const name of dbNames) {
    const opt = document.createElement('option');
    opt.value = name;
    opt.textContent = name;
    sel.appendChild(opt);
  }
  sel.addEventListener('change', () => { S.db = sel.value; switchDB(); });
  S.db = dbNames[0];
  if (dbNames.length <= 1) sel.style.display = 'none';

  // Event listeners
  document.getElementById('searchInput').addEventListener('input', e => {
    clearTimeout(searchTimeout);
    searchTimeout = setTimeout(() => {
      S.search = e.target.value;
      S.page = 1;
      fetchData();
    }, 250);
  });
  document.getElementById('clearBtn').addEventListener('click', clearFilters);
  document.getElementById('csvBtn').addEventListener('click', exportCSV);
  document.getElementById('csvSelectedBtn').addEventListener('click', exportSelected);
  document.getElementById('themeToggle').addEventListener('click', toggleTheme);
  document.getElementById('overlay').addEventListener('click', e => {
    if (e.target.id === 'overlay') closeModal();
  });
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape') closeModal();
  });

  switchDB();
}

// ---- Theme ----

function applyTheme(theme) {
  document.documentElement.setAttribute('data-theme', theme);
  const btn = document.getElementById('themeToggle');
  if (btn) {
    btn.querySelector('.icon').innerHTML = theme === 'dark'
      ? '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="5"/><path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/></svg>'
      : '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>';
    btn.querySelector('.label').textContent = theme === 'dark' ? 'Light' : 'Dark';
  }
}

function toggleTheme() {
  S.theme = S.theme === 'dark' ? 'light' : 'dark';
  applyTheme(S.theme);
  try { localStorage.setItem('stdb-theme', S.theme); } catch {}
}

// ---- DB / Table switching ----

async function switchDB() {
  const tables = Object.keys(S.dbMeta[S.db] || {});
  S.table = tables[0] || null;
  S.filters = {};
  S.search = '';
  S.sort = null;
  S.page = 1;
  S.selected = new Set();
  document.getElementById('searchInput').value = '';
  buildTabs();
  await loadFacets();
  await fetchData();
}

async function switchTable(t) {
  S.table = t;
  S.filters = {};
  S.search = '';
  S.sort = null;
  S.page = 1;
  S.selected = new Set();
  document.getElementById('searchInput').value = '';
  buildTabs();
  await loadFacets();
  await fetchData();
}

// ---- Tabs ----

function buildTabs() {
  const container = document.getElementById('tableTabs');
  container.innerHTML = '';
  const info = S.dbMeta[S.db];
  for (const t of Object.keys(info)) {
    const btn = document.createElement('button');
    btn.className = 'tab' + (t === S.table ? ' on' : '');
    btn.innerHTML = t + `<span class="n">${info[t].count.toLocaleString()}</span>`;
    btn.addEventListener('click', () => switchTable(t));
    container.appendChild(btn);
  }
}

// ---- Facets / Filters ----

async function loadFacets() {
  const resp = await fetch(`/api/facets?db=${S.db}&table=${S.table}`);
  S.facets = await resp.json();
  buildSidebar();
}

function buildSidebar() {
  const side = document.getElementById('sidebar');
  side.innerHTML = '';

  for (const [col, facetData] of Object.entries(S.facets)) {
    const items = facetData.values || [];
    if (!items.length) continue;

    const grp = document.createElement('div');
    grp.className = 'facet-group';

    // Count how many are currently checked for this column
    const activeCount = (S.filters[col] || []).length;

    const hdr = document.createElement('div');
    hdr.className = 'facet-hdr';
    hdr.innerHTML =
      `<span class="facet-label">${col.replace(/_/g, ' ')}</span>` +
      `<span class="facet-right">` +
        (activeCount > 0 ? `<span class="facet-active">${activeCount}</span>` : '') +
        `<span class="facet-cnt">${items.length}</span>` +
        `<span class="facet-chevron">›</span>` +
      `</span>`;

    // Collapsed by default
    const opts = document.createElement('div');
    opts.className = 'facet-opts collapsed';

    hdr.addEventListener('click', () => {
      opts.classList.toggle('collapsed');
      hdr.classList.toggle('expanded');
    });

    for (const item of items) {
      const lbl = document.createElement('label');
      lbl.className = 'fopt';
      const valStr = String(item.value);
      const checked = (S.filters[col] || []).includes(valStr);
      lbl.innerHTML =
        `<input type="checkbox" data-col="${col}" ` +
        `data-val="${valStr.replace(/"/g, '&quot;')}" ${checked ? 'checked' : ''}>` +
        `<span class="vl">${esc(valStr)}</span>` +
        `<span class="vc">${item.count}</span>`;
      lbl.querySelector('input').addEventListener('change', onFilterChange);
      opts.appendChild(lbl);
    }

    grp.appendChild(hdr);
    grp.appendChild(opts);
    side.appendChild(grp);
  }
}

function onFilterChange() {
  S.filters = {};
  document.querySelectorAll('.facet-opts input:checked').forEach(cb => {
    const c = cb.dataset.col;
    if (!S.filters[c]) S.filters[c] = [];
    S.filters[c].push(cb.dataset.val);
  });
  S.page = 1;
  const has = Object.keys(S.filters).length > 0;
  document.getElementById('clearBtn').classList.toggle('hide', !has);
  // Rebuild sidebar to update active counts
  buildSidebar();
  fetchData();
}

function clearFilters() {
  S.filters = {};
  document.getElementById('clearBtn').classList.add('hide');
  S.page = 1;
  buildSidebar();
  fetchData();
}

// ---- Data fetching ----

function buildQueryString(forExport = false) {
  const p = new URLSearchParams();
  p.set('db', S.db);
  p.set('table', S.table);
  if (S.search) p.set('search', S.search);
  if (S.sort) { p.set('sort', S.sort); p.set('dir', S.dir); }
  if (!forExport) p.set('page', S.page);
  for (const [col, vals] of Object.entries(S.filters)) {
    for (const v of vals) p.append(`filter.${col}`, v);
  }
  return p.toString();
}

async function fetchData() {
  const resp = await fetch(`/api/query?${buildQueryString()}`);
  const data = await resp.json();
  renderTable(data);
  renderPagination(data);
  updateSelectionUI();
}

// ---- Selection ----

function updateSelectionUI() {
  const count = S.selected.size;
  const btn = document.getElementById('csvSelectedBtn');
  if (count > 0) {
    btn.classList.remove('hide');
    btn.textContent = `↓ Export ${count} selected`;
  } else {
    btn.classList.add('hide');
  }
}

function onSelectAll(e) {
  const tbody = document.getElementById('tbody');
  const rows = tbody._rows || [];
  const checked = e.target.checked;
  rows.forEach(row => {
    if (row.id != null) {
      if (checked) S.selected.add(row.id);
      else S.selected.delete(row.id);
    }
  });
  // Update all row checkboxes on current page
  tbody.querySelectorAll('.row-check').forEach(cb => cb.checked = checked);
  updateSelectionUI();
}

function onRowSelect(e, rowId) {
  e.stopPropagation();
  if (e.target.checked) {
    S.selected.add(rowId);
  } else {
    S.selected.delete(rowId);
  }
  // Update "select all" checkbox state
  updateSelectAllState();
  updateSelectionUI();
}

function updateSelectAllState() {
  const tbody = document.getElementById('tbody');
  const rows = tbody._rows || [];
  const pageIds = rows.filter(r => r.id != null).map(r => r.id);
  const allChecked = pageIds.length > 0 && pageIds.every(id => S.selected.has(id));
  const someChecked = pageIds.some(id => S.selected.has(id));
  const selectAllCb = document.getElementById('selectAllCb');
  if (selectAllCb) {
    selectAllCb.checked = allChecked;
    selectAllCb.indeterminate = someChecked && !allChecked;
  }
}

// ---- Table rendering ----

function renderTable(data) {
  const { rows, total, columns, page, pages } = data;
  const hasId = columns.includes('id');

  document.getElementById('metaInfo').innerHTML =
    `<b>${total.toLocaleString()}</b> rows` + (pages > 1 ? ` · pg ${page}/${pages}` : '');

  // Header
  const thead = document.getElementById('thead');
  let headerHtml = '<tr>';
  if (hasId) {
    headerHtml += '<th class="check-col"><input type="checkbox" id="selectAllCb" title="Select all on page"></th>';
  }
  headerHtml += columns.map(c => {
    const isSorted = S.sort === c;
    const arrow = isSorted ? (S.dir === 'asc' ? '▲' : '▼') : '▲';
    return `<th class="${isSorted ? 'sorted' : ''}" data-col="${c}">` +
           `${c.replace(/_/g, ' ')}<span class="arrow">${arrow}</span></th>`;
  }).join('') + '</tr>';
  thead.innerHTML = headerHtml;

  // Select-all checkbox listener
  const selectAllCb = document.getElementById('selectAllCb');
  if (selectAllCb) {
    selectAllCb.addEventListener('change', onSelectAll);
  }

  // Sort listeners (skip the checkbox column)
  thead.querySelectorAll('th[data-col]').forEach(th => {
    th.addEventListener('click', () => {
      const c = th.dataset.col;
      if (S.sort === c) {
        S.dir = S.dir === 'asc' ? 'desc' : 'asc';
      } else {
        S.sort = c;
        S.dir = 'asc';
      }
      S.page = 1;
      fetchData();
    });
  });

  // Body
  const tbody = document.getElementById('tbody');
  if (!rows.length) {
    tbody.innerHTML = '';
    document.getElementById('empty').style.display = 'flex';
    return;
  }
  document.getElementById('empty').style.display = 'none';

  tbody.innerHTML = rows.map((row, i) => {
    const isChecked = hasId && S.selected.has(row.id);
    let html = `<tr class="data-row ${isChecked ? 'row-selected' : ''}" data-i="${i}">`;
    if (hasId) {
      html += `<td class="check-col"><input type="checkbox" class="row-check" ` +
              `data-id="${row.id}" ${isChecked ? 'checked' : ''}></td>`;
    }
    html += columns.map(c => cellHtml(c, row[c])).join('');
    html += '</tr>';
    return html;
  }).join('');

  // Store for detail view
  tbody._rows = rows;
  tbody._cols = columns;

  // Row checkbox listeners
  tbody.querySelectorAll('.row-check').forEach(cb => {
    cb.addEventListener('change', (e) => onRowSelect(e, +cb.dataset.id));
    cb.addEventListener('click', (e) => e.stopPropagation());
  });

  // Row click → detail (but not on checkbox)
  tbody.querySelectorAll('tr.data-row').forEach(tr => {
    tr.addEventListener('click', () => {
      showDetail(tbody._rows[+tr.dataset.i], tbody._cols);
    });
  });

  // Sync select-all state
  updateSelectAllState();
}

function cellHtml(col, val) {
  if (val == null) return '<td class="null">—</td>';

  if (col === 'url' || col === 'download_url') {
    const s = String(val);
    const short = s.length > 45 ? s.slice(0, 43) + '…' : s;
    return `<td><a href="${esc(s)}" target="_blank" rel="noopener" ` +
           `onclick="event.stopPropagation()">${esc(short)}</a></td>`;
  }
  if (col === 'id' || col === 'dataset_pk' || col === 'sample_pk') {
    return `<td class="mono">${val}</td>`;
  }
  if (col === 'size_bytes' && val) {
    return `<td class="mono">${fmtBytes(val)}</td>`;
  }

  const s = String(val);
  const display = s.length > 90 ? s.slice(0, 88) + '…' : s;
  return `<td title="${esc(s)}">${esc(display)}</td>`;
}

// ---- Pagination ----

function renderPagination(data) {
  const { page, pages, total } = data;
  const container = document.getElementById('pagination');
  if (pages <= 1) { container.innerHTML = ''; return; }

  let html = `<button class="pg-btn" ${page <= 1 ? 'disabled' : ''} data-p="${page - 1}">‹ Prev</button>`;
  const start = Math.max(1, page - 3);
  const end = Math.min(pages, start + 6);
  for (let i = start; i <= end; i++) {
    html += `<button class="pg-btn ${i === page ? 'current' : ''}" data-p="${i}">${i}</button>`;
  }
  html += `<button class="pg-btn" ${page >= pages ? 'disabled' : ''} data-p="${page + 1}">Next ›</button>`;
  html += `<span class="pg-info">${total.toLocaleString()} total</span>`;
  container.innerHTML = html;

  container.querySelectorAll('.pg-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      if (btn.disabled) return;
      S.page = +btn.dataset.p;
      fetchData();
      document.getElementById('tableWrap').scrollTop = 0;
    });
  });
}

// ---- Detail modal ----

function showDetail(row, columns) {
  const modal = document.getElementById('modal');
  let html = '<button class="close-btn" onclick="closeModal()">✕</button>';
  html += `<h3>${S.table} — Row Detail</h3>`;
  for (const c of columns) {
    const v = row[c];
    const isNull = v == null;
    let display = isNull ? 'null' : String(v);
    if ((c === 'url' || c === 'download_url') && !isNull) {
      display = `<a href="${esc(display)}" target="_blank" rel="noopener">${esc(display)}</a>`;
    } else {
      display = esc(display);
    }
    html += `<div class="modal-row"><div class="modal-key">${c}</div>` +
            `<div class="modal-val${isNull ? ' is-null' : ''}">${display}</div></div>`;
  }
  modal.innerHTML = html;
  document.getElementById('overlay').classList.add('open');
}

function closeModal() {
  document.getElementById('overlay').classList.remove('open');
}

// ---- CSV export ----

function exportCSV() {
  window.open(`/api/export?${buildQueryString(true)}`, '_blank');
}

async function exportSelected() {
  if (!S.selected.size) return;

  const resp = await fetch('/api/export-selected', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      db: S.db,
      table: S.table,
      ids: Array.from(S.selected),
    }),
  });

  if (!resp.ok) return;

  // Download the CSV
  const blob = await resp.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `${S.table}_selected.csv`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

// ---- Utilities ----

function esc(s) {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function fmtBytes(b) {
  if (!b) return '—';
  const units = ['B', 'KB', 'MB', 'GB'];
  let i = 0;
  while (b >= 1024 && i < units.length - 1) { b /= 1024; i++; }
  return b.toFixed(i ? 1 : 0) + ' ' + units[i];
}

// ---- Boot ----
init();

// ---- SQL Console ----

function initSQLConsole() {
  const toggleBtn = document.getElementById('sqlToggleBtn');
  const closeBtn = document.getElementById('sqlCloseBtn');
  const runBtn = document.getElementById('sqlRunBtn');
  const input = document.getElementById('sqlInput');

  toggleBtn.addEventListener('click', toggleSQLConsole);
  closeBtn.addEventListener('click', () => setSQLConsoleOpen(false));
  runBtn.addEventListener('click', runSQL);

  input.addEventListener('keydown', e => {
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
      e.preventDefault();
      runSQL();
    }
    // Tab inserts spaces
    if (e.key === 'Tab') {
      e.preventDefault();
      const start = input.selectionStart;
      const end = input.selectionEnd;
      input.value = input.value.substring(0, start) + '  ' + input.value.substring(end);
      input.selectionStart = input.selectionEnd = start + 2;
    }
  });
}

function toggleSQLConsole() {
  const panel = document.getElementById('sqlConsole');
  const isOpen = !panel.classList.contains('hide');
  setSQLConsoleOpen(!isOpen);
}

function setSQLConsoleOpen(open) {
  const panel = document.getElementById('sqlConsole');
  const btn = document.getElementById('sqlToggleBtn');
  if (open) {
    panel.classList.remove('hide');
    btn.classList.add('active');
    document.getElementById('sqlInput').focus();
  } else {
    panel.classList.add('hide');
    btn.classList.remove('active');
  }
}

async function runSQL() {
  const input = document.getElementById('sqlInput');
  const results = document.getElementById('sqlResults');
  const runBtn = document.getElementById('sqlRunBtn');
  const sql = input.value.trim();

  if (!sql) return;

  runBtn.disabled = true;
  runBtn.textContent = '⏳ Running…';
  results.innerHTML = '<div class="sql-placeholder">Running query…</div>';

  try {
    const resp = await fetch('/api/sql', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ db: S.db, sql }),
    });
    const data = await resp.json();

    if (data.error) {
      results.innerHTML = `<div class="sql-error">Error: ${esc(data.error)}</div>`;
      return;
    }

    if (!data.columns || !data.columns.length) {
      results.innerHTML = '<div class="sql-placeholder">Query executed — no results returned</div>';
      return;
    }

    let html = '<div class="sql-meta"><b>' + data.row_count.toLocaleString() + '</b> rows returned';
    if (data.truncated) html += ' (truncated to 2,000)';
    html += '</div>';

    html += '<table><thead><tr>';
    html += data.columns.map(c => `<th>${esc(c)}</th>`).join('');
    html += '</tr></thead><tbody>';

    for (const row of data.rows) {
      html += '<tr>';
      for (const c of data.columns) {
        const v = row[c];
        if (v == null) {
          html += '<td class="null">NULL</td>';
        } else {
          const s = String(v);
          const display = s.length > 100 ? s.slice(0, 98) + '…' : s;
          html += `<td title="${esc(s)}">${esc(display)}</td>`;
        }
      }
      html += '</tr>';
    }
    html += '</tbody></table>';
    results.innerHTML = html;

  } catch (e) {
    results.innerHTML = `<div class="sql-error">Network error: ${esc(e.message)}</div>`;
  } finally {
    runBtn.disabled = false;
    runBtn.textContent = '▶ Run';
  }
}

// Init the SQL console after main init
initSQLConsole();
