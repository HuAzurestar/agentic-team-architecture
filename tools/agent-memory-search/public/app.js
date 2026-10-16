import { MODES, DEFAULTS, buildBody, persistable, restoreState, resultRows } from './core.js';

const STORAGE_KEY = 'agentmemory-search:v1';
const $ = id => document.getElementById(id);
let storageAvailable = true;
let stored;
try { stored = localStorage.getItem(STORAGE_KEY); } catch { storageAvailable = false; }
const state = restoreState(stored);
let imageBase64 = '';
let imageGeneration = 0;
let controller;
let generation = 0;
let currentResult;
let previousResult;
let rawVisible = false;

function node(tag, className, text) {
  const element = document.createElement(tag);
  if (className) element.className = className;
  if (text !== undefined) element.textContent = text;
  return element;
}

function save() {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(persistable(state)));
    storageAvailable = true;
    $('saved-status').textContent = '已自动保存到此浏览器';
  } catch {
    storageAvailable = false;
    $('saved-status').textContent = '浏览器存储不可用，刷新后配置会丢失';
  }
}

function feedback(text = '', error = false) {
  $('feedback').textContent = text;
  $('feedback').classList.toggle('error', error);
  $('feedback').hidden = !text;
}

function renderPreview() {
  try {
    const body = buildBody(state.mode, state, imageBase64);
    if (body.queryImageBase64) body.queryImageBase64 = '[已选择参考图片，Base64 不保存]';
    $('request-preview').textContent = JSON.stringify(body, null, 2);
  } catch (error) { $('request-preview').textContent = error.message; }
}

function renderHistory() {
  const container = $('history');
  container.replaceChildren();
  if (!state.history.length) container.append(node('p', 'history-empty', '你的查询会出现在这里。'));
  for (const item of state.history) {
    const button = node('button', 'history-item');
    button.type = 'button';
    button.append(node('span', '', item.query), node('small', '', `${MODES[item.mode].label}${item.project ? ' · ' + item.project : ''}`));
    button.title = item.query;
    button.addEventListener('click', () => {
      state.drafts[item.mode] = item.query;
      state.project = item.project || '';
      $('project').value = state.project;
      switchMode(item.mode);
      $('query').focus();
    });
    container.append(button);
  }
}

function switchMode(mode) {
  if (controller) { controller.abort(); generation++; setBusy(false); }
  state.mode = mode;
  const definition = MODES[mode];
  for (const button of $('mode-tabs').children) button.setAttribute('aria-pressed', String(button.dataset.mode === mode));
  $('query').value = state.drafts[mode] || '';
  $('query').placeholder = definition.placeholder;
  $('endpoint').textContent = 'POST ' + definition.path;
  $('mode-hint').textContent = definition.hint;
  const textual = mode === 'search' || mode === 'smart';
  $('image-fields').hidden = mode !== 'vision';
  $('project-field').hidden = mode === 'vision';
  $('session-field').hidden = mode !== 'vision';
  $('confidence-field').hidden = !['lessons', 'insights'].includes(mode);
  $('format-field').hidden = mode !== 'search';
  $('agent-field').hidden = !textual;
  $('budget-field').hidden = mode !== 'search';
  $('layer-field').hidden = !textual;
  $('targetLayer').disabled = state.compatibility !== 'latest';
  $('lessons-field').hidden = mode !== 'smart';
  $('compatibility-note').textContent = textual
    ? state.compatibility === 'local'
      ? '本机兼容模式不发送 targetLayer。旧版智能搜索的项目过滤不完整；要严格查询某个会话，请在结果中选择“查看会话”。'
      : '最新代码模式支持 targetLayer。项目为精确匹配；智能搜索的顶层 sessionId 不是搜索范围。'
    : mode === 'vision' ? '选中参考图片时优先使用图片查询；清除图片后使用文字描述或图片引用。'
      : '置信度和返回条数由页面校验。搜索对象是独立保存的经验或洞见。';
  feedback();
  save();
  renderPreview();
}

function setBusy(busy) {
  $('submit-search').disabled = busy;
  $('submit-search').firstElementChild.textContent = busy ? '正在搜索…' : '开始搜索';
  $('cancel-search').hidden = !busy;
  document.querySelector('.results-section').setAttribute('aria-busy', String(busy));
  if (!busy) controller = undefined;
}

