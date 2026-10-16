# Agent Memory 本地搜索

独立、只读的命令行脚本，目录结构参考同级 `md-sync`。Python 3.10+，只使用标准库，不需要安装依赖。

只调用现有 Agent Memory 的五个搜索接口。不会写入或删除记忆、导入会话、调整配置、启动服务、注册或修改 iii function，也不读取 Agent Memory 数据库。不提供网页、后台进程或同步功能。

## 最小调用

Agent Memory 服务需已启动。默认地址为 `http://127.0.0.1:3111`。

```powershell
$env:AGENTMEMORY_TOKEN = "你的 Token"
python scripts/agentmemory-search/search.py "论文结构"
```

默认返回最多 5 条 compact 结果，估算结果预算为 1500 token。成功时只向 stdout 输出服务端 JSON，错误向 stderr 输出 JSON 并返回非零退出码，可直接供 agent 或其他脚本调用。

从任何工作目录调用时，使用 `search.py` 的绝对路径即可，不依赖当前目录。

## 搜索类型

| `--kind` | HTTP API（均为 POST） | 内容 |
| --- | --- | --- |
| `search`（默认） | `/agentmemory/search` | 观察记录和长期记忆 |
| `smart` | `/agentmemory/smart-search` | 标题和 ID，可附带经验 |
| `lessons` | `/agentmemory/lessons/search` | 经验教训 |
| `insights` | `/agentmemory/insights/search` | 归纳洞见 |
| `vision` | `/agentmemory/vision-search` | 已建立向量的图片，需服务端启用对应功能 |

```powershell
python scripts/agentmemory-search/search.py "论文结构" --project project-analyse-local --format narrative
python scripts/agentmemory-search/search.py "论文" --kind smart --no-lessons
python scripts/agentmemory-search/search.py "用户偏好" --kind lessons --min-confidence 0.5
python scripts/agentmemory-search/search.py "缓存 性能" --kind insights --limit 3
python scripts/agentmemory-search/search.py "登录页截图" --kind vision --session-id "codex:example"
python scripts/agentmemory-search/search.py --kind vision --image-file reference.png
```

只有 `vision` 的 `--session-id` 是实际会话过滤。普通文本搜索没有单个 session 的过滤参数。

## 配置与只读挂载

| 参数 / 环境变量 | 用途 |
| --- | --- |
| `--api-url` / `AGENTMEMORY_URL` | 已运行服务的地址；也支持容器内的 `http://agentmemory:3111` |
| `--token-file` / `AGENTMEMORY_TOKEN_FILE` | 读取挂载的 Token 文件，优先于环境变量 |
| `AGENTMEMORY_TOKEN` | Bearer Token；没有提供时兼容 `AGENTMEMORY_SECRET` |
| `--timeout` | HTTP 超时秒数，默认 90，范围 1～300 |

Token 不作为命令行参数传入，也不会保存到文件或输出到日志。脚本无 Token 时仍可调用未配置鉴权的服务。

可将本目录只读挂载到任意已有 Python 环境，并把 Token 文件单独只读挂载。示例路径是**容器内路径**：

```sh
export AGENTMEMORY_URL=http://agentmemory:3111
export AGENTMEMORY_TOKEN_FILE=/run/secrets/agentmemory-token
python -B /opt/tools/agentmemory-search/search.py "论文结构"
```

对应挂载关系：

```text
本脚本目录 → /opt/tools/agentmemory-search:ro
本地 Token 文件 → /run/secrets/agentmemory-token:ro
```

服务地址必须从调用环境可达。容器内的 `127.0.0.1` 指向该容器本身；调用另一个容器时使用现有网络中的服务名。这里不创建容器、网络或服务。

## 范围和版本

- `--limit` 为 1～100；图片为 1～50。它限制返回条数，不保证后端扫描量。
- `--project` 支持四类文本搜索；`--agent-id` 只支持 search/smart。
- `--format`、`--token-budget` 只支持 search。
- `--min-confidence` 只支持 lessons/insights，范围 0～1。
- `--image-ref` 表示服务端受管图片路径；`--image-file` 读取调用环境中的参考图，最大 8 MiB。两种图片输入不能与文字同时提供。
- `--layer observation` 可以请求仅检索会话观察记录，但需要支持 `targetLayer` 的新版服务。旧包可能忽略它，因此默认不发送。
- 旧版 smart-search 的 project 过滤不完整，不能将它视为严格项目隔离。
- 普通搜索不是完整对话原文的全文检索，返回内容由现有 Agent Memory API 决定。

所有不适用于当前搜索类型的参数都会拒绝，不会静默改为其他操作。脚本不跟随重定向，也不使用系统 HTTP 代理。

## 验证

```powershell
python -B -m unittest discover -s scripts/agentmemory-search/tests -v
```

测试使用本机模拟 HTTP 服务，不读取真实 Token，不连接真实 Agent Memory。
