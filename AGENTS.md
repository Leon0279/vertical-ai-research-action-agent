# AGENTS.md

## 1. 项目概述

本仓库用于实现一个 Vertical AI Research & Action Agent。

系统目标是支持结构化的 research / reasoning / action-oriented workflow，包括但不限于：
- 请求理解
- 任务规划与拆解
- 上下文与记忆加载
- 基于工具/检索的研究执行
- 证据处理
- 结构化结论生成
- memory distillation / write-back

当前仓库处于“架构优先（architecture-first）”阶段。

当前目标不是构建完整可运行的生产系统，而是先把以下内容落成清晰、可演进的代码骨架：
- 顶层架构
- 包结构与模块边界
- domain models
- API schemas
- orchestration skeleton
- service interfaces
- test scaffolding

---

## 2. 文档优先级与事实来源

实现时优先参考以下文件：

1. `docs/hld-summary.md`
2. `docs/hld.md`
3. `AGENTS.md`

补充设计参考文件：

4. `docs/research-runtime-lld.md`
5. `docs/context-memory-storage-lld.md`

规则如下：

- 日常实现任务，优先读取 `docs/hld-summary.md`
- 当 `hld-summary` 信息不够时，再查 `docs/hld.md`
- `AGENTS.md` 提供仓库级、长期有效的实现规则
- 两篇 LLD 不是默认第一读取对象，而是“按任务需要选择性读取”
- 如果代码便利性与 HLD 冲突，优先保持 HLD 的架构意图
- 如果 LLD 与当前高层架构阶段存在张力，优先保持高层架构清晰，不要因为 LLD 存在就过早展开低层实现

---

## 3. 当前阶段目标

当前阶段只做 top-level architecture 和 skeleton，不做真实业务能力落地。

### 当前应优先实现
优先实现以下内容：
- package structure
- module boundaries
- typed domain models
- FastAPI-style request/response schemas
- orchestration skeleton
- stage skeletons
- service interfaces / protocols / abstract contracts
- stub implementations
- lightweight pytest scaffolding
- docstrings，用于说明职责与边界

### 当前不要默认实现
除非明确要求，否则不要实现：
- real LLM API calls
- real retrieval backend
- real vector DB integration
- real long-term memory backend
- real tool execution
- background jobs
- deployment infra
- auth/authz
- frontend/UI
- framework-heavy runtime
- LangGraph
- Celery
- Redis
- Kafka
- SQLAlchemy
- heavy dependency injection frameworks

如果行为尚未确定，优先使用：
- `TODO`
- `pass`
- `NotImplementedError`

不要为了“看起来完整”而伪造业务逻辑。

---

## 4. 技术栈约束

当前默认技术栈：

- Python
- Pydantic
- 普通 Python package 分层
- FastAPI 风格 schema
- pytest

代码风格偏好：
- 显式类型标注
- 结构清晰
- 小而专注的类与函数
- 尽量少依赖
- 清晰边界
- 命名与架构保持一致

---

## 5. 架构落地原则

### 5.1 明确分层
保持以下层次分离：
- `api`
- `domain`
- `orchestration`
- `services`
- `adapters`
- `common`
- `config`

不要把这些职责混在少数几个大文件里。

### 5.2 skeleton 优先于 speculative implementation
如果行为还没定清楚，先建 clean skeleton，不要脑补复杂内部逻辑。

### 5.3 interface / contract 优先
对 core components，必要时先定义：
- protocol
- abstract base class
- typed service interface

具体实现可以先 stub。

### 5.4 强类型优先
重要概念优先使用 typed models / enums，不要过早退化成 loose dicts 或泛化的 metadata blobs。

### 5.5 orchestration 与 integrations 分离
高层流程编排不要和以下代码混在一起：
- LLM adapter
- retrieval adapter
- memory backend adapter
- external tool connector

### 5.6 避免过早复杂化
保持系统可扩展，但不要为了未来假设提前引入复杂框架和机制。

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

## Python 接口与实现文件组织规则

本仓库对 Python 接口（Protocol / ABC）与实现类的文件组织有严格要求。生成或修改代码时必须遵守以下规则。

### 1. 一个文件只放一个顶层接口
- 每个接口文件中只能定义一个顶层接口。
- 不要在同一个 `interfaces.py`、`base.py` 或其他文件中放多个接口。
- 如果发现已有文件中包含多个接口，优先将其拆分为多个文件。

### 2. 一个文件只放一个顶层实现类
- 每个实现类文件中只能定义一个顶层实现类。
- 不要在同一个实现文件中放多个实现类。
- 如果发现已有文件中包含多个实现类，优先将其拆分为多个文件。

### 3. 文件名必须与接口名或类名一一对应
文件名必须使用“类名/接口名的小写蛇形命名（snake_case）”。

规则如下：
- `EvidenceProcessorProtocol` -> `evidence_processor_protocol.py`
- `EvidenceProcessorService` -> `evidence_processor_service.py`

不要使用以下泛化文件名来承载多个类型：
- `interfaces.py`
- `base.py`
- `contracts.py`
- `services.py`

