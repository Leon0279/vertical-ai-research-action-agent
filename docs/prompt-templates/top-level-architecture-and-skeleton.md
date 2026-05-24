请以以下文件作为主要上下文：

- docs/hld-summary.md
- docs/hld.md
- AGENTS.md

任务目标：
为这个 Vertical AI Research & Action Agent 项目实现第一版顶层架构 skeleton。

当前阶段要求：
- 只做 top-level architecture 和 skeleton
- 不实现真实业务逻辑
- Core Components 内部可以保持 stub
- 当前重点是把 HLD 落成清晰的代码结构

技术栈约束：
- Python
- Pydantic
- 普通 Python package 分层
- FastAPI 风格 schema
- pytest

明确限制：
- 不要实现真实 LLM API 调用
- 不要实现真实 retrieval backend
- 不要实现 vector DB integration
- 不要实现真实 memory persistence
- 不要引入 LangGraph
- 不要引入 Celery / Redis / Kafka / SQLAlchemy
- 不要过早做低层实现

架构偏好：
- orchestration 使用“分 stage 模块 + 轻量 pipeline/orchestrator 串联”
- API 层 Phase 1 使用单入口 run
- memory 先使用 typed skeleton，不做真实 backend
- domain models 与 api schemas 分离
- orchestration 与 services / adapters 分离

请先只做规划，不要立即改文件。

请输出：
1. 你理解到的目标
2. 推荐的目录结构
3. HLD 中各核心部分到代码模块的映射
4. 计划创建或修改的文件列表
5. 关键假设与 open questions
6. 你建议的最小可落地 skeleton 范围

在我确认之前，不要开始实现。