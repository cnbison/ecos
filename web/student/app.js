/* ECOS Student Dashboard - Application JS
 * v0.51.0: 从 index.html 拆出（Phase 4 架构现代化）
 *   之前 inline 在 <script> 块, v0.51.0 拆到独立 app.js, defer 加载
 *   依赖: styles.css (CSS), DOMContentLoaded 时执行
 */
const API = 'http://localhost:5173/api';
let sid = '', q = null;

// v0.51.0: API 封装（Phase 4 架构现代化）
//   之前 8 个 fetch 调用点散落各函数,现在统一走 api 对象
//   _fetch: 内部统一处理 HTTP 错误 + JSON 解析
//   各方法: 一个端点一个方法,参数语义化
const api = {
  async _fetch(url, opts = {}) {
    const r = await fetch(API + url, opts);
    if (!r.ok) {
      const text = await r.text().catch(() => '');
      throw new Error(`HTTP ${r.status} ${url}${text ? ': ' + text.slice(0, 200) : ''}`);
    }
    return r.json();
  },
  getRecentStudents()                 { return this._fetch('/students/recent'); },
  getVersion()                        { return this._fetch('/version'); },
  getQuestion(sid)                    { return this._fetch('/question/' + sid); },
  judgeAnswer(body, signal)           { return this._fetch('/judge', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(body), signal }); },
  submitAnswer(body)                  { return this._fetch('/answer', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(body) }); },
  generateIntervention(sid, body)     { return this._fetch('/intervention/' + sid, { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(body || {}) }); },
  getState(sid)                       { return this._fetch('/state/' + sid); },
  getReport(sid)                      { return this._fetch('/report/' + sid); },
  getHistory(sid)                     { return this._fetch('/history/' + sid); },
};

// 页面加载时,自动填 localStorage 里的 sid + 加载最近学生列表
initLogin();
// v0.48.8: 删 loadEcosVersion() 调用(函数本体已删)
// v0.51.2: 页面加载时, 如果 localStorage 有 ecos_last_sid, 自动 start
//   之前 v0.49.1 用 MutationObserver 监听 study display 再切 tab, 但 start 没自动调用
//   导致刷新后总停在登录界面, URL hash 切 tab 那段空转
//   修复: DOMContentLoaded 时检测 last_sid, 有就 auto-start
//         start() 内部已调 restoreTabFromHash (Phase 4 URL hash 路由), 不再需要单独切 tab
// v0.51.4: 同时拉 /api/version 填设置页 "关于" 区的版本号
//   之前 v0.49.1 hardcoded v0.49.1, 后续 v0.50/v0.51 都没改, Bisen 反馈设置页版本号过时
document.addEventListener('DOMContentLoaded', () => {
  // 拉版本号填设置页（独立 await, 失败不影响 auto-start）
  api.getVersion().then(d => {
    if (d && d.version) {
      const el = document.getElementById('about-version');
      if (el) el.textContent = d.version;
    }
  }).catch(e => console.warn('getVersion:', e));

  try {
    const lastSid = localStorage.getItem('ecos_last_sid');
    if (lastSid) {
      // 把 lastSid 填到 input, 避免 start() fallback 到 'python_student_001' 默认值
      const sidInput = document.getElementById('sid');
      if (sidInput) sidInput.value = lastSid;
      // auto-start (start 内部会 hide login + show topbar + show study + restoreTabFromHash)
      start();
    }
  } catch(e) {
    console.warn('auto-start:', e);
  }
});

const DIMS = [
  {k:'K', label:'概念理解', color:'#1e40af'},
  {k:'P', label:'程序知识', color:'#7c3aed'},
  {k:'S', label:'策略知识', color:'#059669'},
  {k:'C', label:'元认知',   color:'#d97706'},
  {k:'X', label:'跨域迁移', color:'#dc2626'},
];

