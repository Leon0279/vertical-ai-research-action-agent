请按以下顺序读取上下文：

1. AGENTS.md
2. docs/hld-summary.md
3. docs/hld.md
4. docs/research-runtime-lld.md（如果本轮改动影响 runtime / orchestration / workflow stage / executor / planning / routing）
5. docs/context-memory-storage-lld.md（如果本轮改动影响 context / memory / storage / state / write-back）
6. 本轮任务相关的已有代码文件

当前任务：
在既定顶层架构下，实现一个用于接入智谱 LLM 的 `LLMClientProtocol` 具体 adapter 实现类。

任务背景：
- 当前项目已经有 `LLMClientProtocol`
- 当前也已经有 `StubLLMClient` 作为 stub implementation
- 现在希望新增一个真实的 adapter，用于接入智谱 LLM
- 如果确有必要，可以调整 `LLMClientProtocol` 的方法定义
- 但对 protocol 的修改应尽量最小，并且必须评估对现有 `StubLLMClient`、调用方、tests 的影响

当前阶段说明：
- 当前阶段是在既定顶层架构下逐步实现真实能力
- 本轮任务属于 adapter implementation，不是 core business component 的内部逻辑实现
- 保持现有顶层架构、pipeline 主流程、分层边界、contracts 结构不变
- 不要为了接入智谱 LLM 而破坏既定分层
- adapter 负责封装 LLM 调用，不负责承担业务解释、规划、研究等领域逻辑

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
- 不要把本应属于 service / domain 的业务逻辑塞进 adapter
- 不要把本应属于 adapter 的基础设施调用逻辑塞回 orchestration 或 route
- 不要扩大到与 `LLMClientProtocol` 和智谱 adapter 无关的范围
- 不要顺手重构无关 component
- 如果需要修改 `LLMClientProtocol`，应保持最小必要修改，不要为了 adapter 方便而过度重塑协议

实现偏好：
- 保持 domain models 与 api schemas 分离
- 保持 orchestration 与 services / adapters 分离
- 保持接口与实现类的文件组织规则符合 AGENTS.md
- adapter 应位于合适的 adapters/llm 目录下
- protocol 应仍然保持为上层依赖的抽象契约
- 新增的智谱 adapter 应通过配置 / 环境变量读取必要参数，不要把密钥或 endpoint 硬编码在代码里
- 保留 `StubLLMClient`，用于测试或非真实调用场景
- 如果调整 protocol，需同步说明 `StubLLMClient` 是否要更新，以及调用方是否要更新

本轮聚焦范围：
- 目标 adapter: 智谱 LLM adapter
- 相关契约: `LLMClientProtocol`
- 相关已有实现: `StubLLMClient`
- 本轮希望实现的重点：
  - 新增一个真实的 `LLMClientProtocol` 实现类，用于调用智谱 LLM
  - 如有必要，对 `LLMClientProtocol` 做最小必要调整
  - 保持调用方通过 protocol 依赖 adapter，而不是直接依赖具体实现
  - 增加必要的配置读取、错误处理、超时/失败封装、最小测试支撑
- 本轮不处理的内容：
  - 与 LLM adapter 无关的 component 内部业务逻辑扩展
  - 大范围 pipeline / orchestration 重构
  - 与智谱接入无关的其他 adapter 实现

补充要求：
- 如果你发现 `LLMClientProtocol` 当前定义不足以支撑真实 adapter，请先提出协议调整方案和影响分析，不要直接修改
- 请先只做规划，不要立即改文件

请输出：
1. 你理解到的本轮目标
2. 本轮需要读取和依赖的 HLD / LLD / 代码文件
3. `LLMClientProtocol`、`StubLLMClient`、新智谱 adapter 之间的职责边界
4. 你是否建议修改 `LLMClientProtocol`；如果建议，请说明最小修改范围及理由
5. 计划创建或修改的文件列表
6. 你准备实现的“最小真实行为”是什么
7. 你准备如何处理配置、认证信息、错误处理、超时与失败场景
8. 你准备如何保持与现有调用方和 contracts 的一致性
9. `StubLLMClient` 是否需要同步调整；如果需要，请说明范围
10. 哪些内容本轮仍会保留为 stub / TODO
11. 关键假设与 open questions
12. 建议的测试范围

在我确认之前，不要开始实现。