# AOPC Notify

显式调用 `notify("消息")` → 后台保存消息 → Windows 原生通知 → 点击打开对应消息的完整网页。

采用分享方案中的 `windows-toasts`，将原悬浮 GUI 替换为 Windows 系统通知。消息服务和网页运行在 Docker 中；一个 Windows 本地小进程订阅消息并显示 Toast。无需保持浏览器打开，无需 Electron、Qt、前端框架或独立数据库服务。

## 启动

需要 Docker Desktop、Windows 10/11、Python 3.10+，在已登录的 Windows 桌面中执行。从 AOPC-AI 仓库根目录运行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/notify/start.ps1
```

首次执行会在本目录创建独立 `.venv`，安装 Windows 通知依赖，构建并启动容器，然后隐藏运行通知桥接进程。后续执行可重新构建更新，不会启动重复的桥接进程。消息服务地址：[http://127.0.0.1:17654](http://127.0.0.1:17654)。

可选：加 `-LoginStartup` 安装当前用户的登录启动快捷方式。Docker Desktop 也需设为登录启动；容器会由 `restart: unless-stopped` 恢复。桥接进程会等待 Docker 就绪并自动重连。默认不会添加登录启动项。

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/notify/start.ps1 -LoginStartup
```

登录启动快捷方式指向当前检出目录。若以后移动或删除目录，应重新安装或从 Windows 启动文件夹中删除 `AOPC Notify.lnk`。

## 发送消息

```powershell
python scripts/notify/notify.py "你好，点击这条 Windows 通知查看全文"
python -c "import sys; sys.path.insert(0, 'scripts/notify'); from notify import notify; notify('任务已完成')"
```

在 `scripts/notify` 目录中，或将该目录加入模块搜索路径后：

```python
from notify import notify

notify("任务已完成\n完整结果可以写在这里。")
```

发送函数和服务端只使用 Python 标准库，不需要安装 Windows 通知依赖。函数在消息写入 SQLite 后返回 `None`，失败则抛出异常。非空文本限 UTF-8 编码后 32 KiB。

相比原 GUI 版本，首次发送不再自动启动窗口；先执行一次 `start.ps1`，之后服务在后台常驻。没有 Windows 桥接时仍能保存和浏览消息，但不会弹出系统通知。

## HTTP 接口

日常使用只需要两个接口：`POST /notify` 主动发送通知，`GET /api/messages` 查看通知列表。Python 函数只是 HTTP 封装，任何支持 HTTP 的语言或工具都可以调用。

Windows PowerShell 中使用 `curl.exe`（以下引号写法适用于 Windows PowerShell 5.1）：

```powershell
curl.exe --json '{\"message\":\"任务已完成\"}' http://127.0.0.1:17654/notify
curl.exe http://127.0.0.1:17654/api/messages
```

Bash / Linux / macOS 中：

```bash
curl --json '{"message":"任务已完成"}' http://127.0.0.1:17654/notify
curl http://127.0.0.1:17654/api/messages
```

`--json` 需要 curl 7.82+；较早版本可改用 `-H 'Content-Type: application/json' --data-raw '<相同 JSON>'`。也可以直接用浏览器打开收件箱，或者点击 Windows 通知查看全文。

向 `POST http://127.0.0.1:17654/notify` 发送 `Content-Type: application/json`：

```json
{"message": "任务已完成\n这里是完整内容。"}
```

响应示例：

```json
{"ok": true, "id": 1, "path": "/messages/1"}
```

- `/`：最近 100 条消息的收件箱，点击查看全文，刷新可读取最新消息。
- `/messages/1`：对应消息的完整内容，正文按纯文本处理。
- `/health`：服务标识、数据库实例、最新消息 ID，以及 `bridge_connected`（最近一分钟是否有订阅请求）。
- `/api/messages`：最近 100 条消息，按 ID 倒序。
- `/api/events?after=0&wait=25`：桥接进程使用的长轮询接口，按 ID 正序，每次最多 100 条，等待上限 25 秒。

通知正文及“查看全文”按钮均使用 HTTP 协议激活，由 Windows 打开默认浏览器中的对应消息页。通知缩略正文最多 240 字符，网页保留全文。通知横幅和通知中心的最终显示受 Windows 通知设置、专注助手等系统选项控制。

## Docker / Linux 调用

可以把 `notify.py` 放入调用方的 Python 模块路径，并设置 `AOPC_NOTIFY_URL`。发送端不限操作系统。若调用方也是容器，可以接入本工具的 Docker 网络：

```powershell
docker network connect aopc-notify_default <调用方容器名>
```

调用方容器内使用 `AOPC_NOTIFY_URL=http://inbox:17654`。默认宿主机映射只绑定 `127.0.0.1`，不向局域网开放。Windows 桥接始终使用宿主机的 `http://127.0.0.1:17654`，所以通知点击地址不会变成 Docker 内部地址。

消息数据库保存在 Docker 命名卷 `aopc-notify_messages`。容器重建、停止和浏览器关闭不会清空消息；页面仅列出最近 100 条，较早消息仍可通过原详情链接查看。服务端无第三方 Python 包，容器内存上限 64 MiB。

## 桥接进程与排查

桥接状态和轮转日志位于 `%LOCALAPPDATA%\AOPCNotify\<服务地址哈希>\`。只在当前用户范围注册 `AOPC.Notify` 应用身份，通知中显示名称为 **AOPC Notify**，无需管理员权限。

首次连接只订阅新消息，避免把旧消息全部弹出；以后重连会从本地游标继续补发。消息已保存不等于用户已经看到通知；若 Windows 禁用了横幅或启用专注助手，可直接打开收件箱查看内容。

手动前台运行可检查错误：

```powershell
scripts/notify/.venv/Scripts/python.exe scripts/notify/bridge.py
```

单独停止桥接（最多等待 30 秒结束长轮询），或重新隐藏运行：

```powershell
scripts/notify/.venv/Scripts/python.exe scripts/notify/bridge.py --stop
scripts/notify/.venv/Scripts/python.exe scripts/notify/bridge.py --background
```

停止全部组件，保留消息卷：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/notify/stop.ps1
```

若不用 Docker，可用 `python scripts/notify/notify.py --serve` 在本机运行同样的 Web 服务，再单独运行 Windows 桥接。数据库默认写入本目录的 `data/messages.db`。

## 验证

```powershell
scripts/notify/.venv/Scripts/python.exe -m unittest discover -s scripts/notify -p "test_*.py" -v
```

测试覆盖真实 HTTP 收发、中文多行、并发、不合法输入、网页转义、SQLite 重开、长轮询、分页、断线恢复游标，以及原生通知正文/按钮的协议跳转 XML；不弹出测试通知。不装 Windows 依赖时，可用普通 Python 执行，通知 XML 测试会跳过。

参考：[用户分享方案](https://chatgpt.com/share/6ad725f0-df5c-83e8-beb4-8210fb63e043)、[Windows-Toasts 自定义应用身份](https://windows-toasts.readthedocs.io/en/latest/custom_aumid.html)、[通知点击地址](https://windows-toasts.readthedocs.io/en/latest/user/toast.html)。
