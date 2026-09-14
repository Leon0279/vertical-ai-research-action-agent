# Vertical AI Research & Action Agent

一个面向 AI 技术研究和工程决策的有状态 Agent。系统通过固定外层 Pipeline 和受预算约束的研究循环完成任务理解、上下文加载、多来源检索、证据处理、结构化结论、长期记忆写回和会话连续性维护。

## 核心能力

- 基于任务类型的 topic exploration、comparison、recommendation 和 action planning。
- Docs、arXiv、Tavily Web Search 和 Research Knowledge Memory 多来源检索。
- 有限重试、fallback、partial success 和证据不足时的安全降级。
- Redis session memory，以及 PostgreSQL + pgvector 长期 memory。
- Project 创建和查询 API、结构化 JSONL 日志及 request trace。

## 本地一键启动

### 前置要求

- Docker Desktop，且支持 Docker Compose。
- 可用的 `ZHIPU_API_KEY` 和 `TAVILY_API_KEY`。
- arXiv 请求使用的真实联系邮箱标识。

### 新环境启动

```bash
cp .env.example .env
```

编辑 `.env`，至少替换：

```text
ZHIPU_API_KEY
TAVILY_API_KEY
ARXIV_PAPER_SEARCH_CLIENT_IDENTITY
ARXIV_PAPER_CONTENT_FETCH_CLIENT_IDENTITY
```

然后执行：

```bash
make dev
```

该命令会检查配置、创建本地持久化 volume、构建 API 镜像、启动 Redis 和 PostgreSQL、启用 pgvector、执行五个建表脚本，并等待 API 进入 ready 状态。启动本身不会调用 Zhipu、Tavily 或 arXiv。

服务地址：

- API：<http://127.0.0.1:8000>
- Swagger：<http://127.0.0.1:8000/docs>
- Health：<http://127.0.0.1:8000/healthz>
- Readiness：<http://127.0.0.1:8000/readyz>

如果在 `.env` 中修改了 `API_PORT`，请使用对应端口。

### 从旧手工容器迁移

如果本机已经存在旧的 `vaa-postgres` 和 `vaa-redis` 容器，`make dev` 会拒绝继续，避免端口冲突。确认它们分别使用 `vaa-postgres-data` 和 `vaa-redis-data` 后，执行一次：

```bash
make adopt-local-data CONFIRM_ADOPT=YES
```

接管命令会：

1. 验证旧容器的镜像和 volume。
2. 记录五张 memory 表和 Redis 的数据数量。
3. 停止并删除两个旧容器，但保留数据 volume。
4. 使用 Compose 启动新环境。
5. 对比接管前后的数据数量，并检查 pgvector 和五张表。

任一验证失败时不会删除 volume。

## 常用命令

```bash
make dev           # 构建并启动全部后端服务
make status        # 查看容器和健康状态
make logs          # 跟踪 API、Redis、PostgreSQL 日志
make smoke         # 免费检查 health、readiness、OpenAPI 和 docs
make down          # 停止服务，保留 Redis/PostgreSQL 数据
make test-docker   # 在 API 容器环境运行自动化测试
```

执行一次真实、会产生外部 API 费用的最小请求：

```bash
make smoke-live CONFIRM_PAID=YES
```

删除本地 Redis 和 PostgreSQL 数据必须显式确认：

```bash
make reset-data CONFIRM_RESET=YES
```

不要在需要保留 memory 时执行 `reset-data`。

## 本机 Python 开发

Docker Compose 是推荐启动方式。已有 Python 3.11 虚拟环境时，也可以继续使用：

```bash
make test
make test-unit
make run
```

本机运行使用 `.env` 中的 `localhost` DSN；Compose 会在 API 容器内自动覆盖为 `postgres` 和 `redis` 服务地址。

## API

主要接口：

```text
POST /v1/agent/run
POST /v1/projects
GET  /v1/projects?user_id=...
GET  /v1/projects/{project_id}?user_id=...
GET  /healthz
GET  /readyz
```

最小 Agent 请求：

```bash
curl --request POST http://127.0.0.1:8000/v1/agent/run \
  --header 'content-type: application/json' \
  --data '{
    "query": "What is retrieval-augmented generation? Cite reliable sources.",
    "user_id": "local-demo",
    "iteration_budget": 2
  }'
```

`iteration_budget` 允许范围为 `1–5`，表示本次请求允许的最大研究轮数。外部请求会消耗对应 provider 的额度。

## 日志

结构化运行日志默认写入：

```text
logs/app.jsonl
```

可以通过以下命令查看容器日志：

```bash
make logs
```

日志包含 `trace_id`、Pipeline 阶段、retrieval attempt/fallback、研究迭代和 memory writeback 结果，但不会记录 API Key、Authorization、完整 prompt 或 provider 原始响应。

## 常见问题

### Docker Desktop 未启动

`make dev` 会在构建前退出。启动 Docker Desktop 后重试。

### 配置仍是模板值

Preflight 只输出缺失变量的名称，不输出变量内容。编辑 `.env` 并替换对应占位符。

### 端口被占用

修改 `.env` 中的 `API_PORT`、`POSTGRES_PORT` 或 `REDIS_PORT`。如果占用者是旧的 `vaa-postgres`、`vaa-redis`，使用上面的安全接管命令。

### 数据库初始化失败

```bash
docker compose logs db-init postgres
```

五个 SQL 文件位于 `docs/sql/`，每次启动都会幂等执行。已有表不会被删除或清空。

### Readiness 返回 503

```bash
make status
docker compose logs api redis postgres db-init
```

`/readyz` 会检查 Redis、五个 PostgreSQL memory table 和 pgvector，不会访问付费外部 provider。

## 当前边界

该 Compose 配置用于本地开发和作品集演示，不是生产部署配置。当前没有认证、HTTPS、生产级 secret manager、异步任务队列或多 worker 文件日志支持；请勿直接暴露到公网。

架构设计见：

- `docs/hld-summary.md`
- `docs/hld.md`
- `docs/research-runtime-lld.md`
- `docs/context-memory-storage-lld.md`
