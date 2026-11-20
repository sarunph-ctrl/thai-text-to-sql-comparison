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

  function render(rootId, result, method) {
    const root = $(rootId); root.replaceChildren();
    const statusClass = result.status === 'ok' ? '' : result.status === 'unsupported' ? ' unsupported' : ' error';
    root.append(el('span', `result-status${statusClass}`, result.status === 'ok' ? 'รันสำเร็จ' : result.status === 'unsupported' ? 'นอกขอบเขต' : 'ถูกบล็อก'));
    if (result.message || result.reason) root.append(el('p', 'panel-message', result.message || result.reason));

    const metrics = el('div', 'metric-row');
    const guard = result.sql_valid === true ? 'ผ่าน' : result.sql_valid === false ? 'ไม่ผ่าน' : 'ไม่ได้สร้าง SQL';
    const firstMetric = method === 'rule' ? ['Intent', result.family || '—'] : ['Prompt', result.prompt_version || '—'];
    [firstMetric, ['เวลารวม', `${result.elapsed_ms} ms`], ['SQL Guard', guard], ['Rows', result.rows?.length ?? 0]].forEach(([label, value]) => {
      const item = el('div', 'metric'); item.append(el('span', '', label), el('strong', '', value)); metrics.append(item);
    });
    root.append(metrics);
    if (result.status === 'ok') root.append(renderTable(result.columns, result.rows));
    if (result.interpretation && Object.keys(result.interpretation).length) root.append(details('การตีความคำถาม', JSON.stringify(result.interpretation, null, 2)));
    const sql = method === 'rule' ? result.sql : result.generated_sql;
    if (sql) {
      root.append(details(method === 'rule' ? 'Parameterized SQL' : 'SQL ที่โมเดลสร้าง', sql));
    }
    if (method === 'rule' && result.sql) {
      root.append(details('Bind parameters', JSON.stringify(result.params || [], null, 2)));
    }
    if (result.rules?.length) root.append(details('กฎที่จับได้', result.rules.join('\n')));
    if (result.business_rules?.length) root.append(details('Business rule IDs', result.business_rules.join('\n')));
    if (method === 'llm' && result.generation) {
      const usage = result.generation;
      root.append(details('การเรียกโมเดล', JSON.stringify({
        provider: usage.provider, model: usage.returned_model || usage.requested_model,
        generation_ms: usage.generation_ms, input_tokens: usage.input_tokens,
        output_tokens: usage.output_tokens, total_tokens: usage.total_tokens
      }, null, 2)));
    }
    if (result.tables?.length) root.append(el('p', 'result-meta', `ตารางที่ AST Guard อนุญาต: ${result.tables.join(', ')}`));
  }

  function busy(on) {
    $('wms-run').disabled = on;
    $('wms-question').disabled = on;
    document.querySelectorAll('input[name="wms-mode"], [data-wms-question]').forEach(item => { item.disabled = on; });
    if (on) {
      $('wms-result').replaceChildren(el('div', 'wms-loading', 'กำลังประมวลผล Rule-based…'));
      if (!$('wms-llm-panel').hidden) $('wms-llm-result').replaceChildren(el('div', 'wms-loading', 'กำลังเรียกโมเดล ตรวจ SQL และอ่านฐานข้อมูล…'));
    }
  }

  function selectedMode() {
    return document.querySelector('input[name="wms-mode"]:checked').value;
  }

  function setMode(mode) {
    const compare = mode === 'compare';
    $('wms-llm-panel').hidden = !compare;
    $('wms-mode-note').textContent = compare ? 'เรียก IntelSphere 1 ครั้ง · ใช้โควตา API' : 'รันเฉพาะ Rule-based · ไม่เรียก LLM API';
    $('wms-run').firstChild.textContent = compare ? 'เปรียบเทียบสองวิธี ' : 'แปลงและรัน SQL ';
  }

  $('wms-form').addEventListener('submit', async event => {
    event.preventDefault(); busy(true); $('wms-notice').hidden = true;
    try {
      const mode = selectedMode();
      const result = await request(mode === 'compare' ? '/wms/compare' : '/wms/query', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({text: $('wms-question').value})});
      if (mode === 'compare') {
        render('wms-result', result.rule_based, 'rule');
        render('wms-llm-result', result.llm, 'llm');
        const notice = $('wms-notice');
        notice.textContent = result.same_rows_as_rule === true ? 'ทั้งสองวิธีคืนผลตรงกัน แต่ยังต้องเทียบ Reference SQL จึงจะสรุปว่าถูก' : result.same_rows_as_rule === false ? 'ผลสองวิธีไม่ตรงกัน ต้องตรวจเทียบ Reference SQL' : 'ยังเปรียบเทียบผลลัพธ์ไม่ได้ เพราะอย่างน้อยหนึ่งวิธีไม่คืนคำตอบ';
        notice.className = 'notice'; notice.hidden = false;
      } else {
        render('wms-result', result, 'rule');
      }
    } catch (error) {
      const notice = $('wms-notice'); notice.textContent = `รันไม่สำเร็จ: ${error.message}`; notice.className = 'notice error'; notice.hidden = false;
      $('wms-result').replaceChildren(el('p', 'panel-message', 'ยังไม่ได้รับผลลัพธ์จากฐานข้อมูล'));
    } finally { busy(false); }
  });

  document.querySelectorAll('[data-wms-question]').forEach(button => button.addEventListener('click', () => {
    $('wms-question').value = button.dataset.wmsQuestion; $('wms-question').focus();
  }));
  document.querySelectorAll('input[name="wms-mode"]').forEach(input => input.addEventListener('change', () => setMode(input.value)));

  request('/wms/health').then(info => {
    const status = $('wms-status'); status.textContent = `พร้อมใช้ · ${info.stock_serials} serials`; status.classList.add('connected');
  }).catch(() => { const status = $('wms-status'); status.textContent = 'WMS dataset ยังไม่พร้อม'; status.classList.add('offline'); });
})();
