(async () => {
  const $ = (sel) => document.querySelector(sel);
  async function fetchJSON(url) {
    const r = await fetch(url);
    if (!r.ok) throw new Error(await r.text());
    return r.json();
  }
  function badge(cls, text) {
    const span = document.createElement('span');
    span.className = `badge ${cls} me-1 mb-1`;
    span.textContent = text;
    return span;
  }

  try {
    const detail = await fetchJSON(`${API_BASE}/models/${encodeURIComponent(MODEL_ID)}`);
    $('#author').textContent = detail.author || '—';
    $('#pipeline').textContent = detail.pipeline_tag || '—';
    $('#library').textContent = detail.library_name || '—';
    $('#license').textContent = detail.license || '—';
    $('#downloads').textContent = detail.downloads ?? '—';
    $('#likes').textContent = detail.likes ?? '—';
    $('#last_modified').textContent = detail.last_modified ? new Date(detail.last_modified).toLocaleString() : '—';
    $('#raw').textContent = JSON.stringify(detail.raw || {}, null, 2);

    // tags
    const tagHost = $('#tags');
    tagHost.innerHTML = '';
    (detail.tags || []).forEach(t => tagHost.appendChild(badge('bg-light text-dark', t)));
    if (!detail.tags || !detail.tags.length) tagHost.textContent = '—';

    // files
    const files = $('#files');
    files.innerHTML = '';
    (detail.siblings || []).forEach(fn => files.appendChild(badge('bg-secondary', fn)));
    if (!detail.siblings || !detail.siblings.length) files.textContent = '—';

    // spaces
    const spaces = $('#spaces');
    spaces.innerHTML = '';
    (detail.spaces || []).forEach(sp => spaces.appendChild(badge('bg-info', sp)));
    if (!detail.spaces || !detail.spaces.length) spaces.textContent = '—';

    // similar
    const sim = await fetchJSON(`${API_BASE}/similar/${encodeURIComponent(MODEL_ID)}`);
    const simHost = $('#similar');
    simHost.innerHTML = '';
    if (!sim.length) {
      simHost.innerHTML = '<span class="text-muted">—</span>';
    } else {
      const ul = document.createElement('ul');
      ul.className = 'list-group list-group-flush';
      sim.forEach(s => {
        const li = document.createElement('li');
        li.className = 'list-group-item d-flex justify-content-between align-items-center';
        const a = document.createElement('a');
        a.href = `/models/${encodeURIComponent(s.id)}`;
        a.textContent = s.id;
        const b = document.createElement('span');
        b.className = 'badge bg-secondary rounded-pill';
        b.textContent = s.shared_tags;
        li.appendChild(a);
        li.appendChild(b);
        ul.appendChild(li);
      });
      simHost.appendChild(ul);
    }
  } catch (e) {
    console.error(e);
    $('#raw').textContent = 'Failed to load model.';
  }
})();
