请按以下顺序读取上下文：

1. AGENTS.md
2. docs/hld-summary.md
3. docs/hld.md
4. docs/research-runtime-lld.md（如果本轮任务涉及 runtime / orchestration / workflow stage / executor / planning / routing）
5. docs/context-memory-storage-lld.md（如果本轮任务涉及 context / memory / storage / state / write-back）
6. 本轮任务相关的已有代码文件

当前任务：
在既定顶层架构下，实现 [component 名称] 的最小真实行为。

当前阶段说明：
- 当前阶段不是继续搭顶层骨架，而是在既定架构下逐个实现 core components
- 保持现有顶层架构、pipeline 主流程、分层边界、contracts 结构不变
- 优先实现最小可信行为，而不是继续保留纯 stub
- 不要为了局部实现方便而破坏既定架构

技术栈约束：
- Python
- Pydantic
- 普通 Python package 分层
- FastAPI 风格 schema
- pytest

明确限制：
- 不要引入 LangGraph
- 不要重构顶层 orchestration 结构
- 不要随意改写 pipeline 主流程
- 不要引入 Celery / Redis / Kafka / SQLAlchemy / heavy dependency injection frameworks
- 不要接入复杂生产级基础设施，除非任务明确要求
- 不要把本应属于 service / adapter / domain 的逻辑塞回 orchestration 或 route
- 不要编造不可信的业务逻辑
- 不要扩大到与本轮 component 无关的范围

实现偏好：
- 保持固定 outer workflow + stage-by-stage 调用的结构
- 保持 API 层单入口 run
- 保持 domain models 与 api schemas 分离
- 保持 orchestration 与 services / adapters 分离
- 保持接口与实现类的文件组织规则符合 AGENTS.md
- 优先通过最小真实实现替换已有 stub

本轮聚焦范围：
- 目标 component: [component 名称]
- 相关上游/下游组件: [可选填写]
- 本轮不处理的内容: [可选填写]

请先只做规划，不要立即改文件。

请输出：
1. 你理解到的本轮目标
2. 本轮需要读取和依赖的 HLD / LLD / 代码文件
3. 计划创建或修改的文件列表
4. 该 component 在当前架构中的职责边界
5. 你准备实现的“最小真实行为”是什么
6. 你准备如何保持与相邻组件的契约一致
7. 哪些内容本轮仍会保留为 stub / TODO
8. 关键假设与 open questions
9. 建议的测试范围

在我确认之前，不要开始实现。