# AGENTS.md

## 1. 项目概述

本仓库用于实现一个 Vertical AI Research & Action Agent。

系统目标是支持结构化的 research / reasoning / action-oriented workflow，包括但不限于：

* 请求理解
* 任务规划与拆解
* 上下文与记忆加载
* 基于工具/检索的研究执行
* 证据处理
* 结构化结论生成
* memory distillation / write-back

当前仓库已经完成了顶层架构与主要模块边界设计。

当前阶段的核心目标是：

* 在既定顶层架构下，逐个实现 core components
* 让关键 workflow 从“骨架可见”推进到“组件可运行”
* 在不破坏既定架构边界的前提下，用真实逻辑逐步替换 stub
* 优先形成一个最小但可信的端到端运行链路

当前阶段不是重新设计顶层架构，也不是默认引入新的 orchestration framework。

---

## 2. 文档读取顺序与事实来源

开始任务前，按以下顺序读取和使用文档：

1. `AGENTS.md`
2. `docs/hld-summary.md`
3. `docs/hld.md`
4. `docs/research-runtime-lld.md`（当任务涉及 runtime / orchestration / workflow stage / executor / planning / routing 时）
5. `docs/context-memory-storage-lld.md`（当任务涉及 context / memory / storage / state / write-back 时）

规则如下：

* `AGENTS.md` 提供仓库级、长期有效的实现规则、代码组织约束、命名规则、测试要求和任务执行方式
* `docs/hld-summary.md` 用于快速把握系统架构、End-to-End Workflow、State and Memory、Core Components
* `docs/hld.md` 用于确认完整架构意图与高层约束
* `docs/research-runtime-lld.md` 是 runtime / orchestration / stage / executor / planning / routing 等相关实现的主要设计依据
* `docs/context-memory-storage-lld.md` 是 context / memory / storage / state / write-back 等相关实现的主要设计依据
* 如果实现方式与设计文档冲突，优先保持设计一致性，不要为了局部方便破坏既定边界
* 如果 HLD 与 LLD 存在张力：

  * HLD 决定系统级结构与跨组件边界
  * LLD 决定局部组件实现方向、职责划分和接口语义

---

## 3. 当前阶段目标

当前阶段是：在既定顶层架构下实现 core components。

### 当前应优先做的事

优先推进以下工作：

* 将已有 stub component 逐步替换为最小真实实现
* 实现 core components 的核心内部逻辑，而不只是保留空壳
* 保持 pipeline / orchestration 主流程稳定，同时逐步增强 stage 内部能力
* 保持 domain models、contracts、services、adapters 之间边界清晰
* 为关键组件补充 unit tests、contract tests，以及必要的轻量集成测试
* 优先让系统形成“最小可跑通链路”，而不是继续扩张骨架

### 当前不要默认做的事

除非明确要求，否则不要默认进行以下动作：

* 重构顶层架构
* 引入 LangGraph
* 引入新的 orchestration framework
* 大规模改写现有 pipeline 结构
* 接入真实生产级基础设施
* 接入复杂 deployment / job / distributed runtime
* 引入 Celery / Redis / Kafka / SQLAlchemy / heavy dependency injection frameworks
* 为了“显得高级”而引入当前并不需要的抽象层

### 实现原则

* 能实现真实逻辑时，不要继续保留纯 stub
* 但也不要为了“看起来完整”而编造不可信的业务逻辑
* 如果某块逻辑暂时无法确定，可保留局部 TODO；但当前阶段整体目标不是继续大量 TODO 化

---

## 4. 技术栈约束

当前默认技术栈：

* Python
* Pydantic
* 普通 Python package 分层
* FastAPI 风格 schema
* pytest

代码风格偏好：

* 显式类型标注
* 小而专注的类与函数
* 结构清晰
* 命名与架构一致
* 尽量少依赖
* 明确边界
* 可测试性优先
* 优先可读性，不追求炫技

---

## 5. 架构落地原则

### 5.1 顶层架构已确定，默认不要重写

当前默认前提是：

* 顶层架构已确定
* 主流程阶段划分已确定
* core components 的主要职责边界已确定

因此：

* 不要默认重新设计 workflow
* 不要默认把当前项目改造成另一种架构风格
* 不要因为某个局部实现不方便，就改写系统级结构

如果确实发现顶层架构有问题，应先提出问题与影响，再等待确认，不要直接改。

### 5.2 保持分层清晰

保持以下层次分离：

