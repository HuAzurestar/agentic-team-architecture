import http from 'node:http';
import { readFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { resolve, dirname } from 'node:path';
import { spawn } from 'node:child_process';

const root = dirname(fileURLToPath(import.meta.url));
const files = new Map([
  ['/', ['index.html', 'text/html; charset=utf-8']],
  ['/index.html', ['index.html', 'text/html; charset=utf-8']],
  ['/app.js', ['app.js', 'text/javascript; charset=utf-8']],
  ['/core.js', ['core.js', 'text/javascript; charset=utf-8']],
  ['/styles.css', ['styles.css', 'text/css; charset=utf-8']],
]);
const endpoints = new Map([
  ['/agentmemory/search', 'POST'],
  ['/agentmemory/smart-search', 'POST'],
  ['/agentmemory/insights/search', 'POST'],
  ['/agentmemory/lessons/search', 'POST'],
  ['/agentmemory/vision-search', 'POST'],
  ['/agentmemory/sessions', 'GET'],
  ['/agentmemory/observations', 'GET'],
]);

function json(response, status, value) {
  response.writeHead(status, { 'content-type': 'application/json; charset=utf-8', 'cache-control': 'no-store' });
  response.end(JSON.stringify(value));
}

async function readJson(request) {
  const chunks = [];
  let length = 0;
  for await (const chunk of request) {
    length += chunk.length;
    if (length > 12 * 1024 * 1024) throw new Error('请求超过 12 MB，请选择更小的图片。');
    chunks.push(chunk);
  }
  return JSON.parse(Buffer.concat(chunks).toString('utf8'));
}

export function createServer() {
  return http.createServer(async (request, response) => {
    response.setHeader('x-content-type-options', 'nosniff');
    response.setHeader('referrer-policy', 'no-referrer');
    response.setHeader('content-security-policy', "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data:; base-uri 'none'; frame-ancestors 'none'; form-action 'self'");
    const local = new URL(`http://${request.headers.host}`);
    if (!['localhost', '127.0.0.1', '[::1]'].includes(local.hostname)) return json(response, 403, { error: '只接受本机请求。' });
    if (request.headers.origin) {
      try {
        const origin = new URL(request.headers.origin);
        if (!['localhost', '127.0.0.1', '[::1]'].includes(origin.hostname) || origin.port !== local.port || origin.protocol !== 'http:') {
          return json(response, 403, { error: '请求来源不允许。' });
        }
      } catch { return json(response, 403, { error: '请求来源无效。' }); }
    }
    const route = new URL(request.url, local).pathname;
    if (route === '/api/health' && request.method === 'GET') return json(response, 200, { app: 'agentmemory-search-local', status: 'ok' });
    if (route === '/api/request' && request.method === 'POST') {
      if (!request.headers['content-type']?.startsWith('application/json')) return json(response, 415, { error: '请使用 JSON 请求。' });
      let input, target;
      try {
        input = await readJson(request);
        const base = new URL(input.baseUrl);
        if (!['http:', 'https:'].includes(base.protocol) || !['localhost', '127.0.0.1', '[::1]'].includes(base.hostname) || base.username || base.password || base.search || base.hash || !['/', '/agentmemory', '/agentmemory/'].includes(base.pathname)) {
          throw new Error('API 地址请填写本机地址，例如 http://127.0.0.1:3111。');
        }
        target = new URL(input.path, base.origin);
        if (target.origin !== base.origin || endpoints.get(target.pathname) !== input.method) throw new Error('不支持的搜索接口。');
        if (input.method === 'GET') {
          const limit = Number(target.searchParams.get('limit') || 10);
          target.searchParams.set('limit', String(Math.min(100, Math.max(1, Number.isFinite(limit) ? Math.floor(limit) : 10))));
        } else if (!input.body || typeof input.body !== 'object' || Array.isArray(input.body)) throw new Error('Body 必须是 JSON 对象。');
      } catch (error) { return json(response, 400, { error: error.message }); }
      try {
        const upstream = await fetch(target, {
          method: input.method,
          headers: {
            'content-type': 'application/json',
            ...(request.headers.authorization ? { authorization: request.headers.authorization } : {}),
          },
          ...(input.method === 'POST' ? { body: JSON.stringify(input.body) } : {}),
          redirect: 'error',
          signal: AbortSignal.timeout(90000),
        });
        const text = await upstream.text();
        let data;
        try { data = JSON.parse(text); } catch { data = { error: 'API 未返回 JSON。', detail: text.slice(0, 500) }; }
        return json(response, upstream.status, data);
      } catch (error) {
        return json(response, 502, { error: error.name === 'TimeoutError' ? 'API 请求超过 90 秒，请缩小搜索范围。' : '无法连接 API，请检查服务和地址。', detail: error.cause?.code || error.code || error.name });
      }
    }
    if (request.method === 'GET' && files.has(route)) {
      const [file, type] = files.get(route);
      try {
        response.writeHead(200, { 'content-type': type, 'cache-control': 'no-store' });
        response.end(await readFile(resolve(root, 'public', file)));
      } catch { json(response, 500, { error: '页面文件读取失败。' }); }
      return;
    }
    json(response, 404, { error: '接口不存在。' });
  });
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const port = Number(process.env.AGENTMEMORY_SEARCH_PORT || 3120);
  const server = createServer();
  server.on('error', error => {
    console.error(error.code === 'EADDRINUSE' ? `端口 ${port} 已被占用，请打开已有页面，或设置 AGENTMEMORY_SEARCH_PORT。` : error.message);
    process.exitCode = 1;
  });
  server.listen(port, '127.0.0.1', () => {
    const url = `http://127.0.0.1:${port}`;
    console.log(`Agent Memory 搜索：${url}\n按 Ctrl+C 停止。配置保存在浏览器中。`);
    if (process.argv.includes('--open') && process.platform === 'win32') {
      const opener = spawn('powershell.exe', ['-NoProfile', '-NonInteractive', '-WindowStyle', 'Hidden', '-Command', `Start-Process '${url}'`], { windowsHide: true, stdio: 'ignore' });
      opener.on('error', () => console.log('请手动打开上面的地址。'));
    }
  });
}
