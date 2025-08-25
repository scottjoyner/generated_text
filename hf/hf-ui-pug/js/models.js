(() => {
  const el = (sel) => document.querySelector(sel);
  const elAll = (sel) => Array.from(document.querySelectorAll(sel));
  const state = {
    page: 1,
    page_size: 25,
    lastQuery: null
  };

  async function fetchJSON(url) {
    const r = await fetch(url);
    if (!r.ok) throw new Error(await r.text());
    return r.json();
  }

  function qs(params) {
    const p = new URLSearchParams();
    for (const [k, v] of Object.entries(params)) {
      if (v === undefined || v === null || v === '' || (Array.isArray(v) && v.length === 0)) continue;
      if (Array.isArray(v)) {
        v.forEach(val => p.append(k, val));
      } else {
        p.set(k, v);
      }
    }
    return p.toString();
  }

  async function loadFacets() {
    // Authors
    const authors = await fetchJSON(`${API_BASE}/authors`);
    const sel = el('#author');
    authors
      .filter(a => a.author) // skip null
      .slice(0, 500)
      .forEach(a => {
        const opt = document.createElement('option');
        opt.value = a.author;
        opt.textContent = `${a.author} (${a.count})`;
        sel.appendChild(opt);
      });
    // Tags
    const tags = await fetchJSON(`${API_BASE}/tags`);
    const selT = el('#tags');
    tags.slice(0, 500).forEach(t => {
      const opt = document.createElement('option');
      opt.value = t.tag;
      opt.textContent = `${t.tag} (${t.count})`;
      selT.appendChild(opt);
    });
  }

  function collectFilters() {
    const tagsSel = el('#tags');
    const selectedTags = Array.from(tagsSel.selectedOptions).map(o => o.value);
    const gated = el('#gated').value;
    const privateVal = el('#private').value;
    return {
      q: el('#q').value.trim(),
      author: el('#author').value || undefined,
      tag: selectedTags,
      license: el('#license').value.trim() || undefined,
      pipeline: el('#pipeline').value.trim() || undefined,
      min_downloads: el('#min_downloads').value ? Number(el('#min_downloads').value) : undefined,
      gated: gated === '' ? undefined : gated,
      private: privateVal === '' ? undefined : privateVal,
      sort: el('#sort').value,
      order: el('#order').value,
      page: state.page,
      page_size: state.page_size
    };
  }

  function renderRows(items) {
    const tbody = el('#rows');
    tbody.innerHTML = '';
    if (!items.length) {
      const tr = document.createElement('tr');
      const td = document.createElement('td');
      td.colSpan = 8;
      td.textContent = 'No results';
      tr.appendChild(td);
      tbody.appendChild(tr);
      return;
    }
    for (const m of items) {
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td><a href="/models/${encodeURIComponent(m.id)}">${m.id}</a></td>
        <td>${m.author || '—'}</td>
        <td>${(m.tags || []).slice(0,6).map(t => `<span class="badge bg-light text-dark badge-tag">${t}</span>`).join(' ')}</td>
        <td>${m.downloads ?? '—'}</td>
        <td>${m.likes ?? '—'}</td>
        <td>${m.license ?? '—'}</td>
        <td>${m.last_modified ? new Date(m.last_modified).toLocaleDateString() : '—'}</td>
        <td><a class="btn btn-sm btn-outline-primary" href="/models/${encodeURIComponent(m.id)}">View</a></td>
      `;
      tbody.appendChild(tr);
    }
  }

  async function runSearch() {
    const params = collectFilters();
    state.lastQuery = params;
    const url = `${API_BASE}/models?${qs(params)}`;
    const data = await fetchJSON(url);
    renderRows(data.items);
    el('#total').textContent = data.total.toLocaleString();
    const totalPages = Math.max(1, Math.ceil((data.total || 0) / state.page_size));
    el('#pageinfo').textContent = `Page ${state.page} / ${totalPages}`;
    el('#prev').disabled = state.page <= 1;
    el('#next').disabled = state.page >= totalPages;
  }

  // Events
  el('#filters').addEventListener('submit', (e) => {
    e.preventDefault();
    state.page = 1;
    runSearch().catch(console.error);
  });
  el('#reset').addEventListener('click', () => {
    el('#filters').reset();
    // clear multi-select selection
    Array.from(el('#tags').options).forEach(o => o.selected = false);
    state.page = 1;
    runSearch().catch(console.error);
  });
  el('#prev').addEventListener('click', () => {
    if (state.page > 1) { state.page--; runSearch().catch(console.error); }
  });
  el('#next').addEventListener('click', () => {
    state.page++; runSearch().catch(console.error);
  });
  el('#page_size').addEventListener('change', (e) => {
    state.page_size = Number(e.target.value);
    state.page = 1;
    runSearch().catch(console.error);
  });

  // init
  loadFacets().then(runSearch).catch(err => {
    console.error(err);
    document.querySelector('#rows').innerHTML = '<tr><td colspan="8">Failed to load data.</td></tr>';
  });
})();