除非该文件中确实只定义一个顶层类型，且文件名与该类型严格对应，否则不允许使用这些泛化命名。

### 4. 接口与实现类必须物理隔离
接口与实现类不应放在同一个目录下。

规则如下：
- 如果实现类位于当前目录，例如：
  - `app/services/evidence/evidence_processor_service.py`
- 则对应接口必须位于当前目录下的 `contracts` 子目录，例如：
  - `app/services/evidence/contracts/evidence_processor_protocol.py`

也就是说：
- 实现类放在功能目录本身
- 接口放在该功能目录下的 `contracts/` 子目录

### 5. contracts 目录规则
- `contracts/` 目录用于放置接口、协议、抽象基类等契约定义
- `contracts/` 中每个文件仍然只能包含一个顶层接口
- 接口文件名必须与接口名严格对应

### 6. 生成新代码时的默认落位规则
当新增一个能力模块时，默认按以下方式组织：

- 实现类：
  - `app/services/<domain>/<implementation_class_snake_case>.py`
- 接口：
  - `app/services/<domain>/contracts/<protocol_or_interface_snake_case>.py`

例如：
- `app/services/evidence/evidence_processor_service.py`
- `app/services/evidence/contracts/evidence_processor_protocol.py`

### 7. 修改旧代码时的整理要求
如果任务涉及已有接口或实现类文件，并且其组织方式不符合上述规则，则应在本次改动范围内尽量顺手整理为符合规范的结构，前提是：
- 不扩大无关范围
- 不引入额外行为变化
- 保持导入路径更新正确
- 保持测试可通过

### 8. 导入约束
- 实现类应从对应的 `contracts/` 子目录导入接口
- 不要为了省事把接口和实现重新放回同一文件或同一目录
- 不要创建聚合式 `interfaces.py` 作为多个接口的统一出口，除非明确要求

### 9. 命名约束
- Protocol 接口命名优先使用 `...Protocol`
- 实现类命名应体现职责，例如 `...Service`
- 文件名始终与顶层类型名一一对应，不做缩写，不做模糊泛化

### 10. 评审标准
以下情况视为不符合仓库规范：
- 一个文件中有多个接口
- 一个文件中有多个实现类
- 使用 `interfaces.py` 或 `base.py` 聚合多个接口
- 接口和实现类放在同一目录
- 文件名与顶层类型名不一致

---

## 7. orchestration 落地偏好

当前阶段，workflow orchestration 采用：

- 分 stage 结构
- 再加一个轻量 pipeline / orchestrator 串联

也就是：
- 每个 workflow stage 单独成私有方法或轻量模块
- 另有一个轻量 pipeline / orchestrator 按 HLD 顺序串联这些 stage
- stage 内部逻辑先 stub
- orchestration 负责“流程连接”，services 负责“能力职责”

目标：
- 让 End-to-End Workflow 在代码结构中可见
- 避免单个大协调器过胖
- 避免只定义接口却看不到实际 workflow 骨架

---

## 8. API 层落地偏好

Phase 1 的 API 层采用：

- 单入口 `run`

要求：
- 先只保留一个薄的 API 入口，例如 `POST /run`
- route 只做 transport boundary 工作
- request/response validation 放在 `api/schemas`
- route 不要承载业务逻辑
- route 应委托给 orchestration

当前阶段不要过早拆成多个 product-facing endpoints（例如 `query` / `plan`），等外部交互模型更清晰后再拆分。

---

## 9. workflow 对齐要求

代码结构应清晰映射 `docs/hld-summary.md` 中的 End-to-End Workflow。

优先把 workflow 骨架体现为类似阶段：
- receive request
- interpret request
- load relevant context and memory
- route by task type
- planning and decomposition
- research execution loop
- evidence sufficiency check
- structured conclusion generation
- memory distillation / write-back
- return final output

这些 stage 不要求现在具备完整逻辑，但要求其存在在架构上是可见的、可追踪的。

---

## 10. State 与 Memory 落地偏好

State and Memory 是当前阶段的核心内容，要求清晰建模。

### 10.1 memory 模型偏好
Phase 1 采用：
- 完整 typed skeletons
- 不做真实 persistence
- 不做 backend-specific design
- 不做数据库实现
- 不做复杂 ranking / scoring / retrieval logic

也就是说：
- 先建清晰 typed models
- 先把概念边界定住
- 所有行为实现都可 stub

### 10.2 需要保持清晰分离的概念
保持以下概念边界明确：
- short-term working state
- retrieved context
- long-term memory candidates

### 10.3 State / Memory 建模方向
优先为以下概念提供 typed internal models（按 HLD 对齐）：
- original query
- user goal
- task type
- project context
- constraints
- plan
- sub-questions
- retrieved evidence
- evidence summary
- intermediate findings
- final recommendation
- action items
- citations
- confidence
- memory candidates

不要把 transport-layer request/response schema 与 internal execution state 混为一体。

---

## 11. domain model 与 API schema 规则