async function apiRequest(path, body, method = 'POST', signal) {
  const token = state.token.trim().replace(/^Bearer\s+/i, '');
  let response;
  try {
    response = await fetch('/api/request', {
      method: 'POST',
      headers: { 'content-type': 'application/json', ...(token ? { authorization: 'Bearer ' + token } : {}) },
      body: JSON.stringify({ baseUrl: state.baseUrl.trim(), path, method, ...(body ? { body } : {}) }),
      signal,
    });
  } catch (error) {
    if (error.name === 'AbortError') throw error;
    throw new Error('无法连接本地搜索服务。请重新运行 start.cmd，再刷新 http://127.0.0.1:3120；已保存的 Token 和配置会保留。');
  }
  let data;
  try { data = await response.json(); }
  catch { throw new Error('当前页面没有可用的搜索转发接口。请运行 start.cmd，并通过 http://127.0.0.1:3120 打开。'); }
  if (response.status === 404) throw new Error('当前地址没有搜索转发接口。请通过 start.cmd 启动，再刷新页面。');
  if (!response.ok || data.success === false || data.error) {
    const advice = response.status === 401 ? '请检查左侧 Token。' : response.status === 503 ? '请检查服务端是否启用了对应功能。' : '';
    throw new Error(`HTTP ${response.status} · ${data.error || '请求失败'}${advice ? ' ' + advice : ''}`);
  }
  return { data, status: response.status };
}

function dateLabel(value) {
  if (!value) return '';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleString('zh-CN', { hour12: false });
}

function detail(record) {
  const details = node('details', 'card-details');
  details.append(node('summary', '', '原始记录'), node('pre', '', JSON.stringify(record, null, 2)));
  return details;
}

function resultCard(row, index) {
  const card = node('article', 'result-card');
  const top = node('div', 'card-top');
  top.append(node('h3', '', row.title));
  if (typeof row.score === 'number') top.append(node('span', 'card-score', `相关度 ${row.score.toFixed(3)}`));
  card.append(top);
  const badges = node('div', 'badges');
  badges.append(node('span', 'badge', row.layer || 'record'));
  if (typeof row.confidence === 'number') badges.append(node('span', 'badge', `置信度 ${row.confidence.toFixed(2)}`));
  if (row.timestamp) badges.append(node('span', 'card-time', dateLabel(row.timestamp)));
  card.append(badges);
  if (row.content) card.append(node('p', 'card-content', row.content.length > 1600 ? row.content.slice(0, 1600) + '\n…完整内容见原始记录' : row.content));
  const footer = node('div', 'card-footer');
  footer.append(node('span', 'card-id', row.obsId || `结果 ${index + 1}`));
  if (row.obsId && (row.obsId.startsWith('obs_') || row.obsId.startsWith('mem_'))) {
    const expand = node('button', 'text-button', '展开');
    expand.type = 'button';
    expand.addEventListener('click', async () => {
      expand.disabled = true;
      expand.textContent = '读取中…';
      try {
        const entry = row.sessionId ? { obsId: row.obsId, sessionId: row.sessionId } : row.obsId;
        const { data } = await apiRequest(MODES.smart.path, { expandIds: [entry] });
        const record = data.results?.[0]?.observation;
        if (!record) throw new Error('未找到可展开的记录。');
        const expanded = node('div', 'expanded-record');
        expanded.append(node('p', 'card-content', record.narrative || record.content || '此记录没有摘要。'));
        expanded.append(detail(record));
        card.append(expanded);
        expand.textContent = '已展开';
      } catch (error) {
        feedback(error.message, true);
        expand.textContent = '重试展开';
        expand.disabled = false;
      }
    });
    footer.append(expand);
  }
  if (row.sessionId && !['memory', 'lesson', 'insight'].includes(row.sessionId)) {
    const session = node('button', 'text-button', '查看会话');
    session.type = 'button';
    session.title = row.sessionId;
    session.addEventListener('click', () => loadSession(row.sessionId));
    footer.append(session);
  }
  card.append(footer, detail(row.raw));
  return card;
}