* `api`
* `domain`
* `orchestration`
* `services`
* `adapters`
* `common`
* `config`

不要把这些职责混在少数几个大文件里。

### 5.3 实现时遵守 contracts，而不是绕过 contracts

对 core components：

* 优先保留既定的 protocol / abstract contract
* 实现类应遵循 contract 语义
* 不要为了省事跳过 contract，直接在 orchestration 中写临时逻辑

### 5.4 强类型优先

重要概念优先使用 typed models / enums，不要退化成 loose dicts 或泛化 metadata blobs。

### 5.5 orchestration 与 integrations 分离

高层流程编排不要和以下代码混在一起：

* LLM adapter
* retrieval adapter
* memory backend adapter
* external tool connector

### 5.6 最小真实实现优先于过度抽象

当前阶段更看重：

* 一个可信的最小实现

而不是：

* 过度抽象的框架化空壳

---

## 6. 推荐目录结构

除非有明确理由，否则优先按以下结构组织：

```
app/
  api/
    routes/
    schemas/
  domain/
    models/
    enums/
  orchestration/
    stages/
  services/
    planner/
    executor/
    retrieval/
    evidence/
    memory/
    output/
  adapters/
    llm/
    retrieval/
    memory/
    tools/
  common/
    errors/
    types/
    utils/
  config/

tests/
  unit/
  contract/

docs/
  hld-summary.md
  hld.md
  research-runtime-lld.md
  context-memory-storage-lld.md
```

这是推荐方向，不是绝对死规则；但新增代码应尽量贴合这一结构。

---

## 7. Python 接口与实现文件组织规则

本仓库对 Python 接口（Protocol / ABC）与实现类的文件组织有严格要求。生成或修改代码时必须遵守以下规则。

### 7.1 一个文件只放一个顶层接口

* 每个接口文件中只能定义一个顶层接口
* 不要在同一个 `interfaces.py`、`base.py` 或其他文件中放多个接口
* 如果发现已有文件中包含多个接口，优先拆分为多个文件

### 7.2 一个文件只放一个顶层实现类

* 每个实现类文件中只能定义一个顶层实现类
* 不要在同一个实现文件中放多个实现类
* 如果发现已有文件中包含多个实现类，优先拆分为多个文件

### 7.3 文件名必须与接口名或类名一一对应

文件名必须使用“类名/接口名的小写蛇形命名（snake_case）”。

例如：

* `EvidenceProcessingServiceProtocol` -> `evidence_processing_service_protocol.py`
* `EvidenceProcessingService` -> `evidence_processing_service.py`

不要使用以下泛化文件名来承载多个类型：

* `interfaces.py`
* `base.py`
* `contracts.py`
* `services.py`

除非该文件中确实只定义一个顶层类型，且文件名与该类型严格对应，否则不允许使用这些泛化命名。

### 7.4 接口与实现类必须物理隔离

接口与实现类不应放在同一个目录下。

规则如下：

* 如果实现类位于当前目录，例如：

  * `app/services/evidence/evidence_processing_service.py`
* 则对应接口必须位于当前目录下的 `contracts` 子目录，例如：

  * `app/services/evidence/contracts/evidence_processing_service_protocol.py`

也就是说：

* 实现类放在功能目录本身
* 接口放在该功能目录下的 `contracts/` 子目录

### 7.5 contracts 目录规则

* `contracts/` 目录用于放置接口、协议、抽象基类等契约定义
* `contracts/` 中每个文件仍然只能包含一个顶层接口
* 接口文件名必须与接口名严格对应

### 7.6 生成新代码时的默认落位规则

当新增一个能力模块时，默认按以下方式组织：

* 实现类：

  * `app/services/<domain>/<implementation_class_snake_case>.py`
* 接口：

  * `app/services/<domain>/contracts/<protocol_or_interface_snake_case>.py`

### 7.7 修改旧代码时的整理要求

如果任务涉及已有接口或实现类文件，并且其组织方式不符合上述规则，则应在本次改动范围内尽量顺手整理为符合规范的结构，前提是：

* 不扩大无关范围
* 不引入额外行为变化
* 保持导入路径更新正确
* 保持测试可通过

### 7.8 导入约束

* 实现类应从对应的 `contracts/` 子目录导入接口
* 不要为了省事把接口和实现重新放回同一文件或同一目录
* 不要创建聚合式 `interfaces.py` 作为多个接口的统一出口，除非明确要求

