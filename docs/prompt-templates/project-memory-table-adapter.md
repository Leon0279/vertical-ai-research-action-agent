请按以下顺序读取上下文：

1. AGENTS.md
2. docs/hld-summary.md
3. docs/hld.md
4. docs/context-memory-storage-lld.md
5. docs/research-runtime-lld.md（如果你认为本轮改动会影响 memory loading / write-back / pipeline runtime 的调用方式）
6. 本轮任务相关的已有代码文件

当前任务：
参考 docs/context-memory-storage-lld.md，为 project_profile_memory 这个 PostgreSQL 表实现对应的 memory adapter。

任务背景：
- 本轮任务的重点是 project_profile_memory 这一张表
- 这是 PostgreSQL 表级别的 adapter 实现任务
- 后续还会为其他 PostgreSQL 表生成各自的 adapter
- 因此本轮不要为了“通用性”过度抽象到影响当前任务的清晰度
- 接口和实现类的放置位置已经确定：
  - 接口：app/adapters/memory/contracts
  - 实现类：app/adapters/memory

当前阶段说明：
- 当前阶段是在既定顶层架构下逐步实现真实能力
- 本轮任务属于 adapter / persistence boundary implementation，不是 business component 的内部逻辑实现
- 保持现有顶层架构、pipeline 主流程、分层边界、contracts 结构不变
- 不要为了接 PostgreSQL 而破坏既定分层
- adapter 负责封装对 project_profile_memory 表的读写、映射、序列化/反序列化、错误处理
- adapter 不负责承担业务解释、规划、研究等领域逻辑

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
- 如果需要 PostgreSQL client / driver，请优先选择轻量、直接、适合当前项目阶段的方案
- 不要把本应属于 service / domain 的业务逻辑塞进 adapter
- 不要把本应属于 adapter 的数据库访问逻辑塞回 orchestration / route / service
- 不要扩大到与 project_profile_memory adapter 无关的范围
- 不要顺手重构其他 memory adapter 或其他表的实现
- 如果需要修改接口定义，应保持最小必要修改，不要为了未来其他表的 adapter 过度设计

实现偏好：
- 主要设计依据是 docs/context-memory-storage-lld.md
- 保持 domain models 与 api schemas 分离
- 保持 orchestration 与 services / adapters 分离
- 保持接口与实现类的文件组织规则符合 AGENTS.md
- 与 project_profile_memory 表相关的接口应放在 app/adapters/memory/contracts
- 具体 PostgreSQL 实现类应放在 app/adapters/memory
- adapter 应通过配置 / 环境变量读取 PostgreSQL 连接信息，不要把连接参数硬编码在代码里
- 如果 project_profile_memory 表的 schema、主键、唯一键、upsert 策略、字段映射、序列化方式需要明确，请优先根据 LLD 推导；若仍不明确，请先提出问题，不要直接脑补
- 本轮应优先做“单表 adapter 的最小真实实现”，而不是提早构造一个过度通用的 repository framework

本轮聚焦范围：
- 目标 adapter：project_profile_memory PostgreSQL adapter
- 相关契约：放在 app/adapters/memory/contracts
- 相关实现：放在 app/adapters/memory
- 本轮希望实现的重点：
  - 定义或确认该表对应的 adapter contract
  - 实现针对 project_profile_memory 的 PostgreSQL adapter
  - 明确 domain model 与表记录之间的映射关系
  - 明确读取 / 写入 / upsert / not found / error handling 的最小行为
  - 增加必要的配置读取、SQL 组织方式、最小测试支撑
- 本轮不处理的内容：
  - 其他 PostgreSQL 表的 adapter
  - 大范围通用化 memory repository 框架
  - 与 project_profile_memory 无关的 component 逻辑扩展
  - 大范围 pipeline / orchestration / component 重构

补充要求：
- 如果你发现当前没有合适的 contract，请先提出最小 contract 设计方案
- 如果你发现当前已有 contract 不能很好支撑 project_profile_memory adapter，请先提出最小修改方案和影响分析，不要直接修改
- 如果你发现 domain model 与表结构映射不清，请先列出映射假设和待确认点
- 请先只做规划，不要立即改文件

请输出：
1. 你理解到的本轮目标
2. 本轮需要读取和依赖的 HLD / LLD / 代码文件
3. project_profile_memory adapter、contract、domain model 三者之间的职责边界
4. 你是否建议新增或修改 contract；如果建议，请说明最小修改范围及理由
5. 计划创建或修改的文件列表
6. 你准备实现的“最小真实行为”是什么
7. 你准备如何设计表字段映射、SQL 读写、upsert、错误处理与 not-found 行为
8. 你准备如何保持与现有调用方和 contracts 的一致性
9. 哪些内容本轮仍会保留为 stub / TODO
10. 关键假设与 open questions
11. 建议的测试范围（尤其说明如何避免测试强依赖真实 PostgreSQL）

在我确认之前，不要开始实现。