function renderResults(result) {
  currentResult = result;
  const rows = resultRows(result.data);
  $('results-title').textContent = result.title || '搜索结果';
  const total = result.data.total;
  $('result-meta').textContent = `${rows.length} 条${typeof total === 'number' ? ' / 总计 ' + total : ''} · HTTP ${result.status} · ${(result.ms / 1000).toFixed(2)} 秒`;
  $('back-results').hidden = !result.sessionId;
  $('toggle-json').hidden = false;
  $('copy-json').hidden = false;
  $('empty-state').hidden = true;
  const container = $('results');
  container.replaceChildren();
  if (!rows.length) {
    const empty = node('div', 'empty-state');
    empty.append(node('h3', '', '没有找到匹配内容'), node('p', '', '可以换一个关键词，或放宽项目、置信度和搜索范围。'));
    container.append(empty);
  }
  rows.forEach((row, index) => container.append(resultCard(row, index)));
  if (Array.isArray(result.data.lessons) && result.data.results && result.data.lessons.length) {
    container.append(node('h3', 'group-heading', '相关经验教训'));
    resultRows({ lessons: result.data.lessons }).forEach((row, index) => container.append(resultCard(row, index)));
  }
  if (result.sessionId && result.data.nextCursor) {
    const more = node('button', 'button secondary load-more', '加载更多会话记录');
    more.type = 'button';
    more.addEventListener('click', () => loadSession(result.sessionId, result.data.nextCursor));
    container.append(more);
  }
  $('raw-json').textContent = JSON.stringify(result.data, null, 2);
  $('raw-json').hidden = !rawVisible;
  container.hidden = rawVisible;
  $('toggle-json').textContent = rawVisible ? '查看卡片' : '查看 JSON';
  if (result.data.truncated) feedback('部分结果已受条数或预算限制，详情见 JSON 中的 truncated / excluded_results 字段。');
}

async function runSearch() {
  let body;
  try { body = buildBody(state.mode, state, imageBase64); } catch (error) { feedback(error.message, true); return; }
  if (controller) controller.abort();
  const mine = ++generation;
  controller = new AbortController();
  const signal = controller.signal;
  const mode = state.mode;
  const query = state.drafts[mode] || '';
  const start = performance.now();
  setBusy(true);
  feedback();
  try {
    const response = await apiRequest(MODES[mode].path, body, 'POST', signal);
    if (mine !== generation) return;
    previousResult = undefined;
    renderResults({ ...response, ms: performance.now() - start });
    if (query.trim()) {
      state.history = [{ mode, query: query.trim(), project: state.project, at: Date.now() }, ...state.history.filter(item => !(item.mode === mode && item.query === query.trim() && item.project === state.project))].slice(0, 15);
      save();
      renderHistory();
    }
  } catch (error) {
    if (mine === generation) feedback(error.name === 'AbortError' ? '已取消搜索。' : error.message, error.name !== 'AbortError');
  } finally { if (mine === generation) setBusy(false); }
}

async function loadSession(sessionId, cursor) {
  if (controller) controller.abort();
  const mine = ++generation;
  controller = new AbortController();
  const signal = controller.signal;
  setBusy(true);
  feedback();
  const start = performance.now();
  try {
    const params = new URLSearchParams({ sessionId, limit: '20' });
    if (cursor) params.set('cursor', cursor);
    const response = await apiRequest('/agentmemory/observations?' + params, null, 'GET', signal);
    if (mine !== generation) return;
    if (!currentResult?.sessionId) previousResult = currentResult;
    if (cursor && currentResult?.sessionId === sessionId) response.data.observations = [...currentResult.data.observations, ...response.data.observations];
    renderResults({ ...response, ms: performance.now() - start, title: '会话记录', sessionId });
  } catch (error) {
    if (mine === generation) feedback(error.name === 'AbortError' ? '已取消读取。' : error.message, error.name !== 'AbortError');
  } finally { if (mine === generation) setBusy(false); }
}

for (const [mode, definition] of Object.entries(MODES)) {
  const button = node('button', 'mode-tab', definition.label);
  button.type = 'button';
  button.dataset.mode = mode;
  button.setAttribute('aria-pressed', 'false');
  button.addEventListener('click', () => switchMode(mode));
  $('mode-tabs').append(button);
}

