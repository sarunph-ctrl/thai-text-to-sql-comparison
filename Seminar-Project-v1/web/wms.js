(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const el = (tag, className, text) => {
    const item = document.createElement(tag);
    if (className) item.className = className;
    if (text !== undefined) item.textContent = text;
    return item;
  };
  const valueText = value => value === null ? '—' : typeof value === 'object' ? JSON.stringify(value) : String(value);

  async function request(path, options = {}) {
    const response = await fetch(path, options);
    if (!response.ok) throw new Error((await response.json().catch(() => ({}))).detail || `HTTP ${response.status}`);
    return response.json();
  }

  function details(title, content) {
    const box = el('details', 'result-details');
    box.append(el('summary', '', title), el('pre', '', content));
    return box;
  }

  function renderTable(columns, rows) {
    if (!rows.length) return el('div', 'table-empty', 'ไม่พบข้อมูลที่ตรงเงื่อนไข');
    const wrap = el('div', 'table-area');
    const table = el('table');
    const head = el('thead');
    const hr = el('tr');
    columns.forEach(name => hr.append(el('th', '', name)));
    head.append(hr);
    const body = el('tbody');
    rows.forEach(row => {
      const tr = el('tr');
      row.forEach(value => tr.append(el('td', typeof value === 'number' ? 'numeric' : '', valueText(value))));
      body.append(tr);
    });
    table.append(head, body); wrap.append(table); return wrap;
  }

  function render(result) {
    const root = $('wms-result'); root.replaceChildren();
    const statusClass = result.status === 'ok' ? '' : result.status === 'unsupported' ? ' unsupported' : ' error';
    root.append(el('span', `result-status${statusClass}`, result.status === 'ok' ? 'รันสำเร็จ' : result.status === 'unsupported' ? 'นอกขอบเขต' : 'ถูกบล็อก'));
    if (result.message) root.append(el('p', 'panel-message', result.message));

    const metrics = el('div', 'metric-row');
    [['Intent', result.family || '—'], ['เวลารวม', `${result.elapsed_ms} ms`], ['SQL Guard', result.sql_valid === true ? 'ผ่าน' : result.sql_valid === false ? 'ไม่ผ่าน' : 'ไม่ได้สร้าง SQL'], ['Rows', result.rows?.length ?? 0]].forEach(([label, value]) => {
      const item = el('div', 'metric'); item.append(el('span', '', label), el('strong', '', value)); metrics.append(item);
    });
    root.append(metrics);
    if (result.status === 'ok') root.append(renderTable(result.columns, result.rows));
    if (result.interpretation && Object.keys(result.interpretation).length) root.append(details('การตีความคำถาม', JSON.stringify(result.interpretation, null, 2)));
    if (result.sql) {
      root.append(details('Parameterized SQL', result.sql));
      root.append(details('Bind parameters', JSON.stringify(result.params || [], null, 2)));
    }
    if (result.rules?.length) root.append(details('กฎที่จับได้', result.rules.join('\n')));
    if (result.business_rules?.length) root.append(details('Business rule IDs', result.business_rules.join('\n')));
    if (result.tables?.length) root.append(el('p', 'result-meta', `ตารางที่ AST Guard อนุญาต: ${result.tables.join(', ')}`));
  }

  function busy(on) {
    $('wms-run').disabled = on;
    $('wms-question').disabled = on;
    if (on) $('wms-result').replaceChildren(el('div', 'wms-loading', 'กำลังตีความ ตรวจ SQL และอ่านฐานข้อมูล…'));
  }

  $('wms-form').addEventListener('submit', async event => {
    event.preventDefault(); busy(true); $('wms-notice').hidden = true;
    try {
      const result = await request('/wms/query', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({text: $('wms-question').value})});
      render(result);
    } catch (error) {
      const notice = $('wms-notice'); notice.textContent = `รันไม่สำเร็จ: ${error.message}`; notice.className = 'notice error'; notice.hidden = false;
      $('wms-result').replaceChildren(el('p', 'panel-message', 'ยังไม่ได้รับผลลัพธ์จากฐานข้อมูล'));
    } finally { busy(false); }
  });

  document.querySelectorAll('[data-wms-question]').forEach(button => button.addEventListener('click', () => {
    $('wms-question').value = button.dataset.wmsQuestion; $('wms-question').focus();
  }));

  request('/wms/health').then(info => {
    const status = $('wms-status'); status.textContent = `พร้อมใช้ · ${info.stock_serials} serials`; status.classList.add('connected');
  }).catch(() => { const status = $('wms-status'); status.textContent = 'WMS dataset ยังไม่พร้อม'; status.classList.add('offline'); });
})();