### 11.1 domain models
`domain/models` 用于内部业务概念，例如：
- task type
- plan
- plan step
- evidence item
- evidence summary
- intermediate finding
- final recommendation
- action item
- execution state
- memory candidate

### 11.2 API schemas
`api/schemas` 用于：
- request payloads
- response payloads
- transport-layer validation

### 11.3 明确分离
即使字段相似，也不要默认把：
- API request/response schema
和
- internal domain model

合并成同一个 model，除非有充分理由。

---

## 12. Core Components 落地要求

当前阶段应让以下 core components 在代码结构中有对应位置或骨架：

- request intake
- task interpretation
- context and memory loading
- workflow routing
- planning and decomposition
- research execution
- retrieval / tool access layer
- evidence processing
- structured conclusion generation
- memory distillation / write-back
- observability hooks
- failure handling hooks

要求：
- responsibilities clear
- internals may remain stubbed
- naming should reflect HLD clearly

---

## 13. 两篇 LLD 的使用方式

### 13.1 Research Runtime LLD
当任务涉及以下内容时，读取 `docs/research-runtime-lld.md`：
- orchestration design
- workflow stages
- pipeline structure
- executor / runtime responsibilities
- stage-to-service mapping
- runtime observability hooks
- runtime failure handling
- research loop skeleton

使用原则：
- 用它来约束 runtime 相关的结构、职责和命名
- 不要因为它存在，就在当前阶段自动展开低层实现细节

### 13.2 Context, Memory, and Storage LLD
当任务涉及以下内容时，读取 `docs/context-memory-storage-lld.md`：
- state models
- context loading
- memory concepts
- memory candidates
- storage boundaries
- write-back flow
- context / memory / storage interfaces
- identity / lifecycle / dedup 相关结构约束

使用原则：
- 用它来约束 state / memory / storage 相关的 cross-cutting structure
- 不要因为它存在，就过早实现 repository、storage backend 或 persistence policy

### 13.3 当前阶段总规则
虽然这两篇 LLD 已存在，但当前阶段仍然以“高层架构清晰 + skeleton 完整”为主。

因此：
- LLD 主要用于补充已确定的 cross-cutting decisions
- 不要把当前阶段自动升级成低层实现阶段
- 如果 LLD 中有局部实现细节，而当前任务只是在搭顶层骨架，则优先保留高层结构与接口，不展开实现

---

## 14. testing 指导

使用 `pytest`。

当前阶段优先测试：
- importability
- structural expectations
- schema validation
- contract / interface behavior
- lightweight orchestration wiring

不要在当前阶段写重型 end-to-end tests，除非明确要求。

当模块行为尚未实现时，优先测试：
- model construction
- validation behavior
- interface shape
- wiring assumptions
- import boundaries

---

## 15. 任务执行规则

对于非 trivial 任务，遵循以下顺序：

### Step 1: read context
先读：
- `docs/hld-summary.md`
- `docs/hld.md`
- `AGENTS.md`
- relevant existing files

如果任务涉及 runtime 细节，再读：
- `docs/research-runtime-lld.md`

如果任务涉及 context / memory / storage 细节，再读：
- `docs/context-memory-storage-lld.md`

### Step 2: plan before coding
涉及多文件或结构调整时，先输出：
- 你理解到的目标
- 计划创建/修改的文件
- HLD / LLD 概念到代码模块的映射
- 假设与 open questions
- 建议结构

在得到批准前，不要直接进行大规模改动。

### Step 3: keep changes scoped
优先小步、可审查、可回滚的改动。

### Step 4: preserve architecture
优先保持清晰边界，而不是为了快而把逻辑堆在一起。

### Step 5: be explicit about placeholders
未实现内容要明确标记为 stub / TODO，不要伪装为已完成。

---

## 16. 需要避免的情况

避免：
- fake implementations pretending to be complete
- oversized service classes with mixed responsibilities
- business logic in route handlers
- orchestration code mixed with adapter code
- giant generic models that hide domain meaning
- speculative abstractions not justified by HLD / LLD
- broad uncontrolled rewrites
- hidden side effects in skeleton-level code

---

## 17. 当前阶段的 done 定义

一个任务在当前阶段可视为 done，当且仅当：

- repository structure 更清晰
- architectural boundaries 更明确
- code aligns with `docs/hld-summary.md`
- design remains consistent with `docs/hld.md`
- runtime-related skeletons are consistent with `docs/research-runtime-lld.md` when relevant
- context / memory / storage-related skeletons are consistent with `docs/context-memory-storage-lld.md` when relevant
- top-level skeletons exist in the right places
- typed models / schemas / interfaces are properly defined
- unfinished behavior is clearly marked as unfinished
- tests reflect current structural expectations

---

## 18. 输出风格要求

在提出计划或提交改动时，尽量包含：

1. 你理解到的目标
2. 要创建/修改的文件
3. 关键假设
4. 简要设计理由
5. 哪些内容仍然是 stub / TODO

对于较大改动，先给 plan，再实施。