async function start(sidOverride) {
  // v0.51.2: 支持 auto-start（页面刷新时跳过登录入口）
  //   优先级: sidOverride > input.value > localStorage ecos_last_sid > 'python_student_001'
  if (sidOverride) {
    sid = sidOverride;
  } else {
    sid = document.getElementById('sid').value.trim();
  }
  if (!sid) {
    try { sid = localStorage.getItem('ecos_last_sid') || ''; } catch(e) { sid = ''; }
  }
  if (!sid) sid = 'python_student_001';
  // 记住 sid 到 localStorage（W4 改进：避免重启后忘记 ID）
  try { localStorage.setItem('ecos_last_sid', sid); } catch(e) {}
  // v0.51.2: 同步到 input.value, 退出后再回来能看见当前 sid
  try {
    const sidInput = document.getElementById('sid');
    if (sidInput && !sidInput.value) sidInput.value = sid;
  } catch(e) {}
  // W5+: topbar 显示当前学生 ID
  document.getElementById('current-sid').innerText = sid;
  document.getElementById('login').style.display = 'none';
  document.getElementById('topbar').style.display = 'block';
  // 0.47.7: 改 async + await,先 fetch state/question 再显示 study
  //   修复 race condition(Bisen 反馈"重新登录刚开始 5D/Bloom/TC 区域空白,刷新才好")
  //   根因:之前 study.style.display='block' 同步执行,refresh() 还没返回,
  //         用户先看到的是 5D/Bloom/TC 区域未渲染的初始 HTML 注释
  //   修复:Promise.all 并行 fetch state + question,完成后再显示 study
  //   副作用:fetch 慢时用户卡在 login 区——加 loading 文字提示
  const loginBtn = document.querySelector('.form-row button');
  const origBtnText = loginBtn ? loginBtn.innerText : null;
  if (loginBtn) {
    loginBtn.disabled = true;
    loginBtn.innerText = '加载中…';
  }
  try {
    // v0.48.4: 加 5s timeout 保护 + fetch 失败不 display study
    //   Bisen 反馈 0.47.7 修过同款 race condition,但偶尔还出现"5D 空白 + 总置信度 0.000"
    //   根因 1: Flask 冷启动时 /api/state 慢,Promise.all 一直 await
    //   根因 2: refresh() 之前 try/catch 包裹整个函数,fetch 失败被静默吞掉
    //           → start() 以为成功了 → display:block → 但 d=undefined → 5D 显示初始 innerText
    //   修复: 5s 超时 + refresh() 重构(fetch 阶段让 promise reject)
    //         start() 收到 reject/timeout → 不 display study,提示用户刷新
    const timeout = new Promise((_, reject) =>
      setTimeout(() => reject(new Error('加载超时(5s) — 后端 /api/state 可能冷启动')), 5000)
    );
    await Promise.race([Promise.all([refresh(), loadQ()]), timeout]);
  } catch (e) {
    console.warn('start() fetch 失败/超时:', e);
    const study = document.getElementById('study');
    // v0.51.2: auto-start 失败时不弹 alert, 让用户手动重新登录
    //   静默恢复 login 区, 按钮恢复可点
    if (sidOverride) {
      // auto-start 失败: 静默, 恢复 login 区让用户手动
      document.getElementById('topbar').style.display = 'none';
      document.getElementById('login').style.display = '';
      if (study) study.style.display = 'none';
    } else {
      // 手动点登录失败: 弹 alert 提示刷新
      alert('数据加载失败:\n' + e.message + '\n\n请刷新浏览器重试。');
      if (study) study.innerHTML = '<div class="card" style="text-align:center;color:#ef4444;padding:24px;">❌ 数据加载失败<br><small style="color:#9ca3af;">' + e.message + '</small><br><br><button onclick="location.reload()" style="padding:6px 16px;background:#2563eb;color:#fff;border:none;border-radius:4px;cursor:pointer;">刷新页面</button></div>';
    }
    if (loginBtn) {
      loginBtn.disabled = false;
      if (origBtnText !== null) loginBtn.innerText = origBtnText;
    }
    return;  // 不 display:block,让 study 保持 display:none(用户看到 login + alert)
  }
  if (loginBtn) {
    loginBtn.disabled = false;
    if (origBtnText !== null) loginBtn.innerText = origBtnText;
  }
  document.getElementById('study').style.display = 'block';
  // v0.51.0: 恢复 tab (Phase 4 URL hash 路由)
  //   必须在 study display:block 之后,否则 panel 还没创建,switchTab 找不到元素
  restoreTabFromHash();
}

function clearLastSid() {
  try { localStorage.removeItem('ecos_last_sid'); } catch(e) {}
  alert('已清除浏览器记住的 ID');
}

// v0.48.8: 删 loadEcosVersion (v0.48.7 commit 把顶栏的版本号显示移除了)
//   函数本身被 0.46.4 commit 加进来用,现在不需要单独拉版本号了
//   保留 API /api/version(其他调试用),仅删这个 JS helper

// v0.49.1: Tab 切换(学习 / 轨迹 / 设置)
//   默认 Tab 1 active,localStorage 记忆选择(刷新保留)
function switchTab(name) {
  const panels = ['study', 'traj', 'settings'];
  for (const p of panels) {
    const panel = document.getElementById('panel-' + p);
    const btn = document.querySelector(`.tab-btn[data-tab="${p}"]`);
    if (p === name) {
      if (panel) panel.style.display = '';
      if (btn) btn.classList.add('active');
      // 切到 settings 时同步学生 ID
      if (p === 'settings') {
        const settingsSid = document.getElementById('settings-sid');
        const currentSid = document.getElementById('current-sid');
        if (settingsSid && currentSid) settingsSid.innerText = currentSid.innerText;
      }
      // v0.49.2: 切到 traj 时,如果答题历史未加载,自动加载一次
      if (p === 'traj') {
        const hb = document.getElementById('histList');
        if (!hb || !hb.dataset.loaded) {
          loadHistory();
        }
      }
    } else {
      if (panel) panel.style.display = 'none';
      if (btn) btn.classList.remove('active');
    }
  }
  // v0.51.0: URL hash 路由（Phase 4）
  //   优先级: hash > localStorage > 默认 study
  //   这样刷新 #traj 时自动回到轨迹 tab,书签也能定位 tab
  try {
    if (location.hash !== '#/' + name) {
      history.replaceState(null, '', '#/' + name);
    }
    localStorage.setItem('ecos_last_tab', name);
  } catch(e) {}
}

