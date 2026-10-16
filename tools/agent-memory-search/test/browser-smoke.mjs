import { spawn } from 'node:child_process';
import { createServer as httpServer } from 'node:http';
import { mkdtemp, readFile, mkdir, writeFile, rm, realpath } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join, dirname, resolve, sep, basename } from 'node:path';
import { fileURLToPath } from 'node:url';
import assert from 'node:assert/strict';
import { createServer } from '../server.mjs';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const chromePath = process.env.CHROME_PATH || 'C:/Program Files/Google/Chrome/Application/chrome.exe';
const profile = await mkdtemp(join(tmpdir(), 'agentmemory-browser-'));
const requests = [];
const record = { id: 'obs_demo', sessionId: 'demo-session', timestamp: '2026-10-16T06:00:00Z', type: 'decision', title: '论文结构与检索策略', narrative: '先通过索引找出相关条目，再定点展开会话内容。', facts: ['避免全量读取'], concepts: ['检索'], files: ['paper.tex'], importance: 7 };
const mock = httpServer(async (request, response) => {
  let raw = '';
  for await (const chunk of request) raw += chunk;
  const body = raw ? JSON.parse(raw) : {};
  requests.push({ path: request.url, body, auth: request.headers.authorization });
  response.setHeader('content-type', 'application/json');
  if (request.headers.authorization !== 'Bearer browser-test-only') { response.writeHead(401); response.end(JSON.stringify({ error: 'unauthorized' })); return; }
  let data;
  if (request.url.startsWith('/agentmemory/sessions')) data = { sessions: [{ id: 'demo-session' }] };
  else if (request.url.startsWith('/agentmemory/observations')) data = { observations: [{ ...record, id: request.url.includes('cursor=') ? 'obs_second' : 'obs_demo' }], total: 2, nextCursor: request.url.includes('cursor=') ? null : 'page2' };
  else if (request.url === '/agentmemory/smart-search' && body.expandIds) data = { mode: 'expanded', results: [{ obsId: record.id, sessionId: record.sessionId, observation: record }] };
  else if (request.url === '/agentmemory/lessons/search') data = { success: true, lessons: [{ id: 'lsn_demo', content: '优先使用有界检索', confidence: 0.95 }] };
  else if (request.url === '/agentmemory/insights/search') data = { success: true, insights: [{ id: 'ins_demo', title: '小范围查询减少等待', content: '先搜索，再展开。', confidence: 0.8 }] };
  else if (request.url === '/agentmemory/vision-search') data = { success: true, results: [{ imageRef: '/images/demo.png', observationId: 'obs_demo', sessionId: 'demo-session', score: 0.8 }], total: 1 };
  else data = { results: [{ obsId: record.id, sessionId: record.sessionId, title: record.title, narrative: record.narrative, type: record.type, score: 0.82, timestamp: record.timestamp }, { obsId: 'obs_xss', title: '<img src=x onerror="window.injected=true">', narrative: '结果按纯文本显示。', type: 'command_run' }], tokens_used: 180, truncated: false };
  response.end(JSON.stringify(data));
});
const app = createServer();
const listen = server => new Promise(resolveListen => server.listen(0, '127.0.0.1', () => resolveListen(`http://127.0.0.1:${server.address().port}`)));
const mockUrl = await listen(mock);
const appUrl = await listen(app);
const browser = spawn(chromePath, ['--headless=new', '--disable-gpu', '--no-first-run', '--no-default-browser-check', '--remote-debugging-port=0', '--remote-allow-origins=http://localhost', `--user-data-dir=${profile}`, 'about:blank'], { windowsHide: true, stdio: 'ignore' });
let socket;
const delay = ms => new Promise(resolveDelay => setTimeout(resolveDelay, ms));
try {
  let port;
  for (let i = 0; i < 100; i++) {
    try { port = (await readFile(join(profile, 'DevToolsActivePort'), 'utf8')).split('\n')[0]; break; } catch { await delay(100); }
  }
  assert.ok(port, 'Chrome debugging endpoint started');
  const targets = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
  socket = new WebSocket(targets.find(target => target.type === 'page').webSocketDebuggerUrl);
  await new Promise((resolveOpen, reject) => { socket.onopen = resolveOpen; socket.onerror = reject; });
  let id = 0;
  const pending = new Map();
  socket.onmessage = event => {
    const message = JSON.parse(event.data);
    if (!pending.has(message.id)) return;
    const entry = pending.get(message.id);
    pending.delete(message.id);
    if (message.error) entry.reject(new Error(JSON.stringify(message.error))); else entry.resolve(message.result);
  };
  const cdp = (method, params = {}) => new Promise((resolveCall, reject) => {
    const callId = ++id;
    const timeout = setTimeout(() => { pending.delete(callId); reject(new Error('CDP timeout: ' + method)); }, 15000);
    pending.set(callId, { resolve: value => { clearTimeout(timeout); resolveCall(value); }, reject });
    socket.send(JSON.stringify({ id: callId, method, params }));
  });
  const evaluate = async expression => {
    const result = await cdp('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true });
    if (result.exceptionDetails) throw new Error(JSON.stringify(result.exceptionDetails));
    return result.result.value;
  };
  const waitFor = async expression => {
    for (let i = 0; i < 100; i++) { if (await evaluate(expression)) return; await delay(50); }
    const diagnostic = await evaluate("({feedback:document.getElementById('feedback')?.textContent,invalid:[...document.querySelectorAll(':invalid')].map(e=>({id:e.id,value:e.value,message:e.validationMessage})),text:document.body.innerText.slice(-1000)})");
    throw new Error('Browser condition not met: ' + expression + '\n' + JSON.stringify(diagnostic));
  };
  const fill = (name, value) => evaluate(`(()=>{const e=document.getElementById(${JSON.stringify(name)});e.value=${JSON.stringify(value)};e.dispatchEvent(new Event(e.tagName==='SELECT'?'change':'input',{bubbles:true}));})()`);
  const click = selector => evaluate(`document.querySelector(${JSON.stringify(selector)}).click()`);
  const submit = async () => { await evaluate("document.getElementById('search-form').requestSubmit()"); await waitFor("document.querySelectorAll('.result-card').length>0 && !document.getElementById('submit-search').disabled"); };
  await cdp('Emulation.setDeviceMetricsOverride', { width: 1440, height: 1100, deviceScaleFactor: 1, mobile: false });
  await cdp('Page.navigate', { url: appUrl });
  await waitFor("document.querySelectorAll('.mode-tab').length===5");
  await fill('baseUrl', mockUrl);
  await fill('token', 'browser-test-only');
  await fill('query', 'PIRC-17 论文结构');
  await fill('project', 'demo-project');
  await click('#test-connection');
  await waitFor("document.getElementById('connection-status').classList.contains('ok')");
  await submit();
  assert.equal(requests.find(item => item.path === '/agentmemory/search').body.targetLayer, undefined);
  assert.equal(await evaluate('window.injected'), undefined);
  assert.equal(await evaluate("document.querySelectorAll('#results img').length"), 0);
  await click('.result-card .card-footer button');
  await waitFor("document.querySelector('.expanded-record')!==null");
  await click('.result-card .card-footer button:nth-of-type(2)');
  await waitFor("document.getElementById('results-title').textContent==='会话记录' && !document.getElementById('submit-search').disabled");
  await click('.load-more');
  await waitFor("document.querySelectorAll('.result-card').length===2 && !document.getElementById('submit-search').disabled");
  await click('#back-results');
  await mkdir(join(root, 'artifacts'), { recursive: true });
  await writeFile(join(root, 'artifacts', 'desktop.png'), Buffer.from((await cdp('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false })).data, 'base64'));
  await cdp('Page.reload');
  await waitFor("document.querySelectorAll('.mode-tab').length===5");
  assert.equal(await evaluate("document.getElementById('token').value"), 'browser-test-only');
  assert.equal(await evaluate("document.getElementById('query').value"), 'PIRC-17 论文结构');
  assert.equal(await evaluate("document.getElementById('project').value"), 'demo-project');
  assert.equal(await evaluate("document.querySelectorAll('.history-item').length"), 1);
  for (const mode of ['smart', 'lessons', 'insights', 'vision']) {
    await click(`[data-mode="${mode}"]`);
    await fill('query', '测试检索');
    await submit();
  }
  assert.ok(requests.some(item => item.path === '/agentmemory/vision-search' && item.body.queryText === '测试检索'));
  await fill('token', 'invalid-test-token');
  await evaluate("document.getElementById('search-form').requestSubmit()");
  await waitFor("document.getElementById('feedback').textContent.includes('401')");
  await click('#rememberToken');
  assert.equal(await evaluate("JSON.parse(localStorage.getItem('agentmemory-search:v1')).token"), '');
  await cdp('Page.reload');
  await waitFor("document.querySelectorAll('.mode-tab').length===5");
  assert.equal(await evaluate("document.getElementById('token').value"), '');
  await click('[data-mode="search"]');
  await evaluate("window.originalFetch=window.fetch;window.fetch=(...args)=>args[0]==='/api/request'?Promise.reject(new TypeError('Failed to fetch')):window.originalFetch(...args)");
  await click('#test-connection');
  await waitFor("document.getElementById('connection-status').textContent.includes('重新运行 start.cmd')");
  await evaluate('window.fetch=window.originalFetch');
  await cdp('Emulation.setDeviceMetricsOverride', { width: 390, height: 1100, deviceScaleFactor: 1, mobile: true });
  assert.equal(await evaluate('document.documentElement.scrollWidth > window.innerWidth'), false);
  await writeFile(join(root, 'artifacts', 'mobile.png'), Buffer.from((await cdp('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false })).data, 'base64'));
  console.log('PASS: five search modes, auth, XSS-as-text, expansion, session paging, reload persistence, token opt-out, offline recovery message, mobile layout.');
  await cdp('Browser.close').catch(() => {});
} finally {
  socket?.close();
  browser.kill();
  await Promise.all([new Promise(resolveClose => app.close(resolveClose)), new Promise(resolveClose => mock.close(resolveClose))]);
  const actual = await realpath(profile);
  const tempRoot = await realpath(tmpdir());
  if (actual.startsWith(tempRoot + sep) && basename(actual).startsWith('agentmemory-browser-')) await rm(actual, { recursive: true, force: true, maxRetries: 6, retryDelay: 300 });
}