### 7.9 命名约束

* Protocol 接口命名优先使用 `...Protocol`
* 实现类命名应体现职责，例如 `...Service`
* 文件名始终与顶层类型名一一对应，不做缩写，不做模糊泛化

### 7.10 评审标准

以下情况视为不符合仓库规范：

* 一个文件中有多个接口
* 一个文件中有多个实现类
* 使用 `interfaces.py` 或 `base.py` 聚合多个接口
* 接口和实现类放在同一目录
* 文件名与顶层类型名不一致

---

## 8. orchestration 落地偏好

当前阶段，workflow orchestration 的总体结构已经确定。

默认要求：

* 保持现有固定 outer workflow 的设计方向
* 保持轻量 pipeline / orchestrator 串联 stage 的模式
* 不要把 orchestration 重写成另一种完全不同的表达方式
* 不要因为某个 component 尚未实现，就把逻辑回填到 orchestration 层

当前阶段，orchestration 的职责主要是：

* 连接既定 stage
* 驱动 state 在各 stage 间流转
* 调用各 core components
* 维持流程顺序、边界与生命周期

当前阶段的主要工作重点不是继续雕刻 orchestration 骨架，而是让各 stage 背后的 component 真正承担逻辑。

---

## 9. API 层落地偏好

当前阶段 API 层仍然保持：

* 单入口 `run`

要求：

* route 只做 transport boundary 工作
* request/response validation 放在 `api/schemas`
* route 不要承载业务逻辑
* route 应委托给 orchestration

不要默认扩展成多个 product-facing endpoints，除非外部交互模型已经明确并被显式要求实现。

---

## 10. workflow 对齐要求

代码结构应继续清晰映射 `docs/hld-summary.md` 中的 End-to-End Workflow。

优先保持以下阶段语义清晰：

* receive request
* interpret request
* load relevant context and memory
* route by task type
* planning and decomposition
* research execution loop
* evidence sufficiency check
* structured conclusion generation
* memory distillation / write-back
* return final output

当前阶段的目标不是再去“证明这些阶段存在”，而是让这些阶段背后的 core components 逐步具备真实能力。

---

## 11. State 与 Memory 落地偏好

State and Memory 仍然是实现阶段的核心内容。

### 11.1 当前实现方向

* 保持 typed models
* 保持概念边界清晰
* 在已有模型基础上逐步实现 loader / distiller / persistence boundary 相关逻辑
* 不要退化成“单一 generic record + metadata 大字典”风格

### 11.2 需要保持分离的概念

保持以下概念边界明确：

* short-term working state
* retrieved context
* long-term memory candidates

### 11.3 当前阶段关注点

当前阶段对 memory / context / state 的工作重点是：

* 让已有模型真正参与运行时流转
* 让 context loading 和 memory distillation 具备最小真实行为
* 保持与 LLD 中的 cross-cutting decisions 一致
* 不要过早引入复杂 backend-specific persistence 设计

---

## 12. domain model 与 API schema 规则

### 12.1 domain models

`domain/models` 用于内部业务概念，例如：

* task type
* plan
* plan step
* evidence item
* evidence summary
* intermediate finding
* final recommendation
* action item
* execution state
* memory candidate

### 12.2 API schemas

`api/schemas` 用于：

* request payloads
* response payloads
* transport-layer validation

### 12.3 明确分离

即使字段相似，也不要默认把：

* API request/response schema
  和
* internal domain model

合并成同一个 model，除非有充分理由。

---

## 13. Core Components 实现要求

当前阶段的核心工作是逐个实现 core components。

以下组件在实现时应优先考虑：

* task interpretation
* context and memory loading
* workflow routing
* planning and decomposition
* research execution
* evidence processing
* structured conclusion generation
* memory distillation / write-back
* response assembly
* session continuity management

实现要求：

* 优先实现最小真实逻辑，而不是继续保留纯 stub
* 逻辑要与 HLD / LLD 一致
* 组件边界要清晰
* 不要把本应属于某个 service 的逻辑塞回 pipeline
* 如果某个组件暂时只能部分实现，应明确指出“已实现的部分”和“仍待实现的部分”

---

## 14. 两篇 LLD 的使用方式

### 14.1 Research Runtime LLD

当任务涉及以下内容时，读取 `docs/research-runtime-lld.md`：

* orchestration design
* workflow stages
* pipeline structure
* executor / runtime responsibilities
* stage-to-service mapping
* runtime observability hooks
* runtime failure handling
* research loop behavior

