import { test } from 'node:test';
import assert from 'node:assert/strict';
import http from 'node:http';
import { createServer } from '../server.mjs';
import { DEFAULTS, buildBody, persistable, restoreState, resultRows } from '../public/core.js';

const fixture = overrides => ({ ...DEFAULTS, drafts: { search: '论文', smart: '论文', lessons: '规则', insights: '结论', vision: '登录截图' }, history: [], ...overrides });
const listen = server => new Promise(resolve => server.listen(0, '127.0.0.1', () => resolve(`http://127.0.0.1:${server.address().port}`)));
const close = server => new Promise(resolve => server.close(resolve));

test('local compatibility omits unsupported filters; latest mode scopes observations', () => {
  assert.equal(buildBody('search', fixture({ targetLayer: 'observation' })).targetLayer, undefined);
  assert.equal(buildBody('smart', fixture({ targetLayer: 'observation', compatibility: 'latest' })).targetLayer, 'observation');
  assert.equal(buildBody('smart', fixture({ sessionId: 's1' })).sessionId, undefined);
  assert.equal(buildBody('vision', fixture({ sessionId: 's1', limit: 80 })).sessionId, 's1');
  assert.equal(buildBody('vision', fixture({ limit: 80 })).topK, 50);
  assert.throws(() => buildBody('lessons', fixture({ minConfidence: 2 })), /置信度/);
});

test('persistent state restores drafts and can remove a remembered token', () => {
  const state = fixture({ token: 'test-only', project: 'demo', history: [{ mode: 'search', query: '论文' }] });
  const restored = restoreState(JSON.stringify(persistable(state)));
  assert.equal(restored.token, 'test-only');
  assert.equal(restored.project, 'demo');
  assert.equal(restored.drafts.search, '论文');
  assert.equal(restoreState(JSON.stringify(persistable({ ...state, rememberToken: false }))).token, '');
  assert.deepEqual(restoreState('{broken').history, []);
  assert.deepEqual(restoreState('{"history":[null],"drafts":null}').history, []);
});

test('normalizes compact, full, lessons and images without executing result content', () => {
  assert.equal(resultRows({ results: [{ obsId: 'obs_a', title: '<script>bad</script>', sessionId: 's1' }] })[0].title, '<script>bad</script>');
  assert.equal(resultRows({ results: [{ observation: { id: 'obs_b', narrative: '正文' } }] })[0].content, '正文');
  assert.equal(resultRows({ lessons: [{ id: 'lsn_a', content: '规则' }] })[0].layer, 'lesson');
  assert.equal(resultRows({ results: [{ observationId: 'obs_image', imageRef: '/a.png' }] })[0].obsId, 'obs_image');
});

test('local proxy forwards auth and UTF-8, bounds lists, and rejects unsupported targets', async () => {
  const received = [];
  const upstream = http.createServer(async (request, response) => {
    let body = '';
    for await (const chunk of request) body += chunk;
    received.push({ url: request.url, auth: request.headers.authorization, origin: request.headers.origin, body: body ? JSON.parse(body) : null });
    response.writeHead(request.headers.authorization === 'Bearer test-only' ? 200 : 401, { 'content-type': 'application/json' });
    response.end(request.headers.authorization === 'Bearer test-only' ? JSON.stringify({ results: [], sessions: [] }) : JSON.stringify({ error: 'unauthorized' }));
  });
  const server = createServer();
  const baseUrl = await listen(upstream);
  const local = await listen(server);
  const request = (input, extra = {}) => fetch(local + '/api/request', { method: 'POST', headers: { 'content-type': 'application/json', authorization: 'Bearer test-only', origin: local, ...extra }, body: JSON.stringify({ baseUrl, ...input }) });
  try {
    const page = await fetch(local);
    assert.equal(page.status, 200);
    assert.match(page.headers.get('content-security-policy'), /script-src 'self'/);
    assert.deepEqual(await (await fetch(local + '/api/health')).json(), { app: 'agentmemory-search-local', status: 'ok' });
    assert.equal((await request({ method: 'POST', path: '/agentmemory/search', body: { query: '中文测试' } })).status, 200);
    assert.equal(received[0].body.query, '中文测试');
    assert.equal(received[0].auth, 'Bearer test-only');
    assert.equal(received[0].origin, undefined);
    await request({ method: 'GET', path: '/agentmemory/sessions?limit=9999' });
    assert.match(received[1].url, /limit=100/);
    assert.equal((await request({ method: 'POST', path: '/agentmemory/search', body: { query: 'test' } }, { authorization: '' })).status, 401);
    assert.equal((await request({ method: 'POST', path: '/agentmemory/search', body: {} }, { origin: 'https://example.org' })).status, 403);
    assert.equal((await request({ method: 'POST', path: '/agentmemory/forget', body: {} })).status, 400);
    assert.equal((await request({ baseUrl: 'https://example.org', method: 'POST', path: '/agentmemory/search', body: {} })).status, 400);
  } finally { await Promise.all([close(server), close(upstream)]); }
});
