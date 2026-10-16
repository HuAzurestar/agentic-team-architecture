# Agent Memory 本地搜索工具

HTML + 原生 JavaScript 页面，配套无依赖的 Node.js 本地转发服务。只用于查询现有 Agent Memory，不导入、写入或删除记忆，不修改 Agent Memory / iii 配置。

## 启动

需要 Node.js 22+，不需要 `npm install`。

Windows 双击 `start.cmd`，会在后台启动服务并打开 <http://127.0.0.1:3120>。重复启动复用已有服务，关闭启动窗口不会停止服务；双击 `stop.cmd` 停止。重启电脑后需要再次启动。

也可以从任意工作目录直接运行：

```sh
node /你的仓库/tools/agent-memory-search/server.mjs
```

前台运行时按 Ctrl+C 停止。可通过 `AGENTMEMORY_SEARCH_PORT` 更改端口，默认 3120。

在页面左侧填写 API 地址和 Token，再点击“测试连接”。API 默认地址为 `http://127.0.0.1:3111`；仅支持本机 `localhost`、`127.0.0.1`、`::1`。页面通过同源本地服务转发请求，避免直接访问 Agent Memory 时的跨域限制。请通过启动器或 Node 服务打开页面，不要直接双击 `public/index.html`。

## 目录与挂载

```text
public/index.html       搜索页面
public/app.js           交互、请求、结果显示和持久化
public/core.js          请求构造与状态恢复
public/styles.css      页面样式
server.mjs             本地静态服务和只读查询转发
start.cmd / start.ps1   Windows 后台启动
stop.cmd               Windows 停止
test/                  模拟 API 与浏览器测试
```

可以整体复制或挂载本目录到其他项目，使用挂载路径中的 `server.mjs` 启动。源码目录只读挂载时使用 `node .../server.mjs`；Windows 后台启动器需要写入本目录的 `.runtime/` 日志和 PID 文件。

Token 由使用者在浏览器配置，服务端不保存 Token，源码不包含真实 Token。工具不挂载或读取 Agent Memory 的数据库，也不需要访问 iii 内部状态。

## 搜索与结果

- 内容搜索：`POST /agentmemory/search`。
- 智能搜索、按 ID 展开：`POST /agentmemory/smart-search`。
- 经验教训：`POST /agentmemory/lessons/search`。
- 归纳洞见：`POST /agentmemory/insights/search`。
- 图片搜索：`POST /agentmemory/vision-search`，需要服务端启用图片向量；参考图片最大 8 MB。
- 连接测试只读取一条会话元数据；命中结果可查看所属会话的观察记录并分页加载。

所有转发接口均在白名单中，不提供任意 iii function 调用或记忆管理操作。支持结果卡片、原始 JSON、复制结果及取消等待。HTTP 超时为 90 秒；取消浏览器等待不保证服务端任务同步停止。

默认选择“本机已安装版本”，不发送 `targetLayer`。旧版 smart-search 的 project 过滤不完整；只有确认服务端支持新参数后再切换“GitHub 最新代码”。需要严格限定某个 session 时，使用结果中的“查看会话”。

## 持久化

API 地址、筛选、兼容模式、各类查询输入和最近 15 条成功查询自动保存在当前浏览器的 localStorage。

勾选“在此浏览器记住 Token”后，Token 也存入 localStorage，**未加密**。取消勾选会删除持久化 Token；“清除 Token”会清除当前页面和已保存的值。“清空”只清除查询历史。搜索结果与参考图片不持久化。

固定使用同一浏览器、地址和端口；`localhost` 与 `127.0.0.1` 的浏览器存储互相独立。遇到本地服务断连，重新启动并刷新页面即可，已有配置会保留。

## 验证

在本目录执行：

```sh
npm run check
npm test
npm run test:browser
```

浏览器测试默认使用 Windows Chrome，可通过 `CHROME_PATH` 指定其他 Chrome 路径。测试使用临时模拟 API 和测试 Token，不访问真实 Agent Memory；截图输出到 `artifacts/`。`artifacts/` 与 `.runtime/` 均已忽略，不纳入 Git。