使用原则：

* 用它约束 runtime 相关结构、职责和命名
* 当前阶段应更多依据它来实现 `research_executor`、routing、planning、loop control 等组件
* 不要仅停留在 skeleton 层面，应在其允许的范围内做真实实现

### 14.2 Context, Memory, and Storage LLD

当任务涉及以下内容时，读取 `docs/context-memory-storage-lld.md`：

* state models
* context loading
* memory concepts
* memory candidates
* storage boundaries
* write-back flow
* context / memory / storage interfaces
* identity / lifecycle / dedup 相关结构约束

使用原则：

* 用它约束 state / memory / storage 的 cross-cutting structure
* 当前阶段应更多依据它实现 context loader、memory distiller、persistence boundary 等组件
* 仍然不要过早绑定复杂 backend，但应实现合理的最小行为

### 14.3 当前阶段总规则

当前阶段已经不再是“只搭顶层骨架”。

因此：

* LLD 不只是补充参考，而是组件实现时的重要依据
* 对相关组件的实现，应主动读取对应 LLD
* 不要再以“当前只是 skeleton 阶段”为理由长期回避核心逻辑实现

---

## 15. testing 指导

使用 `pytest`。

当前阶段测试重点应从“结构存在”转向“组件行为正确”。

优先测试：

* unit tests for component logic
* contract tests for interfaces
* schema validation tests
* stage/service integration at lightweight level
* state transition correctness
* failure path / degraded path behavior where meaningful

仍然不默认要求重型端到端测试，但对于已经实现出真实行为的组件，不应只停留在 importability 或空壳测试。

当模块行为已实现时，应尽量测试：

* 输入输出行为
* 边界条件
* 关键状态更新
* 合约一致性
* 与相邻组件的协作关系

---

## 16. 任务执行规则

对于非 trivial 任务，遵循以下顺序：

### Step 1: read context

先读：

* `AGENTS.md`
* `docs/hld-summary.md`
* `docs/hld.md`
* relevant existing files

如果任务涉及 runtime 细节，再读：

* `docs/research-runtime-lld.md`

如果任务涉及 context / memory / storage 细节，再读：

* `docs/context-memory-storage-lld.md`

### Step 2: plan before coding

涉及多文件或结构调整时，先输出：

* 你理解到的目标
* 计划创建/修改的文件
* HLD / LLD 概念到代码模块的映射
* 关键假设与 open questions
* 本轮要实现的最小真实行为是什么

在得到批准前，不要直接进行大规模改动。

### Step 3: keep changes scoped

优先小步、可审查、可回滚的改动。

### Step 4: preserve architecture

优先保持既定架构清晰边界，不要为了图快把逻辑堆在错误层次。

### Step 5: be explicit about remaining gaps

如果仍有未实现部分，要明确说明：

* 已经实现了什么
* 暂未实现什么
* 为什么暂未实现

---

## 17. 需要避免的情况

避免：

* fake implementations pretending to be complete
* oversized service classes with mixed responsibilities
* business logic in route handlers
* orchestration code mixed with adapter code
* giant generic models that hide domain meaning
* 继续堆积大量长期不处理的 TODO / pass / NotImplementedError
* speculative abstractions not justified by HLD / LLD
* broad uncontrolled rewrites
* hidden side effects in skeleton-level code
* 为了局部方便而破坏既定 pipeline / state / contract 结构

---

## 18. 当前阶段的 done 定义

一个任务在当前阶段可视为 done，当且仅当：

* 既定架构边界保持清晰
* code aligns with `docs/hld-summary.md`
* design remains consistent with `docs/hld.md`
* runtime-related implementation is consistent with `docs/research-runtime-lld.md` when relevant
* context / memory / storage-related implementation is consistent with `docs/context-memory-storage-lld.md` when relevant
* 对应 core component 有明确、可信的最小真实行为
* typed models / schemas / interfaces 仍保持清晰
* 测试覆盖了当前已实现行为，而不只是结构存在性
* 仍未实现的部分被清楚标记，并且范围可控

---

## 19. 输出风格要求

在提出计划或提交改动时，尽量包含：

1. 你理解到的目标
2. 要创建/修改的文件
3. 关键假设
4. 简要设计理由
5. 本轮实现了哪些真实行为
6. 哪些内容仍然是 stub / TODO
7. 下一步最自然的推进点是什么

对于较大改动，先给 plan，再实施。
