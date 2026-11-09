/* Presentation only. Dynamic content always enters through textContent. */
(() => {
  'use strict';
  function boot() {
    const $ = id => document.getElementById(id);
    const node = (tag, cls, text) => { const n = document.createElement(tag); if (cls) n.className = cls; if (text !== undefined) n.textContent = text; return n; };
    const offlineElement = $('offline-payload');
    const offline = Boolean(offlineElement);
    const state = { mode: offline ? 'recorded' : 'live', report: null, info: null, data: null, busy: false, result: null, liveQuestion: $('question').value };
    const statusLabels = {ok:'ประมวลผลสำเร็จ', unmatched:'จับรูปประโยคไม่ได้', unsupported:'นอกขอบเขตที่รองรับ', blocked:'SQL ไม่ผ่านการตรวจ', llm_error:'เรียกโมเดลไม่สำเร็จ', not_configured:'ยังไม่ตั้งค่า API', sql_error:'ฐานข้อมูลปฏิเสธ SQL', truncated:'ผลเกินขอบเขต 200 แถว'};
    const labels = {group_id:'รหัสสินค้า', group_label:'สินค้า', metric_value:'ยอดขาย (บาท)', warehouse_id:'รหัสคลัง', warehouse_name:'คลัง', product_id:'รหัสสินค้า', product_name:'สินค้า', quantity_remaining:'คงเหลือ (หน่วย)', quantity_issued:'จ่ายออก (หน่วย)', id:'รหัส', name:'ชื่อ', price:'ราคาปัจจุบัน', order_date:'วันที่ออเดอร์', status:'สถานะ', order_id:'รหัสออเดอร์', qty:'จำนวน', unit_price:'ราคาขณะขาย', movement_date:'วันที่', movement_type:'ประเภท', order_item_id:'รหัสรายการขาย'};
    const number = value => typeof value === 'number' && Number.isFinite(value);
    const duration = value => !number(value) ? 'ไม่ทราบ' : value >= 1000 ? `${(value/1000).toFixed(2)} s` : `${value.toFixed(1)} ms`;
    const count = value => Number.isInteger(value) ? value.toLocaleString('en-US') : 'ไม่ทราบ';
    const date = value => { try { return new Intl.DateTimeFormat('th-TH', {dateStyle:'medium', timeStyle:'short', timeZone:'Asia/Bangkok'}).format(new Date(value)); } catch { return value || ''; } };
    const money = value => { const s = String(value); const match = s.match(/^(-?)(\d+)(?:\.(\d+))?$/); return match ? match[1] + match[2].replace(/\B(?=(\d{3})+(?!\d))/g, ',') + '.' + (match[3] || '').padEnd(2,'0') : s; };
    function notice(message, error=false) { $('notice').hidden = !message; $('notice').textContent = message || ''; $('notice').className = 'notice' + (error ? ' error' : ''); }
    async function fetchJSON(url, options={}) {
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), options.method === 'POST' ? 65000 : 8000);
      try {
        const response = await fetch(url, {...options, signal:controller.signal, cache:'no-store'});
        const data = await response.json();
        if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : `HTTP ${response.status}`);
        return data;
      } finally { clearTimeout(timer); }
    }
    function table(columns, rows) {
      const wrap = node('div','table-area');
      if (!rows?.length) { wrap.append(node('div','table-empty','ไม่มีข้อมูลตรงเงื่อนไข')); return wrap; }
      const t = node('table'); const head = node('thead'); const hr = node('tr');
      columns.forEach(c => hr.append(node('th','',labels[c] || c))); head.append(hr); t.append(head);
      const body = node('tbody');
      rows.forEach(row => { const tr = node('tr'); row.forEach((v,i) => {
        const c = columns[i]; const numeric = typeof v === 'number' || (typeof v === 'string' && /^-?\d+(\.\d+)?$/.test(v));
        const text = v === null ? 'NULL' : c === 'metric_value' || c === 'price' || c === 'unit_price' ? money(v) : String(v);
        tr.append(node('td',numeric ? 'numeric' : '',text));
      }); body.append(tr); }); t.append(body); wrap.append(t); return wrap;
    }
    function detail(parent, title, text, open=false) {
      const d = node('details','result-details'); d.open = open; d.append(node('summary','',title)); d.append(node('pre','',text)); parent.append(d); return d;
    }
    function metric(parent, label, value) { const m = node('div','metric'); m.append(node('span','',label),node('strong','',value)); parent.append(m); }
    function panel(method, result, recorded) {
      const parent = $(method === 'rule' ? 'rule-panel' : 'llm-panel').querySelector('.panel-content'); parent.replaceChildren();
      if (!result) { parent.append(node('div','table-empty','ไม่มีผลลัพธ์ของวิธีนี้')); return; }
      const ok = result.status === 'ok'; const abstain = ['unmatched','unsupported'].includes(result.status);
      parent.append(node('span','result-status' + (ok ? '' : abstain ? ' unsupported' : ' error'),statusLabels[result.status] || result.status));
      const metrics = node('div','metric-row');
      metric(metrics, recorded ? 'เวลาในรอบบันทึก' : 'เวลาภายในวิธี',duration(result.elapsed_ms));
      if (method === 'rule') metric(metrics,'การเรียก LLM API','ไม่มี');
      else { metric(metrics,'Input tokens',count(result.generation?.input_tokens)); metric(metrics,'Output tokens',count(result.generation?.output_tokens)); }
      parent.append(metrics);
      if (ok) {
        if (result.columns?.length === 1 && result.rows?.length === 1) {
          const answer = node('div','big-answer'); answer.append(node('div','answer-label',labels[result.columns[0]] || 'คำตอบจากฐานข้อมูล'));
          const val = result.rows[0][0]; const strong = node('strong','',val === null ? 'ไม่มีข้อมูล' : money(val));
          if (val !== null) strong.append(node('small','','บาท')); answer.append(strong); parent.append(answer);
        } else parent.append(table(result.columns || [],result.rows || []));
      } else parent.append(node('p','panel-message',result.message || result.reason || 'วิธีนี้ไม่ได้คืนคำตอบ จึงยังเปรียบเทียบค่าผลลัพธ์ไม่ได้'));
      if (method === 'llm') {
        const g = result.generation;
        if (g) parent.append(node('p','result-meta',`${g.provider} / ${g.returned_model || g.requested_model} · สร้าง SQL ${duration(g.generation_ms)}`));
        if (result.reason) parent.append(node('p','result-meta',result.reason));
      }
      const sql = method === 'rule' ? result.sql : result.generated_sql;
      if (sql) {
        const d = detail(parent,'ดู SQL',sql);
        if (method === 'rule' && result.params?.length) d.append(node('p','result-meta','ค่าที่ส่งแยกจาก SQL (parameters)'),node('pre','',JSON.stringify(result.params,null,2)));
        if (method === 'llm' && result.executed_sql && result.executed_sql !== sql) {
          d.append(node('p','result-meta','SQL ที่รันจริงหลัง parse และจำกัดจำนวนแถว'),node('pre','',result.executed_sql));
        }
      }
      if (method === 'rule' && result.interpretation && Object.keys(result.interpretation).length) detail(parent,'การตีความคำถาม',JSON.stringify(result.interpretation,null,2));
      if (method === 'rule' && result.rules?.length) {
        const d = node('details','result-details'); d.append(node('summary','','กฎที่จับได้'));
        const list = node('ul','trace-list'); result.rules.forEach(r => list.append(node('li','',r))); d.append(list); parent.append(d);
      }
      if (method === 'rule' && result.tokens?.length) detail(parent,'การตัดคำ',result.tokens.join(' / '));
      if (method === 'rule' && ok && result.business_definition) detail(parent,'นิยามการคำนวณ',result.business_definition);
      if (method === 'llm' && result.generation) detail(parent,'เวลาและการตรวจ SQL',JSON.stringify({generation_ms:result.generation.generation_ms,validation_ms:result.validation_ms,database_ms:result.database_ms,truncated:result.truncated,prompt_version:result.prompt_version,prompt_sha256:result.prompt_sha256,cost:result.generation.cost,cost_note:result.generation.cost_note},null,2));
    }
    function setBusy(busy) {
      state.busy = busy; $('comparison').setAttribute('aria-busy',String(busy));
      $('run-button').disabled = busy; $('run-button').textContent = busy ? 'กำลังประมวลผล…' : state.mode === 'recorded' ? 'เปิดผลที่บันทึกไว้ ↗' : 'เปรียบเทียบ ↗';
      document.querySelectorAll('input[name="mode"], #saved-case, [data-question]').forEach(e => { e.disabled = busy || (offline && e.value === 'live'); });
      $('question').readOnly = busy || state.mode === 'recorded';
      if (busy) {
        ['rule-panel','llm-panel'].forEach(id => { const p = $(id).querySelector('.panel-content'); p.replaceChildren(); const e = node('div','empty-state'); e.append(node('span','busy-symbol'),node('h3','','กำลังประมวลผล'),node('p','','กรุณารอสักครู่')); p.append(e); });
      }
    }
    function renderComparison(data, source) {
      state.result = {source, data}; const recorded = source === 'recorded';
      panel('rule',data.rule_based,recorded); panel('llm',data.llm,recorded);
      const context = $('run-context'); context.replaceChildren(); context.hidden = false;
      context.append(node('span','source-tag' + (recorded ? ' recorded' : ''),recorded ? `ผลบันทึก · ${date(state.report.evaluated_at)} · ไม่มีการเรียกโมเดลใหม่` : `รันสด · ${date(new Date().toISOString())}`));
      const download = node('button','download-button','ดาวน์โหลดผล JSON'); download.type = 'button'; download.addEventListener('click',downloadResult); context.append(download);
      const ref = $('reference-panel'); ref.replaceChildren(); ref.hidden = !data.reference;
      if (data.reference) {
        ref.append(node('h3','','ตรวจคำตอบกับ SQL อ้างอิงในรอบบันทึก'),node('p','','คำตอบอ้างอิงนี้เป็นของ snapshot ตอนทดลอง ไม่ได้คำนวณใหม่กับฐานข้อมูลปัจจุบัน'));
        const scores = node('div','reference-scores');
        [['rule','Rule-based'],['llm','LLM']].forEach(([key,label]) => {
          const out = data.reference[key]; const text = out.execution_correct ? 'ตรงอ้างอิง' : out.result.status === 'ok' ? 'ไม่ตรงอ้างอิง' : 'ไม่คืนคำตอบ';
          scores.append(node('span','reference-score ' + (out.execution_correct ? 'good' : 'bad'),`${label}: ${text}`));
        }); ref.append(scores);
        const cols = data.rule_based?.columns?.length === data.reference.columns.length ? data.rule_based.columns : data.llm?.columns?.length === data.reference.columns.length ? data.llm.columns : data.reference.columns;
        ref.append(table(cols,data.reference.rows));
        notice('กำลังดูผลที่บันทึกไว้ คำถาม เวลา Token และคะแนนเป็นข้อมูลจากรอบทดลองเดิม');
      } else {
        const same = data.same_rows_as_rule;
        notice(same === true ? 'คำตอบทั้งสองวิธีตรงกัน แต่ยังไม่ใช่การยืนยันว่าถูก ต้องตรวจข้อมูลต้นทางหรือคำตอบอ้างอิงด้วย' : same === false ? 'คำตอบทั้งสองวิธีต่างกัน ลองเปิด SQL และตรวจเงื่อนไขของแต่ละวิธี' : 'อย่างน้อยหนึ่งวิธีไม่คืนคำตอบ จึงยังเทียบความตรงกันของผลลัพธ์ไม่ได้');
      }
    }
    function recordedCase(id) {
      const c = state.report?.cases.find(c => c.id === id); if (!c) return;
      $('saved-case').value = c.id; $('question').value = c.question;
      renderComparison({question:c.question,rule_based:c.rule.result,llm:c.llm.result,reference:{rows:c.expected_rows,columns:c.expected_columns,rule:c.rule,llm:c.llm}},'recorded');
    }
    function changeMode(mode) {
      if (state.busy) return;
      if (mode === state.mode && state.result?.source === mode) return;
      if (mode === 'recorded' && !state.report) { notice('ยังโหลดผลบันทึกไม่ได้ กรุณาตรวจไฟล์รายงานหรือเปิดไฟล์สำรอง',true); document.querySelector('input[value="live"]').checked=true; return; }
      if (mode === 'live' && offline) return;
      if (state.mode === 'live') state.liveQuestion = $('question').value;
      state.mode = mode; document.querySelector(`input[name="mode"][value="${mode}"]`).checked=true;
      $('recorded-controls').hidden = mode !== 'recorded'; $('example-buttons').hidden = mode === 'recorded'; $('question').readOnly = mode === 'recorded';
      $('mode-note').textContent = mode === 'recorded' ? 'ผลบันทึกเดิม · ไม่ใช้โควตา API' : 'เรียกโมเดล 1 ครั้ง · ใช้โควตา API';
      $('run-button').textContent = mode === 'recorded' ? 'เปิดผลที่บันทึกไว้ ↗' : 'เปรียบเทียบ ↗';
      $('model-label').textContent = mode === 'recorded' ? state.report.model : state.info?.llm?.requested_model || 'ยังไม่ตั้งค่าโมเดล';
      if (mode === 'recorded') recordedCase($('saved-case').value || state.report.cases[0].id);
      else { $('question').value=state.liveQuestion; $('run-context').hidden=true; $('reference-panel').hidden=true; notice('รันสดพร้อมใช้ กดปุ่มเพื่อส่งคำถามใหม่'); ['rule-panel','llm-panel'].forEach(id => { const p=$(id).querySelector('.panel-content'); p.replaceChildren(); const e=node('div','empty-state'); e.append(node('span','empty-symbol','{ }'),node('h3','','พร้อมทดลองคำถามใหม่'),node('p','','ผลที่แสดงต่อไปจะมาจากการรันสด')); p.append(e); }); }
    }
    function switchTab(tab) {
      if (!['demo','schema','results'].includes(tab)) tab='demo';
      document.querySelectorAll('.view').forEach(e => { e.hidden=e.id!==`view-${tab}`; });
      document.querySelectorAll('[data-tab]').forEach(e => { const on=e.dataset.tab===tab; e.classList.toggle('active',on); if(on)e.setAttribute('aria-current','page');else e.removeAttribute('aria-current'); });
      if (location.hash!==`#${tab}`) history.replaceState(null,'',`#${tab}`);
    }
    function renderSchema(schema) {
      if (!schema) return;
      $('definition-cards').replaceChildren();
      schema.definitions.forEach(d => { const c=node('article','definition-card'); c.append(node('h3','',d.title),node('strong','',d.formula),node('p','',d.note)); $('definition-cards').append(c); });
      $('schema-cards').replaceChildren();
      schema.tables.forEach(t => { const c=node('article','schema-card'); c.append(node('h3','',t.name),node('div','schema-title',t.title),node('p','',t.grain)); const list=node('ul'); t.columns.forEach(col=>list.append(node('li','',col))); c.append(list); $('schema-cards').append(c); });
      $('schema-ddl').textContent=schema.ddl;
    }
    function renderExperiment(report) {
      $('experiment-date').textContent=`ผลบันทึก ${date(report.evaluated_at)} · ${report.provider} / ${report.model}`;
      const summary=$('experiment-summary'); summary.replaceChildren();
      [['rule','Rule-based'],['llm',report.model]].forEach(([method,label])=>{
        const s=report.summary[method]; const c=node('article','score-card' + (method==='llm'?' blue':'')); c.append(node('h3','',label));
        const v=node('div','score-value',String(s.execution_correct)); v.append(node('small','',` / ${s.total}`)); c.append(v,node('p','','คำตอบตรง SQL อ้างอิง'));
        const bar=node('div','score-bar'); const fill=node('span'); fill.style.width=`${Math.max(0,Math.min(100,s.execution_accuracy*100))}%`; bar.append(fill); c.append(bar,node('p','',`เวลาเฉลี่ย ${duration(s.mean_method_ms)} ต่อข้อ`)); summary.append(c);
      });
      const usage=report.summary.llm; const u=node('article','score-card'); u.append(node('h3','','การใช้ Token ในรอบทดลอง'),node('div','token-total',count(usage.known_input_tokens+usage.known_output_tokens)),node('p','',`Input ${count(usage.known_input_tokens)} · Output ${count(usage.known_output_tokens)}`),node('p','','ต้นทุนเงินบาท: ยังไม่ทราบอัตราของบริการ')); summary.append(u);
      const t=node('table');const h=node('thead');const hr=node('tr');['คำถาม','Rule-based','LLM',''].forEach(v=>hr.append(node('th','',v)));h.append(hr);t.append(h);const body=node('tbody');
      report.cases.forEach(c=>{const tr=node('tr');tr.append(node('td','case-question',c.question));['rule','llm'].forEach(m=>{const correct=c[m].execution_correct; tr.append(node('td',correct?'pass':'fail',correct?'ตรงอ้างอิง':c[m].result.status==='ok'?'ไม่ตรง':'ไม่คืนคำตอบ'));}); const td=node('td');const b=node('button','case-action','ดูข้อนี้ ↗');b.type='button';b.addEventListener('click',()=>{if(state.busy){notice('กรุณารอผลการรันปัจจุบันก่อนเปลี่ยนคำถาม');return;}switchTab('demo');changeMode('recorded');recordedCase(c.id);$('question').focus();});td.append(b);tr.append(td);body.append(tr);});t.append(body);$('experiment-cases').replaceChildren(t);
      const meta=$('experiment-metadata');meta.replaceChildren();[
        'เทียบค่าตัวเลขและแถวซ้ำทั้งตาราง ส่วน Top-N ตรวจลำดับด้วย ชื่อ alias ไม่ใช้ตัดสิน',
        '4 ข้อที่ Rule-based ไม่ผ่านในรอบนี้เป็นการจับประโยคไม่ได้หรือปฏิเสธ ไม่ใช่การคืน SQL แล้วได้ค่าผิด',
        'LLM ไม่ได้รับข้อมูล seed หรือคำตอบอ้างอิง ไม่มี fallback, retry หรือการซ่อม SQL อัตโนมัติ',
        'Canonical SQL exact match ของรอบนี้เป็น 0/10 ทั้งสองวิธี เพราะรูปแบบ SQL อาจต่างแม้คำตอบตรงกัน ใช้ Execution Accuracy เป็นหลัก',
        `จำนวนแถวตอนทดลอง: ${Object.entries(report.snapshot_row_counts).map(([k,v])=>`${k} ${v}`).join(' · ')}`,
        `Manifest SHA-256: ${report.manifest_sha256}`,`Data snapshot SHA-256: ${report.data_snapshot_sha256}`
      ].forEach(s=>meta.append(node('p','',s)));
      const select=$('saved-case');select.replaceChildren();report.cases.forEach(c=>{const o=node('option','',`${c.id} · ${c.question}`);o.value=c.id;select.append(o);});
    }
    function showData(name) {
      const d=state.data?.tables[name]; if(!d)return;
      document.querySelectorAll('[data-table-name]').forEach(b=>b.classList.toggle('selected',b.dataset.tableName===name));
      $('data-table').replaceChildren(table(d.columns,d.rows));
      $('data-table').prepend(node('p','muted',`${name} · ${d.total_rows} แถว${d.truncated?' · แสดง 200 แถวแรก':''}`));
    }
    async function loadData() {
      $('load-data').disabled=true;
      try {
        if (!offline) state.data=await fetchJSON('/demo/data');
        if (!state.data) throw new Error('ไฟล์สำรองนี้ไม่มีข้อมูลต้นทางที่ตรงกับ snapshot ของรอบบันทึก กรุณาดูจากเดโมบน localhost');
        const tabs=$('data-tabs');tabs.replaceChildren();Object.keys(state.data.tables).forEach(name=>{const b=node('button','',name);b.type='button';b.dataset.tableName=name;b.addEventListener('click',()=>showData(name));tabs.append(b);});
        $('data-source-note').textContent=offline?'ข้อมูลต้นทางที่บันทึกพร้อมไฟล์สำรอง และมี fingerprint ตรงกับรอบทดลอง':'อ่านจากฐานข้อมูลปัจจุบัน อาจต่างจาก snapshot ในรายงานเก่า';
        showData(Object.keys(state.data.tables)[0]);
      }catch(e){$('data-table').replaceChildren(node('p','panel-message',e.message));}
      finally{$('load-data').disabled=false;}
    }
    function downloadResult() {
      if(!state.result)return;const payload={...state.result,exported_at:new Date().toISOString()};
      const blob=new Blob([JSON.stringify(payload,null,2)],{type:'application/json'});const url=URL.createObjectURL(blob);const a=node('a');a.href=url;a.download=`thai-query-${state.result.source}-${Date.now()}.json`;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
    }
    $('query-form').addEventListener('submit',async event=>{
      event.preventDefault();if(state.busy)return;
      if(state.mode==='recorded'){recordedCase($('saved-case').value);return;}
      const question=$('question').value.trim();if(!question)return;state.liveQuestion=question;
      notice('กำลังรอ Rule-based และ IntelSphere ใช้เวลาประมาณไม่กี่วินาที ไม่มีการส่งซ้ำอัตโนมัติ');$('reference-panel').hidden=true;$('run-context').hidden=true;setBusy(true);
      try {const data=await fetchJSON('/compare',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text:question})});renderComparison(data,'live');}
      catch(e){notice(e.name==='AbortError'?'รอนานเกินกำหนด ยังไม่ส่งคำถามซ้ำอัตโนมัติ คุณสามารถดูผลบันทึกแทนได้':`รันไม่สำเร็จ: ${e.message} · ลองเปิดผลบันทึกเพื่อสาธิตต่อ`,true);['rule-panel','llm-panel'].forEach(id=>$(id).querySelector('.panel-content').replaceChildren(node('p','panel-message','ยังไม่ได้รับผลจากการรันครั้งนี้')));}
      finally{setBusy(false);}
    });
    $('question').addEventListener('keydown',e=>{if((e.ctrlKey||e.metaKey)&&e.key==='Enter'&&!state.busy){e.preventDefault();$('query-form').requestSubmit();}});
    document.querySelectorAll('[data-question]').forEach(b=>b.addEventListener('click',()=>{if(state.mode==='recorded')changeMode('live');$('question').value=b.dataset.question;$('question').focus();}));
    document.querySelectorAll('input[name="mode"]').forEach(r=>r.addEventListener('change',()=>changeMode(r.value)));
    document.querySelectorAll('[data-tab]').forEach(b=>b.addEventListener('click',()=>switchTab(b.dataset.tab)));
    document.querySelectorAll('[data-tab-link]').forEach(b=>b.addEventListener('click',e=>{e.preventDefault();switchTab(b.dataset.tabLink);}));
    window.addEventListener('hashchange',()=>switchTab(location.hash.slice(1)));
    $('saved-case').addEventListener('change',()=>recordedCase($('saved-case').value));$('load-data').addEventListener('click',loadData);
    async function init() {
      switchTab(location.hash.slice(1));
      if(offline){
        try{const payload=JSON.parse(offlineElement.textContent);state.report=payload.report;state.info=payload.info;state.data=payload.data;renderSchema(payload.info.schema);renderExperiment(payload.report);$('db-status').textContent='ออฟไลน์ · ผลบันทึก';$('db-status').className='status-pill offline';$('api-link').hidden=true;document.querySelector('input[value="live"]').disabled=true;$('load-data').textContent='แสดงข้อมูลที่บันทึก';$('data-source-note').textContent='ข้อมูลต้นทางที่ฝังในไฟล์สำรอง ไม่ได้อ่านฐานข้อมูลปัจจุบัน';changeMode('recorded');}
        catch{$('db-status').textContent='อ่านไฟล์สำรองไม่ได้';notice('ไฟล์สำรองไม่สมบูรณ์ กรุณาสร้างใหม่',true);}return;
      }
      const [info,health,report]=await Promise.allSettled([fetchJSON('/demo/info'),fetchJSON('/health'),fetchJSON('/demo/recorded')]);
      if(info.status==='fulfilled'){state.info=info.value;renderSchema(info.value.schema);$('model-label').textContent=info.value.llm.requested_model||'ยังไม่ตั้งค่าโมเดล';}
      if(health.status==='fulfilled'&&health.value.ok){$('db-status').textContent='ฐานข้อมูลพร้อมใช้งาน';$('db-status').className='status-pill connected';}else{$('db-status').textContent='ฐานข้อมูลไม่พร้อม';$('db-status').className='status-pill offline';notice('เชื่อมต่อฐานข้อมูลไม่ได้ แต่ยังเปิดผลบันทึกได้',true);}
      if(report.status==='fulfilled'){state.report=report.value;renderExperiment(report.value);}else{$('experiment-summary').replaceChildren(node('p','panel-message','ยังไม่มีรายงานการทดลองที่เปิดได้'));}
    }
    init();
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot);else boot();
})();