// v0.51.0: URL hash 路由初始化（Phase 4）
//   优先级: location.hash > localStorage > 'study'
//   必须在 start() 加载数据 + display:block 之后调用,否则 panel 还没创建
function restoreTabFromHash() {
  const hash = (location.hash || '').replace(/^#\//, '');
  const valid = ['study', 'traj', 'settings'];
  let target = valid.includes(hash) ? hash : null;
  if (!target) {
    try {
      const last = localStorage.getItem('ecos_last_tab');
      if (valid.includes(last)) target = last;
    } catch(e) {}
  }
  if (!target) target = 'study';
  switchTab(target);
}

// v0.49.1: 退出登录(回到 login 页面)
function logout() {
  if (!confirm('确定退出当前学生?')) return;
  try { localStorage.removeItem('ecos_last_sid'); } catch(e) {}
  // 清空 in-memory 状态(下次 start() 会重新从 DB 加载)
  document.getElementById('study').style.display = 'none';
  document.getElementById('topbar').style.display = 'none';
  document.getElementById('login').style.display = '';
  document.getElementById('sid').value = '';
  if (typeof _STUDENT_STATES !== 'undefined' && _STUDENT_STATES) {
    delete _STUDENT_STATES[sid];
  }
  sid = '';
  q = null;
  // 重新加载最近学生
  if (typeof loadRecentStudents === 'function') loadRecentStudents();
}

// 页面加载时,自动填 localStorage 里的 sid + 加载最近学生列表
function initLogin() {
  loadRecentStudents();
}

async function loadRecentStudents() {
  const input = document.getElementById('sid');
  try {
    const data = await api.getRecentStudents();
    const list = data.students || [];
    if (list.length === 0) {
      // DB 无最近学生,保留默认 placeholder
      input.value = '';
      input.placeholder = '请输入学生 ID';
      input.disabled = false;
      return;
    }
    const container = document.getElementById('recent-students');
    const btns = document.getElementById('recent-buttons');
    let html = '';
    for (const s of list) {
      const safeS = s.replace(/'/g, "\\'");
      html += `<button class="recent-btn" data-sid="${s}" onclick="selectRecent('${safeS}', this)">${s}</button>`;
    }
    btns.innerHTML = html;
    container.style.display = 'block';
    // W5 改进：input 默认值 = localStorage 里的 lastSid;否则 = 最近学生第一个
    const lastSid = (() => { try { return localStorage.getItem('ecos_last_sid'); } catch(e) { return null; } })();
    if (lastSid && list.includes(lastSid)) {
      input.value = lastSid;
      // 高亮对应的按钮
      const btn = btns.querySelector(`[data-sid="${lastSid}"]`);
      if (btn) btn.classList.add('selected');
    } else {
      // 默认选第一个最近学生
      input.value = list[0];
      const firstBtn = btns.querySelector(`[data-sid="${list[0]}"]`);
      if (firstBtn) firstBtn.classList.add('selected');
    }
    input.placeholder = '或输入新学生 ID';
    input.disabled = false;  // 关键：加载完成后启用 input
  } catch(e) {
    console.warn('recent students:', e.message);
    document.getElementById('sid').disabled = false;  // 出错也要启用
  }
}

function selectRecent(sid, btn) {
  document.getElementById('sid').value = sid;
  // 高亮选中的按钮
  document.querySelectorAll('.recent-btn').forEach(b => b.classList.remove('selected'));
  if (btn) btn.classList.add('selected');
}

async function loadQ() {
  try {
    const d = await api.getQuestion(sid);
    // v0.51.1: 防御 d===null / d.error / 缺字段 (Bisen 截图报 'null is not an object'
    //   触发条件: 后端 HTTP 200 但 body 是 null literal, 或字段缺失
    if (!d || typeof d !== 'object') {
      throw new Error('/api/question 返回无效响应: ' + JSON.stringify(d));
    }
    if (d.error) {
      throw new Error(d.error);
    }
    if (d.done) {
      document.getElementById('qtext').innerHTML = '<b style="color:#16a34a">🎉 全部完成！</b>';
      return;
    }
    q = d;
    const h = v => String(v).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
    document.getElementById('qtext').innerHTML = h(d.problem_text).replace(/\n/g,'<br>');
    document.getElementById('qid').innerText = d.problem_id;
    document.getElementById('qtopic').innerText = d.skill_name;
    document.getElementById('qbloom').innerText = d.bloom_layer;
    document.getElementById('ans').value = '';
    document.getElementById('fbox').style.display = 'none';
    document.getElementById('ivbox').style.display = 'none';
    document.getElementById('btnSub').style.display = '';
    document.getElementById('btnNext').style.display = 'none';
  } catch(e) { alert(e.message); }
}

async function submit() {
  if (!q) return;
  const a = document.getElementById('ans').value.trim();
  if (!a) { alert('请输入答案'); return; }
  document.getElementById('btnSub').disabled = true;
  document.getElementById('btnSub').innerText = 'AI 评判中…';
  // v0.48.6: 给 /api/judge 加 30s timeout(LLM 调外部 API 偶尔慢,Bisen 反馈"卡死")
  //   AbortController 比 fetch 直接 timeout 更可靠 — 超时后取消请求,按钮立即恢复
  const judgeController = new AbortController();
  const judgeTimeout = setTimeout(() => judgeController.abort(), 30000);
  try {
    const jd = await api.judgeAnswer(
      { student_id: sid, problem_id: q.problem_id, student_answer: a },
      judgeController.signal,
    );
    clearTimeout(judgeTimeout);
    if (jd.error) { alert(jd.error); return; }
    const ok = jd.correct;
    const reasoning = jd.reasoning || '';

    const d = await api.submitAnswer({
      student_id: sid, problem_id: q.problem_id, skill_id: q.topic,
      correct: ok, bloom_layer: q.bloom_layer, explanation_text: a, reasoning: reasoning,
      // v0.49.2: 给答题历史详情页用(后端也会从 Q 矩阵读 correct_answer 兜底)
      user_answer: a, correct_answer: q.correct_answer || ''
    });

    // v0.48.5: 检查持久化标志,save 失败时弹 alert (Bisen 反馈 7-19~7-21 期间 4 道题数据丢了)
    if (d.persisted === false) {
      alert('⚠️ 持久化失败!\n\n答题结果已更新 in-memory 状态,但保存到数据库失败(可能 Flask 进程需要重启)。\n刷新页面会丢失这题结果。\n\n建议: 重启 Flask 进程后再答题。');
    }

    document.getElementById('fbox').style.display = 'block';
    document.getElementById('fbres').className = 'fb ' + (ok ? 'ok' : 'err');
    document.getElementById('fbres').innerHTML = (ok ? '✅ 正确' : '❌ 错误') + `<div style="margin-top:4px;font-size:12px;color:#6b7280;">AI 评判：${reasoning}</div>`;
    let meta = `K=${d.theta.K}  P=${d.theta.P}  S=${d.theta.S}  C=${d.theta.C}  X=${d.theta.X}`;
    if (d.misc_triggered) meta += ` &nbsp;|&nbsp; ⚠️ ${d.misc_id} (${d.misc_confidence})`;
    document.getElementById('fbres').innerHTML += `<div class="meta">${meta}</div>`;
    if (d.misc_triggered) {
      const d2 = await api.generateIntervention(sid, {
        misc_id: d.misc_id, student_answer: a, problem_text: q.problem_text
      });
      if (d2.intervention) {
        document.getElementById('ivbox').style.display = 'block';
        document.getElementById('ivtype').innerHTML = `<span class="lbl">${d2.misc_id} ${d2.misc_name}</span> ${d2.type}`;
        document.getElementById('ivbd').innerText = d2.intervention;
      }
    }
    document.getElementById('btnSub').style.display = 'none';
    document.getElementById('btnNext').style.display = '';
    // v0.48.3: 答完题重置报告 loaded 标记,让 refresh 末尾的 renderReportCard 强制重画
    //   之前只加载一次,Bisen 反馈\"第 10 题后报告内容没变化\"
    const rb = document.getElementById('reportBody');
    if (rb) delete rb.dataset.loaded;
    // v0.49.2: 重置答题历史 loaded 标记 + 自动刷新（如果已展开）
    const hb = document.getElementById('histList');
    if (hb) delete hb.dataset.loaded;
    if (document.getElementById('histBody').style.display !== 'none') {
      loadHistory();
    }
    await refresh();
  } catch(e) { alert(e.message); } finally {
    document.getElementById('btnSub').disabled = false;
    document.getElementById('btnSub').innerText = '提交答案';
  }
}

async function nextQ() {
  await refresh();
  await loadQ();
}

// 渲染 5D 维度（W4 升级：theta 数字保持清晰,只灰显"置信度"标签 + 信息量 tooltip）
function renderDims(d) {
  const mx = 2.0;
  let html = '';
  for (const dim of DIMS) {
    const v = parseFloat(d.theta[dim.k]) || 0;
    const conf = parseFloat(d.theta_confidence?.[dim.k]) || 0;
    const se = parseFloat(d.theta_se?.[dim.k]) || 1.0;
    // W4 核心改进：theta 数字始终清晰,只灰显"置信度"标签
    //   - conf < 0.5 → 灰显 conf label + tooltip 解释
    //   - conf < 0.5 + SE > 0.7 → tooltip 加"信息量严重不足"
    const isConfLow = conf < 0.5;
    const isHighSE = se > 0.7;
    const confClass = isConfLow ? 'is-warmup' : '';
    const confReason = isConfLow
      ? `${dim.label}:置信度仅 ${Math.round(conf*100)}%（SE=${se.toFixed(2)}）信息量${isHighSE ? '严重' : ''}不足,估计暂不可靠`
      : '';
    const pct = Math.min(100, Math.abs(v)/mx*100);
    const confPct = Math.min(100, conf*100);
    html += `<div class="dim">
      <div class="f-row dim-head">
        <span class="lbl" style="background:${dim.color}">${dim.k}</span>
        <span class="f-name">${dim.label}</span>
      </div>
      <div class="theta">${Number(v).toFixed(2)}</div>
      <div class="bar"><div style="width:${pct}%;background:${dim.color}"></div></div>
      <div class="conf-label ${confClass}" title="${confReason}">置信度 ${Math.round(confPct)}%</div>
      <div class="conf-bar"><div style="width:${confPct}%"></div></div>
    </div>`;
  }
  document.getElementById('dimGrid').innerHTML = html;
}

// 渲染 Bloom L1-L6（W4 升级：未探测层用虚线 + 灰色 + 「—」）
function renderBloom(d) {
  document.getElementById('bdom').innerText = d.bloom_profile?.dominant || '—';
  const bl = d.bloom_profile?.bloom_levels || {};
  const labels = {L1:'记忆',L2:'理解',L3:'应用',L4:'分析',L5:'评价',L6:'创造'};
  let html = '';
  for (const lvl of ['L1','L2','L3','L4','L5','L6']) {
    const v = parseFloat(bl[lvl]) || 0;
    // 未探测判定：v 偏离默认 0.5 < 0.01（说明 update 几乎没碰过这层）
    const isProbed = Math.abs(v - 0.5) > 0.01;
    const pct = Math.round(v * 100);
    if (isProbed) {
      html += `<div class="br">
        <span class="b-lbl">${lvl}</span>
        <span class="b-name">${labels[lvl]}</span>
        <div class="fill"><div style="width:${pct}%"></div></div>
        <span class="pct">${pct}%</span>
      </div>`;
    } else {
      // 未探测层:虚线 + 灰色 + 显示「—」
      html += `<div class="br unprobed" title="${lvl} 尚未被题目探测到（默认 0.5）">
        <span class="b-lbl">${lvl}</span>
        <span class="b-name">${labels[lvl]}</span>
        <div class="fill"><div class="unprobed-bar"></div></div>
        <span class="pct">—</span>
      </div>`;
    }
  }
  document.getElementById('bloomRows').innerHTML = html;
}

// 渲染 TC states（W4 升级：progress 颜色分级 <0.3 灰 / 0.3-0.7 黄 / >0.7 绿）
function renderTC(d) {
  const tc = d.tc_states || [];
  if (tc.length === 0) {
    document.getElementById('tcRows').innerHTML = '<div style="font-size:11px;color:#9ca3af;padding:6px 10px;">暂无 TC 数据（答对高水平题触发）</div>';
    return;
  }
  let html = '';
  for (const t of tc) {
    const statusLabel = {pre_liminal:'前',liminal:'LIMINAL',post_liminal:'已跨越'}[t.status] || t.status;
    const statusClass = {pre_liminal:'pre',liminal:'liminal',post_liminal:'post'}[t.status] || 'pre';
    const pct = Math.round((t.progress || 0) * 100);
    // 颜色分级
    let progClass = 'tc-low';
    if (t.progress >= 0.7) progClass = 'tc-high';
    else if (t.progress >= 0.3) progClass = 'tc-mid';
    html += `<div class="tc-r">
      <span class="tc-id">${t.id}</span>
      <span class="tc-status ${statusClass}">${statusLabel}</span>
      <div class="tc-progress"><div class="${progClass}" style="width:${pct}%"></div></div>
      <span class="tc-pct">${pct}%</span>
    </div>`;
  }
  document.getElementById('tcRows').innerHTML = html;
}

// 渲染 LearningDNA (v0.52.0: 数据量不足, 标"待启用")
//   lbc001 22 道题, 9 道带 timestamp, 错误也少, 推断不出 LearningDNA 字段
//   当前 LearningDNA 是 v0.1.0 占位实现, confidence=0.0, 真实估计逻辑待 Phase 4+
//   隐藏置信度数字, 标"待启用"避免用户疑惑
function renderLDN(d) {
  const ldn = d.learning_dna || {};
  document.getElementById('ldnRow').innerHTML = `
    <div style="color:#9ca3af; font-size:11px; padding:4px 0;">
      需更多答题历史 (≥50 题) + 交互行为数据 才能推断
    </div>
    <div style="color:#6b7280; font-size:11px; padding:2px 0;">
      <span style="display:inline-block; width:60px; color:#9ca3af;">输入偏好</span> ${ldn.input_preference || '—'}
    </div>
    <div style="color:#6b7280; font-size:11px; padding:2px 0;">
      <span style="display:inline-block; width:60px; color:#9ca3af;">反馈偏好</span> ${ldn.feedback_preference || '—'}
    </div>
    <div style="color:#6b7280; font-size:11px; padding:2px 0;">
      <span style="display:inline-block; width:60px; color:#9ca3af;">错误模式</span> ${(ldn.error_pattern || []).length || 0} 条
    </div>
  `;
}

// 渲染 Trajectory
function renderTraj(d) {
  const traj = d.trajectory || [];
  if (traj.length === 0) {
    document.getElementById('trajCard').style.display = 'none';
    return;
  }
  document.getElementById('trajCard').style.display = 'block';
  document.getElementById('trajN').innerText = traj.length;
  let html = '';
  // 反序，最近的在前
  for (let i = traj.length - 1; i >= 0; i--) {
    const t = traj[i];
    const theta = t.theta_5d || [];
    const ts = t.timestamp ? t.timestamp.substring(5,16) : `#${i+1}`;
    html += `<div class="traj-item">
      <span class="t-num">${ts}</span>
      <span class="t-k">K${theta[0]?.toFixed(2)||'—'}</span>
      <span class="t-p">P${theta[1]?.toFixed(2)||'—'}</span>
      <span class="t-s">S${theta[2]?.toFixed(2)||'—'}</span>
      <span style="margin-left:auto;font-size:10px;color:#9ca3af;">${t.bloom_dominant||''}</span>
    </div>`;
  }
  document.getElementById('trajList').innerHTML = html;
}

// 渲染 Misconceptions
function renderMisc(d) {
  const misc = d.misc_history || [];
  if (misc.length === 0) {
    document.getElementById('miscCard').style.display = 'none';
    return;
  }
  document.getElementById('miscCard').style.display = 'block';
  document.getElementById('miscN').innerText = misc.length;
  document.getElementById('miscList').innerHTML = misc.slice(-10).map(m =>
    `<span class="misc-badge">${m}</span>`
  ).join('');
}

async function refresh() {
  // v0.48.4: 重构 — fetch 阶段不 try/catch(让 promise 在 fetch 失败时 reject)
  //   之前 try/catch 包裹整个函数,fetch 失败被静默吞掉 → start() 以为成功了 → display:block
  //   但 d 是 undefined,5D/Bloom/TC 显示初始 innerText (k总置信度 0.000, Bloom: —)
  //   修法:fetch 阶段异常让它冒到外层,start() 看到 reject → 不 display study,提示用户
  let d;
  try {
    d = await api.getState(sid);
    if (d.error) {
      throw new Error('/api/state 返回 error: ' + d.error);
    }
  } catch (e) {
    // fetch 失败:让 promise reject,start() 收到后能正确处理
    throw new Error('state 加载失败: ' + e.message);
  }

  // 渲染阶段: 每个 render 用独立 try/catch,某个失败不影响其他
  try {
    // W1 (2026-07-17): Bloom 距下一层 Δ
    document.getElementById('kb').innerText = d.bloom_profile?.dominant || '—';
    const dist = d.bloom_layer_distance;
    const kdelta = document.getElementById('kdelta');
    if (dist && dist.next) {
      const gapVal = dist.gap || 0;
      const sign = gapVal > 0 ? '+' : '';
      const deltaClass = gapVal > 0.05 ? 'positive' : (gapVal < -0.05 ? 'negative' : '');
      kdelta.className = 'bloom-delta ' + deltaClass;
      kdelta.innerText = `→ ${dist.next} (${sign}${gapVal.toFixed(2)})`;
      kdelta.title = `当前 ${dist.current} 掌握 ${(dist.current_prob*100).toFixed(0)}%，${dist.next} 掌握 ${(dist.next_prob*100).toFixed(0)}%`;
      kdelta.style.display = '';
    } else if (dist && !dist.next) {
      kdelta.innerText = '🎯 已达顶层';
      kdelta.className = 'bloom-delta positive';
      kdelta.title = '已达到 Bloom 6 创造层';
      kdelta.style.display = '';
    } else {
      kdelta.style.display = 'none';
    }

    // W1 (2026-07-17): 总置信度(v0.48.8 移除了 C 折扣顶栏显示 — 移到 C 维度卡里单独看,本 commit 仅删顶栏)
    const isWarmup = !!d.is_warmup;
    const kovEl = document.getElementById('kov');
    kovEl.innerText = '总置信度: ' + (d.overall_confidence || 0).toFixed(3);
    kovEl.className = '';
    kovEl.title = (d.overall_confidence || 0) < 0.5
      ? `整体置信度仅 ${((d.overall_confidence || 0) * 100).toFixed(0)}%,需要更多题目收敛`
      : '';

    // W1 (2026-07-17): warm-up 状态机
    const prevWarmup = window._lastIsWarmup;
    window._lastIsWarmup = isWarmup;
    const wpill = document.getElementById('warmup-pill');
    if (isWarmup) {
      wpill.style.display = '';
      wpill.classList.remove('fadeout');
    } else {
      if (prevWarmup === true) {
        wpill.classList.add('fadeout');
        setTimeout(() => { wpill.style.display = 'none'; wpill.classList.remove('fadeout'); }, 350);
      } else {
        wpill.style.display = 'none';
      }
    }

    renderDims(d);
    renderBloom(d);
    renderTC(d);
    renderLDN(d);
    renderTraj(d);
    renderMisc(d);
    renderReportCard(d);  // W5+ (2026-07-19): 个人学习画像面板
  } catch(e) {
    // 渲染阶段失败:warn 但不 throw(部分渲染仍可工作)
    console.warn('refresh 渲染部分失败(d 已成功拿到):', e);
  }
}

// W5+ (2026-07-19): 个人学习画像面板——纯前端渲染后端 interpretation 字段
// v0.48.3: 加 force 参数,submit 答完题后强制重画（之前只加载一次,Bisen 反馈"第 10 题后内容没变"）
async function renderReportCard(stateData, force = false) {
  // 只在有答题数据后才显示（answered_count > 0）
  const answered = stateData?.summary?.answered_count
    || (stateData?.trajectory ? stateData.trajectory.length : 0)
    || 0;
  const card = document.getElementById('reportCard');
  if (answered < 1) {
    card.style.display = 'none';
    return;
  }
  card.style.display = '';
  document.getElementById('reportStamp').innerText = `${answered} 题后生成`;

  // 懒加载守卫:平时不重拉(避免 refresh 频繁触发),submit 后 force=true 重画
  const body = document.getElementById('reportBody');
  if (!force && body.dataset.loaded === '1') return;

  try {
    const data = await api.getReport(sid);
    if (data.error) {
      body.innerHTML = `<div class="report-loading">❌ 报告错误: ${data.error}</div>`;
      return;
    }
    body.innerHTML = renderInterpretationHTML(data.interpretation, data.ecos_version);
    body.dataset.loaded = '1';
  } catch(e) {
    body.innerHTML = `<div class="report-loading">❌ 报告加载异常: ${e.message}</div>`;
  }
}

function renderInterpretationHTML(interp, ecosVersion) {
  if (!interp || interp.error) {
    return `<div class="report-loading">⚠ 解读暂不可用: ${interp?.error || 'unknown'}</div>`;
  }
  const fiveD = interp.five_d || {};
  const bloom = interp.bloom || {};
  const tc = interp.tc || {};
  const traj = interp.trajectory || {};
  const steps = interp.next_steps || [];

  // 5D 维度顺序
  const dimOrder = ['K', 'P', 'S', 'C', 'X'];
  const fiveDRows = dimOrder
    .filter(d => fiveD[d])
    .map(d => {
      const v = fiveD[d];
      return `<div class="report-5d-row">
        <div class="report-5d-name">${d} ${esc(v.name || '')}</div>
        <div><span class="report-tag ${esc(v.level || 'medium')}">${esc(v.level_label || '')}</span></div>
        <div class="report-5d-comment">${esc(v.comment || '')}</div>
      </div>`;
    }).join('');

  // TC topic 列表
  const tcRows = (tc.topics || []).map(t => {
    const tagClass = t.tag === '接近 liminal' ? 'approaching'
      : t.tag === '进行中' ? 'progressing' : 'untouched';
    return `<div class="report-tc-row">
      <div class="report-tc-name">${esc(t.id)}</div>
      <div class="report-tc-prog">${(t.progress * 100).toFixed(0)}%</div>
      <div><span class="report-tag ${tagClass}">${esc(t.tag)}</span></div>
    </div>`;
  }).join('');

  // 轨迹 Δ5D 芯片
  const deltaChips = Object.entries(traj.delta_5d || {})
    .map(([dim, val]) => {
      const cls = val > 0.01 ? 'up' : val < -0.01 ? 'down' : '';
      const sign = val > 0 ? '+' : '';
      return `<span class="report-delta-chip ${cls}">${dim} ${sign}${val.toFixed(2)}</span>`;
    }).join('');

  // next_steps 列表
  const stepItems = steps.map(s => `<li>${esc(s)}</li>`).join('');

  return `
    <div class="report-section">
      <div class="report-section-title">📌 总评</div>
      <div class="report-overall">${esc(interp.overall || '')}</div>
    </div>

    <div class="report-section">
      <div class="report-section-title">📊 5D 维度解读</div>
      ${fiveDRows}
    </div>

    <div class="report-section">
      <div class="report-section-title">🎯 Bloom 认知深度</div>
      <div class="report-bloom-meta">
        主导层: <strong>${esc(bloom.dominant_label || bloom.dominant || '—')}</strong>
        ${bloom.next_layer ? `· 下一层 <strong>${esc(bloom.next_layer)}</strong> gap = <strong>${(bloom.gap_to_next || 0).toFixed(3)}</strong>` : ''}
        ${bloom.unprobed_layers && bloom.unprobed_layers.length ? `· 未探及: ${bloom.unprobed_layers.map(esc).join(', ')}` : ''}
      </div>
      <div class="report-comment">${esc(bloom.comment || '')}</div>
    </div>

    <div class="report-section">
      <div class="report-section-title">🧠 阈值概念 (TC)</div>
      <div class="report-comment">${esc(tc.comment || '')}</div>
      ${tcRows}
    </div>

    <div class="report-section">
      <div class="report-section-title">📈 成长轨迹</div>
      <div class="report-comment">${esc(traj.trend || '')}</div>
      <div class="report-traj-delta">${deltaChips}</div>
      <div class="report-comment">${esc(traj.comment || '')}</div>
    </div>

    <div class="report-section">
      <div class="report-section-title">💡 下一步建议</div>
      <ol class="report-steps">${stepItems}</ol>
    </div>

    <div class="report-comment" style="text-align:right; color:#9ca3af; font-size:10px; margin-top:8px;">
      ECOS v${esc(ecosVersion || '?')} · 规则引擎生成 · 无 LLM 调用
    </div>
  `;
}

function toggleReport() {
  const body = document.getElementById('reportBody');
  const btn = document.getElementById('reportToggle');
  if (body.style.display === 'none') {
    body.style.display = '';
    btn.innerText = '收起 ↑';
  } else {
    body.style.display = 'none';
    btn.innerText = '展开 ↓';
  }
}

// v0.49.0: 成长轨迹折叠切换(同 toggleReport 模式)
function toggleTraj() {
  const list = document.getElementById('trajList');
  const btn = document.getElementById('trajToggle');
  if (list.style.display === 'none') {
    list.style.display = '';
    btn.innerText = '收起 ↑';
  } else {
    list.style.display = 'none';
    btn.innerText = '展开 ↓';
  }
}

// v0.49.2: 答题历史折叠切换
function toggleHistory() {
  const body = document.getElementById('histBody');
  const btn = document.getElementById('histToggle');
  if (body.style.display === 'none') {
    body.style.display = '';
    btn.innerText = '收起 ↑';
    // 展开时如果还没渲染,触发加载
    const list = document.getElementById('histList');
    if (list && !list.dataset.loaded) {
      loadHistory();
    }
  } else {
    body.style.display = 'none';
    btn.innerText = '展开 ↓';
  }
}

// v0.49.2: 加载答题历史
async function loadHistory() {
  const body = document.getElementById('histBody');
  const card = document.getElementById('histCard');
  const loading = document.getElementById('histLoading');
  if (!body || !card) return;
  if (loading) loading.innerText = '加载中…';
  try {
    const data = await api.getHistory(sid);
    if (data.error) throw new Error(data.error);
    // 顶部统计
    document.getElementById('histN').innerText = data.total || 0;
    document.getElementById('histRate').innerText =
      data.total > 0 ? `正确率 ${(data.correct_rate * 100).toFixed(0)}%` : '—';
    card.style.display = '';
    // 渲染列表
    renderHistory(data.items || []);
  } catch (e) {
    if (loading) loading.innerText = '❌ 加载失败: ' + e.message;
  }
}

function renderHistory(items) {
  const body = document.getElementById('histBody');
  if (!items.length) {
    body.innerHTML = '<div class="hist-empty">还没有答题记录</div>';
    body.dataset.loaded = '1';
    return;
  }
  const rows = items.map((h, idx) => {
    const correct = !!h.correct;
    const mark = correct ? '✅' : '❌';
    const cls = correct ? 'correct' : 'wrong';
    const ts = h.timestamp ? formatTs(h.timestamp) : '—';
    const detail = `
      <div class="label">你的答案：</div><div class="val">${esc(h.user_answer) || '(空)'}</div>
      <div class="label" style="margin-top:4px;">正确答案：</div><div class="val">${esc(h.correct_answer) || '(未存)'}</div>
    `;
    return `
      <div class="hist-row ${cls}" onclick="toggleHistDetail(${idx})">
        <span class="hist-pid">${esc(h.problem_id)}</span>
        <span class="hist-mark">${mark}</span>
        <span class="hist-bloom">${esc(h.bloom_level || '—')}</span>
        <span class="hist-ts">${ts}</span>
      </div>
      <div class="hist-detail" id="histDetail${idx}">${detail}</div>
    `;
  }).join('');
  body.innerHTML = `<div class="hist-list" id="histList" data-loaded="1">${rows}</div>`;
}

function toggleHistDetail(idx) {
  const el = document.getElementById('histDetail' + idx);
  if (el) el.classList.toggle('show');
}

function formatTs(iso) {
  // iso 形如 2026-07-21T12:30:18.xxx
  if (!iso) return '—';
  // 截到分钟
  const m = iso.match(/^(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2})/);
  if (m) return `${m[1]} ${m[2]}`;
  return iso;
}

// 简单 HTML escape 工具（避免 interpretation 中的引号/尖括号被解释成 HTML）
function esc(s) {
  if (s === null || s === undefined) return '';
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

// W3+：导出学习报告（C 端接口）
async function exportReport() {
  const btn = document.getElementById('export-btn');
  const oldText = btn.innerText;
  btn.disabled = true;
  btn.innerText = '导出中…';
  try {
    const data = await api.getReport(sid);
    // 触发下载 JSON 文件
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    const today = new Date().toISOString().slice(0, 10);
    a.download = `ecos_report_${sid}_${today}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    btn.innerText = '✅ 已导出';
    setTimeout(() => { btn.innerText = oldText; }, 1500);
  } catch(e) {
    alert('导出失败：' + e.message);
  } finally {
    btn.disabled = false;
  }
}