const fields = ['baseUrl', 'token', 'rememberToken', 'compatibility', 'project', 'agentId', 'sessionId', 'limit', 'format', 'tokenBudget', 'minConfidence', 'targetLayer', 'includeLessons', 'imageRef'];
for (const key of fields) {
  const input = $(key);
  if (input.type === 'checkbox') input.checked = state[key]; else input.value = state[key];
  input.addEventListener(input.tagName === 'SELECT' || input.type === 'checkbox' ? 'change' : 'input', () => {
    state[key] = input.type === 'checkbox' ? input.checked : input.type === 'number' ? Number(input.value) : input.value;
    save();
    if (key === 'compatibility') switchMode(state.mode); else renderPreview();
    if (key === 'baseUrl' || key === 'token') {
      $('connection-status').textContent = '配置已更改，请重新测试连接';
      $('connection-status').className = 'connection-status';
    }
  });
}
$('query').addEventListener('input', () => { state.drafts[state.mode] = $('query').value; save(); renderPreview(); });
$('query').addEventListener('keydown', event => {
  if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') { event.preventDefault(); if (!controller) runSearch(); }
});
$('search-form').addEventListener('submit', event => { event.preventDefault(); if (!controller) runSearch(); });
$('cancel-search').addEventListener('click', () => controller?.abort());
$('toggle-token').addEventListener('click', () => {
  const show = $('token').type === 'password';
  $('token').type = show ? 'text' : 'password';
  $('toggle-token').textContent = show ? '隐藏' : '显示';
  $('toggle-token').setAttribute('aria-label', show ? '隐藏 Token' : '显示 Token');
});
$('clear-token').addEventListener('click', () => {
  state.token = '';
  $('token').value = '';
  save();
  $('connection-status').textContent = 'Token 已从此浏览器清除';
  $('connection-status').className = 'connection-status';
});
$('clear-history').addEventListener('click', () => { state.history = []; save(); renderHistory(); });
$('test-connection').addEventListener('click', async () => {
  const button = $('test-connection');
  button.disabled = true;
  $('connection-status').textContent = '正在连接…';
  try {
    await apiRequest('/agentmemory/sessions?limit=1', null, 'GET');
    $('connection-status').textContent = '已连接 · 鉴权通过';
    $('connection-status').className = 'connection-status ok';
  } catch (error) {
    $('connection-status').textContent = error.message;
    $('connection-status').className = 'connection-status error';
  } finally { button.disabled = false; }
});
$('toggle-json').addEventListener('click', () => { rawVisible = !rawVisible; if (currentResult) renderResults(currentResult); });
$('copy-json').addEventListener('click', async () => {
  try { await navigator.clipboard.writeText(JSON.stringify(currentResult.data, null, 2)); feedback('结果 JSON 已复制。'); }
  catch { rawVisible = true; renderResults(currentResult); feedback('无法访问剪贴板，请从 JSON 面板手动复制。'); }
});
$('back-results').addEventListener('click', () => {
  if (controller) { controller.abort(); generation++; setBusy(false); }
  feedback();
  if (previousResult) renderResults(previousResult);
});
for (const suggestion of document.querySelectorAll('[data-query]')) suggestion.addEventListener('click', () => {
  $('query').value = suggestion.dataset.query;
  state.drafts[state.mode] = suggestion.dataset.query;
  save();
  renderPreview();
  $('query').focus();
});
$('image-file').addEventListener('change', async () => {
  const mine = ++imageGeneration;
  imageBase64 = '';
  const file = $('image-file').files[0];
  if (!file) { $('image-name').textContent = '未选择图片'; $('clear-image').hidden = true; renderPreview(); return; }
  if (!file.type.startsWith('image/') || file.size > 8 * 1024 * 1024) {
    feedback('请选择小于 8 MB 的图片。', true);
    $('image-file').value = '';
    $('image-name').textContent = '未选择图片';
    $('clear-image').hidden = true;
    renderPreview();
    return;
  }
  const reader = new FileReader();
  reader.onload = () => {
    if (mine !== imageGeneration) return;
    imageBase64 = String(reader.result);
    $('image-name').textContent = file.name;
    $('clear-image').hidden = false;
    renderPreview();
  };
  reader.onerror = () => feedback('图片读取失败，请重新选择。', true);
  reader.readAsDataURL(file);
});
$('clear-image').addEventListener('click', () => {
  imageGeneration++;
  imageBase64 = '';
  $('image-file').value = '';
  $('image-name').textContent = '未选择图片';
  $('clear-image').hidden = true;
  renderPreview();
});

renderHistory();
switchMode(state.mode);
if (!storageAvailable) $('saved-status').textContent = '浏览器存储不可用，刷新后配置会丢失';

fetch('/api/health').then(async response => {
  const health = await response.json();
  if (!response.ok || health.app !== 'agentmemory-search-local') throw new Error('wrong server');
}).catch(() => {
  const message = '本地搜索服务不可用，请运行 start.cmd，然后刷新 http://127.0.0.1:3120。';
  $('connection-status').textContent = message;
  $('connection-status').className = 'connection-status error';
});
