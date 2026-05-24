# Context, Memory, and Storage LLD

# 1. Introduction and Scope

### 1.1 Purpose

本 Low-Level Design 的目标，是为本系统定义一套适合 **Vertical AI Research & Action Agent** 的 `Context`、`Memory` 与 `Storage` 设计方案。

在 High-Level Design 中，系统已经明确采用了：

- workflow-driven outer architecture + agentic inner loop
- staged single-agent topology
- stateful, memory-aware execution model
- session continuity 与 long-term memory 分离
- structured long-term memory 与 retrieval-oriented knowledge 分离

因此，本 LLD 的核心任务，不是简单讨论“数据应该存到哪个数据库”，而是进一步回答以下问题：

1. 系统到底有哪些类型的 memory，它们分别承担什么职责
2. 当前一次运行中，execution context 是如何从 query、session memory、long-term memory 和 retrieval-oriented knowledge 中构造出来的
3. 不同 memory 类型应该如何被读取、筛选、注入、写回和维护
4. 不同 memory 类型应如何映射到对应的逻辑存储层与物理存储方案
5. 如何在保持系统 memory-aware 的同时，避免 context inflation、memory pollution 和 stale memory interference

换句话说，本 LLD 的目标是把 HLD 中较抽象的 state / context / memory / storage 概念，落成一套可实现、可演进、可控制污染的 memory operating model。

---

### 1.2 Scope

本 LLD 覆盖以下内容：

- `Context`、`Memory`、`Storage` 相关核心概念的边界定义
- session short-term memory、structured long-term memory、retrieval-oriented knowledge 的 memory model
- 当前 run 中 execution context 的构造与加载流程
- memory 的 read path、write-back path、update policy 和 retention policy
- 逻辑存储层设计
- 物理存储候选方案的比较与当前版本的选型方向
- session memory、structured long-term memory 和 retrieval-oriented knowledge 的 record / schema 设计原则

本 LLD 关注的是：

**系统如何从多类持久化或半持久化信息资产中，构造出当前运行真正可用的 context，并在运行结束后将高价值信息按规则写回系统。**

---

### 1.3 Out of Scope

本 LLD 不深入以下内容：

- `Research Executor` 内部完整 loop control 的详细实现
- query rewrite、retrieval ranking、reranking 等 retrieval algorithm 的详细算法设计
- evidence normalization、evidence comparison、evidence conflict detection 的完整实现细节
- observability、deployment、failure handling 和 runtime guardrails 的详细实现
- API routing、request/response schema 的完整接口设计
- 企业级权限控制、合规审计、细粒度数据访问治理

这些内容要么已经在 HLD 中以高层方式定义，要么将在后续其他 LLD 中单独展开。

---

### 1.4 Relationship to HLD

本 LLD 是对 HLD 中以下部分的进一步细化：

- **State and Memory**
本 LLD 会将 HLD 中的 running state、execution context、session continuity、long-term memory 等概念进一步明确为可实现的数据模型与访问路径。
- **Core Components**
本 LLD 与以下组件直接相关：
    - Context and Memory Loader
    - Session Continuity Manager
    - Memory Distillation and Persistence Component
    - Tool Execution Layer（在 retrieval-oriented knowledge access 方面）
- **Data / Storage Overview**
HLD 中的 Data / Storage Overview 给出了高层分层视图；本 LLD 会进一步落实各类 memory 的逻辑分层、物理承载方式与 schema 设计方向。

本 LLD 不改变 HLD 已确定的架构方向，而是在这些方向之下明确具体实现边界与实现策略。

# 2. Core Concepts and Boundaries

本章的目标，是明确本系统中若干核心概念的定义与边界，避免后续在 `Context`、`Memory` 与 `Storage` 设计中出现语义混淆。

在本系统中，最容易被混淆的概念包括：

- 当前 request 内的运行态数据
- 从外部来源加载进来的上下文
- 当前 run 的完整执行环境
- 某个具体 stage 实际消费的输入
- session 级短期记忆
- cross-session 长期记忆
- 面向检索的知识型内容
- 承载这些内容的存储层

如果这些概念不先区分清楚，后续在 context construction、memory access、write-back policy 和 storage mapping 中会很容易出现职责重叠与语义不一致的问题。

---

### 2.1 Running State

`Running State` 指的是**单次 request lifecycle 内的全局运行态数据**。

它是当前 run 的主状态对象，也是本次执行过程中的 canonical mutable state。

典型内容包括：

- `original_query`
- `task_type`
- `user_goal`
- `task_framing`
- `constraints`
- `plan`
- `sub_questions`
- `comparison_candidates`
- `retrieved_evidence`
- `evidence_summary`
- `intermediate_findings`
- `final_recommendation`
- `action_items`
- `confidence`

`Running State` 的主要特点是：

- 生命周期仅限当前 run
- 在多个 stage 之间被持续读写和更新
- 代表当前请求处理过程中的核心工作状态
- 默认不作为长期 memory 持久化

因此，`Running State` 不是系统长期持有的 knowledge asset，而是当前请求执行过程中的工作状态容器。

---

### 2.2 Context Sources

`Context Sources` 指的是在当前 run 中，**理论上可以被系统用于构造上下文的信息来源**。

典型来源包括：

- 当前用户 query
- Task Interpretation 产出的 task_type、user_goal、task_framing、constraints
- session short-term memory
- selected long-term memory
- research knowledge memory
- 当前 run 中已产生的 intermediate outputs
- runtime metadata / capabilities（如 tool registry、budget、scope restrictions）

需要强调的是，`Context Sources` 只是上下文来源的集合，并不意味着这些来源中的全部内容都会进入当前 run 的最终执行环境。

因此，`Context Sources` 是一个**来源层概念**，而不是最终对象概念。

---

### 2.3 Context Construction

`Context Construction` 指的是系统在当前 run 中，**从多个 context sources 中加载、筛选、去重、压缩并组织可用上下文**的过程。

这一过程通常包括：

- 读取相关 context sources
- 根据 task_type、user_goal、task_framing 和当前 stage 决定需要哪些信息
- 对候选信息进行 relevance filtering、scope filtering、freshness filtering
- 对跨来源内容进行 redundancy control
- 在 context budget 下进行 final shaping

`Context Construction` 的输出，并不一定形成一个单独、固定、与 `Running State` 并列存在的对象。

更准确地说，被选中的外部上下文在构造完成后，通常会有两种去向：

1. 一部分被提炼并吸收到 `Running State` 中，成为当前 run 的核心工作状态
2. 一部分保留为 `Running State` 之外的补充上下文，供后续 stage 在需要时访问

因此，`Context Construction` 应被理解为一个**运行时过程**，而不是某个单一的静态数据对象。

---

### 2.4 Supplemental Context

`Supplemental Context` 指的是在当前 run 中，**已经过选择与整形、但未被吸收到 `Running State` 中的补充上下文**。

这类内容通常来自外部 memory 或知识层，例如：

- selected session summary
- selected decision memory records
- selected action / execution records
- selected research knowledge snippets
- supporting project profile records

`Supplemental Context` 的主要特点是：

- 它已经通过 context construction process 被选中
- 它在当前 run 中仍然可访问
- 它未必需要被固化为 `Running State` 的核心字段
- 它通常作为 supporting context，辅助某些 stage 的判断与生成

因此，`Supplemental Context` 与 `Running State` 的区别在于：

- 前者更偏辅助性、支持性上下文
- 后者更偏当前 run 的核心工作状态

---

### 2.5 Execution Context

`Execution Context` 指的是**当前 run 的完整执行环境**。

它不是单纯的 memory，也不只是 running state，而是当前 run 中系统真正可用的总体信息环境。

在本设计中，建议将其理解为：

> **Execution Context = Running State + Supplemental Context + Runtime Metadata / Capabilities**
> 

其中包括：

1. **Running State**
当前 run 的核心工作状态
2. **Supplemental Context**
当前 run 仍可访问的补充上下文
3. **Runtime Metadata / Capabilities**
当前 run 的运行时约束与能力信息，例如：
    - tool registry
    - request id
    - latency budget
    - iteration budget
    - scope restrictions

因此，`Execution Context` 是一个**比 Running State 更宽**的概念。

它包含 state，但不等于只有 state。

需要特别说明的是：

- 外部 context 并不是全部停留在 `Running State` 外
- 在 context construction 过程中，部分外部上下文会被提炼后吸收到 `Running State`
- 其余部分则保留为 `Supplemental Context`

因此，`Execution Context` 更适合被视为**当前 run 的总体执行环境**，而不是简单的“state + 外挂 context”。

---

### 2.6 Stage Input

`Stage Input` 指的是某个具体 stage 在执行时，**从当前 `Execution Context` 中取出的输入子集**。

这一定义非常重要，因为并不是每个 stage 都会消费完整的 `Execution Context`。

例如：

- `Task Interpretation` 主要使用 query、session continuity 与基础 project context
- `Research Executor` 主要使用 task framing、selected memory、research knowledge、tool capabilities 与 budgets
- `Conclusion Generator` 主要使用 evidence summary、intermediate findings、constraints 与 selected project context

因此，本设计采用如下关系：

- `Execution Context` 是当前 run 的**完整执行环境**
- `Stage Input` 是某个 stage 实际消费的**上下文视图 / 投影**

这意味着：

- 不同 stage 的 `Stage Input` 可以不同
- 但它们都来源于同一个不断演化的 `Execution Context`

通过显式引入 `Stage Input` 这个概念，可以避免把“全局执行环境”和“阶段实际输入”混为一谈。

---

### 2.7 Session Short-term Memory

`Session Short-term Memory` 指的是在同一个 thread / session 内，为支持多轮连续性而保留的短期记忆层。

其主要目标是：

- 支持 follow-up turn 的自然衔接
- 减少用户重复描述刚刚已经明确的局部背景
- 保留当前 session 的主线工作状态

典型内容包括：

- recent turn memory
- session working summary
- latest recommendation
- latest action items
- active task framing
- open questions

`Session Short-term Memory` 的特点是：

- thread / session scoped
- 生命周期短于 long-term memory，长于 request-time state
- 服务的是会话连续性，而不是 durable cross-session reuse
- 应保持轻量，而不是演变为完整对话归档

因此，session short-term memory 是一种独立的 memory layer，不应与 long-term memory 混用。

---

### 2.8 Long-term Memory

`Long-term Memory` 指的是跨 session 持久存在、且未来可能继续被复用的信息资产总层。

对于本系统而言，long-term memory 的主分类应优先按**功能角色**理解，而不是仅按底层实现方式划分。

其主要类型包括：

- Project Profile Memory
- Decision Memory
- Action / Execution Memory
- Research Knowledge Memory
- Preference / Policy Memory
- Tracking / Watchlist Memory（optional）

这些类型的共同特点是：

- durable
- reusable
- cross-session
- likely useful in future runs

因此，`Long-term Memory` 是一个**语义层总称**。

在实现层，它们可以进一步映射到不同的 storage / retrieval pattern，但这种实现映射不应替代其主语义分类。

---

### 2.9 Structured Long-term Memory

`Structured Long-term Memory` 指的是 long-term memory 在实现层的一种访问 / 存储分组。

它通常用于承载那些更适合：

- metadata filtering
- exact or scoped lookup
- structured update / lifecycle management

的信息类型。

在本系统中，以下 memory 类型通常会映射到 structured long-term memory：

- Project Profile Memory
- Decision Memory
- Action / Execution Memory
- Preference / Policy Memory
- Tracking / Watchlist Memory

需要强调的是：

`Structured Long-term Memory` 是一种**实现分组**，而不是 long-term memory 的主语义分类。

---

### 2.10 Retrieval-oriented Knowledge

`Retrieval-oriented Knowledge` 指的是 long-term memory 在实现层的另一种访问 / 存储分组。

它通常用于承载那些更适合：

- semantic retrieval
- hybrid retrieval
- retrieval-driven reuse

的知识型内容。

在本系统中，`Research Knowledge Memory` 通常会映射到这一层。

典型内容包括：

- paper summaries
- method notes
- topic summaries
- framework / tooling notes
- source-specific research artifacts

同样需要强调的是：

`Retrieval-oriented Knowledge` 是一种**实现分组**，而不是 long-term memory 的主语义分类。

---

### 2.11 Storage Layer

`Storage Layer` 指的是承载上述 state / memory / knowledge 的**逻辑或物理存储层**。

需要强调的是：

**Storage 不等于 Memory。**

- `Memory` 是信息资产的语义概念
- `Storage` 是这些信息资产的承载方式

例如：

- session continuity 是一种 memory 语义
- session store 是它的 storage layer
- decision memory 是一种 durable memory 语义
- structured long-term memory store 是它的 storage layer

因此，在本设计中：

- memory type
- access pattern
- storage mapping

被视为三个相关但不同的维度。

---

### 2.12 Relationship Among State, Context, Memory, and Storage

为了避免后续章节再次出现概念混淆，本设计明确采用以下关系定义：

- **Storage stores memory**
- **Memory is a reusable information asset**
- **Running State is the canonical mutable state of the current request**
- **Execution Context is the full execution environment of the current run**
- **Stage Input is a stage-specific projection of the execution context**

从运行时视角看，这些概念的关系可以概括为：

1. `Context Sources` 提供候选上下文来源
2. 系统通过 `Context Construction` 对这些来源进行加载、筛选、整形
3. 被选中的外部上下文会分流成两部分：
    - 一部分被吸收到 `Running State` 中
    - 一部分保留为 `Supplemental Context`
4. `Running State`、`Supplemental Context` 与 `Runtime Metadata / Capabilities` 共同构成当前 run 的 `Execution Context`
5. 不同 stage 从 `Execution Context` 中读取各自所需的 `Stage Input`

从长期信息资产视角看：

- `Session Short-term Memory` 服务会话连续性
- `Long-term Memory` 服务跨 session durable reuse
- `Structured Long-term Memory` 与 `Retrieval-oriented Knowledge` 是 long-term memory 在实现层的两种主要映射方式
- `Storage Layer` 则负责承载这些 memory 及其相关数据对象

这一定义将作为后续 `Memory Model`、`Context Construction and Loading`、`Memory Access, Persistence, and Lifecycle Policies` 与 `Storage Design` 各章的共同基础。

# 3. Memory Model

## 3.1 Memory Design Goals

本系统的 memory 设计目标，不是尽可能保留所有历史信息，而是围绕 **research、recommendation 和 action continuity**，保留高价值、可复用、低噪声的信息资产。

对本系统而言，memory 的主要作用包括：

- 支持同一 session 内的 follow-up continuity
- 支持跨 session 的项目连续性
- 保留可复用的研究结论、决策理由和行动状态
- 减少重复分析与重复规划
- 提升 recommendation 的项目相关性
- 避免 memory pollution 和 context inflation

因此，本系统采用以下总体原则：

- **memory quality over memory quantity**
- **reuse value over raw preservation**

---

## 3.2 Memory Design Principles

本系统的 memory design 遵循以下原则：

1. **Memory is for reuse, not for raw logging**
memory 用于未来复用，而不是保存 raw logs、raw traces 或完整对话归档。
2. **Short-term continuity and long-term reuse should be separated**
session 内连续性与跨 session 复用应明确分离。
3. **Long-term memory should be organized by functional role**
long-term memory 应优先按功能角色划分，而不是仅按底层实现方式划分。
4. **Memory quality is more important than memory quantity**
只有 durable、reusable、project-relevant 的信息才值得进入 memory。
5. **Memory should serve research, recommendation, and action continuity**
memory 的价值应直接体现在后续 research、recommendation 和项目推进中。

---

## 3.3 Session Short-term Memory

`Session Short-term Memory` 用于在同一个 thread / session 内维持短期连续性。

### 3.3.1 Purpose

其主要目的是：

- 延续当前 session 的工作主线
- 减少用户重复解释刚刚已明确的信息
- 保留最近形成的结论与下一步方向

### 3.3.2 Typical Contents

通常包括：

- recent turn memory
- session working summary
- latest recommendation / latest conclusion
- latest action items
- active task framing
- open questions

### 3.3.3 Boundaries

不应默认保存：

- 完整聊天记录
- raw tool outputs
- 长 reasoning trace
- cross-session durable information

---

## 3.4 Long-term Memory Overview

`Long-term Memory` 用于保存跨 session 的 durable information assets。

本系统的 long-term memory 主分类按**功能角色**划分，主要包括：

- Project Profile Memory
- Decision Memory
- Action / Execution Memory
- Research Knowledge Memory
- Preference / Policy Memory
- Tracking / Watchlist Memory（optional）

这种划分方式更适合本系统，因为它能够直接反映这些 memory 在 future runs 中的复用价值。

---

## 3.5 Project Profile Memory

`Project Profile Memory` 用于保存项目级的稳定背景信息。

### 3.5.1 Purpose

其主要目的是：

- 保留项目的稳定背景
- 支持跨 session 的项目理解
- 提升 recommendation 的项目针对性

### 3.5.2 Typical Contents

通常包括：

- project stage
- long-lived constraints
- project background
- current bottlenecks
- current priorities
- major assumptions

### 3.5.3 Boundaries

不应默认保存：

- 短期临时推测
- 一次性局部讨论结论
- session-local ephemeral context

---

## 3.6 Decision Memory

`Decision Memory` 用于保存历史决策及其理由。

### 3.6.1 Purpose

其主要目的是：

- 保留历史判断及 rationale
- 提升后续 recommendation 的一致性
- 避免对已收敛问题反复重判

### 3.6.2 Typical Contents

通常包括：

- decision statement
- rationale
- selected option
- rejected alternatives
- decision context
- confidence / status

### 3.6.3 Boundaries

不应默认保存：

- 未收敛的临时判断
- 低置信度结论
- 无明确 rationale 的模糊偏好

---

## 3.7 Action / Execution Memory

`Action / Execution Memory` 用于保存跨 session 仍有价值的行动连续性信息。

### 3.7.1 Purpose

其主要目的是：

- 保留项目推进状态
- 支持跨 session 的 action continuity
- 减少重复规划

### 3.7.2 Typical Contents

通常包括：

- pending action items
- persistent next steps
- meaningful progress records
- previously attempted actions or outcomes
- roadmap-relevant execution notes

### 3.7.3 Boundaries

不应默认保存：

- 所有微观执行细节
- 每一次 tool invocation
- 低价值一次性动作
- 原始执行日志

---

## 3.8 Research Knowledge Memory

`Research Knowledge Memory` 用于保存可复用的研究知识。

### 3.8.1 Purpose

其主要目的是：

- 保留可复用 research takeaways
- 支持 future research-stage recall
- 减少重复知识整理

### 3.8.2 Typical Contents

通常包括：

- paper summaries
- method notes
- topic summaries
- framework / tooling notes
- source-specific research artifacts

### 3.8.3 Characteristics

其特点通常包括：

- 更偏文本或半结构化内容
- 更适合 retrieval-oriented access
- 更依赖 semantic / hybrid recall

### 3.8.4 Boundaries

不应承担：

- project current status storage
- stable decision record storage
- session continuity storage

---

## 3.9 Preference / Policy Memory

`Preference / Policy Memory` 用于保存相对稳定的偏好与规则。

### 3.9.1 Purpose

其主要目的是：

- 保留长期有效的偏好或规则
- 减少相同偏好与约束的重复表达

### 3.9.2 Typical Contents

通常包括：

- stable output preference
- persistent formatting preference
- reusable operating policy
- long-lived execution preference

### 3.9.3 Boundaries

不应默认保存：

- 一次性临时偏好
- 当前 turn 特有要求
- 短期噪声型 instructions

---

## 3.10 Tracking / Watchlist Memory (Optional)

`Tracking / Watchlist Memory` 用于承载未来长期跟踪需求。

### 3.10.1 Purpose

其主要目的是：

- 支持 future tracking workflows
- 保留长期关注的 topic / repo / paper / source

### 3.10.2 Typical Contents

通常包括：

- tracked topics
- tracked repos
- tracked papers
- tracked frameworks
- tracked sources

### 3.10.3 Current Status

当前版本中，该类 memory 为 optional extension，而非 MVP 核心依赖。

---

## 3.11 Implementation-oriented Mapping of Long-term Memory

虽然 long-term memory 的主分类按功能角色定义，但在实现层仍需映射到不同的 access / storage pattern。

### 3.11.1 Structured Long-term Memory

通常承载：

- Project Profile Memory
- Decision Memory
- Action / Execution Memory
- Preference / Policy Memory
- Tracking / Watchlist Memory

这类 memory 更适合：

- metadata filtering
- exact or scoped lookup
- 结构化更新与生命周期管理

### 3.11.2 Retrieval-oriented Knowledge

通常承载：

- Research Knowledge Memory

这类 memory 更适合：

- semantic / hybrid retrieval
- retrieval-oriented access

因此：

**功能角色分类定义 memory 的语义角色，structured / retrieval-oriented 划分定义其实现和访问方式。**

---

## 3.12 Memory Type Comparison

本系统中的 memory 可从以下维度进行比较：

- **Session vs Long-term**
session short-term memory 服务当前 session continuity；long-term memory 服务 cross-session reuse。
- **Project / Decision / Action / Research / Policy Memory**
各类 memory 的区别主要体现在其 future reuse role、访问模式和更新方式。
- **Structured vs Retrieval-oriented Mapping**
前者更像“查记录”，后者更像“搜知识”。

---

## 3.13 Memory Candidate and Persistence Boundaries

本系统不将所有“可能有用”的信息都写入 memory。

memory write-back 应遵循明确的 candidate criteria 和 exclusion rules。

### 3.13.1 What Qualifies as a Memory Candidate

通常应满足以下至少一项：

- durable
- reusable
- project-relevant
- decision-relevant
- likely useful in future runs

### 3.13.2 What Should Not Be Persisted by Default

以下内容不应默认持久化为 memory：

- raw execution traces
- full conversation dump
- raw tool payloads
- low-value transient artifacts
- low-confidence weak conclusions

### 3.13.3 Memory Quality Over Memory Quantity

本系统明确采用：

**memory quality over memory quantity**

作为长期原则。

与其保留大量噪声 memory，不如保留少量高价值、未来真正可复用的 memory。

# 4. Context Construction and Loading

## 4.1 Context Design Goals

本章的目标，是定义系统如何在单次 request lifecycle 内，为当前任务构造一个**真正有助于问题求解的执行上下文**。

对于本系统而言，好的 context 设计不应追求“尽可能加载更多信息”，而应围绕以下四个核心问题展开：

- 当前任务真正需要、且在当前情境下仍然有效的信息是什么
- 这些信息应以什么粒度进入当前 run
- 这些信息应在什么时机进入当前 run
- 不同 stage 应如何使用这些信息

基于上述四个问题，本系统的 context design 应满足以下四项要求。

### 1. Relevance

当前 run 中被纳入上下文的信息，应首先与当前任务相关，并且在当前情境下仍然有效。

context construction 应主要受以下因素驱动：

- `task_type`
- `user_goal`
- `task_framing`
- 当前任务的显式 `constraints`

这意味着，系统不应默认注入所有可获得的 memory、knowledge 或历史信息，而应优先保留那些能够直接支持当前问题求解、且在当前项目阶段或当前任务条件下仍然适用的信息。

换句话说，context 设计的第一要求不是“尽可能全面”，而是：

**只加载当前任务真正需要、且仍然适用的上下文。**

### 2. Boundedness

即使某些信息与当前任务相关，也不代表它们都应以完整、原始、无压缩的形式进入当前 run。

因此，Execution Context 应保持受控和轻量，context design 需要同时决定：

- 哪些信息值得进入当前 run
- 这些信息应以何种粒度进入当前 run
- 哪些信息应被压缩、摘要或舍弃

boundedness 的目标包括：

- 控制上下文规模
- 避免低价值细节和重复信息稀释重点
- 避免 raw memory、raw outputs 或长文本直接堆叠
- 保持 execution context 可解释、可管理

因此，本系统不把“更多上下文”视为默认更优，而强调：

**上下文应以受控粒度进入当前 run。**

### 3. Incremental Construction

context 不应被视为 request 开始时一次性固定完成的对象。

由于本系统包含 task interpretation、planning、research execution 和 intermediate findings accumulation 等阶段，系统对上下文的需求会随着执行过程而变化。

因此，context construction 应支持渐进式构造：

- request start 时先建立基础上下文
- research execution 中按需补充支持性 context
- intermediate findings 出现后，对当前上下文进行刷新、收窄或增强

这意味着，系统不应在请求开始时过度加载所有可能相关的信息，而应根据执行过程逐步构造当前 run 所需的上下文。

因此，context design 的第三要求是：

**上下文应按需、分阶段、渐进式构造。**

### 4. Stage-aware Usage

即使 execution context 已经构造完成，不同 stage 也不应无差别地消费同一份完整上下文。

不同 stage 的职责不同，因此它们所需的输入也应不同。

例如：

- `Task Interpretation` 更关注 query、session continuity 和基础 project context
- `Research Executor` 更关注 task framing、selected memory、supporting knowledge 和 runtime capabilities
- `Conclusion Generator` 更关注 evidence summary、intermediate findings、constraints 和 selected supporting context

因此，系统应基于同一个 `Execution Context`，为不同 stage 投影出各自所需的 `Stage Input`，而不是让所有 stage 共用同一份“大而全”的上下文。

这意味着，context design 的第四要求是：

**上下文应在使用阶段体现 stage-aware projection。**

基于上述四项要求，本系统明确采用以下原则：

**Execution Context should be constructed, not dumped.**

也就是说，Execution Context 不应是 memory、history 和 knowledge 的简单堆叠结果，而应是围绕当前任务、当前执行阶段和当前运行边界，经过选择、压缩和整形后形成的受控执行环境。

## 4.2 Context Sources

`Context Sources` 指当前 run 中可被系统用于构造上下文的信息来源。

这些来源共同构成当前请求的上下文候选池，但并不意味着其全部内容都会进入最终的 `Execution Context`。系统仍需根据当前任务、当前阶段和上下文预算，对其进行选择、整形和注入。

本系统中的主要 context sources 包括：

### 4.2.1 User Query

用户当前输入的原始问题，是 context construction 的起点，也是 task interpretation 和后续 relevance 判断的主要依据。

### 4.2.2 Task Interpretation Outputs

Task Interpretation 产出的结构化结果，包括：

- `task_type`
- `user_goal`
- `task_framing`
- `constraints`

这些信息比原始 query 更适合作为 context loading 和 selection policy 的直接输入。

### 4.2.3 Session Short-term Memory

提供当前 session 的短期连续性信息，帮助系统理解当前主线、最近结论、已形成的 action items 以及 open questions。

### 4.2.4 Structured Long-term Memory

提供跨 session 的结构化 durable memory，主要包括：

- project profile memory
- decision memory
- action / execution memory
- preference / policy memory
- tracking / watchlist memory（如适用）

这类内容通常通过 scoped lookup 或 metadata filtering 被选择性加载，用于补充当前任务的项目背景、历史决策和行动连续性。

### 4.2.5 Research Knowledge Memory

提供系统内部已持久化的研究知识，例如：

- paper summaries
- method notes
- topic summaries
- framework / tooling notes
- source-specific research artifacts

这类内容主要用于支持后续 research stage 中的知识 recall 和背景补充。

### 4.2.6 Tool-acquired External Context

当前 run 中，系统还可以通过 tools 动态获取外部信息，例如 papers、repositories、documents、web sources 或其他外部 knowledge sources。

这类信息通常在 research stage 中按需引入，用于补充当前 memory 无法提供的 supporting evidence。它们默认属于当前 run 的外部上下文，而不直接等同于 memory，除非后续被提炼并持久化。

### 4.2.7 Current-run Intermediate Outputs

当前 run 内已产生的中间结果，例如：

- plan
- sub-questions
- intermediate findings
- evidence summary

这些内容会随着执行过程不断更新，并进一步影响后续阶段的 context shaping。

### 4.2.8 Runtime Metadata and Capabilities

包括当前 run 的运行时约束与能力信息，例如：

- tool registry
- latency / iteration budget
- scope restrictions

它们不属于业务 memory，但会影响 execution context 的构造与使用，因此也属于 context sources 的一部分。

## 4.3 Context Loading Flow

本系统中的 context construction 是一个分阶段、渐进式的过程。

系统不会在 request 开始时一次性加载全部上下文，而是随着任务理解、project grounding、research progression 和 intermediate findings 的形成，逐步补充、调整和收窄当前 run 的上下文。

被选中的外部 context 在进入当前 run 后，通常有两种去向：

- 一部分被提炼并吸收到 `RunningState` 中，成为当前 run 的核心工作状态
- 一部分保留为 `SupplementalContext`，作为 supporting context 供后续 stage 使用

### 4.3.1 Base Context Initialization

**Primary stages involved:**

- Request Intake
- Task Interpretation

在 request 开始时，系统先建立当前 run 的最小任务框架。

这一阶段主要基于：

- user query
- minimal runtime metadata / capabilities
- session short-term memory（仅在明显依赖最近会话主线时）

主要产出包括：

- `task_type`
- `user_goal`
- `task_framing`
- `constraints`

这些内容写入 `RunningState`，作为后续 context loading 的依据。

### 4.3.2 Session and Project Context Loading

**Primary stages involved:**

- Context and Memory Loader
- Planning and Decomposition

在形成初步任务理解后，系统补充当前 run 所需的 continuity 和 project grounding。

这一阶段通常读取：

- session short-term memory
- structured long-term memory
    - project profile memory
    - decision memory
    - action / execution memory
    - preference / policy memory（如适用）

在读取 project profile memory 之前，系统通常先完成 **project scope resolution**，再通过 **project-scoped structured lookup** 读取相关 structured memory。

这一阶段会：

- 将高价值摘要信息吸收到 `RunningState`
- 将 supporting records 保留为 `SupplementalContext`

通常进入 `RunningState` 的内容包括：

- `project_context_summary`
- `current_bottleneck_summary`
- `active_decision_summary`
- `current_action_status`

### 4.3.3 Context Augmentation During Research

**Primary stages involved:**

- Research Executor
- Tool Execution Layer

在 research progression 过程中，系统根据 evidence gap 按需补充新的 context。

新增 context 可以来自：

- 系统已有 memory
    - additional structured long-term memory
    - research knowledge memory
- tools 动态获取的外部信息
    - retrieval results
    - external documents
    - papers / repositories / web sources 等

这一阶段通常会：

- 识别 information gap
- 按需加载补充信息
- 对新增内容做 relevance、scope、freshness 和 redundancy control
- 决定其进入 `RunningState`、`SupplementalContext`，或仅作为临时 supporting material 使用

这一阶段的核心特点是：

**context augmentation 由实际 research need 驱动，而不是预先全量加载。**

### 4.3.4 Context Refresh and Narrowing Before Conclusion Generation

**Primary stages involved:**

- Research Executor（later iterations）
- Conclusion Generator（preparation stage）

随着 intermediate findings 和 evidence summary 的形成，系统会在进入 `ConclusionGenerator` 之前，对当前 context 做刷新和收窄。

这一阶段通常会：

- 移除或降权不再关键的 supporting context
- 对较长的上下文进一步压缩
- 将后续结论生成所需的上下文聚焦到：
    - 当前最相关的 findings
    - 当前最关键的 evidence
    - 当前仍有效的 constraints
    - 少量必要的 project / decision / action context

其作用是让 context 从探索模式转入收敛模式。

### 4.3.5 Stage Input Projection

**Primary stages involved:**

- All downstream stages

在 `ExecutionContext` 已构造完成或更新后，不同 stage 不会消费同一份完整上下文。

系统应基于当前 `ExecutionContext`，为不同 stage 投影出各自所需的 `StageInput`。

例如：

- `Planning and Decomposition` 主要消费 task framing、project grounding、active decisions 和 constraints
- `Research Executor` 主要消费 selected memory、supporting knowledge、tool capabilities 和 current findings
- `ConclusionGenerator` 主要消费 evidence summary、intermediate findings、constraints 和少量必要 supporting context

### 4.3.6 Summary

本系统中的 context 会随着任务理解、project grounding、research progression 和 intermediate findings 逐步演化。

其最终目标，是为当前 run 构造一个：

- relevant
- bounded
- incrementally built
- stage-aware

的 `ExecutionContext`。

## 4.4 Context Selection and Shaping Policy

本节定义系统如何将**可获得的上下文**转化为**可执行的上下文**。

其目标不是最大化上下文覆盖，而是为当前 run 保留真正有用、仍然适用、且便于执行的信息。

因此，本系统采用如下原则：

**Execution Context should be shaped for use, not assembled for completeness.**

### 4.4.1 Selection Criteria

在多个 context sources 同时可用的情况下，系统首先需要判断哪些内容值得进入当前 run。

selection 主要基于以下标准：

- **Relevance Filtering**
优先保留与当前 `task_type`、`user_goal`、`task_framing`、`constraints` 以及当前阶段直接相关的上下文。
- **Scope Filtering**
控制上下文的适用范围，避免将错误 user、session 或 project 的 memory 注入当前 run。
- **Freshness Filtering**
优先保留当前仍然有效的信息，避免 stale context 干扰当前 recommendation 或 research。

### 4.4.2 Shaping Operations

完成 selection 后，系统还需要决定这些信息应以什么形式进入当前 run。

- **Cross-source Redundancy Control**
避免 session memory、structured long-term memory、research knowledge 和当前 run 中间结果之间的重复堆叠。
- **Compression and Summarization**
对较长或较散的信息进行压缩和摘要，以控制 context budget 并提高可消费性。
- **Placement into Running State or Supplemental Context**
被选中的上下文不应被一视同仁地处理。
其中：
    - 对当前 run 已成为核心工作变量的信息，应提炼后吸收到 `Running State`
    - 对当前 run 有帮助但不需要成为核心状态字段的信息，应保留为 `Supplemental Context`
    - 仅对当前局部 reasoning 有帮助的信息，可作为临时 supporting material 使用

### 4.4.3 Budget and Priority Ordering

即使在完成 filtering 和 shaping 之后，系统仍可能面临上下文预算有限的问题。

因此，系统需要在最终注入 `Execution Context` 前，对候选上下文进行优先级排序。

priority ordering 通常应受以下因素影响：

- 当前 `task_type`
- 当前 `task_framing`
- 当前 stage
- 当前任务是否更强调 project grounding、knowledge recall 或 action continuity
- 当前 evidence 是否充分

对于 project-specific recommendation 或 action-planning 场景，一个常见的默认优先级通常是：

1. 当前任务框架与显式约束
2. active project grounding
3. active decisions
4. active action continuity
5. directly relevant research knowledge
6. 低优先级 supporting context

其核心目标是：在上下文预算有限时，优先保留最能影响当前 run 结果质量的内容。

### 4.4.4 Result of Context Selection and Shaping

经过 selection and shaping 后，系统最终得到的不是“候选上下文的堆叠结果”，而是一组经过控制和整理的上下文结果。

这些结果会以不同形式进入当前 run：

- 一部分被吸收到 `Running State`
- 一部分保留为 `Supplemental Context`
- 一部分仅作为临时 supporting material 使用
- 其余内容则被丢弃，不进入当前 `Execution Context`

因此，`Context Selection and Shaping Policy` 的本质，是定义系统如何将：

**available context**

转化为

**usable context**

从而确保当前 run 使用的 `Execution Context` 既有足够支持，又保持受控、聚焦和可执行。

## 4.5 Execution Context and Stage Input Representation

本节定义当前 run 的核心运行时对象，以及这些对象在不同 stage 中的使用方式。其目标不是重复解释抽象概念，而是给出足够清晰的运行时表示，使后续编码时可以直接据此定义数据模型、对象边界和 stage input projection 逻辑。

本设计中，运行时上下文表示由四个核心对象组成：

- `RunningState`
- `SupplementalContext`
- `ExecutionContext`
- `StageInput`

其中：

- `RunningState` 承载当前 run 的核心工作变量
- `SupplementalContext` 承载当前 run 中仍可访问的 supporting context
- `ExecutionContext` 是当前 run 的完整执行环境
- `StageInput` 是某个 stage 从 `ExecutionContext` 中获得的输入视图

---

### 4.5.1 Design Objective

本节需要解决以下四个问题：

1. 当前 run 中，哪些信息应作为核心工作状态被持续读写
2. 哪些信息应作为 supporting context 被保留，但不进入核心状态
3. 当前 run 的完整执行环境应如何表示
4. 不同 stage 应如何从统一执行环境中获取各自所需输入

因此，本节输出的不是概念说明，而是一套明确的运行时表示约定，供后续实现直接采用。

---

### 4.5.2 Running State

`RunningState` 是当前 request 的 canonical mutable state。

它是整个 run 中唯一的核心工作状态对象，所有会在多个 stage 中持续使用、更新或覆盖的核心变量，都应进入该对象。

### 4.5.2.1 Inclusion Rule

一条信息应进入 `RunningState`，通常需要同时满足以下至少两项：

- 已成为当前 run 的核心工作变量
- 会在多个后续 stage 中继续使用
- 需要被后续 stage 更新、覆盖或补充
- 适合被提炼成结构化、稳定字段，而不是保留为原始 supporting material

如果某条信息只是“有帮助”，但并不构成当前 run 的核心工作变量，则不应直接进入 `RunningState`，而应保留为 `SupplementalContext`。

### 4.5.2.2 Recommended Field Set

建议 `RunningState` 至少包含以下字段：

**Request framing fields**

- `request_id: str`
当前 run 的唯一标识。
- `original_query: str`
用户原始输入。
- `task_type: str | None`
例如：`topic_exploration` / `comparison` / `recommendation` / `action_planning`
- `user_goal: str | None`
当前请求试图达成的目标。
- `task_framing: str | None`
当前问题的高层处理框架，例如：`project_specific_recommendation`、`engineering_tradeoff_comparison`
- `constraints: list[str]`
当前请求中的显式约束。

**Project grounding fields**

- `project_scope_id: str | None`
当前解析出的 project scope；如果未解析出则为空。
- `project_context_summary: str | None`
当前项目背景的提炼摘要。
- `current_bottleneck_summary: str | None`
当前阶段最关键 bottleneck 的提炼摘要。
- `active_decision_summary: str | None`
当前仍然有效、会影响本次 run 的关键决策摘要。
- `current_action_status: str | None`
当前项目推进状态的提炼摘要。

**Planning fields**

- `plan: list[str]`
当前 run 的执行计划，允许为空。
- `sub_questions: list[str]`
当前 run 拆出的子问题集合。
- `comparison_candidates: list[str]`
当前比较任务中的候选对象集合。
- `information_gaps: list[str]`
当前已识别但尚未补齐的信息缺口。

**Research and reasoning fields**

- `retrieved_evidence_refs: list[str]`
当前 run 已采纳 evidence 的引用标识集合。这里只放引用，不放大段原文。
- `evidence_summary: str | None`
当前 run 已形成的 evidence 层摘要。
- `intermediate_findings: list[str]`
中间结论或中间判断集合。
- `open_questions: list[str]`
当前 run 仍未解决的问题集合。

**Output fields**

- `final_recommendation: str | None`
- `action_items: list[str]`
- `confidence: str | None`
例如：`low` / `medium` / `high`

### 4.5.2.3 Update Rule

`RunningState` 是**会被多个 stage 持续更新**的对象，因此每个字段需要明确更新方式：

- `task_type`, `user_goal`, `task_framing`, `project_scope_id`
通常为单次赋值后少量修正，不应频繁覆盖。
- `project_context_summary`, `current_bottleneck_summary`, `active_decision_summary`, `current_action_status`
允许在 context refresh 后被更新，但应保持摘要级，不应退化成原始记录堆叠。
- `plan`, `sub_questions`, `comparison_candidates`, `information_gaps`
允许在 planning 和 research 过程中增删或重排。
- `retrieved_evidence_refs`, `intermediate_findings`, `open_questions`
允许逐步追加与重整。
- `final_recommendation`, `action_items`, `confidence`
只在结论收敛后写入最终值。

### 4.5.2.4 Exclusion Rule

以下信息**不应默认进入 `RunningState`**：

- full conversation dump
- raw tool payloads
- full decision record 原文
- full research note 原文
- external document 全文
- 局部一次性 supporting snippet
- 低置信度、尚未收敛的临时推测文本

这些内容即使有帮助，也应优先保留为 `SupplementalContext`，而不是污染核心工作状态。

---

### 4.5.3 Supplemental Context

`SupplementalContext` 指当前 run 中已被选择、但未被吸收到 `RunningState` 中的 supporting context。

它仍属于当前 `ExecutionContext` 的一部分，但不作为核心工作变量存在。

### 4.5.3.1 Inclusion Rule

一条信息适合进入 `SupplementalContext`，通常满足以下条件：

- 对当前 run 有帮助，但不是核心状态字段
- 可能只在部分 stage 中被使用
- 更适合作为 supporting material 被引用
- 不需要在多个 stage 中被频繁改写

### 4.5.3.2 Recommended Structure

建议 `SupplementalContext` 按来源和用途拆成明确分区，而不是用一个无结构的大列表。建议至少包含：

- `session_support: list[ContextItem]`
- `project_support: list[ContextItem]`
- `decision_support: list[ContextItem]`
- `action_support: list[ContextItem]`
- `research_support: list[ContextItem]`
- `external_evidence_support: list[ContextItem]`

其中 `ContextItem` 建议具有以下字段：

- `id: str`
- `source_type: str`
例如：`session_memory` / `project_profile` / `decision_memory` / `research_memory` / `tool_result`
- `scope_id: str | None`
- `summary: str`
必须是可直接消费的摘要，不应默认存大段原文
- `priority: int`
- `freshness_tag: str | None`
- `confidence: str | None`
- `can_assimilate_to_state: bool`
- `usage_hint: str | None`
例如：`planning_only` / `research_support` / `conclusion_support`

### 4.5.3.3 Operational Rule

`SupplementalContext` 不是“凡是没进 state 的都扔进来”的缓冲区。

它也必须满足以下约束：

- 总量应受 budget 控制
- 默认只保留摘要级表示
- 同类信息应优先保留高优先级版本
- 明显重复或已失效内容应被移除
- 仅局部有用的信息不应长期停留

### 4.5.3.4 Example Placement

以下信息通常更适合保留在 `SupplementalContext`：

- supporting decision record 的摘要
- supporting research snippet
- selected external evidence snippet
- session working summary
- 某个 project profile 的补充说明片段

---

### 4.5.4 Execution Context

`ExecutionContext` 表示当前 run 的完整执行环境。

它是后续 stage input projection 的统一上位对象。

### 4.5.4.1 Composition

`ExecutionContext` 应由以下三部分组成：

- `running_state: RunningState`
- `supplemental_context: SupplementalContext`
- `runtime_context: RuntimeContext`

其中 `RuntimeContext` 建议至少包含：

- `available_tools: list[str]`
- `tool_registry_version: str | None`
- `latency_budget_ms: int | None`
- `iteration_budget: int | None`
- `scope_restrictions: list[str]`
- `environment_flags: list[str]`

### 4.5.4.2 Representation Rule

在实现上，`ExecutionContext` 可以是：

- 一个显式运行时对象
- 或多个对象的聚合视图

但在 LLD 层面，必须把它视为统一概念，否则后续无法清晰描述：

- 当前 run 真实可用的信息边界
- stage input projection 的来源
- context refresh 的对象范围

### 4.5.4.3 Invariant

`ExecutionContext` 必须满足以下不变量：

- `running_state` 始终存在
- `supplemental_context` 可以为空，但必须有明确结构
- `runtime_context` 始终存在，即使字段部分为空
- stage 不应绕过 `ExecutionContext` 私自拼接额外输入
- 所有 stage input 都应视为从 `ExecutionContext` 投影得到

---

### 4.5.5 Assimilation vs Retention

在 context construction 之后，被选中的外部 context 不应被一视同仁处理。

系统必须明确区分：

- 哪些应被**吸收到 `RunningState`**
- 哪些应被**保留为 `SupplementalContext`**

### 4.5.5.1 Assimilation into Running State

适合吸收到 `RunningState` 的典型信息：

- `project_context_summary`
- `current_bottleneck_summary`
- `active_decision_summary`
- `current_action_status`
- 高层 evidence summary
- 已经稳定的 intermediate finding

这类信息已经被提炼成当前 run 的核心工作变量，后续多个 stage 都会持续使用。

### 4.5.5.2 Retention as Supplemental Context

适合保留在 `SupplementalContext` 的典型信息：

- supporting decision record
- supporting action record
- supporting research snippet
- external evidence snippet
- session working summary

这类信息当前仍然有价值，但没有必要占用 `RunningState` 的核心字段。

### 4.5.5.3 Decision Rule

可以采用下面的判定规则：

若某条信息满足以下任一条件，应优先考虑 Assimilation：

- 已经成为当前 run 的核心判断依据
- 会在多个后续 stage 中反复使用
- 可以被稳定地提炼成摘要化字段
- 后续 stage 需要对其继续更新

否则，优先考虑 Retention。

---

### 4.5.6 Stage Input

`StageInput` 是某个 stage 实际消费的输入子集。

它来自当前 `ExecutionContext`，但不等于完整执行环境。

### 4.5.6.1 Why Stage Input Must Be Explicit

如果不显式定义 `StageInput`，会出现两个问题：

1. 所有 stage 看起来都在消费同一份“大而全”的上下文
2. `ExecutionContext` 与 stage 实际输入边界不清晰，难以编码和调试

因此，系统必须显式支持 stage-specific projection。

### 4.5.6.2 Recommended Projection Rule

建议每个 stage 的 `StageInput` 都显式声明：

- 从 `RunningState` 读取哪些字段
- 从 `SupplementalContext` 读取哪些分区
- 是否可访问 `RuntimeContext`
- 是否允许读取全部 supporting items，或只读取高优先级子集

### 4.5.6.3 Stage Input by Stage

**Task Interpretation**

- from `RunningState`:
    - `original_query`
- from `SupplementalContext`:
    - 少量 `session_support`
- from `RuntimeContext`:
    - minimal runtime constraints

**Planning and Decomposition**

- from `RunningState`:
    - `task_type`
    - `user_goal`
    - `task_framing`
    - `constraints`
    - `project_scope_id`
    - `project_context_summary`
    - `active_decision_summary`
    - `current_action_status`
- from `SupplementalContext`:
    - high-priority `session_support`
    - high-priority `project_support`
    - selected `decision_support`
- from `RuntimeContext`:
    - budget fields

**Research Executor**

- from `RunningState`:
    - `task_type`
    - `user_goal`
    - `task_framing`
    - `constraints`
    - `plan`
    - `sub_questions`
    - `comparison_candidates`
    - `information_gaps`
    - `evidence_summary`
    - `intermediate_findings`
- from `SupplementalContext`:
    - selected `research_support`
    - selected `external_evidence_support`
    - supporting `decision_support` / `action_support` if relevant
- from `RuntimeContext`:
    - full tool availability
    - iteration budget

**Conclusion Generator**

- from `RunningState`:
    - `task_framing`
    - `constraints`
    - `evidence_summary`
    - `intermediate_findings`
    - `confidence`
- from `SupplementalContext`:
    - 少量高优先级 `project_support`
    - 少量高优先级 `decision_support`
    - 必要的 `external_evidence_support`
- from `RuntimeContext`:
    - typically minimal

### 4.5.6.4 Projection Constraint

`StageInput` 必须满足以下约束：

- 只包含该 stage 真正需要的字段
- 不应原样透传整个 `SupplementalContext`
- 不应默认透传全部 external evidence
- 应优先使用已摘要化、已排序的 supporting items
- 应尽量避免将 stage input 退化为“大而全的完整 context dump”

---

### 4.5.7 Minimal Coding Guidance

为方便后续编码，建议按以下顺序实现对象模型：

1. 先定义 `RunningState`
2. 再定义 `ContextItem` 和 `SupplementalContext`
3. 再定义 `RuntimeContext`
4. 最后定义 `ExecutionContext`
5. 为每个 stage 定义显式的 `build_stage_input(execution_context)` 逻辑，而不是让 stage 自己随意读全量对象

建议要求：

- `RunningState` 字段名固定、语义稳定
- `SupplementalContext` 必须分区，不允许无结构大列表
- `ContextItem.summary` 必须是可直接消费文本
- `StageInput` 构造逻辑必须显式、可测试、可 debug

---

### 4.5.8 Representation Summary

综上，本系统中的运行时表示应遵循以下结构：

- `RunningState`
当前 run 的核心工作状态
- `SupplementalContext`
当前 run 中仍可访问的 supporting context
- `RuntimeContext`
当前 run 的能力与边界信息
- `ExecutionContextRunningState` + `SupplementalContext` + `RuntimeContext`
- `StageInput`
某个 stage 从 `ExecutionContext` 中投影得到的输入子集

该结构的直接价值在于：

- 为 context construction 的结果提供清晰落点
- 为 state assimilation 与 supporting retention 提供明确边界
- 为 stage-aware usage 提供统一、可编码、可测试的输入模型

因此，这一节应被视为本系统 context runtime model 的正式定义，并作为后续实现 `Context and Memory Loader`、`Research Executor`、`Conclusion Generator` 以及 stage input builders 的直接依据。

## 4.6 Context Boundaries

本节定义当前 run 中 `Execution Context` 的边界。

其目标不是限制系统**能够访问**哪些信息，而是限制当前 run **应当携带**哪些信息。

对于本系统而言，可访问的信息很多，但并不意味着它们都应进入当前 `Execution Context`。

如果缺乏明确边界，当前 run 很容易出现：

- context inflation
- 无关或低价值信息稀释重点
- stale 或错误 scope 的信息干扰当前判断
- `RunningState` 与 `SupplementalContext` 的职责边界被破坏

因此，本系统要求：

`Execution Context` 只能包含**经过选择、整形，并对当前任务真正有帮助**的信息，而不能成为系统全部可得信息的临时装载区。

### 4.6.1 Default Exclusion Rules

以下内容**不应默认进入 `Execution Context`**：

- full conversation dump
- full long-term memory dump
- raw tool outputs
- raw retrieval payloads
- full external documents or long raw chunks
- low-value transient artifacts
- unresolved low-confidence reasoning fragments
- out-of-scope context

这些内容即使可访问，也不应原样进入当前 run。

系统应优先保留其经过摘要、压缩和筛选后的结果，而不是原始材料本身。

### 4.6.2 Running State and Supplemental Context Boundaries

边界控制不仅作用于 `Execution Context` 的总体规模，也作用于其内部对象边界。

- **`RunningState`** 只应承载当前 run 的核心工作变量，例如任务框架、项目摘要、当前 bottleneck、evidence summary 和 intermediate findings。
full supporting records、raw evidence 和未收敛判断不应直接进入 state。
- **`SupplementalContext`** 用于保留已选中的 supporting context，但同样不应成为无边界堆积层。
raw payloads、full documents、明显重复或已不再相关的 supporting items 不应长期停留在其中。

### 4.6.3 Admissibility Principle

本系统采用如下原则：

**Availability does not imply admissibility.**

也就是说：

- 系统能够访问某条 memory，不代表它应进入当前 run
- 系统能够检索到某条 external evidence，不代表它应进入当前 run
- 某条信息“有一点关系”，也不代表它应进入当前 run

任何信息要进入 `Execution Context`，都必须满足：

- 与当前任务相关
- 在当前情境下仍然适用
- 在当前 scope 内有效
- 以适合执行的形式被整理
- 能够证明其对当前 run 的实际价值

### 4.6.4 Bounded Context Principle

综上，本系统明确采用以下边界原则：

**Execution Context should contain distilled, task-relevant, currently usable information only.**

也就是说，当前 run 的上下文应当是：

- distilled
- relevant
- scoped
- fresh enough
- bounded
- stage-usable

而不是：

- raw
- exhaustive
- cross-scope
- stale
- unbounded
- difficult to consume

`Context Boundaries` 的作用，不是减少系统能力，而是确保系统在每次 run 中真正携带的是：

**对当前任务有帮助的上下文，而不是系统全部可得信息的堆叠结果。**

# 5. Memory Access, Persistence, and Lifecycle Policies

## 5.1 Design Goals

本章的目标，是为系统中的 memory 建立一套明确、可执行、可治理的运行规则，使 memory 能够作为高价值的长期资产服务于未来运行，而不是演变为无边界的历史堆积。

对于本系统而言，memory 的价值不在于尽可能保留更多历史信息，而在于：

- 在未来运行中被正确访问和复用
- 以受控方式沉淀真正值得持久化的内容
- 随着系统运行持续更新、替代、降权或清理
- 长期保持较高的信息质量和较低的噪声水平

基于上述目标，本章围绕以下四项设计原则展开。

### 5.1.1 Controlled Access

系统对 memory 的访问应是受控的，而不是默认全量开放。

不同类型的 memory 在访问方式、访问时机和访问范围上应具有明确边界。例如：

- session short-term memory 主要服务于 session continuity
- structured long-term memory 主要通过 scoped lookup 被选择性访问
- research knowledge memory 主要通过 retrieval-style access 被按需 recall

因此，memory 不应被视为当前 run 的默认背景板，而应被视为一类需要根据任务和阶段按需访问的可复用资产。

### 5.1.2 Selective Persistence

系统对 memory 的持久化应是有选择的，而不应将运行中产生的所有信息默认写入 memory。

只有那些具备明确复用价值、相对稳定、并且对未来运行有意义的信息，才应成为 persistence candidate。

这意味着：

- 不是所有 intermediate outputs 都值得被持久化
- 不是所有 tool results 都应进入 long-term memory
- 不是所有局部结论都适合写入 session memory 或 long-term memory

因此，持久化不应被视为默认动作，而应被视为经过筛选后的系统决策。

### 5.1.3 Lifecycle Governance

memory 一旦被写入，就不应被视为静态记录。

不同 memory 在其生命周期中，可能经历：

- 更新
- 替代
- 降权
- 失效
- 清理
- 归档

例如：

- project profile 可能随着项目阶段变化而被更新
- decision memory 可能被新的 decision supersede
- action memory 可能因状态推进而发生变化
- research knowledge 可能因过时而被降权或清理

因此，本系统要求对 memory 的生命周期进行持续治理，而不是将其视为一次写入后永久有效的静态内容。

### 5.1.4. Memory Quality Over Memory Quantity

本系统优先追求 memory 的质量，而不是数量。

与其保留大量低价值、边界不清或已过时的信息，不如保留少量高价值、可复用、当前仍有效的 memory。

这一原则意味着：

- memory 不应成为原始历史材料的堆积层
- “可能有点用”不等于“值得被持久化”
- 低置信度、低稳定性、低复用价值的内容应默认被排除在外

因此，本系统中的 memory design 应始终以未来运行质量为中心，而不是以最大化存储覆盖为中心。

综上，本章将围绕以上四项目标，定义系统在运行过程中如何访问、持久化和治理各类 memory，并建立一套可支撑长期演化的 memory operating model。

---

## 5.2 Memory Access Overview

本节从运行时视角，总览系统中的 memory access 是如何发生的。

其重点不是定义各类 memory 的具体细则，而是说明：

- 哪些组件会触发 memory access
- memory access 通常发生在 request lifecycle 的哪些位置
- 不同类型 memory 的访问模式有何差异
- memory access 的结果如何与 context construction 流程衔接

对于本系统而言，memory 不是默认附着在每次运行上的背景信息，而是一类需要按任务、按阶段、按访问模式被选择性使用的可复用资产。

### 5.2.1 Access Participants

从运行时行为看，memory access participants 更适合按访问角色理解，而不是按互斥组件类别理解。

在本系统中，一个 stage 既可能在特定时刻触发 direct memory access，也可能在大多数情况下主要消费已经完成 shaping 的上下文。

**可能触发 direct memory access 的组件包括：**

- `Context and Memory Loader`
- `Planning and Decomposition`（仅少量、定向补充）
- `Research Executor`
- `Post-response Memory Distillation / Persistence Component`

**主要消费 shaped context 的组件包括：**

- `Task Interpretation`
- `Planning and Decomposition`
- `Research Executor`
- `Conclusion Generator`

因此，direct access 和 shaped-context consumption 不是互斥关系，而是两个不同维度的运行时角色。

### 5.2.2 Access Timing in the Request Lifecycle

memory access 通常与 request lifecycle 对齐，主要包括以下时机：

- **Request Start**
读取 session continuity 和少量 project grounding。
- **Planning / Early Execution**
读取 active project profile、relevant decision memory 和 current action / execution memory，以支持计划生成。
- **Research Execution**
根据 evidence gap 按需访问 additional structured memory、research knowledge memory 和 tool-acquired external context。
- **Post-response Update**
读取当前 run 的结果，提炼 memory candidates，并决定写回 session memory 或 long-term memory。

### 5.2.3 Access Modes

本系统中的 memory access 主要包括以下三类模式：

- **Session Continuity Read**
读取 recent turn summary、session working summary、latest recommendation 和 latest action items。
特点是 session-scoped、轻量、以 continuity 为目标。
- **Structured Scoped Lookup**
读取 project profile、decision、action / execution、preference / policy 等 structured memory。
特点是 scope-constrained、metadata-based、summary-first。
- **Retrieval-style Access**
访问 research knowledge memory，以及 research stage 中引入的 tool-acquired external context。
特点是 relevance-driven、recall-oriented，通常由 evidence gap 触发。

### 5.2.4 Relationship with Context Construction

memory access 的结果不会直接原样暴露给后续 stage。

相反，memory access 只为 `Context Construction and Loading` 提供候选信息。

这些结果通常还需要经过：

- relevance filtering
- scope filtering
- freshness filtering
- redundancy control
- compression / summarization
- placement decision

之后，才会被：

- 吸收到 `RunningState`
- 保留为 `SupplementalContext`
- 或作为局部临时 supporting material 使用

因此：

**memory access does not imply direct context injection.**

### 5.2.5 Rule-based and LLM-assisted Memory Resolution

本节定义本系统中 memory 读写的通用分工。

其目标不是替代后续各类 memory 的具体 read / write path，而是先明确一个总原则：

**本系统中的 memory 读写默认都是 LLM-assisted 的；规则负责定义边界、允许动作和失败处理；相似度匹配仅在必要时作为候选召回或去重辅助的受限机制参与。**

因此，memory 读写既不是一个单纯基于规则的过程，也不是一个单纯基于相似度匹配的过程，而是一个由规则、LLM 和少量辅助匹配共同完成的混合机制。

#### 1. Role of Rules

规则的职责是定义 memory 系统中的硬边界和最终动作。

规则通常负责：

- scope 是否明确
- 当前记录是否允许被读取
- 当前 candidate 是否允许被写入
- active / stale / superseded / archived 状态如何约束
- 允许执行哪些 update action
- 失败时是否应 `no-read` / `no-write`

因此，规则主要回答的是：

- 什么允许发生
- 什么不允许发生
- 失败时系统该如何处理

规则不负责复杂语义理解，但负责为 memory 读写提供明确边界。

#### 2. Role of LLM

LLM 的职责是处理规则难以直接完成的语义任务。

在 memory 系统中，LLM 通常负责：

- 从当前 `ExecutionContext` 中提炼 memory candidates
- 生成 summary、working summary 或 knowledge unit
- 判断哪些内容值得写入 memory
- 判断新 candidate 与 existing record 在语义上是什么关系
- 判断某条信息更像：
    - state update
    - new decision
    - action status change
    - stable knowledge
    - session-only signal

例如：

- 在 `Session Memory` 中，LLM 负责总结当前主线、提炼 open questions、重写 session working summary
- 在 `Structured Long-term Memory` 中，LLM 负责从当前 run 中提炼 durable candidates，并判断 candidate 与 existing records 的语义关系
- 在 `Research Knowledge Memory` 中，LLM 负责将 research outputs 提炼成可复用的知识单元

因此，LLM 主要回答的是：

- 这段内容在语义上是什么
- 它和值得保留的 memory 之间是什么关系

#### 3. Role of Similarity Matching

相似度匹配在本系统中只承担受限的辅助角色。

它的主要用途包括：

- 模糊输入下的候选对象召回
- 写入前的近似去重
- `Research Knowledge Memory` 的语义召回
- 当前 candidate 与 existing records 的候选缩小范围

需要强调的是：

- 相似度匹配通常只负责找候选
- 不应直接决定最终 read / write 动作
- 其结果通常仍需后续规则检查和 LLM 语义判断

因此，相似度匹配主要回答的是：

- 哪些 existing records 看起来可能相关
- 哪些 knowledge units 可能值得召回

而不是：

- 最终应该读取哪条
- 最终应该写成什么

#### 4. Memory-layer-specific Participation

虽然上述三类机制在所有 memory layer 中都可能出现，但参与强度不同。

**4.1 Session Memory**

在 `Session Memory` 中：

- 规则负责字段边界、retention 和 overwrite / merge / remove 的框架
- LLM 负责 continuity summary、rolling rewrite、open question extraction 和当前主线提炼
- 相似度匹配通常不是主路径，仅在必要时做弱辅助

**4.2 Structured Long-term Memory**

在 `Structured Long-term Memory` 中：

- 规则负责 scope、write admission、active-set invariants、update actions 和 failure handling
- LLM 负责 durable candidate extraction，以及 candidate 与 existing record 之间的语义关系判断
- 相似度匹配主要用于：
    - scope resolution fallback
    - existing record candidate retrieval
    - write-side dedupe assistance

其中，`Preference / Policy Memory` 属于 `Structured Long-term Memory` 的一个 subtype，其读取和写入同样遵循这一总原则，只是它更偏轻量覆盖层，而不是复杂状态记录层。

**4.3 Research Knowledge Memory**

在 `Research Knowledge Memory` 中：

- 规则负责 source requirement、freshness handling、dedupe / prune policy 和 bounded recall
- LLM 负责 knowledge unit distillation、topic summary 生成和 research output 抽象
- 相似度匹配是主召回方式之一，但召回后仍需经过 metadata filtering 和 bounded selection

#### 5. General Resolution Pattern

从整体上看，本系统中的 memory 读写通常遵循以下模式：

1. 规则先定义边界
先确定 scope、memory type、allowed actions 和基本约束
2. LLM 做语义提炼或语义判断
例如从当前 run 中提炼 candidate，或判断 candidate 与 existing record 的语义关系
3. 必要时用相似度匹配辅助召回候选
用于缩小 existing records 或 knowledge units 的范围
4. 最终动作仍由规则决定
例如：
    - `no-read`
    - `no-write`
    - `update`
    - `replace`
    - `append + supersede`
    - `status transition`

因此，本系统中的 memory resolution 不应被理解为：

- 纯规则系统
- 或纯相似度检索系统

而应被理解为：

**以规则为边界、以 LLM 为语义核心、以相似度匹配为受限辅助的混合机制。**

#### Summary

本系统中的 memory 读写遵循以下分工：

- **规则**：定义边界、允许动作和失败处理
- **LLM**：负责语义提炼、摘要生成和语义关系判断
- **相似度匹配**：负责候选召回、模糊定位和去重辅助

因此，本节的核心结论是：

**memory 读写的关键不在于“规则还是相似度”，而在于如何让规则、LLM 和相似度匹配各自承担合适的职责。**

---

## 5.3 Session Memory Policies

### **5.3.1 Session Memory Quality Goals**

本节明确本系统对高质量 `Session Memory` 的评价标准。

对于 **Vertical AI Research & Action Agent** 而言，`Session Memory` 的目标不是保存完整会话历史，而是以低噪声、高信息密度的方式维持当前 session 内的研究、决策与行动连续性。

高质量的 `Session Memory` 应满足以下目标：

#### 1. Continuity Preservation

能够稳定保住当前 session 的工作主线，使系统在后续 turn 中持续理解：

- 当前正在推进的问题
- 最近形成的结论或 recommendation
- 当前仍未解决的关键问题
- 最可能延续的下一步方向

#### 2. Project-grounded Relevance

优先保留与当前 project continuity 直接相关的信息，例如：

- 当前 project scope
- 当前阶段目标
- 当前 bottleneck
- 当前 decision direction
- 当前 action items 与 open questions

#### 3. Information Density

以尽量小的体积保留尽量高价值的连续性信息。

系统应优先保留 summary 和 distilled working status，而不是完整 transcript 或低价值细节。

#### 4. Update Correctness

能够随着 session 演进及时更新，反映当前最新状态，避免旧 focus、旧 recommendation 或过时 action status 长期残留。

#### 5. Noise Control

尽量避免低价值、未收敛、重复或过时信息的积累，例如：

- full transcript accumulation
- raw tool outputs
- unresolved reasoning fragments
- stale local state

#### 6. Downstream Utility

其质量最终应体现在是否真正提高后续运行质量，包括：

- 降低重复分析成本
- 减少用户重复解释背景
- 提高后续 planning 和 recommendation 的贴合度
- 改善同一 session 内的 action continuity

综上，一个高质量的 `Session Memory` 应能够以小而精、持续更新、低噪声的方式，稳定支撑当前 session 内的 project continuity。后续各项 `Session Memory` policy，均以实现上述目标为导向。

### **5.3.2 Session Memory Content Model and Boundaries**

本节定义 `Session Memory` 中应保留的内容及其边界。

其目标不是覆盖更多会话细节，而是保留对当前 session continuity 持续有价值的信息。

对于本系统而言，`Session Memory` 应被视为一个**面向当前 session 的 continuity layer**，而不是完整对话归档，也不是 long-term memory 的临时替代层。

#### 1. Content Model

`Session Memory` 应优先保留以下内容：

- **Recent Turn Summary**
最近少量高价值 turn 的摘要，用于支持短距离 follow-up continuity。
- **Session Working Summary**
当前 session 主线的滚动摘要，包括当前核心问题、推进方向和局部目标。
- **Latest Recommendation**
当前 session 最近形成的 recommendation 摘要。
- **Latest Action Items**
当前 session 最近形成的 action items 或 next steps。
- **Open Questions**
当前 session 中仍未解决、但可能在后续继续推进的问题。
- **Current Local Task Framing**
当前局部任务的 framing 摘要，例如 recommendation、comparison 或 action planning。

#### 2. Content Boundaries

以下内容通常**不应进入 `Session Memory`**：

- full transcript
- raw tool outputs
- raw evidence 或详细 supporting materials
- unresolved reasoning fragments
- low-value local details

若其中部分信息对当前 session continuity 有帮助，应先提炼为 summary，再决定是否写入。

#### 3. Representation Principle

`Session Memory` 中的信息应优先采用：

- summary
- distilled status
- compact continuity signals

而不应采用：

- raw transcript
- full records
- long-form narrative history

其核心原则是：

**Session Memory should preserve continuity signals, not conversational bulk.**

#### 4. Boundary with Long-term Memory

`Session Memory` 只服务于当前 session continuity，不承担 cross-session durable reuse 的职责。

若某些内容具有长期复用价值，应在后续 persistence 阶段被提炼并写入 long-term memory，而不是长期滞留在 session layer 中。

### **5.3.3 Read and Usage Policy**

本节定义 `Session Memory` 在运行时如何被读取和使用。

其目标是为当前 run 恢复必要的 session continuity，而不是回放完整会话历史。

#### 1. Read Objective

读取 `Session Memory` 的目的，是恢复当前 session 的连续性信息，包括：

- 当前主线
- 最近形成的 recommendation 或 action items
- 当前仍未解决的关键问题
- 当前局部任务的 framing

因此，`Session Memory` 的读取服务于 continuity recovery，而不是知识补充或历史回放。

#### 2. Read Timing

在当前 workflow 中，`Session Memory` 的直接读取主要发生在：

- `Task Interpretation` 之后
- `Planning and Decomposition` 之前或过程中

也就是说，系统先基于 `user query` 形成初步任务理解，再由后续阶段引入 session continuity。

后续 stage 应优先消费已经进入 `ExecutionContext` 的结果，而不是重复直接读取 session layer。

#### 3. Read Participants

`Session Memory` 的主要直接读取者是：

- `Context and Memory Loader`

在必要时，以下组件也可触发少量补充读取：

- `Planning and Decomposition`

在当前 workflow 中：

- `Task Interpretation` 默认不直接读取 `Session Memory`
- `Research Executor` 和 `Conclusion Generator` 通常不应默认直接读取 `Session Memory`
- 后两者主要消费已经完成 shaping 的 `StageInput`

#### 4. Read Scope

读取 `Session Memory` 时，系统应优先读取：

- `recent_turn_summary`
- `session_working_summary`
- `latest_recommendation`
- `latest_action_items`
- `open_questions`
- `current_local_task_framing`

默认情况下，不应读取：

- full transcript
- complete previous turn history
- raw intermediate artifacts

因此，`Session Memory` 的读取应以 **summary-first** 为原则。

#### 5. Read Result Selection and Placement

即使 `Session Memory` 已以 summary 形式存储，其内容在进入当前 `ExecutionContext` 之前，通常仍需经过轻量筛选。

该步骤的重点不是重型压缩，而是：

- relevance checking
- freshness / current-focus checking
- redundancy control
- placement decision

也就是说，系统需要判断：

- 当前这轮是否需要这条 summary
- 它是否仍然适用于当前主线
- 它是否与其他 continuity signals 重复
- 它应进入 `RunningState` 还是 `SupplementalContext`

因此，读取到的 `Session Memory` 不会直接原样暴露给后续 stage，而是先作为 continuity candidates 进入 context construction 流程，再决定其在当前 run 中的最终位置。

#### 6. Usage Constraints

`Session Memory` 的使用应遵循以下约束：

- 默认只用于恢复 continuity，不用于补充大量新知识
- 不应替代 project-scoped structured memory
- 不应将过长 session summary 原样注入当前 run
- 当当前请求已明显脱离 previous thread 主线时，应降低其使用权重

综上，`Session Memory` 的读取应当是：

- early-stage
- loader-driven
- summary-first
- continuity-oriented
- lightweight-selection-before-use

其核心作用是为当前 run 恢复必要的 session continuity。

### **5.3.4 Write and Rolling Update Policy**

本节定义 `Session Memory` 如何被写回和滚动更新。

其目标不是累积更多会话内容，而是持续维护一个对当前 session 真正有用的 continuity layer。

对于本系统而言，`Session Memory` 中不同字段的语义不同，因此更新方式也不应统一处理。系统应根据字段类型，分别采用 `append`、`merge / rewrite`、`overwrite` 或 `remove` 等不同策略，而不是将所有内容都按 append-only 方式累积。

#### 1. Write Objective

写回 `Session Memory` 的目的，是保留对后续 turn 仍有持续价值的 continuity signals，包括：

- 当前主线的更新
- 最新 recommendation
- 最新 action items
- 当前仍然有效的 open questions
- 当前局部 task framing 的变化

因此，写回的重点不是“把本轮结果都存下来”，而是“把会影响后续 continuity 的状态更新到 session layer”。

#### 2. Write Timing and Writer

`Session Memory` 的写回通常发生在当前 response 生成之后，由：

- `Post-response Memory Distillation / Persistence Component`

负责执行。

该组件的职责是：

- 从当前 run 的结果中提取 continuity-relevant information
- 判断其应更新到哪些 session memory 字段
- 根据字段语义采用对应的更新方式

默认情况下，中间推理、raw evidence 和 raw tool outputs 不应直接写入 `Session Memory`。

#### 3. Field-specific Update Semantics

`Session Memory` 应至少区分以下几类字段及其更新方式。

**A. Recent Turn Summaries — Bounded Append**

`recent_turn_summaries` 用于保留最近少量高价值 turn 的摘要。

该类字段适合采用 **bounded append**：

- 新的 high-value turn summary 可以追加
- 但只能保留有限窗口
- 超出窗口的较旧内容应被移除

这里不是无限 append，而是**有限追加 + 超限裁剪**。

其作用是支持短距离 follow-up continuity，而不是累积完整 turn history。

**B. Session Working Summary — Merge / Rewrite**

`session_working_summary` 表示当前 session 主线的滚动摘要。

该字段不应采用 append-only，而应采用 **merge / rewrite**：

- 当本轮只是局部推进时，可在现有 summary 基础上 merge 更新
- 当当前主线明显变化、旧 summary 已不再准确时，应整体 rewrite

其核心要求是：

- 始终表达“当前 session 正在做什么”
- 不保留过多已失效的旧状态
- 不通过简单拼接形成越来越长的 summary

因此，`session_working_summary` 的更新本质上是**滚动维护当前状态**。

**C. Latest Recommendation — Overwrite**

`latest_recommendation` 表示当前 session 最新有效的 recommendation。

该字段应采用 **overwrite**：

- 当新的 recommendation 已经形成并替代旧 recommendation 时，应覆盖旧值
- 不应长期并列保留多个“latest” recommendation

如果需要保留 recommendation 演化历史，应交给其他记录机制处理，而不是让 `latest_recommendation` 字段承担历史存档职责。

**D. Latest Action Items — Overwrite with Structured Refresh**

`latest_action_items` 表示当前仍有效的 next steps。

该字段通常应采用 **overwrite with structured refresh**：

- 新一轮产生更准确的 action items 时，应刷新整个 active set
- 已完成、已取消、已被替代的 action items 应移除
- 仍然有效的 action items 可以被保留或重写

这里不建议简单 append，因为 action items 的核心语义是“当前还要做什么”，而不是“历史上曾建议做过什么”。

**E. Open Questions — Merge / Remove**

`open_questions` 表示当前仍未解决的问题集合。

该字段应采用 **merge / remove**：

- 新识别出的未决问题可以追加进入 active set
- 已解决的问题应移除
- 已不再相关的问题应降权或删除

因此，`open_questions` 的更新不是纯 append，而是一个动态维护 active unresolved set 的过程。

**F. Current Local Task Framing — Overwrite**

`current_local_task_framing` 表示当前局部任务的 framing。

该字段应采用 **overwrite**：

- 当局部任务仍然延续时，可保留原值
- 当当前 focus 已明显切换，例如从 explanation 转向 recommendation，或从 design discussion 转向 action planning，应覆盖旧 framing

该字段的目标是表达当前局部任务形态，而不是保留历史 framing 序列。

#### 4. Rolling Update Principle

综上，`Session Memory` 的 rolling update 不应理解为“不断追加”，而应理解为：

- 对 recent-turn continuity signals 做 **bounded append**
- 对 session 主线摘要做 **merge / rewrite**
- 对 latest-state fields 做 **overwrite**
- 对 open questions 和 active items 做 **refresh / remove**

因此，rolling update 的核心不是积累历史，而是：

**持续维护当前仍然有效的 session continuity state。**

#### 5. Update Constraints

为保证 `Session Memory` 质量，写回与更新必须满足以下约束：

- 不得将所有字段统一按 append-only 处理
- 不得让 `session_working_summary` 通过简单拼接不断膨胀
- 不得让 `latest_recommendation`、`current_local_task_framing` 等 latest-state 字段长期保留多个冲突版本
- 不得让已完成或已失效的 action items 长期残留
- 不得让已解决的 open questions 长期停留在 active set 中

#### Summary

`Session Memory` 的写回与更新应基于字段语义采用不同策略：

- `recent_turn_summaries` → **bounded append**
- `session_working_summary` → **merge / rewrite**
- `latest_recommendation` → **overwrite**
- `latest_action_items` → **structured refresh / overwrite**
- `open_questions` → **merge / remove**
- `current_local_task_framing` → **overwrite**

因此，本系统中的 rolling update 不是 append-only 累积，而是围绕“当前仍然有效的 continuity state”进行持续维护。

### **5.3.5 Retention and Promotion Policy**

本节定义 `Session Memory` 的保留边界，以及哪些内容应继续停留在 session layer，哪些内容应被提炼并提升到 long-term memory。

其目标是保证 `Session Memory` 始终服务于当前 session continuity，而不演变为伪 long-term memory 或无边界的历史堆积层。

#### 1. Retention Objective

`Session Memory` 只应保留对当前 session 后续 turn 仍有连续性价值的信息，例如：

- 当前主线
- 当前仍有效的 recommendation
- 当前仍有效的 action items
- 当前 open questions
- 当前局部 task framing

一旦某条信息不再服务当前 session continuity，就不应继续停留在活跃 session layer 中。

#### 2. Retention Strategy by Field Type

不同字段应采用不同保留策略：

- **Recent Turn Summaries**
仅保留最近有限窗口内的高价值 turn summary，超出窗口的内容应移除。
- **Session Working Summary**
仅保留当前有效版本，旧版本不应在活跃 session layer 中并列保留。
- **Latest Recommendation**
仅保留当前最新有效 recommendation，旧 recommendation 应被替换。
- **Latest Action Items**
仅保留当前仍有效的 next steps，已完成、已取消或已替代项应移除。
- **Open Questions**
仅保留当前仍未解决、且仍与当前主线相关的问题；已解决或失去相关性的问题应移除。
- **Current Local Task Framing**
仅保留当前有效 framing；当 focus 切换时，旧 framing 应被覆盖。

#### 3. Promotion Objective

当某条 session-level information 不再只是当前 session continuity 的局部状态，而是具备跨 session 复用价值时，系统应考虑将其提升为 long-term memory candidate。

promotion 的目标是将真正具有 durable value 的内容，从短期 continuity 层转移到长期复用层，而不是简单多存一份。

#### 4. Promotion Criteria

以下内容更适合 promotion 到 long-term memory：

- 具有 project-level 持续意义的状态变化
- 已稳定的 decision direction
- 未来仍可复用的 action status 或 next-step conclusion
- 可复用的高质量知识摘要
- 稳定且会影响后续行为的 preference / policy information

以下内容通常不应 promotion：

- 只对当前局部对话有用的短期 continuity signal
- 未收敛的局部判断
- 低价值细节
- raw tool outputs、raw evidence 或 raw transcript 片段

#### 5. Promotion Timing

promotion 通常发生在 **post-response memory distillation / persistence** 阶段。

系统应在当前 run 结束后再判断：

- 哪些内容继续保留在 `Session Memory`
- 哪些内容应从 session layer 中淡出
- 哪些内容值得被提炼并写入 long-term memory

#### 6. Boundary Principle

`Session Memory` 与 long-term memory 的边界可概括为：

- **Session Memory**：服务当前 session continuity
- **Long-term Memory**：服务跨 session durable reuse

因此，若某条信息的价值已不再主要属于当前 session continuity，就应考虑 promotion 或 drop，而不是继续滞留在 session layer 中。

#### Summary

`Session Memory` 的 retention and promotion policy 应遵循以下原则：

- 当前 session continuity 优先
- 活跃状态优先于历史累积
- 过时内容应及时移除
- durable value 应 promotion 到 long-term memory
- session layer 不承担长期复用职责

因此，`Session Memory` 应被维护为一个**有边界的短期连续性层**。

### **5.3.6 Failure Modes and Control Points**

本节定义 `Session Memory` 的常见失效模式，以及系统用于抑制这些问题的控制点。

其目标是将前文定义的质量目标转化为可治理的风险模型，说明 `Session Memory` 会如何变坏，以及系统应通过哪些机制防止其偏离预期。

---

#### 1. Mainline Drift or Mainline Loss

**Definition**

`Session Memory` 未能持续表达当前 session 的核心主线，导致系统在后续 turn 中无法准确接续当前问题推进方向。

**Negative of Quality Goals**

这是以下目标的反面：

- `Continuity Preservation`
- `Project-grounded Relevance`
- `Downstream Utility`

**Typical Symptoms**

- 系统无法准确识别当前 session 正在推进的问题
- 用户需要反复重述背景
- 当前 response 与前几轮已形成的 recommendation 或 action direction 脱节
- session summary 只记录局部对话片段，无法表达当前主线

**Control Points**

- 维护 `session_working_summary`，并以其作为 session continuity 的核心载体
- 保留 `current_local_task_framing`，确保当前局部任务形态明确
- 在 request early stage 由 `Context and Memory Loader` 读取 session continuity
- 采用 summary-first read，而不是依赖 raw transcript 回放 continuity

---

#### 2. Context Inflation

**Definition**

`Session Memory` 持续膨胀，保留了过多低层次或冗余信息，导致其不再是高密度 continuity layer，而变成缩写版 transcript。

**Negative of Quality Goals**

这是以下目标的反面：

- `Information Density`
- `Noise Control`
- `Downstream Utility`

**Typical Symptoms**

- `session_working_summary` 越来越长
- `recent_turn_summaries` 无边界累积
- 多个字段中重复表达同一信息
- 读取 `Session Memory` 本身开始成为新的上下文负担

**Control Points**

- 对 `recent_turn_summaries` 采用 bounded append，只保留有限窗口
- 对 `session_working_summary` 采用 merge / rewrite，而不是 append-only
- 排除 full transcript、raw evidence 和 raw tool outputs
- 在读入 `ExecutionContext` 之前做 lightweight selection 和 redundancy control

---

#### 3. Stale State Retention

**Definition**

`Session Memory` 中保留了已过时、已被替代或已不再代表当前状态的信息，导致后续 turn 被旧状态误导。

**Negative of Quality Goals**

这是以下目标的反面：

- `Update Correctness`
- `Continuity Preservation`
- `Project-grounded Relevance`

**Typical Symptoms**

- 旧 recommendation 仍被当作 current recommendation
- 已完成或已取消的 action items 仍停留在 active set 中
- 已解决的 open questions 仍被反复带入后续 turn
- 当前 local task framing 已切换，但 session memory 仍保留旧 framing

**Control Points**

- 对 `latest_recommendation` 采用 overwrite
- 对 `latest_action_items` 采用 structured refresh / overwrite
- 对 `open_questions` 采用 merge / remove
- 对 `current_local_task_framing` 采用 overwrite
- 在每轮 post-response update 中显式清理 stale local state

---

#### 4. Low-value Noise Accumulation

**Definition**

低价值、未收敛、仅局部有用或重复的信息持续进入 `Session Memory`，导致 continuity layer 被噪声污染。

**Negative of Quality Goals**

这是以下目标的反面：

- `Noise Control`
- `Information Density`
- `Downstream Utility`

**Typical Symptoms**

- 临时讨论细节被长期保留
- unresolved reasoning fragments 进入 session layer
- raw tool outputs 或 raw evidence 被直接写回
- local paraphrases、局部展开和低复用价值信息不断积累

**Control Points**

- 在 write-back 前做 continuity-first filtering
- 默认排除 raw tool outputs、raw evidence、unresolved reasoning fragments
- 仅写回 continuity-relevant summaries，而不是完整 response 或中间过程
- 明确 low-value local details 不属于 session memory 的合法内容模型

---

#### 5. Session / Long-term Boundary Blur

**Definition**

`Session Memory` 开始承载本应由 long-term memory 持有的 durable information，导致 session layer 越界膨胀，并与 long-term memory 职责混淆。

**Negative of Quality Goals**

这是以下目标的反面：

- `Project-grounded Relevance`
- `Noise Control`
- `Update Correctness`

同时也会削弱 `Session Memory` 作为短期 continuity layer 的边界清晰性。

**Typical Symptoms**

- 本应进入 project profile 或 decision memory 的内容长期滞留在 session layer
- session memory 中保留过多跨 session durable facts
- session layer 被用作“先存着以后再说”的临时长期存储区
- retention boundary 不清，session memory 逐步演变成伪 long-term memory

**Control Points**

- 明确 `Session Memory` 只服务当前 session continuity
- 在 `Retention and Promotion Policy` 中区分 retain / promote / drop 三种去向
- 对具有 durable value 的内容，在 post-response 阶段做 promotion candidate extraction
- 避免因为“未来可能有用”而长期滞留在 session layer 中

---

#### 6. Low Downstream Utility

**Definition**

`Session Memory` 虽然保留了内容，但这些内容对后续 planning、research、recommendation 和 action continuity 的实际帮助有限。

**Negative of Quality Goals**

这是以下目标的反面：

- `Downstream Utility`
- `Continuity Preservation`
- `Information Density`

**Typical Symptoms**

- 后续 turn 仍需要大量重复解释背景
- planning 无法直接利用 session continuity
- recommendation 与当前 session 推进状态贴合度低
- session memory 虽然存在，但对后续 `StageInput` 几乎没有贡献

**Control Points**

- 优先写回 latest recommendation、latest action items、open questions 和 current local framing
- 使用 `session_working_summary` 表达当前主线，而不是保留零散 turn facts
- 在读入当前 run 前做 run-specific selection，确保 continuity signals 真正进入 `ExecutionContext`
- 用 downstream usefulness 而不是内容多少，作为 session memory write-back 的优先标准

---

#### Summary

本系统中，`Session Memory` 的主要失效模式包括：

- 主线丢失
- session context 膨胀
- 旧状态残留
- 低价值噪声积累
- session / long-term 边界模糊
- 对后续运行帮助不足

这些失效模式分别对应前文质量目标的反面。

因此，本系统通过以下控制点对其进行治理：

- `session_working_summary`
- bounded `recent_turn_summaries`
- overwrite / merge / remove 规则
- continuity-first write-back filtering
- explicit retention / promotion boundary
- run-specific selection before use

这些控制点的共同目标，是确保 `Session Memory` 长期保持为一个：

- continuity-preserving
- project-grounded
- high-density
- up-to-date
- low-noise
- downstream-useful

的 session continuity layer。

---

## 5.4 Structured Long-term Memory Policies

### **5.4.1 Quality Goals**

本节明确本系统对高质量 `Structured Long-term Memory` 的评价标准。

对于 **Vertical AI Research & Action Agent** 而言，`Structured Long-term Memory` 的目标不是保存更多历史信息，而是作为跨 session 的稳定项目事实层、决策状态层和行动状态层，被准确读取、正确更新并长期复用。

高质量的 `Structured Long-term Memory` 应满足以下目标。

#### 1. Scope Accuracy

每条 memory 都应具有清晰、稳定、可约束的作用域。

系统应能够明确判断：

- 它属于哪个 project scope
- 属于哪类 structured memory type
- 当前 request 是否应访问该记录

#### 2. Semantic State Correctness

被系统作为当前有效记录读取的 structured memory，应能够在语义上正确表达当前状态，例如：

- 当前 project context
- 当前 active decision
- 当前 action / execution status
- 当前仍成立的 preference / policy constraints

#### 3. Updateability

`Structured Long-term Memory` 应支持自然的更新、替代和状态迁移，而不是只能不断追加新记录。

例如：

- project profile 会变化
- decision 会被 supersede
- action status 会推进
- tracking item 会从 active 转为 archived

#### 4. Read Usefulness

`Structured Long-term Memory` 应能够被高效读取，并直接支持当前 run，例如提供：

- project grounding
- current bottleneck
- active decisions
- current action continuity
- stable constraints

#### 5. Version and Lifecycle Discipline

`Structured Long-term Memory` 应能够清楚表达版本关系和生命周期状态。

系统应能明确区分：

- active
- stale
- superseded
- archived

并正确处理新记录接管 active 状态、旧记录退出 active 层等关系。

#### 6. Durable Signal Quality

`Structured Long-term Memory` 应优先承载稳定、低噪声、适合长期复用的内容，而不是：

- 局部讨论过程
- 未收敛判断
- 原始对话细节
- raw evidence
- raw tool outputs

#### Summary

综上，高质量的 `Structured Long-term Memory` 应能够：

- 准确表达所属 scope
- 在语义上正确反映当前有效状态
- 支持更新、替代和状态演化
- 被高效读取并直接服务当前 run
- 清楚表达版本关系和生命周期状态
- 长期保持低噪声、高稳定性和高复用价值

后续各项 `Structured Long-term Memory` policy，均以实现上述目标为导向。

### **5.4.2 Read Path**

本节定义 `Structured Long-term Memory` 的读取流程。

其目标是让系统能够以 **scope-aware、summary-first、bounded** 的方式读取跨 session 的结构化 durable records，并直接支撑当前 run 的：

- project grounding
- decision continuity
- action continuity
- persistence-time state reconciliation

该读取流程应按如下顺序执行：

1. input normalization
2. project scope resolution
3. scoped structured lookup
4. summary-first read
5. bounded escalation
6. read result contract
7. selection and placement into `ExecutionContext`

---

#### 5.4.2.1 Input Normalization

在正式读取前，系统应先对输入做归一化。

其目标是为后续 `project_scope` 解析和结构化查询提供稳定输入。

归一化步骤至少包括：

- 从 `user query`、`session_working_summary`、`recent_turn_summary` 中提取：
    - `project_id`
    - `project_name`
    - `project_alias`
    - project-like description
- 对 project 名称做规范化处理：
    - lowercasing
    - trim spaces
    - normalize punctuation / hyphen / underscore
- 补充默认过滤条件：
    - default scope = current project only
    - default status = active / currently valid
    - default granularity = summary-first

该阶段输出的是一个规范化后的 structured-read request，而不是直接的数据库查询结果。

---

#### 5.4.2.2 Project Scope Resolution

在读取 structured records 之前，系统必须先尽可能解析 `project_scope`。

建议按以下优先级执行：

1. explicit `project_id`
2. explicit project name / alias
3. current session active project
4. recent decision / action context
5. similarity-assisted candidate resolution

其中：

- 若命中明确 `project_id`，直接视为 `scope_resolved`
- 若基于 name / alias 只命中一个 project，视为 `scope_resolved`
- 若仅通过 similarity 得到多个接近候选，则应视为 `scope_ambiguous`
- 若无法形成可信候选，则视为 `scope_unresolved`

当 `scope_ambiguous` 或 `scope_unresolved` 时：

- 不应将 project-scoped structured memory 直接注入 `RunningState`
- 最多只允许 very light summary 进入 `SupplementalContext`
- 或直接返回 empty structured read result

相似度匹配主要用于 **scope resolution**，而不是 structured records 的默认主读取方式。

---

#### 5.4.2.3 Scoped Structured Lookup

当 `project_scope` 已确定后，系统进入默认主读取路径：`scoped structured lookup`。

该路径应以结构化过滤为主，而不是 broad semantic recall。

默认查询对象包括：

- `project_profile`
- active `decision_records`
- active-like `action_records`
- current effective `preference / policy_records`
- active `tracking / watchlist_records`（如适用）

默认过滤条件包括：

- `project_scope_id = resolved_scope`
- `status in active-like states`
- `archived = false`
- `superseded = false`
- order by `priority desc`, `updated_at desc`

不同 memory type 的默认读取范围如下：

- **Project Profile Memory**
默认只读取当前 active profile summary
- **Decision Memory**
默认只读取 active decision summaries
- **Action / Execution Memory**
默认只读取 active-like items，例如 `todo`、`in_progress`、`blocked`
- **Preference / Policy Memory**
默认只读取 current effective constraints
- **Tracking / Watchlist Memory**
默认只读取 active tracked items

---

#### 5.4.2.4 Summary-first Read

在 `scoped structured lookup` 下，默认先读取 **summary-level records**，而不是完整 supporting records。

summary-level read 默认应返回：

- `project_profile_summary`
- `active_decision_summary`
- `current_action_summary`
- `effective_policy_summary`
- `active_tracking_summary`（如适用）

默认不优先返回：

- full decision chain
- full action history
- archived records
- superseded records
- raw record payloads

这样做的目的，是先恢复当前 project / decision / action grounding，再决定是否需要更细的信息。

---

#### 5.4.2.5 Bounded Escalation

当 summary-level 信息不足以支撑当前任务时，系统才应升级读取 supporting records。

这一步称为 `bounded escalation`。

**A. Escalation Trigger**

只有在以下情况出现时，才应触发 escalation：

- summary 无法支撑当前 planning 判断
- summary 无法解释 active decision 的关键依据
- summary 无法说明当前 action continuity
- persistence-time 需要判断：
    - update
    - replace
    - supersede
    - status transition

**B. Supporting Records 是什么**

`supporting records` 指数据库中完整结构化记录的**受控子集**，用于补充 summary 无法覆盖的细节。

它们不是原始自由文本材料，也不是外部 evidence，而是已经存入 structured long-term store 的底层 durable records。

典型例子：

- **supporting decision record**
包含：
    - `decision_id`
    - `decision_summary`
    - `decision_rationale_summary`
    - `decision_status`
    - `superseded_by`
    - `created_at / updated_at`
- **supporting action record**
包含：
    - `action_id`
    - `action_summary`
    - `action_status`
    - `priority`
    - `linked_decision_id`
    - `updated_at`
- **supporting profile note**
包含：
    - `project_scope_id`
    - 某个 profile field 的补充说明
    - `updated_at`
    - `source_of_update`

它们与数据库中的关系是：

- supporting record 本身对应一条或少量几条底层结构化记录
- escalation 读取的是这些底层记录的**受控视图**
- 不应把整个表、整个历史链或整组 records 全量拉出

**C. Supporting Records 与 `supporting_*_refs` 的关系**

在 read result 中，建议区分：

1. **supporting records**
    - 实际被 escalation 读取出来、可供当前 run 使用的补充内容
    - 通常为小数量、摘要化后的 supporting block
2. **supporting refs**
    - 对应这些 supporting records 的引用标识
    - 用于：
        - traceability
        - debugging
        - persistence-time reconciliation
        - 后续必要时再次精确读取

例如：

- `supporting_decision_refs = [decision_id_1, decision_id_2]`
- `supporting_action_refs = [action_id_7, action_id_9]`

因此：

- `supporting records` 是当前 run 可消费的补充内容
- `supporting refs` 是这些内容对应的底层记录句柄

通常进入 `ExecutionContext` 的应优先是 **supporting records 的摘要化内容**，而不是只有 refs；

但 refs 应作为元数据保留，供追踪和后续 read-before-write 使用。

**D. Supporting Records 与元数据的关系**

每条 escalation result 建议附带最小元数据，例如：

- `record_id`
- `memory_type`
- `project_scope_id`
- `status`
- `updated_at`
- `priority`
- `source_record_ref`
- `escalation_reason`

这些元数据的作用是：

- 让后续 selection / placement 更容易
- 避免 stale / superseded supporting records 被误用
- 支撑 debugging 与 traceability
- 支撑 post-response persistence decision

**E. Escalation Boundaries**

`bounded escalation` 必须满足以下约束：

- 一次 escalation 只针对单一 memory type
- 默认只读取少量 supporting records
- 不允许升级为全历史展开
- escalation 后的结果仍需经过 selection and placement

建议默认上限：

- supporting decision records: `<= 3`
- supporting action records: `<= 5`
- supporting profile notes: `<= 3`

---

#### 5.4.2.6 Read Result Contract

`Structured Long-term Memory` 的读取输出不应直接等于底层数据库记录。

建议输出分为以下两层。

**A. Summary-level Output**

适合直接进入 context construction 的摘要结果，例如：

- `project_profile_summary`
- `active_decision_summaries`
- `active_action_summaries`
- `effective_policy_summaries`

**B. Supporting-level Output**

仅在 escalation 时返回，例如：

- `supporting_decision_records`
- `supporting_action_records`
- `supporting_profile_notes`

同时应保留对应 refs：

- `supporting_decision_refs`
- `supporting_action_refs`
- `supporting_profile_refs`

**C. Output Metadata**

建议统一附带以下元数据：

- `resolved_project_scope_id`
- `resolution_method`
- `scope_confidence`
- `filters_applied`
- `escalation_used`
- `escalation_reason`

---

#### 5.4.2.7 Selection and Placement into ExecutionContext

structured read result 不会直接原样进入当前 run。

在进入 `ExecutionContext` 前，应经过：

- relevance checking
- scope validation
- lifecycle / freshness checking
- redundancy control
- placement decision

通常：

- `project_profile_summary`
- `active_decision_summary`
- `current_action_status`
- `effective_policy_constraints`

更适合进入 `RunningState`

而：

- `supporting_decision_records`
- `supporting_action_records`
- `supporting_profile_notes`

更适合进入 `SupplementalContext`

换句话说：

- summary-level output 更偏核心状态
- supporting-level output 更偏补充上下文

---

#### Summary

`Structured Long-term Memory` 的 read path 应按以下顺序落地实现：

1. `input normalization`
2. `project scope resolution`
3. `scoped structured lookup`
4. `summary-first read`
5. `bounded escalation`
6. `read result contract`
7. `selection and placement into ExecutionContext`

其中，`bounded escalation` 的实现重点不是“多读一点”，而是：

- 只在 summary 不足时触发
- 只读取小数量 supporting records
- 区分 supporting content、supporting refs 与元数据
- 最终仍通过 selection and placement 进入当前 run

其核心目标，是用尽量小的读取范围，恢复当前任务真正需要的 project / decision / action grounding。

#### Preference / Policy Memory Read

`Preference / Policy Memory` 的读取应保持轻量。

对本系统而言，这类 memory 主要用于提供少量稳定的行为偏好或长期规则，而不是作为核心 project grounding 来源。因此，其读取不应设计成复杂规则引擎，而应作为一个**轻量覆盖层**。

**1. Read Objective**

读取 `Preference / Policy Memory` 的目的，是找出当前这轮运行中少量真正生效的偏好或规则，例如：

- 输出语言偏好
- 文档组织偏好
- 默认 memory 操作规则
- recommendation 或 planning 的长期约束

其作用是对系统行为做轻量调节，而不是替代 `Project Profile`、`Decision` 或 `Action / Execution` 提供核心状态信息。

**2. Read Inputs**

为保持轻量，读取时只需要少量关键信息：

- `project_scope_id`（若已知）
- 当前粗粒度使用场景，例如：
    - `design_doc_writing`
    - `memory_operation`
    - `recommendation_generation`

不建议在当前阶段为此专门解析过多运行时特征。

**3. Read Order**

`Preference / Policy Memory` 的读取建议按以下顺序进行：

1. 先看 **project-level** rules
2. 若没有合适命中，再看 **user-level** preferences
3. 若仍没有，再退回 **system-level** defaults

这意味着：

- project-level 用于当前项目的局部覆盖
- user-level 用于用户的长期稳定偏好
- system-level 用于兜底默认规则

**4. Scene Matching**

在 scope 过滤之后，系统只需做粗粒度场景匹配。

例如：

- 当前在写设计文档
→ 读取 `design_doc_writing` 相关规则
- 当前在做 memory 读取或写入
→ 读取 `memory_operation` 相关规则
- 当前在生成 recommendation
→ 读取 `recommendation_generation` 相关规则

若某条规则与当前场景明显无关，则不应进入当前 run。

**5. Priority Rule**

若同一层 scope 下命中多条规则，系统只需采用简单优先级规则：

- 更具体的规则优先
- 若仍冲突，则按 `priority`
- 若仍冲突，则按 `updated_at`

不需要在当前阶段引入复杂冲突消解逻辑。

**6. Effective Rule Selection**

读取结果应保持小而精。

建议每层只保留少量真正生效的规则，不应把所有命中项都带入当前 run。

通常：

- 当前最重要的 1–3 条规则即可
- 其余规则可忽略，或仅保留为弱参考

**7. Placement into ExecutionContext**

当前真正会影响行为的少量规则，可进入 `RunningState`。

其余补充性规则，如仍需保留，可进入 `SupplementalContext`。

因此，`Preference / Policy Memory` 的读取重点不是“查出所有规则”，而是：

**以最低复杂度找出当前真正生效的少量规则。**

**Summary**

`Preference / Policy Memory` 的读取应遵循以下原则：

- lightweight
- scope-first
- coarse-scene matching
- simple priority ordering
- small effective rule set

它应被实现为一个**轻量覆盖层**，而不是重型规则匹配系统。

### **5.4.3 Persistence Path**

本节定义 `Structured Long-term Memory` 的写入路径。

其目标是让系统能够以 **有选择、类型明确、更新语义清晰** 的方式，将当前 run 或当前 session 中已经稳定下来的高价值信息写入 structured long-term layer，而不是将所有运行产物直接持久化。

该写入路径按以下顺序执行：

1. persistence candidate extraction
2. candidate screening and normalization
3. target memory type resolution
4. existing record lookup
5. persistence action decision
6. durable record shaping
7. write execution
8. post-write result contract

#### 5.4.3.1 Persistence Candidate Extraction

写入起点不是任意中间结果，而是 `persistence candidates`。

candidate 通常来自两类来源：

- **current run outputs**
例如：
    - `final_recommendation`
    - `action_items`
    - 已稳定的 `intermediate_findings`
    - 当前 run 中识别出的 project state update
- **session-level stabilized signals**
例如：
    - 在 `Session Memory` 中已逐步稳定下来的 decision direction
    - 当前 session 内逐步确认的 action continuity
    - 已形成稳定含义的 project phase / bottleneck update

因此，structured persistence 的输入不应直接来自 raw transcript、raw tool outputs 或未收敛推理。

#### 5.4.3.2 Candidate Screening and Normalization

candidate 被提取后，应先做筛选和归一化。

筛选时应重点检查：

- 是否具备明确的 `project_scope`
- 是否已达到可持久化的稳定性
- 是否具有跨 session 复用价值
- 是否属于 structured memory 可承载的 durable signal

归一化后，建议至少明确：

- `project_scope_id`
- candidate source（run-level / session-promotion）
- candidate semantic type
- candidate summary
- confidence / stability level
- proposed memory type（如已可判断）

#### 5.4.3.3 Target Memory Type Resolution

在正式写入之前，系统应判断 candidate 应落入哪类 structured memory。

常见映射包括：

- project-level state update
→ `Project Profile Memory`
- stable decision direction
→ `Decision Memory`
- current action / execution state
→ `Action / Execution Memory`
- stable preference / policy constraint
→ `Preference / Policy Memory`
- long-lived tracked item
→ `Tracking / Watchlist Memory`

若 candidate 无法映射到明确 structured type，则不应强行写入 structured long-term layer。

#### 5.4.3.4 Existing Record Lookup

在决定如何写入之前，系统通常应先读取同 scope、同 type 下的 existing records，用于状态对齐。

读取的重点包括：

- current active record
- latest non-archived record
- 与当前 candidate 明显相关的少量 supporting set

其中 `non-archived` 指仍未归档的记录。

该阶段不应展开大量历史，只需读取足以支撑 write decision 的 existing state。

#### 5.4.3.5 Persistence Action Decision

在 candidate 与 existing records 都准备好之后，系统应判断本次写入应采取哪种 persistence action。

常见 action 包括：

- **create**
当前不存在对应记录，需要新建 durable record
- **update / replace**
当前已有 active record，新 candidate 应更新或替换它
典型适用于：
    - `Project Profile Memory`
    - `Preference / Policy Memory`
- **append + supersede**
新建一条新记录，同时将旧记录标记为“已被替代”
典型适用于：
    - `Decision Memory`
- **status transition**
当前已有 action record，新 candidate 表示该 action 状态推进
典型适用于：
    - `Action / Execution Memory`
- **archive / close**
当前 tracked item 或 action item 已结束，需要退出 active layer
- **no-write**
candidate 不够稳定、与 existing record 重复、或不具备 durable value，因此不写入

#### 5.4.3.6 Durable Record Shaping

在真正写入之前，系统应将 candidate 整形成 durable record，而不是原样落库。

建议至少产出以下字段：

- `memory_id`
- `project_scope_id`
- `memory_type`
- `summary`
- `status`
- `priority`（如适用）
- `created_at / updated_at`
- `source_type`
- `source_run_id` 或 `source_session_id`

以下字段按需要使用：

- `supersedes`
- `superseded_by`
- `linked_decision_id`
- `validity / confidence / stability tags`

其中：

- `supersedes / superseded_by` 用于表达替代关系
- `linked_decision_id` 用于表达 action 与 decision 的关联
- `validity / confidence / stability` 用于描述记录的有效性、可信度和稳定性

写入 structured layer 的应优先是 `summary` 和稳定字段，而不是 raw materials。

#### 5.4.3.7 Write Execution

在完成 action decision 和 durable shaping 后，系统执行实际写入。

该阶段应遵循以下规则：

- 同一 candidate 只能落入一个明确的 structured memory type
- 若 action 为 `update / replace`，应保证 active version 关系清晰
- 若 action 为 `append + supersede`，应建立明确的替代关系
- 若 action 为 `status transition`，应确保 action state machine 合法
- 写入后 active layer 中不应长期保留多个互相冲突的 active records

#### 5.4.3.8 Post-write Result Contract

写入完成后，系统应产生明确的 post-write result，而不是只返回“写入成功”。

建议至少返回：

- `write_action_taken`
- `target_memory_type`
- `project_scope_id`
- `written_record_id`
- `affected_existing_record_ids`
- `supersession_applied`
- `status_transition_applied`
- `no_write_reason`（如适用）

#### Summary

`Structured Long-term Memory` 的 persistence path 应按以下顺序落地实现：

1. `persistence candidate extraction`
2. `candidate screening and normalization`
3. `target memory type resolution`
4. `existing record lookup`
5. `persistence action decision`
6. `durable record shaping`
7. `write execution`
8. `post-write result contract`

其核心目标不是“尽量多写”，而是：

**只将已经稳定、具备 durable value、且适合结构化承载的内容，以正确的 memory type 和正确的更新语义写入 structured long-term layer。**

#### Preference / Policy Memory Write

`Preference / Policy Memory` 的写入也应保持轻量。

对本系统而言，这类 memory 的目标是沉淀少量稳定的行为偏好或长期规则，而不是记录短期局部要求或一次性表达。因此，其写入不应过于激进，而应作为一个**低频、谨慎的长期规则写入路径**。

**1. Write Objective**

写入 `Preference / Policy Memory` 的目的，是保存那些会在后续多轮运行中持续生效的稳定偏好或长期规则，例如：

- 长期输出语言偏好
- 稳定的文档组织偏好
- 当前项目中的长期 memory 操作规则
- recommendation 或 planning 的长期约束

其作用是为后续运行提供一致的行为调节，而不是保存当前回合的临时要求。

**2. Candidate Sources**

`Preference / Policy Memory` 的候选内容通常来自以下来源：

- **用户显式声明的长期偏好**
例如：
    - 以后都用中文写
    - 默认按设计文档风格输出
    - 默认先写目标，再写 policy
- **项目级长期规则**
例如经过多轮讨论后形成的稳定约束：
    - structured memory 默认 summary-first read
    - ambiguous scope 时不直接写入 `RunningState`
- **已被反复验证的稳定偏好**
仅当系统有足够证据表明某项偏好具有持续性时，才可考虑写入

**3. Write Filter**

写入前，系统应先过滤掉不适合进入该层 memory 的内容。

以下内容通常**不应写入**：

- 只对当前回合有用的局部要求
- 一次性的写作偏好
- 尚未稳定的讨论结论
- 会随当前任务快速变化的临时策略
- raw transcript、raw tool outputs、raw evidence

换句话说，只有当一条信息明显属于“以后也应该这样做”时，才适合进入 `Preference / Policy Memory`。

**4. Scope Selection**

写入时，系统应先判断这条偏好或规则属于哪个 scope：

- **project-level**
只对当前项目生效的长期规则
- **user-level**
对该用户的大多数请求都适用的长期偏好
- **system-level**
系统默认规则，通常不应由普通运行自动写入

默认情况下：

- 与当前项目强绑定的规则
→ 写入 project-level
- 与用户整体工作方式相关的长期偏好
→ 写入 user-level
- system-level
→ 只保留给系统预置或管理员维护，不作为普通写入路径

**5. Scene Tagging**

为便于后续读取，写入时应给每条记录附上一个粗粒度使用场景，例如：

- `design_doc_writing`
- `memory_operation`
- `recommendation_generation`

不建议在当前阶段引入过细的场景分类。

粗粒度标签已足以支撑后续轻量读取。

**6. Existing Rule Check**

正式写入前，系统应先检查当前 scope 和当前使用场景下，是否已存在相近的 effective rule。

检查目标包括：

- 是否已有同类规则
- 新 candidate 是否只是对已有规则的轻微改写
- 新 candidate 是否与已有规则冲突
- 当前是否其实不需要新增写入

这一步的目标，是避免：

- 重复规则不断累积
- 冲突规则同时处于 effective 状态
- 局部表达反复制造 durable noise

**7. Write Action**

在当前阶段，`Preference / Policy Memory` 的写入动作应保持简单。

建议只支持以下几种：

- **create**
当前不存在对应规则，新增一条
- **overwrite / selective update**
当前已有规则，新 candidate 明显应替代或更新它
- **archive old conflicting rule**
若旧规则与新规则明显冲突，应让旧规则退出 effective set
- **no-write**
若 candidate 不够稳定、与 existing rule 重复，或只是短期局部要求，则不写入

默认不建议为这类 memory 设计复杂版本链。

**8. Record Shape**

写入 `Preference / Policy Memory` 时，建议至少包含以下字段：

- `scope_type`
- `scope_id`
- `usage_scene`
- `summary`
- `priority`
- `status`
- `updated_at`

如有需要，也可补充：

- `source_run_id` 或 `source_session_id`
- `confidence`
- `stability`

写入内容应以**简短、清晰、可复用的规则摘要**为主，而不是长篇解释。

**9. Write Principle**

`Preference / Policy Memory` 的写入应遵循以下原则：

- low-frequency
- stability-first
- scope-aware
- simple overwrite over complex versioning
- avoid durable noise

它的重点不是“多记一点规则”，而是：

**只沉淀少量真正稳定、以后仍会生效的偏好或长期规则。**

**Summary**

`Preference / Policy Memory` 的写入应按以下思路执行：

1. 识别长期偏好或长期规则候选
2. 过滤掉短期、局部、未稳定内容
3. 选择合适 scope
4. 标记粗粒度使用场景
5. 检查是否已有 effective rule
6. 执行 create / overwrite / archive / no-write
7. 写入简短、稳定的规则摘要

因此，`Preference / Policy Memory` 的写入应被实现为一个**轻量、低频、谨慎的长期规则沉淀路径**。

### **5.4.4 Update Strategy**

本节定义 `Structured Long-term Memory` 的更新语义。

其目标是保证该层 memory 在持续演化过程中，仍能正确表达当前有效状态，并保持版本关系、生命周期状态和 active set 的清晰性。

#### 1. Update Objectives

更新策略主要服务于以下目标：

- 使当前读取结果能够代表当前有效状态
- 防止旧状态长期停留在 active layer
- 在保留必要历史的同时避免 active set 冲突
- 支持项目状态、决策状态和行动状态的自然演化

因此，更新策略的重点不是保留更多历史，而是维持状态清晰和版本有序。

#### 2. Supported Update Actions

`Structured Long-term Memory` 应支持以下更新动作：

- **In-place Update**
在原记录上直接更新字段值，适用于局部状态修正。
- **Replace**
用新版本接管当前有效状态，使旧 active record 退出 active layer。
适用于同一状态对象的新版本替换。
- **Append + Supersede**
新增一条记录，同时将旧记录标记为“已被替代”。
适用于旧记录仍有历史价值的场景。
- **Status Transition**
推动同一对象进入新状态。
适用于 action / execution item 或 tracking item 的状态推进。
- **Archive / Reactivate**
将记录移出 active layer，或重新恢复为 active。
- **No-op / No-update**
当 candidate 与 existing state 实质等价或不够稳定时，不执行写入。

#### 3. Update Action Selection Rules

系统在选择更新动作时，应优先判断：

- 当前 candidate 是旧对象的小幅修正，还是新的当前版本
- 旧记录是否仍有历史保留价值
- active layer 中是否允许多个同类记录并存

建议采用以下规则：

- 小幅修正且无需保留版本分叉
→ `in-place update`
- 新版本接管当前状态
→ `replace`
- 新 decision 取代旧 decision，且旧 decision 仍有历史价值
→ `append + supersede`
- 同一 action / tracking item 的状态推进
→ `status transition`
- 对象退出当前活跃集合
→ `archive`
- 与 existing state 实质重复
→ `no-op`

#### 4. Type-specific Update Semantics

- **Project Profile Memory**
默认使用 `update / replace`，保持当前项目状态的单一表达。
- **Decision Memory**
默认使用 `append + supersede`，保留决策演化链。
- **Action / Execution Memory**
默认使用 `status transition`，维持当前 action continuity。
- **Preference / Policy Memory**
默认使用 `overwrite / selective update`，保持当前有效约束清晰。
- **Tracking / Watchlist Memory**
默认使用 `create / archive / reactivate`，维持 active tracked set 的清晰性。

#### 5. Update Invariants and Failure Prevention

无论采用何种更新动作，更新后都应满足以下不变量：

- active layer 中不应长期保留多个互相冲突的 current records
- superseded decision 不应继续作为 active decision 被读取
- archived item 不应默认参与 active lookup
- action state transition 必须合法
- replace / supersede 后，新旧版本关系必须清晰
- 无实质变化的 candidate 不应反复制造 durable layer 噪声

#### Summary

`Structured Long-term Memory` 不应统一采用 append-only，而应根据 memory type 和状态变化类型，分别采用：

- `in-place update`
- `replace`
- `append + supersede`
- `status transition`
- `archive / reactivate`
- `no-op`

其核心目标是：在持续演化中维持 structured long-term layer 的状态正确、版本清晰和生命周期有序。

### **5.4.5 Type-specific Notes**

本节对不同 `Structured Long-term Memory` type 的主要职责、默认读取重点、默认更新语义和关键边界做简要说明。

#### 5.4.5.1 Project Profile Memory

`Project Profile Memory` 主要表达当前项目的整体状态，例如当前阶段、当前 bottleneck 和当前重点方向。

默认读取重点应为当前 active profile summary。

默认更新语义以 `update / replace` 为主。

其关键边界是：不应将其写成项目全历史堆积层，也不应在 active layer 中并列保留多个冲突 profile。

#### 5.4.5.2 Decision Memory

`Decision Memory` 主要表达已经形成并具有持续意义的稳定 decision。

默认读取重点应为 active decision summary。

默认更新语义应为 `append + supersede`，以保留决策演化链。

其关键边界是：不应将局部讨论、探索性想法或未收敛判断直接写成 decision memory。

#### 5.4.5.3 Action / Execution Memory

`Action / Execution Memory` 主要表达当前 action items、执行状态和推进情况。

默认读取重点应为 active-like action summaries。

默认更新语义应以 `status transition` 为主。

其关键边界是：不应让已完成、已取消或已失效的 action 长期停留在 active set，也不应将同一 action 的状态推进不断写成新的独立 record。

#### 5.4.5.4 Preference / Policy Memory

`Preference / Policy Memory` 主要表达当前仍有效的偏好、约束或长期规则。

默认读取重点应为 current effective preference / policy summaries。

默认更新语义应以 `overwrite / selective update` 为主。

其关键边界是：不应将短期、局部、一次性的表达沉淀为长期规则，也不应长期并列保留多个冲突的 active policy。

#### 5.4.5.5 Tracking / Watchlist Memory

`Tracking / Watchlist Memory` 主要表达当前仍在跟踪或持续关注的对象集合。

默认读取重点应为 active tracked items。

默认更新语义应以 `create / archive / reactivate` 为主。

其关键边界是：不应让 stale tracked items 无限停留在 active set，也不应让 tracking layer 退化成无边界的历史清单。

#### Summary

不同 structured memory type 共享同一套治理框架，但在默认读取重点、更新语义和边界控制上仍需区别对待：

- `Project Profile Memory` 强调当前项目状态
- `Decision Memory` 强调稳定决策及其替代关系
- `Action / Execution Memory` 强调当前执行推进
- `Preference / Policy Memory` 强调当前有效约束
- `Tracking / Watchlist Memory` 强调 active tracking set 的清晰性

### 5.4.6 Guardrails, Invariants, and Failure Handling

本节定义 `Structured Long-term Memory` 的写入边界、active set 不变量和失败处理规则。

其目的不是重复前文的 read / persistence / update 流程，而是明确：

- 什么内容允许进入 structured long-term layer
- 写入后哪些状态必须成立
- 当检测到异常状态时，系统应如何处理

#### 1. Write Admission Guardrails

并非所有 candidate 都允许写入 `Structured Long-term Memory`。

一条 candidate 只有同时满足以下条件，才允许进入该层 memory：

**1.1 Scope Must Be Resolved**

candidate 必须具有明确 scope，例如：

- project-level
- user-level
- system-level（如适用）

若 `project_scope` 未解析清楚，则不允许写入 project-scoped structured memory。

**1.2 Memory Type Must Be Resolved**

candidate 必须能够映射到明确的 structured memory type，例如：

- `Project Profile Memory`
- `Decision Memory`
- `Action / Execution Memory`
- `Preference / Policy Memory`
- `Tracking / Watchlist Memory`

若无法明确类型，则不应强行写入 structured layer。

**1.3 Candidate Must Be Stable Enough**

candidate 必须达到足够稳定性。

以下内容不应进入 structured layer：

- unresolved reasoning fragments
- 探索性想法
- 临时讨论结论
- 短期 session continuity 信号
- 低价值局部细节

**1.4 Candidate Must Have Durable Value**

candidate 必须具有跨 session 复用价值。

若内容只对当前 session 或当前单轮运行有帮助，则不应写入 structured long-term layer。

**1.5 Raw Materials Must Not Be Persisted Directly**

以下内容不得直接写入 structured layer：

- raw transcript
- raw tool outputs
- raw evidence
- raw retrieval payloads

写入 structured layer 的内容应优先是 summary 和稳定字段，而不是原始材料。

**1.6 No-write on Admission Failure**

若 candidate 未通过上述任一 admission check，则必须执行 `no-write`，而不是“先写进去以后再清理”。

---

#### 2. Active-set Invariants

structured write 完成后，active layer 必须满足以下不变量。

**2.1 Active Records Must Be Scope-consistent**

所有 active records 必须与其所属 scope 一致。

不允许不同 project 的 active records 在同一 current grounding 中混用。

**2.2 Active Project Profile Must Be Unambiguous**

同一 `project_scope` 下，不应长期存在多个互相冲突的 active project profiles。

若存在新 profile 接管当前状态，旧 profile 必须退出 active layer。

**2.3 Active Decision Set Must Be Clear**

同一 `project_scope` 下，active decision set 必须保持清晰。

若设计上默认只允许单一 active decision，则不得同时保留多个互相冲突的 active decisions。

被替代的 decision 不应继续参与 active lookup。

**2.4 Active Action Set Must Reflect Current Execution State**

active action set 只应包含当前仍有效的 actions。

以下 action 不应继续停留在 active set：

- done
- cancelled
- invalidated

同一 action object 不应同时存在多个冲突状态。

**2.5 Effective Preference / Policy Set Must Be Non-conflicting**

同一 scope、同一使用场景下，不应长期并列保留多个互相冲突的 active preference / policy rules。

若新规则已接管当前有效行为约束，旧规则必须退出 effective set。

**2.6 Archived or Superseded Records Must Not Participate in Default Active Read**

以下记录不应默认参与 active read：

- archived records
- superseded records
- stale records

它们可以作为历史记录保留，但不应继续作为当前有效状态参与默认读取。

---

#### 3. Failure Detection Points

系统应在以下关键点执行检测，而不是等到问题扩散后再修补。

**3.1 Before Write**

在实际写入前检查：

- scope 是否已解析
- target memory type 是否明确
- candidate 是否稳定
- candidate 是否具备 durable value
- candidate 是否属于 raw materials

**3.2 After Action Decision**

在确定 `create / update / replace / append + supersede / status transition / archive` 之后，检查：

- 动作是否与 memory type 匹配
- 是否会引入多个冲突 active records
- 是否需要 old active record 退出 active layer
- 是否需要建立 supersession linkage

**3.3 After Write**

在写入完成后检查：

- active set 是否仍满足不变量
- 是否出现多个冲突 active records
- 是否存在 superseded record 仍停留在 active read path
- 是否存在 archived item 仍被默认读取

---

#### 4. Failure Handling Rules

当检测失败时，系统应执行明确处理，而不是静默接受异常状态。

**4.1 Admission Failure**

若 candidate 未通过 admission check：

- 执行 `no-write`
- 记录 failure reason
- 不得绕过 guardrail 强行写入 structured layer

**4.2 Scope Failure**

若 scope unresolved 或 scope inconsistent：

- 不执行 project-scoped persistence
- 必要时退化为 session-only handling
- 不得将该 candidate 写入错误 project

**4.3 Conflict in Active Set**

若写入后检测到多个冲突 active records：

- 优先阻止新结果进入 active layer
- 或自动使旧 record 退出 active 状态
- 若无法可靠修复，则标记为 persistence conflict，进入 repair path

**4.4 Missing Supersession Handling**

若新 decision 已形成，但旧 decision 未退出 active layer：

- 不允许新旧 decision 同时作为 active decision 使用
- 必须补齐 supersession linkage，或阻止新 decision 成为 active

**4.5 Invalid State Transition**

若 action / execution item 的状态迁移不合法：

- 不执行该次状态更新
- 保留 existing valid state
- 记录 invalid transition reason

**4.6 Duplicate or Low-value Durable Writes**

若 candidate 与 existing state 实质重复，或 durable value 不足：

- 执行 `no-write`
- 不得为了“多存一些”制造 durable noise

---

#### Summary

`Structured Long-term Memory` 的实现必须满足以下三类约束：

- **Write Admission Guardrails**
只有 scope 明确、类型明确、稳定且具备 durable value 的 candidate 才允许写入
- **Active-set Invariants**
写入后 active layer 必须保持 scope 一致、状态清晰、无冲突、无失效记录混入
- **Failure Handling Rules**
检测失败时必须执行 `no-write`、退出 active、补齐替代关系或拒绝非法状态迁移

因此，本节的作用不是补充概念说明，而是为 structured long-term layer 提供一组实现时必须遵守的硬约束。

---

## 5.5 Research Knowledge Memory Policies

### 5.5.1 Quality Goals for Research Knowledge Memory

本节明确本系统对高质量 `Research Knowledge Memory` 的评价标准。

对于 **Vertical AI Research & Action Agent** 而言，`Research Knowledge Memory` 的目标不是保存更多原始资料，而是沉淀可复用的研究知识单元，并在后续任务中被有效召回和有边界地使用。

高质量的 `Research Knowledge Memory` 应满足以下目标。

**1. Retrieval Usefulness**

该层 memory 应能在后续 research、planning 和 recommendation 中被有效召回，并对当前任务产生实际帮助。

**2. Knowledge Granularity**

知识单元的粒度应适中。

系统应优先沉淀：

- method summary
- topic summary
- comparison summary
- distilled conclusion
- source-backed engineering observation

而不是过长原文或过碎片段。

**3. Source Traceability**

每条 knowledge unit 都应具有明确来源。

系统应能够追溯该知识来自哪篇 paper、哪个 repository、哪篇 article / document，或哪次研究结论整理。

**4. Freshness Awareness**

该层 memory 应能表达知识的新旧程度，并支持系统在读取时考虑 freshness，区分：

- 当前仍较可靠的知识
- 可能已经过时的知识
- 需要 refresh 或降权的知识

**5. Low Redundancy**

该层 memory 不应重复沉淀大量语义接近的 knowledge units。

系统应支持必要的 dedupe、merge 和 prune。

**6. Durable Value**

只有具备跨任务、跨 session 复用价值的研究结果，才适合进入 `Research Knowledge Memory`。

只对当前单轮 research 有帮助的临时观察，不应进入该层 memory。

#### Summary

综上，高质量的 `Research Knowledge Memory` 应能够：

- 被后续任务有效召回
- 以合适粒度存储知识单元
- 保持来源可追溯
- 对 freshness 保持敏感
- 控制重复和冗余
- 只沉淀具有 durable value 的研究知识

后续各项 `Research Knowledge Memory` policy，均以实现上述目标为导向。

### 5.5.2 Knowledge Unit and Content Boundary

#### 5.5.2.1 Definition of Knowledge Unit

在本系统中，`Knowledge Unit` 指一个**可被独立召回、独立理解、独立复用**的研究知识单元。

它不是原始资料片段，也不是当前 run 的临时中间结果，而是从 research 过程中提炼出来的、具有后续复用价值的知识摘要。

一个合格的 `Knowledge Unit` 应满足以下条件：

- 表达一个相对完整的知识点
- 被单独召回时，基本可以被理解和使用
- 具有明确来源或可追溯来源
- 对后续 research、planning 或 recommendation 仍有复用价值

`Knowledge Unit` 的典型类型包括：

- `method_summary`
- `topic_summary`
- `comparison_summary`
- `distilled_conclusion`
- `engineering_observation`
- `paper_summary`

因此，`Research Knowledge Memory` 中存储的对象，不应理解为“检索切片”，而应理解为“提炼后的知识单元”。

#### 5.5.2.2 Knowledge Unit Minimum Structure

为支持后续过滤、召回、去重、刷新和治理，一条 `Knowledge Unit` 在存储上至少应包含两部分：

- **retrieval-visible content**
- **governance metadata**

**A. Retrieval-visible Content**

这是该 knowledge unit 在读取阶段会被直接检索、排序和注入上下文的核心内容。

建议至少包括：

- `title`
- `summary`

其中：

- `title` 应能清楚概括该知识点
- `summary` 应围绕单一主点展开，并能够在被单独召回时基本被理解和使用

默认情况下，`title` 和 `summary` 应作为 knowledge unit 的主要语义表示，用于后续向量化、召回和 rerank。

**B. Governance Metadata**

这是该 knowledge unit 在访问控制、生命周期治理和质量控制中使用的辅助字段。

这部分 metadata 不应替代核心内容本身，但应支持：

- pre-filter
- source traceability
- freshness handling
- dedupe / merge
- pruning / archive

因此，`Knowledge Unit` 不应被设计为只有一段 summary 的轻量文本对象，而应被设计为：

**由可检索内容和可治理 metadata 共同构成的知识单元。**

#### 5.5.2.3 Knowledge Unit Metadata

`Knowledge Unit` 的 metadata 应至少覆盖以下几类信息。

**A. Identity and Access Scope**

用于标识该 knowledge unit 及其访问边界：

- `knowledge_id`
- `owner_user_id`
- `project_scope_id`（可空）
- `visibility_scope_effective`

其中：

- `owner_user_id` 用于表达归属
- `project_scope_id` 用于表达该知识是否与某个项目强相关
- `visibility_scope_effective` 用于读取前过滤，而不是在召回后再处理权限问题

**B. Content and Classification**

用于描述该知识单元的内容类型和主题归属：

- `knowledge_type`
- `topic_tags`
- `language`

其中：

- `knowledge_type` 用于区分该 unit 是 `method_summary`、`topic_summary`、`comparison_summary`、`engineering_observation` 等
- `topic_tags` 用于后续 filter 和 retrieval 辅助

**C. Source Traceability**

用于保证知识来源可追溯：

- `source_type`
- `source_refs`
- `derived_from_run_id`（可选）

系统默认应要求 knowledge unit 具备来源信息。

没有来源或无法追溯来源的内容，不应直接进入 `Research Knowledge Memory`。

**D. Lifecycle and Quality**

用于支持 freshness、refresh 和 pruning：

- `status`
- `created_at`
- `updated_at`
- `freshness_bucket`
- `confidence`
- `stability`

其中：

- `status` 用于区分 active / archived / deprecated
- `freshness_bucket` 用于表达该知识的新旧敏感性
- `confidence` 和 `stability` 用于表达该知识的当前可靠程度

**E. Dedupe and Merge Support**

用于控制重复知识单元和 canonical 归并：

- `dedupe_key`
- `canonical_knowledge_id`
- `is_canonical`
- `merged_into_id`（可选）

这类字段的作用不是增加检索复杂度，而是保证知识层长期可治理、可收敛，而不会不断膨胀为重复摘要集合。

**F. Retrieval vs Filter Usage**

从读取实现的角度看，metadata 字段应区分为两类：

1. **Retrieval-visible Fields**

默认参与语义召回或 rerank 的字段：

- `title`
- `summary`
1. **Filter / Governance Fields**

默认用于 pre-filter、post-filter 或 lifecycle control 的字段：

- `owner_user_id`
- `project_scope_id`
- `visibility_scope_effective`
- `knowledge_type`
- `topic_tags`
- `source_type`
- `status`
- `freshness_bucket`

系统不应将全部 metadata 一起向量化，而应明确哪些字段用于语义检索，哪些字段只用于过滤和治理。

#### 5.5.2.4 Granularity Rules

`Knowledge Unit` 的粒度应按**知识点完整性和复用性**定义，而不是按长度机械定义。

一条 knowledge unit 最好只表达一个相对完整的知识点，例如：

- 一个方法总结
- 一个比较结论
- 一个带来源的工程观察
- 一个主题下的单一子结论

**A. Core Rule**

系统应优先保证：

- 一条 unit 表达一个主点
- 被单独召回时基本可理解
- 后续可独立复用、独立去重、独立更新

如果一条内容同时覆盖多个并列主点，则通常不适合作为单一 knowledge unit 持久化。

**B. Oversized Unit**

若一条 knowledge unit 过大，常见表现包括：

- 同时回答多个不同问题
- 同时包含多个并列结论
- 难以赋予单一 `knowledge_type`
- 召回后仍需要二次拆解才能使用

过大的 unit 会带来以下问题：

- 召回结果不够精准
- 一条 unit 中混入过多无关内容
- 去重和 merge 更困难
- 局部知识更新时只能整体重写
- 后续复用时难以只取其中一个子点

若出现这种情况，系统应优先：

- 拆分为多个更小的 knowledge units
- 或拒绝直接写入，要求重新 distill

**C. Undersized Unit**

若一条 knowledge unit 过小，常见表现包括：

- 只是零散片段或单句观察
- 脱离原始上下文后难以理解
- 缺乏完整主点或清晰标题
- 需要和多条其他 unit 一起拼接后才能使用

过小的 unit 会带来以下问题：

- 召回结果碎片化
- 单条 unit 难以独立使用
- metadata 和治理成本升高
- 后续 retrieval 需要拼装多个碎片才能形成有效上下文

若出现这种情况，系统应优先：

- 与相邻知识点合并
- 或拒绝直接写入，避免知识层碎片化

**D. Practical Heuristics**

在实现中，可采用以下经验法则判断粒度是否合适：

- 一条 unit 应能用一个清晰标题概括
- 一条 unit 的 `summary` 应围绕单一主点展开
- 若一条内容难以赋予单一 `knowledge_type`，通常说明粒度过大
- 若一条内容脱离来源上下文后几乎无法理解，通常说明粒度过小

因此，粒度问题的核心不是“多长”，而是：

**它是否仍然是一个单一、完整、可复用的知识点。**

#### 5.5.2.5 Why It Is Not Defined by Token Size

`Knowledge Unit` 不应按 token 数或字符数机械定义。

原因在于，长度只能反映文本大小，不能反映语义完整性、复用价值和治理可行性。

同样长度的两段内容，可能出现完全不同的情况：

- 一段较短文本已经足以表达一个完整方法总结
- 一段同样长度的文本却混杂了多个并列结论
- 一段较长文本可能只是同一知识点的完整展开
- 另一段较长文本则可能仍然是多个碎片的拼接

因此，`Knowledge Unit` 的核心问题不是“多长”，而是：

- 是否表达单一主点
- 是否可被独立理解
- 是否可被独立复用
- 是否便于去重、更新和治理

token 长度在实现中仍可作为软约束，例如：

- 识别明显过长、可能需要拆分的 candidate
- 避免单条 summary 过短而失去独立可理解性

但它不应成为 `Knowledge Unit` 的主定义方式。

系统不应采用“达到多少 token 就切分、低于多少 token 就合并”的机械规则，而应优先基于知识点完整性做判断。

#### 5.5.2.6 Comparison with RAG Chunk

`Knowledge Unit` 与 RAG 中的 `chunk` 有相似之处，但两者不应等同。

**A. Similarity**

两者都需要考虑粒度问题。

过大时会影响召回精度，过小时会导致结果碎片化。

因此，它们都需要在“检索可用性”和“上下文完整性”之间取得平衡。

**B. Difference in Purpose**

RAG chunk 的目标主要是：

- 为原始资料建立可检索切片
- 在生成阶段提供原文上下文片段

而 `Knowledge Unit` 的目标是：

- 存储提炼后的研究知识
- 为后续 research、planning 和 recommendation 提供可复用知识单元
- 支持长期治理、去重、刷新和降权

因此，RAG chunk 更偏向**原始资料切分对象**，而 `Knowledge Unit` 更偏向**提炼后的知识对象**。

**C. Difference in Source Form**

RAG chunk 通常直接来自原始资料切分，例如：

- paper 原文片段
- document 段落
- web page chunk
- repo 文档切片

而 `Knowledge Unit` 应来自：

- 对原始资料的提炼
- 对多来源研究结果的总结
- 对方法、主题或比较结论的抽象

因此，`Knowledge Unit` 不应直接等同于“切分后的 retrieval chunk”。

**D. Difference in Granularity Principle**

RAG chunk 的粒度通常更受：

- chunk size
- overlap
- retrieval coverage

等因素影响。

而 `Knowledge Unit` 的粒度主要受：

- 单一知识点完整性
- 独立可理解性
- 独立复用性
- 后续治理便利性

等因素影响。

因此，RAG chunk 更偏“切得是否适合检索原文”，而 `Knowledge Unit` 更偏“是否已经是一个合格的知识单元”。

**E. Difference in Governance Requirement**

RAG chunk 主要服务 retrieval，本身通常不承担复杂治理职责。

而 `Knowledge Unit` 进入 `Research Knowledge Memory` 后，还需要支持：

- source traceability
- freshness handling
- dedupe / merge
- canonical selection
- refresh / aging / pruning

因此，`Knowledge Unit` 在设计上必须比普通 chunk 更可治理。

**Summary**

可以将两者的关系概括为：

- `RAG chunk`：原始资料的可检索切片
- `Knowledge Unit`：提炼后的可复用知识单元

因此，`Knowledge Unit` 更接近：

**经过提炼、可长期复用、可治理的语义化知识对象**，而不是原始资料切分片段。

#### 5.5.2.7 Write Admission and Content Boundary

并非所有 research 过程中的产出都适合进入 `Research Knowledge Memory`。

一条内容只有同时满足以下条件，才适合作为 `Knowledge Unit` 被持久化：

**A. It Must Be a Distilled Knowledge Unit**

写入对象必须是提炼后的知识单元，而不是原始资料本身。

以下内容不应直接写入：

- paper / article / document 原文
- repo 原始内容
- 原始检索片段
- raw tool outputs

`Research Knowledge Memory` 存储的是从这些材料中提炼出来的知识，而不是这些材料本身。

**B. It Must Express a Reusable Knowledge Point**

写入对象应表达一个相对完整、后续仍可复用的知识点。

若内容只对当前单轮 research 有帮助，或只服务当前 session continuity，则不应写入该层 memory。

适合进入的典型内容包括：

- method summary
- topic summary
- comparison summary
- distilled conclusion
- source-backed engineering observation
- paper summary

**C. It Must Be Independently Understandable**

写入对象被单独召回时，应基本能够被理解和使用。

若内容脱离当前 run 上下文后难以理解，或仍依赖大量隐含背景，则不应直接作为 knowledge unit 写入。

**D. It Must Have Traceable Sources**

默认情况下，knowledge unit 应具备可追溯来源。

没有来源、无法追溯来源，或仅基于未验证猜测形成的内容，不应直接进入 `Research Knowledge Memory`。

**E. It Must Not Belong to Other Memory Layers**

以下内容不应误写入 `Research Knowledge Memory`：

- `Session Memory` 中的短期会话摘要
- `Structured Long-term Memory` 中的项目状态、decision、action 或 policy records
- 当前 run 的临时 scratchpad
- unresolved reasoning fragments

也就是说，`Research Knowledge Memory` 只存储研究知识，不存储短期会话连续性，也不存储当前状态记录。

**F. Action on Admission Failure**

若 candidate 未满足上述任一条件，系统应：

- 执行 `no-write`
- 或要求进一步 distill / split / merge 后再尝试写入

系统不应为了“先存着以后再说”而放宽写入边界，否则该层 memory 很快会被低价值内容污染。

#### 5.5.2.8 Examples

以下示例用于说明什么样的内容适合作为 `Knowledge Unit`，什么样的内容不适合。

**A. Good Example: Method Summary**

**Title**

`Self-RAG Core Mechanism`

**Summary**

`Self-RAG introduces retrieval and critique tokens so that the model can decide when to retrieve and how to evaluate retrieved evidence during generation.`

**Why It Is a Good Knowledge Unit**

- 表达单一主点
- 可被独立理解
- 可在后续关于 Self-RAG、adaptive retrieval 或 retrieval control 的任务中复用
- 可附带明确来源

---

**B. Good Example: Comparison Summary**

**Title**

`Workflow-driven Outer Orchestration vs Fully Autonomous Agent`

**Summary**

`For engineering decision support systems, workflow-driven outer orchestration is usually easier to control, observe, and debug than a fully autonomous agent design, while still allowing adaptive reasoning inside bounded execution stages.`

**Why It Is a Good Knowledge Unit**

- 是一个清晰的比较结论
- 后续可用于 architecture discussion、planning 或 recommendation
- 粒度适中
- 可附带来源

---

**C. Bad Example: Raw Material Fragment**

**Content**

`Section 3.2 of the paper explains ... [long raw paragraph copied from source]`

**Why It Is Not a Good Knowledge Unit**

- 它是原始资料片段，不是提炼后的知识
- 被单独召回时未必清楚表达一个独立知识点
- 更适合留在原始资料或检索结果中，而不是写入 `Research Knowledge Memory`

---

**D. Bad Example: Temporary Scratchpad**

**Content**

`Maybe workflow is better, but multi-agent might also work. Need to think more.`

**Why It Is Not a Good Knowledge Unit**

- 这是未收敛判断
- 没有明确知识点
- 没有来源支撑
- 只适合留在当前 run 的 scratchpad 或临时 reasoning 中

---

**E. Bad Example: Oversized Unit**

**Title**

`All Key Ideas About Self-RAG`

**Summary**

同时包含：

- Self-RAG 的机制
- Self-RAG 与 RAG-Fusion 的区别
- Self-RAG 的优点
- Self-RAG 的局限
- Self-RAG 的工程适用场景

**Why It Is Not a Good Knowledge Unit**

- 同时覆盖多个并列知识点
- 后续召回时不够精准
- 不利于去重、更新和复用

更合理的做法是拆分为多个独立 knowledge units。

---

**F. Bad Example: Undersized Unit**

**Title**

`Critique Token`

**Summary**

`Used for critique.`

**Why It Is Not a Good Knowledge Unit**

- 过于碎片化
- 缺乏足够上下文
- 被单独召回时难以独立理解和使用

更合理的做法是将其扩展为一个完整知识点，或与相邻内容合并。

---

**Summary**

一个合格的 `Knowledge Unit` 应当：

- 表达单一、完整的知识点
- 可被独立理解和复用
- 具有可追溯来源
- 不属于 raw materials、短期会话摘要或当前状态记录

不满足这些条件的内容，不应直接进入 `Research Knowledge Memory`。

### 5.5.3 Read Path

#### **5.5.3.1 Read Objective**

`Research Knowledge Memory` 的读取目标，是优先复用系统已沉淀的研究知识，而不是每次都从原始资料重新开始检索和总结。

该层 memory 主要用于为当前 run 提供：

- topic background
- method understanding
- comparison basis
- prior research conclusions
- source-backed engineering observations

因此，读取 `Research Knowledge Memory` 的核心目的不是“找原始资料”，而是：

**在当前任务需要时，召回少量已经提炼好的、可复用的知识单元。**

与 retrieval tool 相比，`Research Knowledge Memory` 提供的是更高层、已加工的知识对象；retrieval tool 提供的是原始 evidence 或新的外部资料。

两者职责不同：

- `Research Knowledge Memory` 负责复用已有知识，避免重复研究
- retrieval tool 负责在已有知识不足时补充新的 evidence、更新信息或更细粒度材料

因此，本系统默认应优先尝试复用 `Research Knowledge Memory`；当已有 knowledge units 无法充分支持当前任务时，再按需调用 retrieval tool 获取补充 evidence。

这种设计的主要价值在于：

- 降低重复检索、重复阅读和重复总结的成本
- 提高当前 run 的知识复用效率
- 为 planning、research 和 recommendation 提供更稳定的一致性输入
- 将 retrieval tool 保留给真正需要 fresh evidence 或额外细节的场景

`Research Knowledge Memory` 默认不承担以下职责：

- project grounding
- session continuity recovery
- current decision / action state recovery
- 原始资料存储

这些需求应分别由 `Structured Long-term Memory`、`Session Memory` 或 retrieval / source access path 承担。

综上，`Research Knowledge Memory` 的读取目标可以概括为：

**优先复用已沉淀的研究知识；仅在这些知识不足时，再通过 retrieval tool 获取新的 evidence。**

#### **5.5.3.2 Read Scenarios**

`Research Knowledge Memory` 的读取应按**读取场景**组织，而不是机械按 HLD stage 逐项展开。

每个读取场景再映射到常见的 HLD stage。

**A. Early Knowledge Bootstrap**

当用户请求明显属于知识密集型主题时，系统可在 `Load Relevant Context & Memory` 阶段轻量读取少量高相关 knowledge units，作为当前 run 的背景补充。

这一步的目标是：

- 判断当前主题是否已有可复用知识
- 为后续 planning 或 research 提供初始背景
- 避免系统在已有知识充分时仍从零开始检索和总结

该场景通常发生在：

- `Load Relevant Context & Memory`

需要强调的是，这一步应保持轻量，只做 small top-k summary-level prefetch，不应在该阶段做深度知识召回。

---

**B. Planning-time Background Enrichment**

当系统在做 task decomposition、plan shaping 或 comparison framing 时，可能需要先补充 topic background、method understanding 或已有研究结论。

该场景的典型用途包括：

- 先补方法背景，再决定 research 计划
- 先补已有 topic knowledge，再细化 sub-questions
- 先补已有 comparison basis，再确定比较维度

该场景通常发生在：

- `Planning and Decomposition`

---

**C. Research-time Knowledge Recall**

当系统在 research 过程中遇到需要已有知识支持的子问题时，应读取 `Research Knowledge Memory`。

该场景的典型用途包括：

- 复用某个 topic 的已有总结
- 复用某个方法的已有理解
- 复用 framework / architecture 的比较摘要
- 复用已有 source-backed engineering observations

该场景通常发生在：

- `Research Execution`

这是 `Research Knowledge Memory` 最主要的读取场景。

---

**D. Recommendation-time Support**

当系统在形成 recommendation、trade-off analysis 或 structured conclusion 时，可能需要复用已有 research knowledge 作为支持材料。

该场景的典型用途包括：

- 复用 prior conclusions
- 复用 comparison summaries
- 复用 engineering observations 作为 recommendation support
- 复用 topic-level knowledge 作为 conclusion framing 的背景

该场景通常发生在：

- `Generate Structured Conclusion`
- `Return Structured Output`

---

**E. Boundary of Read Scenarios**

`Research Knowledge Memory` 默认不应用于以下场景：

- 恢复当前 project profile
- 恢复当前 active decision
- 恢复当前 action status
- 恢复当前 session working summary

这些需求不属于 research knowledge recall，而属于：

- `Structured Long-term Memory`
- `Session Memory`

因此，`Research Knowledge Memory` 的读取场景应聚焦于：

**补充可复用知识，而不是恢复当前状态。**

#### **5.5.3.3 End-to-End Read Flow**

`Research Knowledge Memory` 的读取应按以下步骤执行。

其目标是：在受控范围内，从已有 knowledge units 中召回少量与当前任务真正相关、可复用、可追溯的知识单元，并将其整理为当前 run 可直接使用的输入。

**Step 1. Determine Whether Knowledge Recall Is Needed**

系统先判断当前 request 是否真的需要读取 `Research Knowledge Memory`。

只有当当前请求明显需要：

- topic background
- method understanding
- comparison basis
- prior research conclusions
- engineering observations

时，才进入后续流程。

若当前请求主要是在恢复：

- project profile
- active decision
- action status
- session continuity

则应分别转向：

- `Structured Long-term Memory`
- `Session Memory`

**Output**

- `knowledge_recall_needed`
- `knowledge_need_type`

---

**Step 2. Build Retrieval Query**

当确认需要 knowledge recall 后，系统构造本次读取的 retrieval query。

query 的来源可包括：

- 原始 user query
- planning 生成的 sub-question
- LLM 重写后的更聚焦 query

建议输出：

- `retrieval_query`
- `knowledge_need_type`
- optional `preferred_knowledge_types`
- optional `preferred_topic_tags`

---

**Step 3. Apply Pre-retrieval Filters**

在执行语义召回之前，系统先按 metadata 做硬过滤。

默认 pre-filter 应至少包含：

- `owner_user_id = current_user_id`
- `visibility_scope_effective` 满足当前读取范围
- `status = active`

必要时再加：

- `project_scope_id = current_project_scope_id`
- `knowledge_type in preferred_knowledge_types`
- `topic_tags overlap preferred_topic_tags`
- `source_type` 限制

**Output**

- `filtered_candidate_pool`

若过滤后为空，则返回 `no_local_knowledge_hit`，由上层决定是否调用 retrieval tool。

---

**Step 4. Run Semantic Recall**

系统在 `filtered_candidate_pool` 上执行向量相似度召回。

召回对象默认基于 knowledge unit 的：

- `title`
- `summary`

建议采用 bounded recall，先取 small top-N candidates，而不是无边界搜索。

**Output**

- `recalled_candidates`
- optional recall scores

---

**Step 5. Post-retrieval Filtering and Ranking**

对 `recalled_candidates`，系统不应直接按召回分数使用，而应先做后处理。

由于 canonical 收敛已在写路径完成，默认读路径不再单独执行 canonical resolution。

**Step 5.1 Hard Exclusion**

系统先排除不应进入默认读取集合的候选。

默认排除条件至少包括：

- `status != active`
- `visibility_scope_effective` 不满足当前读取范围
- 当前场景要求 source-backed knowledge，但 `source_refs` 缺失
- freshness 明显不可接受，且当前任务对 freshness 敏感

若系统仍保留少量 merge 历史记录，则：

- `merged_into_id != null` 的记录默认也应排除

**Step 5.2 Quality-aware Ranking**

在完成硬过滤后，系统对剩余候选排序。

排序信号应至少包括：

- semantic relevance
- `freshness_bucket`
- `confidence`
- `stability`
- source completeness
- `updated_at`

若结果中仍存在明显重复的候选，系统应只保留质量更高的一条。

**Step 5.3 Final Bounded Selection**

排序完成后，系统执行 bounded top-k selection。

默认应：

- 保持 top-k 受控
- 避免多个高度相近 unit 同时进入当前 run
- 根据读取场景调整注入数量

**Output**

- `selected_knowledge_units`

---

**Step 6. Decide Whether Local Knowledge Is Sufficient**

在 `selected_knowledge_units` 形成后，系统应判断本地 knowledge 是否足以支持当前任务。

建议至少判断：

- 命中数量是否足够
- 覆盖主题是否足够
- freshness 是否可接受
- 是否缺少关键 source-backed support

**Output**

- `knowledge_sufficiency: sufficient | partial | insufficient`

若结果为 `partial` 或 `insufficient`，则系统应允许后续调用 retrieval tool 获取新的 evidence。

---

**Step 7. Shape Selected Knowledge into Run-ready Input**

系统将 `selected_knowledge_units` 整形成适合当前 run 使用的输入。

默认应以 summary-level 形式进入，而不是展开原始来源内容。

建议每条输出至少包含：

- `knowledge_id`
- `title`
- `summary`
- `knowledge_type`
- `topic_tags`
- `source_refs`
- optional `freshness_bucket`

**Output**

- `run_ready_knowledge_inputs`

---

**Step 8. Place into ExecutionContext**

最后，系统决定这些 `run_ready_knowledge_inputs` 如何进入当前 `ExecutionContext`。

通常：

- 当前问题强依赖的少量核心 knowledge units
→ 放入 `RunningState`
- 次级支持材料
→ 放入 `SupplementalContext`

默认不应将全部 recalled knowledge 一次性塞入 `RunningState`。

---

**Step 9. Handoff to Retrieval Tool When Needed**

若 Step 6 判断为 `partial` 或 `insufficient`，则上层流程可继续调用 retrieval tool 获取新的原始 evidence。

此时两者分工如下：

- `Research Knowledge Memory`：提供已有背景知识和已有结论复用
- retrieval tool：提供新 evidence、更细节材料和更高 freshness 的外部资料

**Summary**

`Research Knowledge Memory` 的读取流程可概括为：

1. 判断是否需要 knowledge recall
2. 构造 retrieval query
3. 先做 pre-filter
4. 再做向量召回
5. 做后过滤、排序和 bounded selection
6. 判断本地 knowledge 是否足够
7. 将结果整形成 run-ready input
8. 放入 `RunningState` 或 `SupplementalContext`
9. 若不足，则继续调用 retrieval tool 补充 evidence

其重点不是“召回尽可能多的知识”，而是：

**在受控范围内，优先复用少量高价值 knowledge units；只有在这些知识不足时，再继续检索新的 evidence。**

#### 5.5.3.4 Retrieval Query Construction

`Research Knowledge Memory` 的读取不应机械复制原始 user query，而应构造更贴近当前 knowledge need 的 retrieval query。

query 的来源可包括：

- 当前 user query
- planning / decomposition 产生的 sub-question
- LLM 重写后的更聚焦 query

构造 query 时，应尽量表达：

- 当前想找的 topic
- 当前想比较的方法或方案
- 当前需要复用的已有研究结论

其目标是提高后续 semantic recall 的命中质量。

---

#### 5.5.3.5 Filter-first Semantic Recall

`Research Knowledge Memory` 默认采用 **filter-first semantic recall**。

系统不应直接在全量 knowledge units 上做向量检索，而应先按 metadata 做过滤，再执行语义召回。

默认 pre-filter 应至少考虑：

- `owner_user_id`
- `visibility_scope_effective`
- 必要时 `project_scope_id`
- `status = active`

必要时，也可进一步按以下字段缩小候选集合：

- `knowledge_type`
- `topic_tags`
- `source_type`

过滤完成后，再基于 knowledge unit 的：

- `title`
- `summary`

执行向量相似度召回。

---

#### 5.5.3.6 Why Hybrid Retrieval Is Not Used for Now

`Research Knowledge Memory` 理论上可以考虑 hybrid retrieval，例如：

- dense retrieval
- lexical retrieval / BM25
- 融合排序

这种方案对以下 query 可能有帮助：

- paper name
- method name
- framework name
- acronym
- exact technical term

但当前阶段暂不默认采用，原因包括：

- 当前更优先的是把 `Knowledge Unit` 粒度设计正确
- 当前更优先的是把 metadata filter 做稳定
- 当前默认读取对象是提炼后的 knowledge unit，而不是原始 chunk
- 提前引入 hybrid retrieval 会增加 retrieval logic、fusion logic 和 tuning cost

因此，当前阶段默认采用：

**metadata filter + vector recall + bounded selection**

---

#### 5.5.3.7 Read Output Contract

`Research Knowledge Memory` 的读取输出，应以 summary-level knowledge units 为主，至少包括：

- `knowledge_id`
- `title`
- `summary`
- `knowledge_type`
- `topic_tags`
- `source_refs`
- `freshness_bucket`
- optional `relevance_score`

默认情况下，不应在该路径中直接展开：

- 原始 paper 正文
- 原始 web page 正文
- 原始检索片段

该层读取输出的是可复用知识摘要，而不是原始资料片段。

---

#### 5.5.3.8 Bounded Recall and Placement

`Research Knowledge Memory` 的读取必须保持 bounded。

系统不应一次性将大量 knowledge units 注入当前 run，而应只保留少量最相关、最可复用的结果。

默认原则包括：

- top-k 保持受控
- 优先选择 active、freshness 更合理、来源更完整的 units
- 避免将多个语义重复 units 同时注入当前 run
- 默认以 summary-level 输出为主

在 placement 上，通常：

- 当前问题强依赖的少量核心 knowledge units
→ 进入 `RunningState`
- 次级支持性 knowledge units
→ 进入 `SupplementalContext`

其目标是让当前 run 获得足够知识支持，但不被大量历史 knowledge 淹没。

### 5.5.4 Persistence / Ingestion Path

#### 5.5.4.1 Objective

`Research Knowledge Memory` 的写入目标，不是保存更多原始资料，而是将 research 过程中产生的高价值结果沉淀为**可复用、可追溯、可治理**的 `Knowledge Unit`。

该路径的核心目标包括：

- 将 research results 提炼为标准化 knowledge units
- 只接纳具有 durable value 的研究知识
- 保证写入对象具有 source traceability
- 控制重复、低价值和不稳定内容进入 `Research Knowledge Memory`

因此，该路径不是原始材料捕获路径，而是一个：

**distillation-and-admission path**

---

#### 5.5.4.2 Candidate Sources

`Research Knowledge Memory` 的候选内容，至少可来自以下两类来源。

**A. Run-time Distilled Candidates**

最常见的来源，是当前 research run 中提炼出的高价值知识，例如：

- paper summary
- topic summary
- comparison conclusion
- source-backed engineering observation
- distilled conclusion

这类 candidate 通常是 `Research Knowledge Memory` 的默认主来源。

**B. Offline or External Ingestion**

系统也可接收离线整理或外部导入的知识，例如：

- 人工整理的 method notes
- 历史 research archive 中筛出的高价值总结
- 手工导入的 paper summaries
- 批量导入的 curated knowledge units

这类来源仍应经过统一的 admission 和 shaping 过程，而不是直接原样写入。

**C. Boundary of Candidate Sources**

以下内容不应直接作为候选来源进入写入流程：

- raw paper / raw article / raw repository contents
- raw retrieval chunks
- 当前 run 的临时 scratchpad
- unresolved reasoning fragments
- 仅服务当前 session continuity 的摘要
- 当前 project state、decision 或 action records

因此，candidate source 的核心要求不是“和 research 有关”，而是：

**它必须能够被进一步提炼为一个合格的 `Knowledge Unit`。**

#### 5.5.4.3 End-to-End Write Flow

`Research Knowledge Memory` 的写入应按以下顺序执行，目标是将 research 结果收敛为少量可复用的 `Knowledge Unit`。

**Step 1. Identify Candidate**

系统先识别当前是否存在可进入 `Research Knowledge Memory` 的 candidate。

candidate 可来自：

- 当前 run 的 research distill
- offline / external ingestion
- curated import

明显属于 raw materials、session continuity 或 structured state 的内容，不进入后续流程。

**Step 2. Check Write Admission**

系统对 candidate 做准入检查。

若不满足条件，则执行：

- `no-write`
- 或进一步 distill / split / merge 后再重试

**Step 3. Form Knowledge Unit**

对通过准入检查的 candidate，系统将其整形成标准化 `Knowledge Unit`，包括：

- `title`
- `summary`
- `knowledge_type`
- `topic_tags`
- `source_refs`
- lifecycle / quality metadata

**Step 4. Lookup Existing Related Knowledge**

落库前，系统查找是否已有语义接近或主题重合的 existing knowledge units。

该步骤可结合：

- `dedupe_key`
- metadata filter
- similarity recall
- LLM 关系判断

**Step 5. Decide Write Action**

系统基于 candidate 与 existing knowledge 的关系，决定本次写入动作。

默认动作包括：

- `create`
- `update_metadata`
- `update_summary`
- `replace_canonical`
- `no-write`

对于 `Research Knowledge Memory`，近似重复内容默认优先通过 `no-write` 或 canonical replacement 收敛，而不是长期保留大量 merged history。

**Step 6. Persist and Check**

系统将最终 `Knowledge Unit` 落库，并检查：

- metadata 是否完整
- canonical active set 是否仍干净
- 是否引入不必要的重复记录

---

#### 5.5.4.4 Write Admission

并非所有 research 相关内容都适合进入 `Research Knowledge Memory`。

一条 candidate 只有同时满足以下条件，才应允许写入。

**A. It Must Be Distilled Knowledge**

写入对象必须是提炼后的知识，而不是原始材料本身，例如：

- raw paper / raw article / raw repository contents
- raw retrieval chunks
- raw tool outputs

**B. It Must Express a Reusable Knowledge Point**

candidate 应表达一个相对完整、后续仍可复用的知识点。

只对当前单轮 research 有帮助的内容，不应写入。

**C. It Must Be Independently Understandable**

candidate 被单独召回时，应基本能够被理解和使用。

脱离当前 run 后难以理解的内容，不应直接写入。

**D. It Must Have Traceable Sources**

默认情况下，knowledge unit 应具备可追溯来源。

没有来源或无法追溯来源的内容，不应直接进入该层 memory。

**E. It Must Not Belong to Other Memory Layers**

以下内容不应误写入 `Research Knowledge Memory`：

- `Session Memory` 中的短期会话摘要
- `Structured Long-term Memory` 中的状态、decision、action 或 policy records
- 当前 run 的临时 scratchpad
- unresolved reasoning fragments

**F. It Must Have Acceptable Granularity**

candidate 不应过大，也不应过小。

过大应先拆分，过小应先合并或拒绝写入。

**G. Action on Admission Failure**

若 candidate 未满足上述任一条件，系统应：

- `no-write`
- 或进一步 distill / split / merge 后再重试

系统不应为了“先存着以后再说”而放宽写入边界。

#### 5.5.4.5 Knowledge Unit Formation

对通过准入检查的 candidate，系统应先将其整形成标准化 `Knowledge Unit`，再进入后续查重与写入决策。

默认形成过程至少包括：

- 生成 `title`
- 生成 `summary`
- 确定 `knowledge_type`
- 补齐 `topic_tags`
- 绑定 `source_refs`
- 设置基础 metadata，例如：
    - `owner_user_id`
    - `project_scope_id`
    - `visibility_scope_effective`
    - `status`
    - `created_at`
    - `updated_at`
    - `freshness_bucket`
    - `confidence`
    - `stability`

若 candidate 仍无法被整形成一个：

- 单一主点明确
- 可独立理解
- 可独立复用
- 来源可追溯

的 `Knowledge Unit`，则不应继续写入，而应：

- `no-write`
- 或进一步 distill / split / merge 后再重试

---

#### 5.5.4.6 Existing Knowledge Lookup and Reconciliation

在真正写入前，系统应先检查是否已有语义接近或主题重合的 existing knowledge units。

默认查找过程可结合：

- `dedupe_key`
- metadata filter
- similarity recall
- LLM relation judgment

系统至少需要区分以下几类关系：

- **independent new knowledge**
与 existing knowledge 无明显重合，可作为新 knowledge unit 写入
- **near-duplicate**
与已有 knowledge 实质重复，应优先执行 `no-write`
- **better replacement**
表达同一知识点，但质量更高、更完整或更新，可执行 `replace canonical`

默认情况下，`Research Knowledge Memory` 不鼓励长期保留大量 merged history。

因此，对近似重复内容，系统应优先采用：

- `no-write`
- 或 `replace canonical`

而不是持续新增历史记录。

该步骤的输出应至少包括：

- `related_existing_units`
- `reconciliation_result`
- `write_action`

其中 `write_action` 默认包括：

- `create`
- `replace canonical`
- `no-write`

#### 5.5.4.7 Persistence Output

`Research Knowledge Memory` 的落库输出应是一个完整的 `Knowledge Unit`，而不是仅一段 summary 文本。

默认至少应包含以下字段：

**A. Identity and Access Scope**

- `knowledge_id`
- `owner_user_id`
- `project_scope_id`（可空）
- `visibility_scope_effective`

**B. Content and Classification**

- `title`
- `summary`
- `knowledge_type`
- `topic_tags`
- `language`

**C. Source Traceability**

- `source_type`
- `source_refs`
- `derived_from_run_id`（可选）

**D. Lifecycle and Quality**

- `status`
- `created_at`
- `updated_at`
- `freshness_bucket`
- `confidence`
- `stability`

**E. Dedupe and Canonical Support**

- `dedupe_key`
- `canonical_knowledge_id`
- `is_canonical`
- `merged_into_id`（如保留）

落库结果应能支持后续：

- 过滤与召回
- freshness / pruning 治理
- dedupe / canonical 判断
- source traceability

---

#### 5.5.4.8 Failure Handling and No-write Cases

并非所有 candidate 都应进入 `Research Knowledge Memory`。

当 candidate 不满足要求时，系统应优先执行 `no-write`。

默认 `no-write` 场景至少包括：

**A. Raw Material**

例如：

- raw paper / raw article / raw repository contents
- raw retrieval chunks
- raw tool outputs

**B. Missing Source Traceability**

candidate 缺乏来源，或无法追溯来源。

**C. Poor Granularity**

candidate 粒度明显不合适，例如：

- 同时覆盖多个并列主点
- 过于碎片化，脱离上下文后难以理解

**D. Wrong Memory Layer**

candidate 实际属于其他 memory layer，例如：

- `Session Memory` 的短期摘要
- `Structured Long-term Memory` 的状态、decision、action 或 policy records
- 当前 run 的 scratchpad
- unresolved reasoning fragments

**E. Insufficient Durable Value**

candidate 只对当前单轮 research 有用，缺乏后续复用价值。

**F. Near-duplicate Existing Knowledge**

candidate 与 existing canonical knowledge 实质重复。

默认应执行 `no-write`，而不是继续累积近似重复 knowledge units。

当出现上述情况时，系统应：

- `no-write`
- 或进一步 `distill / split / merge` 后再重试
- 必要时记录 failure reason

默认不应采用“先写进去，后面再清理”的策略。

### 5.5.5 Refresh, Aging, and Pruning

#### 5.5.5.1 Objective

`Research Knowledge Memory` 不能被视为 write-once 的静态知识池。

由于 research knowledge 会随时间变化、被新资料补充，或被更高质量总结替代，因此系统需要通过 refresh、aging 和 pruning 机制持续治理该层 memory。

本节的目标包括：

- 区分**这类知识是否容易变旧**与**这条知识当前是否已经变旧**
- 让旧知识在默认读取中逐步老化
- 在必要时用新 evidence refresh 现有 knowledge
- 让低价值、重复或明显过时的 knowledge 退出主召回集合

---

#### 5.5.5.2 Freshness Model and Field Lifecycle

`Research Knowledge Memory` 不应只用一个字段同时表达“这类知识是否容易变旧”和“这条知识当前是否已经变旧”。

系统应将两者分开维护。

**A. Core Fields**

建议至少维护以下字段：

- `freshness_sensitivity ∈ {low, medium, high}`
- `freshness_status ∈ {fresh, aging, stale}`
- `created_at`
- `updated_at`
- optional `last_verified_at`

其中：

- `freshness_sensitivity` 表达这类知识的时效敏感性，通常在写入时确定，之后较少变化
- `freshness_status` 表达该条知识当前的新旧状态，会随时间、验证结果和 refresh 结果变化
- `updated_at` 表达最近一次内容更新的时间
- `last_verified_at` 表达最近一次被新 evidence 验证的时间

**B. Freshness Reference Time**

系统应定义：

- `freshness_ref_time = max(updated_at, last_verified_at if present else updated_at)`

后续 freshness 状态判断，默认基于：

- `age_days = now - freshness_ref_time`

这意味着，知识的新旧程度应看“最近一次被更新或被验证”的时间，而不是只看首次写入时间。

**C. Sensitivity Definition**

`freshness_sensitivity` 的默认含义如下：

- `low`：较稳定的方法原理、论文机制、基础概念
- `medium`：有一定演进速度的工程经验、框架理解、方案总结
- `high`：产品能力、最佳实践、快速变化主题、明显依赖外部版本的信息

**D. Freshness Status Maintenance Rule**

系统应按 `freshness_sensitivity` 和 `age_days` 重算 `freshness_status`。

默认可采用以下规则：

**1. High Sensitivity**

- `age_days <= 30` → `fresh`
- `30 < age_days <= 90` → `aging`
- `age_days > 90` → `stale`

**2. Medium Sensitivity**

- `age_days <= 90` → `fresh`
- `90 < age_days <= 270` → `aging`
- `age_days > 270` → `stale`

**3. Low Sensitivity**

- `age_days <= 365` → `fresh`
- `365 < age_days <= 730` → `aging`
- `age_days > 730` → `stale`

这些阈值是当前阶段的默认治理规则，后续可按实际数据分布再调优。

**E. Evidence-first Downgrade Rule**

除时间阈值外，若当前 run 获取到的新 evidence 明确表明现有 knowledge 已经过时或关键事实不再成立，则系统应直接将：

- `freshness_status = stale`

而不必等待时间阈值触发。

必要时可同时记录：

- `staleness_reason`

**F. When Freshness Fields Are Read**

`freshness` 相关字段主要在以下场景中被读取：

- 在 `Research Knowledge Memory` 的 read path 中，影响 filtering、ranking 和 bounded selection
- 在 refresh 判断阶段，判断当前 knowledge 是否需要进入 refresh 流程
- 在 pruning / archive 判断阶段，判断某条 knowledge 是否应退出主召回集合

**G. When Freshness Fields Are Updated**

`freshness` 相关字段默认在以下时点更新：

**1. New Knowledge Unit Is First Written**

在 `Persistence / Ingestion Path` 中首次写入新 knowledge 时，初始化：

- `freshness_sensitivity`
- `freshness_status`
- `created_at`
- `updated_at`

**2. Knowledge Is Hit in Read Path**

当某条 knowledge 在 read path 中被命中时，系统可按本节规则重算 `freshness_status`。

若重算结果与当前状态不一致，则更新：

- `freshness_status`
- optional `staleness_reason`

**3. Successful Verification or Summary Refresh**

当系统拿到足够新 evidence，并成功完成验证或 summary refresh 后，应更新：

- `freshness_status = fresh`
- `updated_at`
- optional `last_verified_at`

**4. Evidence Indicates Downgrade**

当系统拿到新 evidence，判断旧 knowledge 需要降级但当前不足以完成有效翻新时，应更新：

- `freshness_status = aging` 或 `stale`
- `updated_at`
- optional `staleness_reason`

**5. Offline Governance Job (Optional)**

若后续引入后台治理任务，则也可在离线扫描中批量更新：

- `freshness_status`
- `last_verified_at`
- `staleness_reason`

**Summary**

`Freshness Model` 的核心不是精确预测知识何时失效，而是用一组简单、可解释的字段和阈值规则，回答两件事：

- 这类知识是否容易变旧
- 这条知识当前是否已经变旧

其中：

- `freshness_sensitivity` 主要决定老化速度
- `freshness_status` 主要决定当前读取优先级和后续治理动作

#### 5.5.5.3 Refresh Triggers and Refresh Action

在本设计中，**refresh** 专指：

**由于现有 knowledge 的 freshness 下降，系统对其执行验证、更新或降级处理。**

refresh 关注的是**已有 knowledge 的 freshness maintenance**，而不是一般性的知识写入收敛。

若当前 run 产生了明显更合适的新 knowledge，则应转交 `Persistence / Ingestion Path`，由写入流程决定是否 `create` 或 `replace_canonical`。

**A. Refresh Triggers**

系统不需要对所有 `Knowledge Unit` 持续执行 refresh，但在以下情况下应进入 refresh 判断流程。

**1. Read-time Hit on Non-fresh Knowledge**

当某条 knowledge 在 read path 中被命中，且其 `freshness_status` 已为：

- `aging`
- `stale`

系统应进入 refresh 判断流程。

**2. High-sensitivity Knowledge Is Actively Relied On**

当某条 knowledge 的 `freshness_sensitivity = high`，且该知识被当前 run 依赖，或长期作为默认支持知识被频繁命中时，系统应更容易进入 refresh 判断流程。

**3. New Evidence Suggests Existing Knowledge May Be Outdated**

当当前 run 通过 retrieval tool 获取到新的 external evidence，且该 evidence 表明现有 knowledge：

- 可能过时
- 需要重新验证
- 需要补充或修正

系统应进入 refresh 判断流程。

---

**B. Refresh Decision Logic**

触发 refresh 后，系统不应直接选择动作，而应按以下顺序做判断。

**Step 1. Gather Refresh Inputs**

系统收集：

- current knowledge unit
- `freshness_sensitivity`
- `freshness_status`
- `updated_at`
- optional `last_verified_at`
- new evidence / verification result（如有）

**Step 2. Check Whether Sufficient New Evidence Is Available**

系统先判断当前是否已经拿到足够的新 evidence，用于验证或更新现有 knowledge。

- 若**没有足够新 evidence**
→ 进入 Step 3
- 若**已有足够新 evidence**
→ 进入 Step 4

**Step 3. If No Sufficient New Evidence Is Available**

当系统发现 freshness 风险，但当前没有足够新 evidence 完成有效验证时，不应将该 knowledge 刷新为 `fresh`。

此时系统应根据风险程度执行保守处理：

- 风险较轻
→ 降级为 `aging`
- 风险较高
→ 降级为 `stale`

必要时可同时记录：

- optional `staleness_reason`

**Step 4. If Sufficient New Evidence Is Available**

当系统已经拿到足够新 evidence 后，再判断新 evidence 对现有 knowledge 的影响幅度。

- 若新 evidence 仅表明现有 knowledge 仍然成立，且内容主体无需改写
→ 执行 `metadata-only refresh`
- 若新 evidence 表明现有 knowledge 基本仍成立，但 summary 需要补充、修正或局部改写
→ 执行 `summary refresh`
- 若新 evidence 表明现有 knowledge 已明显落后，且已足以形成更合适的新 knowledge
→ 不再按普通 refresh 处理，而应将新知识转交 `Persistence / Ingestion Path`

**Step 5. Finalize Refresh Outcome**

在完成上述判断后，系统输出最终 refresh 决策。

默认结果包括：

- `metadata-only refresh`
- `summary refresh`
- `downgrade to aging`
- `downgrade to stale`
- `handoff to persistence path`
- `no refresh`

---

**C. Refresh Actions**

refresh action 是策略层动作；

其最终会映射到 `Research Knowledge Memory` 的具体存储操作。

**1. Metadata-only Refresh**

适用于：已有 knowledge 仍成立，内容主体无需改写，只需更新 freshness 相关状态。

通常更新：

- `freshness_status = fresh`
- `updated_at`
- optional `last_verified_at`

对应的 persistence operation 通常为：

- `update_metadata`

**2. Summary Refresh**

适用于：已有 knowledge 仍成立，但 summary 需要根据新 evidence 做补充、修正或局部改写。

通常更新：

- `summary`
- `topic_tags`（如有需要）
- `source_refs`
- `freshness_status = fresh`
- `updated_at`
- optional `last_verified_at`

对应的 persistence operation 通常为：

- `update_summary`

**3. Downgrade**

适用于：系统发现 freshness 风险，但当前没有足够新 evidence 完成有效刷新。

通常更新：

- `freshness_status = aging` 或 `stale`
- `updated_at`
- optional `staleness_reason`

必要时，该 knowledge 在 read path 中降权，或进入 archive / pruning 候选集合。

对应的 persistence operation 通常为：

- `update_metadata`

**4. No Refresh**

适用于：系统评估后认为现有 knowledge 仍可接受，且当前既不需要修改内容，也不需要调整 freshness 状态。

对应的 persistence operation 为：

- `no-write`

**5. Handoff to Persistence Path**

适用于：当前 run 已拿到足够新 evidence，且已形成更合适的新 knowledge。

此时旧 knowledge 不再作为普通 refresh 处理，而应：

- 对旧 knowledge 执行降级或退出主集合处理
- 将新知识转交 `Persistence / Ingestion Path`
- 由写入流程决定是否 `create` 或 `replace_canonical`

---

**D. Design Principle**

refresh 的目标不是制造更多版本，也不是把所有“新知识更好”的情况都纳入 refresh，

而是：

- 维护现有 knowledge 的 freshness
- 让变旧 knowledge 被及时验证、更新或降级
- 将真正的新知识写入和 canonical 收敛留在 persistence 路径中处理

因此，refresh 应优先服务于：

**对现有 knowledge 的 freshness-driven maintenance。**

#### 5.5.5.4 Freshness Decay and Ranking Impact

`Freshness Decay` 指的是：一条 knowledge 在不同时效状态下，其默认读取优先级逐步下降。

它影响的是 read path 中的 **filtering、ranking、bounded selection 和 placement**，而不是 knowledge 与 query 的语义相关性本身。

**A. Freshness Decay Means Deprioritization, Not Immediate Removal**

当一条 knowledge 的 `freshness_status` 从 `fresh` 下降到 `aging` 或 `stale` 时，系统默认应先降低其读取优先级，而不是立即删除。

只有在后续满足 pruning / archive 条件时，该 knowledge 才应退出主召回集合。

因此，freshness decay 的首要影响是：

- 降低默认排序优先级
- 降低成为 primary support 的概率
- 提高被过滤、降权或移入次级位置的概率

**B. Ranking Impact by Freshness Status**

系统在 post-retrieval ranking 中，除 semantic relevance 外，还应考虑 `freshness_status`。

**1. `fresh`**

- 正常参与默认排序
- 可作为 primary support
- 在 relevance 相近时，应优先于 `aging` 和 `stale`

**2. `aging`**

- 仍可参与召回
- 在 relevance 相近时，应排在 `fresh` 之后
- 更适合作为 secondary support
- 更容易触发 refresh 检查

**3. `stale`**

- 默认不应高优先级使用
- 在 freshness-sensitive 场景下可直接过滤
- 在非 freshness-sensitive 场景下，最多作为低优先级补充材料

因此，`freshness_status` 不替代 relevance，而是作为：

**post-retrieval ranking modifier**

参与默认排序。

**C. Query-sensitive Handling**

不同 query 对 freshness 的敏感程度不同，因此系统不应对所有 query 一律使用同样的 freshness 规则。

**1. Freshness-sensitive Queries**

例如：

- 当前能力判断
- 最新最佳实践
- 当前框架比较
- 明显依赖外部版本的信息

在这类 query 中：

- `aging` knowledge 应明显降权
- `stale` knowledge 可直接过滤

**2. Freshness-insensitive Queries**

例如：

- 方法原理解释
- 经典论文机制总结
- 基础概念比较

在这类 query 中：

- `aging` knowledge 仍可正常参与召回
- `stale` knowledge 不一定必须完全排除，但不应作为高优先级 primary support

因此，freshness decay 的影响应结合 query 类型，而不是机械套用统一规则。

**D. Placement Impact**

`freshness_status` 不仅影响 ranking，也影响 knowledge 被选中后的 placement。

默认情况下：

- `fresh` knowledge
→ 更适合进入 `RunningState`
- `aging` knowledge
→ 更适合进入 `SupplementalContext`
- `stale` knowledge
→ 默认不应进入主 context；若当前场景允许保留，则仅作为低优先级背景支持

其目标是：

即使某条旧 knowledge 未被完全过滤，也不应让其轻易占据当前 run 的核心上下文位置。

**Summary**

`Freshness Decay and Ranking Impact` 的核心不是判断知识是否还存在，而是定义：

**在进入 pruning 之前，knowledge 的 freshness 状态如何改变其默认读取优先级。**

具体来说：

- `fresh` → 正常参与默认读取
- `aging` → 继续可读，但默认降权
- `stale` → 默认不高优先使用，必要时过滤或仅作弱支持

因此，freshness decay 主要通过：

- ranking
- filtering
- bounded selection
- placement

来影响 `Research Knowledge Memory` 的默认读路径。

#### 5.5.5.5 Pruning and Archive Policy

`Pruning and Archive Policy` 的目标，不是简单删除旧知识，而是控制 `Research Knowledge Memory` 的膨胀，并保持主召回集合尽量小而干净。

系统应区分：

- **archive**：退出主召回集合，但记录仍保留
- **prune**：进一步清理低价值记录；当前阶段可先表现为 `status = pruned`

**A. Candidate Conditions**

以下 knowledge 可进入 archive / prune 流程：

- 长期处于 `stale`，且未被成功 refresh 的 knowledge
- 长期未使用、且无独特价值的 knowledge
- 重复度高、信息增量很低的 knowledge
- 已退出主使用位置、仅剩少量历史参考价值的 knowledge

其中：

- 仍有历史参考价值的 knowledge
→ 更适合 `archive`
- 明显低价值、长期不再需要保留的 knowledge
→ 更适合 `prune`

**B. Archive and Prune Actions**

当一条 knowledge 不应继续留在主召回集合，但仍值得保留时，应执行 archive。

其典型表现为：

- `status = archived`
- optional `archived_at`
- optional `archive_reason`

当一条 knowledge 已无明显保留价值时，应执行 prune。

当前阶段可先采用软清理方式表示：

- `status = pruned`
- optional `pruned_at`
- optional `prune_reason`

**C. Execution Timing**

默认建议：

- **run-time path**
只做轻量判断和标记
- **offline governance**
执行更系统的批量 archive / prune

因此，`archived → pruned` 通常更适合由 offline job 完成，而不是依赖在线请求逐步推进。

**D. Effect on Read Path**

默认情况下：

- `active` knowledge
→ 可参与正常读取
- `archived` knowledge
→ 默认不参与主召回
- `pruned` knowledge
→ 默认不参与任何正常读取

其重点不是“状态变了”，而是：

**让低价值、旧的、重复的 knowledge 不再继续污染默认读路径。**

### 5.5.6 Boundaries and Failure Modes

本节从系统职责边界和系统级失效模式两个角度，收口 `Research Knowledge Memory` 的设计约束。

其目的不是重复前文的 read / write / refresh 细节，而是明确：

- `Research Knowledge Memory` 在整个系统中负责什么
- 不负责什么
- 若前述机制失守，系统会出现哪些典型失败
- 系统应依靠哪些控制点进行约束

#### 5.5.6.1 Responsibility Boundary

`Research Knowledge Memory` 的职责是保存**提炼后的、可复用的研究知识单元**，并在后续 planning、research 和 recommendation 中提供已有知识复用。

其主要责任包括：

- 保存可复用的 topic / method / comparison / conclusion knowledge
- 提供 summary-level 的 research knowledge recall
- 支持 source-backed 的知识复用
- 支持 freshness-aware 的读取与治理

`Research Knowledge Memory` 不负责：

- 保存原始 paper、raw chunk 或 raw evidence
- 恢复 session continuity
- 恢复 project state、decision、action 或 policy
- 替代 retrieval tool 获取最新外部资料
- 作为通用文档仓库

#### 5.5.6.2 Failure Modes

若前述机制失守，`Research Knowledge Memory` 容易出现以下典型失败模式。

**A. Stale Knowledge Leakage**

旧知识未被正确降权、refresh 或移出主集合，仍频繁进入默认读路径。

**B. Duplicate Knowledge Accumulation**

近似重复 knowledge 持续累积，导致 store 膨胀、召回噪声增加。

**C. Wrong-layer Persistence**

本应属于 `Session Memory` 或 `Structured Long-term Memory` 的内容，被误写入 `Research Knowledge Memory`。

**D. Low-traceability Knowledge**

缺乏 `source_refs` 或来源质量较弱的 knowledge 进入主集合，导致后续难以验证和 refresh。

**E. Over-reliance on Local Knowledge**

系统在需要最新 evidence 或更细粒度支持时，仍过度依赖本地 knowledge memory，而没有正确转交 retrieval tool。

**F. Knowledge Drift in Primary Recall Set**

主召回集合长期缺乏治理，导致默认高优先级 knowledge 逐渐偏离当前更高质量、更相关或更新的 knowledge。

#### 5.5.6.3 Control Points

针对上述失败模式，系统应至少具备以下控制点。

**A. Admission Boundary Control**

通过 write admission、memory-layer routing 和 content boundary，避免 raw materials、session-only content 和 state records 误入该层 memory。

**B. Existing Knowledge Reconciliation**

通过 existing knowledge lookup、`no-write`、`replace_canonical` 等机制，限制近似重复知识持续进入主集合。

**C. Freshness Governance**

通过 freshness 字段、refresh trigger 和 freshness-aware ranking，降低 stale knowledge leakage 的风险。

**D. Read-path Sufficiency Check**

通过 local knowledge sufficiency check 和 retrieval handoff，避免系统在需要 fresh evidence 时仍错误依赖本地 knowledge。

**E. Pruning and Archive Governance**

通过 archive / prune policy，将长期 stale、低价值或重复度高的 knowledge 逐步移出 primary recall set。

**F. Source Traceability Requirement**

通过 source-required write admission 和 source-aware ranking，降低 low-traceability knowledge 进入主集合的概率。

#### 5.5.6.4 Design Principle

`Research Knowledge Memory` 应被视为**可复用知识层**，而不是原始证据层、短期会话层或状态恢复层。

其主集合应保持小而干净，并通过 freshness、reconciliation 和 pruning 持续治理，而不是写入后长期不变。

# 6. Storage Design

## 6.1 Storage Requirements and Design Goals

本节定义 memory storage layer 需要支持的核心能力。

前文已经定义了 `Session Memory`、`Structured Long-term Memory` 和 `Research Knowledge Memory` 的读写策略；本节将这些 policy-level 设计转化为 storage-level requirements，为后续 storage backend selection、schema design 和 indexing design 提供依据。

---

### 6.1.1 Support Multiple Memory Types

Storage layer 需要支持多类 memory，而不是只保存一种通用文本记录。

当前系统至少包含：

- `Session Memory`
- `Structured Long-term Memory`
- `Research Knowledge Memory`

不同 memory type 的存储需求不同：

- `Session Memory`
偏短期会话连续性，按 `user_id + session_id` 读写。
其中，`session_id` 表示一个连续的多轮对话上下文，而不是单次 run。
- `Structured Long-term Memory`
偏长期结构化状态、decision、action、preference，需要 scoped lookup、update 和 lifecycle control。
- `Research Knowledge Memory`
偏可复用知识单元，需要 metadata filtering、semantic recall、source traceability 和 freshness governance。

因此，storage design 应分别支持不同 memory type 的读写模式和治理需求。

---

### 6.1.2 Support Request, Session, and Run Boundaries

Storage layer 需要明确区分以下几个 scope：

- `user_id`
用户归属边界。所有 memory records 都应通过 `user_id` 或 `owner_user_id` 做数据隔离。
- `session_id`
当前连续多轮对话的边界。主要用于 `Session Memory`，维护当前 session 内的研究、决策与行动连续性。
- `run_id`
一次具体 Agent execution 的边界。主要用于 tracing、tool call logging、retrieved evidence、generated plan 和 memory candidate 溯源。

因此：

- `Session Memory` 的主读取边界是 `user_id + session_id`
- `Structured Long-term Memory` 通常按 `user_id + project_id / memory_type / status` 读取
- `Research Knowledge Memory` 通常按 `owner_user_id + visibility_scope + optional project_scope_id` 读取
- `run_id` 不作为 Session Memory 的主读取边界，只作为 execution trace 和 memory provenance 字段使用

当前设计不引入 `thread_id` 作为 memory scope。

---

### 6.1.3 Support Read and Write Access Patterns

Storage design 应从 read / write path 推导，而不是只按数据类型静态建表。

主要访问模式包括：

- `Session Memory`
按 `user_id + session_id` 读取当前 session 的短期上下文，并支持频繁更新。
- `Structured Long-term Memory`
按 `user_id`、`project_id`、`memory_type`、`status` 做 scoped structured lookup，并支持 update、replace、archive 等状态变更。
- `Research Knowledge Memory`
先做 metadata pre-filter，再执行 vector similarity recall，并支持 freshness-aware ranking。

因此，storage layer 需要支持：

- key-based lookup
- scoped structured query
- metadata filtering
- vector similarity search
- controlled update / mutation

---

### 6.1.4 Support Metadata Filtering and Semantic Recall

`Research Knowledge Memory` 的读取采用 **filter-first semantic recall**。

因此 storage layer 需要支持：

- 先按 metadata 过滤候选集合
- 再对过滤后的候选执行向量召回

关键过滤字段包括：

- `owner_user_id`
- `visibility_scope_effective`
- `project_scope_id`
- `status`
- `knowledge_type`
- `topic_tags`
- `source_type`

同时，storage layer 需要支持基于 `title + summary` 的 embedding 存储和向量检索。

---

### 6.1.5 Support Lifecycle, Freshness, and Governance

Storage layer 需要支持不同 memory type 的 lifecycle 和 governance 字段，但**不是每类 memory 都包含所有字段**。

不同 memory type 的字段重点不同：

- `Session Memory`
主要需要：
    - `created_at`
    - `updated_at`
    - `expires_at`
- `Structured Long-term Memory`
主要需要：
    - `status`
    - `created_at`
    - `updated_at`
    - `supersedes`
    - `superseded_by`
    - `confidence`
    - `validity`
- `Research Knowledge Memory`
主要需要：
    - `status`
    - `created_at`
    - `updated_at`
    - `freshness_sensitivity`
    - `freshness_status`
    - `last_verified_at`
    - `dedupe_key`
    - `canonical_knowledge_id`
    - `is_canonical`

因此，storage design 不应强行让所有 memory table 共享同一套字段，而应根据每类 memory 的 read path、write path 和 governance policy 选择对应字段。

---

### 6.1.6 Support Source Traceability

长期 memory，尤其是 `Research Knowledge Memory`，需要保留来源追踪能力。

Storage layer 应支持记录：

- `source_type`
- `source_refs`
- `derived_from_run_id`
- optional source metadata

其中：

- `source_refs` 用于追溯 knowledge 的来源
- `derived_from_run_id` 用于追溯该 memory 是否来自某次 Agent execution
- source metadata 可用于后续 refresh、verification 和 recommendation explanation

因此，source traceability 是 storage-level requirement，而不仅是最终 response formatting 的问题。

---

### 6.1.7 Keep MVP Storage Simple and Evolvable

当前阶段应优先选择简单、可落地、可演进的存储设计。

MVP storage design 应优先满足：

- 易于本地开发和调试
- schema 清晰
- 支持 structured query
- 支持 vector recall
- 支持 lifecycle / freshness 字段
- 支持 source traceability
- 后续可迁移到更专业的存储组件

因此，第一版应倾向于统一、简单、可扩展的 storage architecture。

更复杂的独立 vector DB、cache layer、event store 或搜索引擎，可在数据规模和性能需求明确后再引入。

## 6.2 Storage Backend Selection

### 6.2.1 Session Memory Storage

`Session Memory` 用于维护当前 `session_id` 内的多轮对话连续性，保存的是压缩后的 working memory，例如：

- session summary
- recent turns
- current focus
- open questions
- temporary research / decision / action context

它不保存完整会话历史，也不承担 long-term memory 的职责。

因此，`Session Memory` 的 storage backend 应优先支持：

- 按 `user_id + session_id` 快速读写
- 高频更新
- TTL / expiration
- 低延迟访问
- 可接受的短期数据丢失风险

---

#### A. Candidate Options

| Option | Pros | Cons |
| --- | --- | --- |
| **Application In-memory** | 实现最简单；无外部依赖；延迟最低；适合 Phase 0 prototype | 服务重启后丢失；多实例无法共享；不可恢复；不适合作为正式 storage backend |
| **PostgreSQL Table** | 不引入额外数据库；持久化强；方便 SQL 调试 | 对 hot session state 不够自然；大 JSON 高频更新可能有写放大；TTL 需要额外 cleanup job；延迟不如 Redis |
| **Redis** | 与 Session Memory 模型高度匹配；key-value 访问简单；低延迟；适合高频读写；原生支持 TTL；可通过 RDB / AOF 提供一定恢复能力 | 需要额外引入 Redis；内存成本高于磁盘型数据库；持久化语义弱于 PostgreSQL；需要明确故障降级策略 |
| **DynamoDB** | Key-value / document model 与 `user_id + session_id` 匹配；AWS-native；serverless；扩展性强 | AWS 绑定；本地开发调试成本更高；单 item 有 400KB 限制；大 session object 需要 compression / chunking / S3 pointer |
| **Redis + PostgreSQL Hybrid** | Redis 做 hot store，PostgreSQL 做 checkpoint / fallback；兼顾低延迟与持久化 | 系统复杂度明显上升；需要处理双写、回写、一致性和恢复策略；当前阶段偏重 |

---

#### B. Recommended Choice: Redis

本系统选择 **Redis** 作为 `Session Memory` 的默认 storage backend。

原因是 `Session Memory` 的访问模式天然接近 hot key-value state：

```
key   = session_memory:{user_id}:{session_id}
value = compact session memory JSON
ttl   = session lifetime / inactivity timeout
```

Redis 与该模式高度匹配：

- `user_id + session_id` 可以自然映射为 Redis key
- session state 需要频繁读写
- session memory 对低延迟较敏感
- TTL 是 Session Memory 的自然生命周期机制
- Redis 比 PostgreSQL 大 JSON 更适合 hot session state

---

#### C. Persistence and Failure Scope

Redis 的持久化能力弱于 PostgreSQL，但对 `Session Memory` 来说可以接受。

原因是：

- `Session Memory` 不是 long-term memory 的 source of truth
- Redis 故障最多影响当前 session continuity
- Redis 故障不应破坏长期 memory
- 可通过 RDB / AOF 恢复到较近状态
- 极端情况下，用户可以开启新的 session，系统仍可依赖 long-term memory 继续工作

因此，Redis 的故障影响范围是可控的：

```
Redis failure
  -> lose or degrade current session continuity
  -> does not corrupt long-term memory
```

---

#### D. Why Not PostgreSQL as Default

PostgreSQL 是务实备选，但不是最适合 `Session Memory` 的技术选择。

它的优势是：

- 不需要额外引入数据库
- 持久化和调试体验好

但它的缺点是：

- `Session Memory` 更像频繁更新的 compact JSON object
- PostgreSQL 对大 JSON / text 的高频更新不如 Redis 自然
- TTL 和 session expiration 需要额外 cleanup job
- session hot path 延迟不如 Redis

因此，PostgreSQL 更适合作为“减少组件数量”的折中方案，而不是默认选择。

---

#### E. Why Not DynamoDB as Default

DynamoDB 在模型上也适合 `Session Memory`，但当前不作为默认方案，主要原因是：

- AWS-native，增加平台绑定
- 本地开发和调试成本更高
- 单 item 有 400KB 限制
- session memory 膨胀时需要额外设计 compression、chunking 或 S3 pointer

因此，DynamoDB 可作为未来 AWS-native deployment 的备选方案，但不是当前默认选择。

### 6.2.2 Structured Long-term Memory Storage

#### 6.2.2.1 Backend Database Selection

`Structured Long-term Memory` 是跨 session 的长期结构化记忆层，用于保存 project profile、decision、action、preference / policy 等 records。

它的 storage backend 需要支持：

- long-term persistence
- scoped structured lookup
- controlled update / replace / supersede / archive
- transaction-safe mutation
- similarity-assisted candidate resolution
- local debugging and schema evolution

---

**A. Candidate Backends**

| Backend | Pros | Cons | Decision |
| --- | --- | --- | --- |
| **PostgreSQL** | 关系型查询能力强；适合按 `user_id / project_id / memory_type / scope / status` 查询；事务和状态流转清晰；可通过 pgvector 支持 similarity-assisted candidate resolution | 开发者熟悉度低于 MySQL；需要学习 PostgreSQL / pgvector 生态 | **Primary choice** |
| **MySQL** | 开发者更熟悉；关系型查询和事务能力足以支持大部分 structured memory 需求；落地成本低 | similarity-assisted candidate resolution 不如 PostgreSQL + pgvector 自然，可能需要 external vector index | **Secondary choice** |
| **MongoDB / Document DB** | 文档模型灵活 | 本层更依赖稳定 scope 字段、status transition、supersession 和治理语义，document model 容易带来 schema drift | Not selected |
| **DynamoDB** | AWS-native；扩展性强；适合 key-value / document access | 查询模式强依赖 PK / SK / GSI；复杂状态流转和 similarity-assisted resolution 不够自然 | Not selected |
| **Redis** | 低延迟 | 不适合作为 long-term source of truth；复杂查询、审计和状态治理能力弱 | Not suitable |

---

**B. Why PostgreSQL Is Preferred**

`Structured Long-term Memory` 的核心访问模式是 scoped structured lookup，例如：

```
user_id + project_id + memory_type + scope + status
```

PostgreSQL 可以自然支持：

- 查询某个 user / project 下的 active records
- 更新 decision / action / preference 状态
- 执行 supersede / archive
- 按 scope / priority / status 读取 records
- 通过事务保证受控变更

此外，PostgreSQL 可通过 pgvector 支持：

```
structured filter + vector similarity candidate retrieval
```

这对 `similarity-assisted candidate resolution` 很重要。

相比 “MySQL + external vector index”，PostgreSQL + pgvector 可以减少 structured records 与 embedding index 之间的同步复杂度。

---

**C. Why MySQL Remains a Secondary Choice**

MySQL 仍是有效备选，因为开发者更熟悉 MySQL，且它能支持大部分核心需求：

- scoped lookup
- transaction-safe update
- status transition
- supersede / archive
- structured indexing

但如果使用 MySQL，`similarity-assisted candidate resolution` 通常需要额外设计：

```
MySQL as source of truth
+ external vector index for candidate retrieval
+ memory_id mapping back to MySQL records
```

该方案可行，但会增加同步和一致性成本。

因此，MySQL 暂作为 secondary choice；如果后续整体 storage design 更适合 MySQL + external vector store，可重新评估。

---

**D. Decision**

当前阶段，`Structured Long-term Memory` 默认选择：

```
PostgreSQL
```

主要原因是：

- 适合长期结构化 memory records
- 支持 scoped structured lookup
- 支持 transaction-safe mutation
- 支持 supersede / archive 等状态流转
- 可通过 pgvector 支持 similarity-assisted candidate resolution
- 可能与后续 `Research Knowledge Memory` 的向量检索需求形成统一 storage path

MySQL 保留为次选方案。

#### 6.2.2.2 Single-table vs Multi-table Layout

在确定 `Structured Long-term Memory` 的 backend database 后，还需要决定 table layout。

本设计主要比较两种方案：

- **Single-table layout**：所有 structured memory records 存在一张统一表中，通过 `memory_type` 区分类型。
- **Multi-table layout**：不同 memory type 使用独立表，例如 `project_profile_memory`、`decision_memory`、`action_memory`、`preference_policy_memory`。

---

**A. Option 1: Single-table Layout**

Single-table layout 使用一张统一表，例如：

```
structured_memory_records
```

典型设计方式是：

```
common columns + memory_type + typed payload
```

**Pros**

- MVP 实现简单
- 新增 memory type 成本低
- read / write / archive / supersede 逻辑较统一
- similarity-assisted candidate resolution 实现较统一
- 跨类型读取方便，例如一次读取某 project 下所有 active structured memories

**Cons**

- 不同 memory type 的业务字段差异较大，payload 容易变重

type-specific 字段主要依赖应用层 schema validation

- payload 内字段不适合作为高频查询条件
- 如果将所有字段摊平成 columns，会形成稀疏大宽表
- 长期维护中容易演变成半结构化杂表

---

**B. Option 2: Multi-table Layout**

Multi-table layout 为不同 structured memory type 建独立表，例如：

```
project_profile_memory
decision_memory
action_memory
preference_policy_memory
```

每张表保留自己的核心业务字段、生命周期字段和可选 embedding 字段。

**Pros**

- 每类 memory 的 schema 更清晰
- DB-level constraints 更强
- 避免 single-table 的稀疏字段问题
- 类型内查询性能更好
- 每类 memory 可以维护独立索引
- 每张表可维护自己的 embedding 字段，支持同类型 similarity-assisted candidate resolution
- 长期维护更接近正式业务系统设计

**Cons**

- 表数量更多
- 每类 memory 需要独立 repository / DAO / migration
- 新增 memory type 需要新增表和相关代码
- 跨类型读取需要多表查询或应用层合并
- 公共 create / update / archive / supersede 逻辑需要在多表之间抽象复用

---

**C. Comparison**

| Dimension | Single-table Layout | Multi-table Layout |
| --- | --- | --- |
| MVP implementation | 更简单 | 更复杂 |
| Schema clarity | 较弱，依赖 `memory_type + payload_json` | 更强，每类 memory 有明确 schema |
| Type-specific constraints | 主要依赖应用层校验 | 可通过 DB schema 和约束表达 |
| Sparse fields | 需避免大宽表；可用 common columns + payload 缓解 | 基本没有跨类型稀疏问题 |
| Query performance | 通用查询方便；type-specific 查询较弱 | 类型内查询更清晰、更容易优化 |
| Cross-type read | 更方便 | 需要多表查询或应用层合并 |
| Write path | 更统一 | 更分散，需要抽象公共逻辑 |
| Similarity-assisted resolution | 统一实现更简单 | 每张表各自维护 embedding，适合同类型匹配 |
| Extensibility | 新增 memory type 容易 | 新增类型需要新表和 migration |
| Long-term maintainability | 可能变成半结构化杂表 | 更清晰，更适合长期维护 |
| Transaction consistency | 单表最简单 | 同一 DB 内仍是本地事务，不涉及分布式事务 |

---

**D. Decision**

当前设计选择：

```
Structured Long-term Memory -> Multi-table Layout
```

选择理由是：

- `Project Profile`、`Decision`、`Action`、`Preference / Policy` 的业务语义差异明显
- 各类 memory 的核心查询字段不同
- multi-table 能提供更清晰的 schema 和更强约束
- 类型内检索和索引设计更自然
- 每张表可独立维护 embedding 字段，支持同类型的 similarity-assisted candidate resolution
- 长期来看更利于维护和演进

Single-table layout 仍适合快速 MVP，但本项目希望 `Structured Long-term Memory` 更接近长期可维护的业务状态层，因此选择 multi-table。

---

**E. Design Note**

Multi-table layout 不意味着每类 memory 完全独立。

各表仍应保持统一的公共治理字段，例如：

```
user_id
project_id
record_status
confidence
created_at
updated_at
derived_from_session_id
derived_from_run_id
```

同时应区分：

- `record_status`：memory record 的生命周期状态，例如 `active`、`superseded`、`archived`、`pruned`
- domain-specific status：业务状态，例如 `action_status`、`decision_state`

### 6.2.3 Research Knowledge Memory Storage

`Research Knowledge Memory` 用于保存可复用的 research knowledge units。

它需要同时支持：

- metadata filtering
- vector similarity recall
- source traceability
- freshness governance
- canonical / dedupe control
- archive / pruning
- visibility / ownership filtering

因此，本节主要比较：

- `PostgreSQL + pgvector`
- `PostgreSQL + Milvus`

---

#### A. Storage Requirements

`Research Knowledge Memory` 的 storage backend 需要支持：

- 按 `owner_user_id`、`visibility_scope_effective`、`project_scope_id`、`status` 等字段做 metadata filtering
- 基于 `title + summary` embedding 做 vector similarity recall
- 保存完整 Knowledge Unit，包括 `title`、`summary`、`knowledge_type`、`topic_tags`、`source_refs`
- 支持 `freshness_sensitivity`、`freshness_status`、`last_verified_at` 等 freshness 字段
- 支持 `dedupe_key`、`canonical_knowledge_id`、`is_canonical`、`merged_into_id` 等 canonical / dedupe 字段
- 支持 refresh、archive、prune、replace canonical 等受控变更

---

#### B. Candidate Options

| Option | Pros | Cons |
| --- | --- | --- |
| **PostgreSQL + pgvector** | metadata、governance fields、source refs 和 embedding 在同一数据库；可在同一 backend 内完成 metadata filter + vector similarity recall；不需要同步外部 vector index；事务、约束和 SQL 治理查询更自然 | 向量检索性能和扩展性不如专用 vector database；需要理解 pgvector 的 vector type、distance operator、ANN index 和 embedding lifecycle |
| **PostgreSQL + Milvus** | PostgreSQL 保存完整 Knowledge Unit 和治理字段；Milvus 作为专业 vector retrieval index，向量检索性能和扩展性更强 | 多一个存储组件；需要同步 PostgreSQL 与 Milvus；write / refresh / archive / prune / canonical replacement 都要更新 Milvus index；read path 需要先查 Milvus 再回 PostgreSQL 做治理校验和 reranking |

---

#### C. Why PostgreSQL + pgvector Is Preferred

当前阶段选择 **PostgreSQL + pgvector** 作为默认方案。

原因是 `Research Knowledge Memory` 的核心复杂度不只是 vector search，而是 governed knowledge storage。

一条 Knowledge Unit 不只是：

```
summary + embedding
```

还包含大量治理字段：

```
status
freshness_sensitivity
freshness_status
last_verified_at
dedupe_key
canonical_knowledge_id
is_canonical
merged_into_id
source_refs
archived_at
pruned_at
```

这些字段会参与 read path、write path、refresh、dedupe、canonical replacement 和 pruning。

因此，将 metadata、governance fields 和 embedding 放在同一个 PostgreSQL table 中，可以减少跨系统同步和一致性问题。

默认 read path 为：

```
query embedding
  -> PostgreSQL metadata filter
  -> pgvector similarity recall
  -> freshness-aware ranking
  -> bounded selection
```

---

#### D. Why Not PostgreSQL + Milvus as Default

`PostgreSQL + Milvus` 是合理的未来扩展方案，但当前不作为默认选择。

在该方案中：

```
PostgreSQL = source of truth
Milvus     = derived semantic retrieval index
```

Milvus 只保存：

```
knowledge_id
embedding_vector
lightweight retrieval metadata
```

完整 Knowledge Unit 和治理字段仍以 PostgreSQL 为准。

该方案的优势是向量检索性能更强，但会引入额外复杂度：

- knowledge 写入后需要同步 upsert Milvus
- summary refresh 后需要重新生成 embedding 并更新 Milvus
- archive / prune / supersede 后需要更新 Milvus 的 `is_searchable` 或删除 entity
- Milvus 与 PostgreSQL 之间可能短暂不一致
- Milvus 返回 top-k 后仍需要回 PostgreSQL 做 final governance check

因此，在当前 knowledge scale 和 QPS 尚未证明 pgvector 成为瓶颈前，引入 Milvus 属于过早复杂化。

---

#### E. Decision

当前设计选择：

```
Research Knowledge Memory -> PostgreSQL + pgvector
```

选择理由是：

- `Research Knowledge Memory` 更像 governed reusable knowledge store，而不是普通 vector collection
- PostgreSQL 更适合保存 canonical Knowledge Unit 和治理型 metadata
- pgvector 足以支持当前阶段 semantic recall
- metadata filter、vector recall、freshness governance 和 canonical state 可以放在同一 storage backend 中
- 避免维护外部 vector index 的同步和一致性成本
- 后续如果向量规模或 QPS 成为瓶颈，可以演进为 `PostgreSQL + Milvus`

未来演进方向：

```
MVP / 中小规模:
PostgreSQL + pgvector

Scale-up:
PostgreSQL as source of truth
+ Milvus as derived semantic retrieval index
```

## 6.3 Logical Data Model

本节定义 memory storage layer 中的核心逻辑实体及其关系。

本节不展开具体表字段、SQL 类型或索引，只说明主要 data entities、职责边界和实体关系。

---

### 6.3.1 Entity Overview

当前系统的 core memory-related logical entities 包括：

- `User`
用户归属边界，用于隔离不同用户的 memory 数据。
- `Session Memory`
当前连续多轮 session 内的短期工作记忆，用于维持研究、决策与行动连续性。
当前设计中存储在 Redis 中，并可通过 TTL 过期。
- `Project / Project Scope`
project-related memories 的逻辑归属边界，可由 `project_id` 表达，不一定在 MVP 中独立建表。
- `Project Profile Memory`
保存项目背景、目标、约束和当前阶段。
- `Decision Memory`
保存项目中的设计决策、技术选型和方案取舍。
- `Action Memory`
保存项目行动项、后续任务和待办事项。
- `Preference / Policy Memory`
保存用户偏好、输出规则、项目约束和行为策略。
- `Research Knowledge Unit`
保存 source-backed、summary-level、freshness-governed 的可复用研究知识。
- `Source Reference`
用于追踪 memory 或 knowledge 的 evidence 来源。
在 logical model 中是独立概念；物理上可先以内嵌 JSON / array 形式保存，是否拆表留到 `6.4 Schema Design` 决定。

Optional entities:

- `Conversation Session`
可选的持久化 session metadata，用于保存 session 的身份、归属、标题和生命周期状态。
它不同于 Redis-backed `Session Memory`。
- `Message Log`
可选的持久化消息历史，用于保存用户与系统之间的原始或近原始对话消息。
它服务于历史回看、debug、audit 和 provenance reconstruction，不替代 `Session Memory`。
- `Run / Execution Log`
可选的持久化 execution trace，用于记录一次 Agent execution 的输入、工具调用、检索结果、plan、intermediate findings 和 memory candidates。
当前阶段只要求有 `run_id` 作为 provenance identifier，不强制实现完整 run log。

---

### 6.3.2 Ownership, Scope, and Execution Boundaries

#### user_id

`user_id` 是所有 memory records 的用户归属边界。

所有读取和写入都必须通过 `user_id` 或 `owner_user_id` 做数据隔离。

#### session_id

`session_id` 表示一个连续的多轮对话 session。

它是 `Session Memory` 的主要读取和写入边界：

```
Session Memory scope = user_id + session_id
```

对于 long-term memory，`session_id` 不作为主读取边界，只能作为 provenance 字段。

由于 `Session Memory` 存在 Redis 中，并可能因 TTL 过期，系统不应仅依赖 `session_id` 回查完整来源上下文。

如果未来启用持久化 `Conversation Session` 和 `Message Log`，则 `session_id` 可以从 weak provenance 增强为可回查的 session-level provenance。

#### run_id

`run_id` 表示 session 内的一次具体 Agent execution。

它不作为 memory 的主读取边界，主要用于 tool call tracing、retrieved evidence tracking、memory candidate provenance 和 `derived_from_run_id`。

#### message_id Optional

如果后续引入 `Message Log`，`message_id` 表示一条具体消息，例如 user message、assistant message 或 tool message。

```
user_id
  └── session_id
        └── message_id
```

#### project_id

`project_id` 是 structured long-term memory 的主要项目归属边界。

`Project Profile`、`Decision` 和 `Action` 通常都应绑定到某个 project。

#### visibility_scope

`visibility_scope` 控制 `Research Knowledge Unit` 的可见范围，例如 user-level、project-level、domain-level 或后续可能的 shared-level。

`Research Knowledge Memory` 的读取通常基于：

```
owner_user_id + visibility_scope + optional project_scope_id
```

---

### 6.3.3 Structured Long-term Memory Entity Relations

`Structured Long-term Memory` 采用 multi-table layout。

逻辑关系如下：

```
Project / Project Scope
  ├── Project Profile
  ├── Decision
  │     └── Action
  └── Action

Preference / Policy
  └── applies to global / project / task_type / memory_type scope
```

- `Project Profile` 描述 project 的长期背景和当前状态。一个 project 通常有一个 active profile，也可能存在被 superseded 的历史 profile。
- `Decision` 表示项目中的设计决策或技术选型。一个 project 可以包含多个 decisions。
- `Action` 表示行动项或待办任务。一个 action 必须属于某个 project，但不一定来自某个 decision。

```
Project 1 -- N Decision
Project 1 -- N Action
Decision 1 -- N Action optional
```

因此，`Action` 应支持：

```
project_id required
parent_decision_id optional
```

- `Preference / Policy` 表示用户偏好、输出规则、项目约束或行为策略。它可作用于 `global`、`project`、`task_type` 或 `memory_type` scope。

每类 structured memory entity 可以维护自己的 embedding representation，用于同类型的 `similarity-assisted candidate resolution`。

Embedding 是辅助候选匹配的 retrieval representation，不是 memory 本体。

---

### 6.3.4 Research Knowledge Unit Model

`Research Knowledge Unit` 是 `Research Knowledge Memory` 的核心逻辑实体。

它表示经过提炼、可复用、可追溯来源的研究知识，而不是 raw chunk、session summary 或 structured decision / action record。

逻辑上可以表示为：

```
ResearchKnowledgeUnit
  ├── content: title + summary
  ├── scope: owner_user_id + visibility_scope + optional project_scope_id
  ├── source: source_refs
  ├── governance: status + freshness + canonical / dedupe fields
  └── retrieval representation: embedding
```

其中，embedding 是 retrieval representation，不是 Knowledge Unit 的完整本体。

完整本体由 content、source 和 governance fields 共同定义。

`Research Knowledge Unit` 与 `Decision Memory` 的边界应明确：

- `Research Knowledge Unit` 保存 source-backed reusable knowledge
- `Decision Memory` 保存用户或项目已经形成的决策状态

例如，“Redis 适合 hot session state”可以是 research knowledge；而“本项目决定使用 Redis 保存 Session Memory”则是 decision memory。

---

### 6.3.5 Source and Provenance Model

Memory records 和 knowledge units 应支持来源追踪。系统需要区分：

- `source reference`：该 memory / knowledge 基于哪些 external / internal evidence
- `session provenance`：该 memory / knowledge 来源于哪个 session
- `message provenance`：如果启用 `Message Log`，可追溯到具体 messages
- `run provenance`：该 memory / knowledge 来源于哪次 Agent execution

#### Source Reference

`Source Reference` 用于表示 evidence 来源，典型信息包括：

- `source_type`
- `source_uri`
- `title`
- `retrieved_at`
- `evidence_span`
- citation metadata

MVP 中可以先作为 JSON / array 字段保存；后续如果 source 查询、审计或复用需求增强，再拆成独立表。

#### Session Provenance

`derived_from_session_id` 用于说明某条 long-term memory 或 research knowledge 可能来源于哪个 session。

在未启用 `Message Log` 时，由于 Redis-backed `Session Memory` 可能过期，它只能提供 weak provenance。

#### Message Provenance Optional

如果启用 `Message Log`，系统可以记录：

```
derived_from_message_ids
```

用于支持 debug、audit、用户回看和 memory distillation traceability。

#### Run Provenance

`derived_from_run_id` 用于说明某条 memory 或 knowledge 来源于哪次 Agent execution。

当前阶段，`run_id` 主要作为 provenance identifier；是否持久化完整 run log，留到后续 observability / tracing 设计。

---

### Summary

`Logical Data Model` 明确以下边界：

- `Session Memory` 按 `user_id + session_id` 维护当前对话连续性，并存储在 Redis 中
- `Conversation Session` 和 `Message Log` 是 optional persistent layers，用于 session metadata、历史回看、debug、audit 和 provenance reconstruction
- 未启用 `Message Log` 时，`session_id` 只提供 weak provenance
- `run_id` 表示一次 Agent execution，可用于 provenance，但不默认意味着完整 run log 已持久化
- `Structured Long-term Memory` 由 Project Profile、Decision、Action、Preference / Policy 等实体组成，并采用 multi-table layout
- `Research Knowledge Unit` 是 source-backed、freshness-governed、可语义召回的可复用知识单元
- `Source Reference` 提供 evidence-level provenance，物理上是否独立成表留到 schema design 决定
- embedding 是 retrieval representation，不是 memory 本体本身

## 6.4 Schema Design

### 6.4.1 Session Memory Schema

`Session Memory` 保存当前连续多轮 session 内的 compact working memory。

它不是完整对话历史，也不是 long-term memory 的 source of truth，而是当前 Agent execution 用于维持上下文连续性的短期运行时状态。

当前设计中，`Session Memory` 存储在 Redis 中，并通过 TTL 控制生命周期。

---

**A. Redis Key Format**

`Session Memory` 使用 `user_id + session_id` 作为主读取边界。

```
session_memory:{user_id}:{session_id}
```

其中：

- `user_id`：用户归属边界
- `session_id`：连续多轮对话 session 的边界
- `run_id`：单次 Agent execution，不作为 Redis key 的主 scope

---

**B. Redis Value Schema**

Redis value 存储为 compact JSON object。

```
{
  "user_id":"user_123",
  "session_id":"session_456",
  "session_summary":"...",
  "recent_turns": [
    {
      "role":"user",
      "content_summary":"...",
      "created_at":"2026-04-29T10:00:00Z"
    }
  ],
  "current_focus":"6.4 Schema Design",
  "open_questions": [
"Should Source Reference be embedded or normalized?"
  ],
  "temporary_context": {
    "active_section":"6.4.1 Session Memory Schema",
    "recent_decisions": [
"Session Memory uses Redis"
    ]
  },
  "updated_at":"2026-04-29T10:10:00Z",
  "expires_at":"2026-04-30T10:10:00Z"
}
```

---

**C. Core Fields**

| Field | Description |
| --- | --- |
| `user_id` | 用户归属边界 |
| `session_id` | 连续多轮 session 边界 |
| `session_summary` | 当前 session 的滚动摘要 |
| `recent_turns` | 最近若干轮对话的压缩表示，不保存完整历史 |
| `current_focus` | 当前讨论或任务焦点 |
| `open_questions` | 尚未解决的问题 |
| `temporary_context` | 当前 run 需要的短期上下文 |
| `updated_at` | 最近更新时间 |
| `expires_at` | 逻辑过期时间，与 Redis TTL 对齐 |

---

**D. TTL and Update Semantics**

`Session Memory` 应设置 Redis TTL：

```
Redis TTL = session inactivity timeout
```

过期后：

- Redis 中的 compact working memory 可被删除
- long-term memory 不受影响
- optional `Message Log` 若启用，仍可保留完整或近完整消息历史

典型更新流程：

```
Before run:
  load session_memory:{user_id}:{session_id}

After run:
  update session_summary
  update recent_turns
  update current_focus
  update open_questions
  refresh TTL
```

更新应遵循 compactness 原则：

- 不保存完整会话历史
- 不无限追加 `recent_turns`
- 旧内容应滚动压缩进 `session_summary`
- 长期有价值的信息应转写到 Structured Long-term Memory 或 Research Knowledge Memory

---

**E. Boundary with Message Log**

`Session Memory` 不等同于 `Message Log`。

```
Session Memory = compact runtime working memory
Message Log    = persistent conversation history, optional
```

如果未来启用 `Message Log`，完整或近完整消息历史应写入持久化 message table，而不是写入 Redis `Session Memory`。

### 6.4.2 Structured Long-term Memory Schema

`Structured Long-term Memory` 用于保存跨 session 可复用的结构化长期记忆，包括 project profile、decision、action 和 preference / policy。

当前设计采用：

```
Structured Long-term Memory -> PostgreSQL + Multi-table Layout
```

每类 memory 使用独立表，以获得更清晰的 schema、更强的类型约束和更自然的类型内查询能力。

---

**A. Common Schema Principles**

各类 structured memory table 应共享一组公共治理字段：

| Field | Description |
| --- | --- |
| `user_id` | 用户归属边界 |
| `project_id` | 项目归属边界；global-level policy 可为空 |
| `record_status` | memory record 生命周期状态，例如 `active`, `superseded`, `archived`, `pruned` |
| `confidence` | 系统对该 memory 的置信度 |
| `created_at` | 创建时间 |
| `updated_at` | 更新时间 |
| `derived_from_session_id` | 来源 session，可选 |
| `derived_from_run_id` | 来源 Agent execution，可选 |
| `source_refs` | 来源引用，可选，可先用 JSON / array 保存 |

需要区分：

```
record_status = memory record 的生命周期状态
domain-specific status = 业务对象自己的状态
```

例如：

- `record_status = active`
- `decision_state = accepted`
- `action_status = todo`

---

**B. `project_profile_memory`**

保存项目背景、目标、约束和当前阶段。

| Field | Description |
| --- | --- |
| `project_profile_id` | 某一版 project profile record 的 ID |
| `project_id` | 稳定的逻辑项目 ID |
| `user_id` | 用户归属 |
| `project_name` | 项目名称 |
| `project_goal` | 项目目标 |
| `project_background` | 项目背景 |
| `domain` | 项目领域 |
| `current_stage` | 当前阶段 |
| `constraints` | 项目约束，可用 JSON / array |
| `important_context` | 重要上下文 |
| `record_status` | `active`, `superseded`, `archived`, `pruned` |
| `confidence` | 置信度 |
| `supersedes_profile_id` | 被当前 profile 替代的旧 profile，可空 |
| `superseded_by_profile_id` | 替代当前 profile 的新 profile，可空 |
| `embedding_text` / `embedding_vector` | 用于同类型 similarity-assisted candidate resolution |
| `embedding_model` / `embedding_version` | embedding 模型与版本 |
| `created_at` / `updated_at` | 创建与更新时间 |
| `derived_from_session_id` / `derived_from_run_id` | 来源追踪，可选 |
| `source_refs` | 来源引用，可选 |

说明：

```
project_id = logical project identity
project_profile_id = a specific version of project profile
```

初始 profile 可以让 `project_id = project_profile_id`，但系统逻辑不应依赖二者相等。后续 profile 更新产生新版本时，新旧 profile 共享同一个 `project_id`，但拥有不同的 `project_profile_id`。

同一 `user_id + project_id` 下通常最多只有一条 `active` profile。

---

**C. `decision_memory`**

保存项目中的设计决策、技术选型和方案取舍。

| Field | Description |
| --- | --- |
| `decision_id` | Primary key |
| `user_id` | 用户归属 |
| `project_id` | 所属项目 |
| `decision_title` | 决策标题 |
| `decision_question` | 该 decision 要解决的问题 |
| `chosen_option` | 最终选择 |
| `alternatives` | 备选方案，可用 JSON / array |
| `rationale` | 决策理由 |
| `tradeoffs` | 主要 trade-offs，可用 JSON / array |
| `decision_state` | 业务状态，例如 `proposed`, `accepted`, `reconsidering`, `rejected` |
| `record_status` | memory 生命周期状态 |
| `impact_scope` | 决策影响范围 |
| `confidence` | 置信度 |
| `decided_at` | 决策形成时间，可空 |
| `supersedes_decision_id` | 被当前 decision 替代的旧 decision，可空 |
| `superseded_by_decision_id` | 替代当前 decision 的新 decision，可空 |
| `embedding_text` / `embedding_vector` | 用于同类型 similarity-assisted candidate resolution |
| `embedding_model` / `embedding_version` | embedding 模型与版本 |
| `created_at` / `updated_at` | 创建与更新时间 |
| `derived_from_session_id` / `derived_from_run_id` | 来源追踪，可选 |
| `source_refs` | 来源引用，可选 |

---

**D. `action_memory`**

保存项目行动项、后续任务和待办事项。

| Field | Description |
| --- | --- |
| `action_id` | Primary key |
| `user_id` | 用户归属 |
| `project_id` | 所属项目 |
| `parent_decision_id` | 来源 decision，可空 |
| `action_title` | 行动项标题 |
| `action_description` | 行动项描述 |
| `action_status` | 业务状态，例如 `todo`, `in_progress`, `blocked`, `done`, `cancelled` |
| `priority` | 优先级 |
| `owner` | 负责人，可选 |
| `due_at` | 截止时间，可选 |
| `blocking_reason` | 阻塞原因，可选 |
| `result_summary` | 完成结果摘要，可选 |
| `completed_at` | 完成时间，可选 |
| `record_status` | memory 生命周期状态，例如 `active`, `archived`, `pruned` |
| `confidence` | 置信度 |
| `embedding_text` / `embedding_vector` | 用于同类型 similarity-assisted candidate resolution |
| `embedding_model` / `embedding_version` | embedding 模型与版本 |
| `created_at` / `updated_at` | 创建与更新时间 |
| `derived_from_session_id` / `derived_from_run_id` | 来源追踪，可选 |
| `source_refs` | 来源引用，可选 |

`Action` 必须属于某个 project，但不强制绑定 decision：

```
project_id required
parent_decision_id optional
```

---

**E. `preference_policy_memory`**

保存用户偏好、输出规则、项目约束和行为策略。

| Field | Description |
| --- | --- |
| `policy_id` | Primary key |
| `user_id` | 用户归属 |
| `project_id` | 所属项目，可空 |
| `scope_type` | 作用范围，例如 `global`, `project`, `task_type`, `memory_type` |
| `scope_value` | 具体 scope 值，可空 |
| `policy_type` | 规则类型，例如 `preference`, `constraint`, `format_rule`, `behavior_rule` |
| `policy_text` | 规则正文 |
| `conditions` | 触发条件，可用 JSON |
| `priority` | 冲突处理优先级 |
| `enforcement_level` | 执行强度，例如 `soft`, `default`, `strict` |
| `record_status` | `active`, `superseded`, `archived`, `pruned` |
| `confidence` | 置信度 |
| `supersedes_policy_id` | 被当前 policy 替代的旧 policy，可空 |
| `superseded_by_policy_id` | 替代当前 policy 的新 policy，可空 |
| `embedding_text` / `embedding_vector` | 用于同类型 similarity-assisted candidate resolution |
| `embedding_model` / `embedding_version` | embedding 模型与版本 |
| `created_at` / `updated_at` | 创建与更新时间 |
| `derived_from_session_id` / `derived_from_run_id` | 来源追踪，可选 |
| `source_refs` | 来源引用，可选 |

---

**F. Embedding Usage**

每类 structured memory table 可以维护自己的 embedding 字段，用于同类型的 `similarity-assisted candidate resolution`。

```
new decision candidate
  -> search similar active decisions

new action candidate
  -> search similar active actions

new preference / policy candidate
  -> search similar active policies
```

Embedding 是 retrieval representation，不是 memory 本体。

最终是否 create / update / supersede / no-write，仍由 application logic 和 LLM / rule-based reconciliation 决定。

### 6.4.3 Research Knowledge Memory Schema

`Research Knowledge Memory` 用于保存可复用、可追溯、可治理的 research knowledge units。

当前设计采用：

```
Research Knowledge Memory -> PostgreSQL + pgvector
```

核心表为：

```
research_knowledge_units
```

该表同时保存 Knowledge Unit 的内容、scope、source、freshness、canonical / dedupe 状态和 embedding representation。

---

#### A. Core Table: `research_knowledge_units`

**Identity / Scope Fields**

| Field | Description |
| --- | --- |
| `knowledge_id` | Primary key，唯一标识一条 knowledge unit |
| `owner_user_id` | 用户归属边界 |
| `project_scope_id` | 可选，表示该 knowledge 是否绑定到某个 project |
| `visibility_scope` | 声明的可见范围，例如 `user`, `project`, `domain`, `global` |
| `visibility_scope_effective` | 实际生效的可见范围，用于 read path filtering |

---

**Content Fields**

| Field | Description |
| --- | --- |
| `title` | knowledge unit 标题 |
| `summary` | 提炼后的核心内容 |
| `knowledge_type` | 知识类型，例如 `concept`, `method`, `comparison`, `conclusion`, `tradeoff`, `pattern` |
| `topic_tags` | 主题标签，可用 JSON / array 保存 |
| `confidence` | 系统对该 knowledge 的置信度 |

`Research Knowledge Unit` 保存的是 summary-level knowledge，而不是 raw chunk 或完整原始材料。

---

#### Source / Provenance Fields

| Field | Description |
| --- | --- |
| `source_refs` | 来源引用，可先用 JSON / array 保存 |
| `source_type` | 主要来源类型，例如 `paper`, `web_page`, `user_upload`, `conversation`, `run_output` |
| `derived_from_session_id` | 来源 session，可选 |
| `derived_from_run_id` | 来源 Agent execution，可选 |
| `created_by` | 可选，例如 `system`, `user`, `llm` |

其中：

- `source_refs` 表示 evidence-level provenance
- `derived_from_session_id` 表示 session-level provenance
- `derived_from_run_id` 表示 execution-level provenance

---

**Lifecycle Fields**

| Field | Description |
| --- | --- |
| `status` | lifecycle 状态，例如 `active`, `superseded`, `archived`, `pruned` |
| `created_at` | 创建时间 |
| `updated_at` | 更新时间 |
| `archived_at` | 归档时间，可空 |
| `pruned_at` | prune 时间，可空 |

默认 read path 只读取：

```
status = active
```

---

**Freshness Fields**

| Field | Description |
| --- | --- |
| `freshness_sensitivity` | 数据是否容易变旧，例如 `low`, `medium`, `high` |
| `freshness_status` | 当前新鲜度状态，例如 `fresh`, `aging`, `stale` |
| `last_verified_at` | 最近一次被 evidence 验证或刷新时间 |
| `freshness_checked_at` | 最近一次 freshness evaluation 时间，可选 |
| `staleness_reason` | 被降级为 aging / stale 的原因，可选 |

freshness 字段会影响 ranking、refresh trigger 和 pruning policy。

---

**Canonical / Dedupe Fields**

| Field | Description |
| --- | --- |
| `dedupe_key` | 用于识别近似重复 knowledge 的归一化 key |
| `canonical_knowledge_id` | 当前 record 所属 canonical knowledge 的 ID |
| `is_canonical` | 当前 record 是否是 canonical record |
| `merged_into_id` | 若当前 record 已并入其他 knowledge，则指向目标 knowledge ID |

默认主召回集合应满足：

```
status = active
AND is_canonical = true
AND merged_into_id IS NULL
```

这些字段用于支持 duplicate control、canonical replacement、merge 和旧 knowledge exclusion。

---

**Embedding Fields**

| Field | Description |
| --- | --- |
| `embedding_text` | 用于生成 embedding 的文本，通常由 `title + summary` 构成 |
| `embedding_vector` | pgvector 向量字段，用于 semantic recall |
| `embedding_model` | embedding 模型名称 |
| `embedding_version` | embedding 版本 |

Embedding 是 retrieval representation，不是 knowledge 本体。

当 `title` 或 `summary` 发生实质变化时，应重新生成 embedding。

---

#### B. Default Read Eligibility

一条 knowledge unit 只有满足以下条件，才进入默认召回集合：

```
owner_user_id matches current user
AND visibility_scope_effective is allowed
AND project_scope_id matches or is allowed
AND status = active
AND is_canonical = true
AND merged_into_id IS NULL
```

召回后，系统可以进一步应用：

- freshness-aware ranking
- source quality adjustment
- confidence adjustment
- task-specific selection rules

---

#### C. Design Notes

- `research_knowledge_units` 是 reusable research knowledge 的 source of truth。
- `embedding_vector` 只服务 semantic recall，不定义 knowledge 本体。
- `source_refs` MVP 阶段可先用 JSON / array 保存，后续如 source-level audit、reuse、refresh 需求增强，可拆成独立 Source Reference schema。
- `status`、`freshness_status`、`canonical_knowledge_id`、`is_canonical`、`merged_into_id` 是核心治理字段，不应视为普通 metadata。
- `archived`、`pruned`、`superseded` 或 merged records 可以留在存储中用于 audit 和 traceability，但不应进入默认召回路径。

### 6.4.4 Source Reference Schema

`Source Reference` 用于表示 memory / knowledge 所依赖的 evidence 来源。

它是 cross-cutting provenance schema（多类memory共享的来源追踪结构），可被 `Research Knowledge Unit`、`Decision Memory`、`Preference / Policy Memory`、optional `Run / Execution Log` 等引用。

它主要支持：

- evidence traceability
- refresh / verification
- recommendation explanation
- audit / debugging
- future source-level reuse

---

#### A. MVP Format: Embedded `source_refs`

MVP 阶段，`Source Reference` 先作为 JSON / array 字段嵌入到 memory / knowledge record 中。

```json
{
  "source_type": "paper",
  "source_uri": "https://...",
  "title": "...",
  "author_or_publisher": "...",
  "published_at": "2024-02-01T00:00:00Z",
  "retrieved_at": "2026-04-29T10:00:00Z",
  "evidence_span": {
    "page": 3,
    "section": "Abstract",
    "paragraph": 2
  },
  "citation_text": "...",
  "metadata": {}
}
```

| Field | Description |
| --- | --- |
| `source_type` | 来源类型，例如 `paper`, `web_page`, `user_upload`, `conversation`, `run_output`, `code_repo` |
| `source_uri` | 来源地址，例如 URL、file path、paper id、repo path |
| `title` | 来源标题 |
| `author_or_publisher` | 作者、发布方或来源机构 |
| `published_at` | source 原始发布时间，可空 |
| `retrieved_at` | 系统获取该 source 的时间 |
| `evidence_span` | 证据片段位置，例如 page、section、paragraph、line range |
| `citation_text` | 可选的短引用或 citation label |
| `metadata` | source-specific metadata |

---

#### B. Embedded JSON vs Normalized Table

当前选择：

```
source_refs embedded JSON / array
```

**Pros**

- 实现简单
- 不需要额外 source table
- 写入路径轻
- 适合 source 数量较少的阶段

**Cons**

- source 去重和复用较弱
- 不方便查询“某个 source 支撑了哪些 memory”
- source-level audit、refresh、quality control 能力有限

---

#### C. Future Normalized Schema

如果后续 source 查询、审计、复用或 refresh 需求增强，可以拆成独立表：

```
source_references
- source_ref_id
- source_type
- source_uri
- title
- author_or_publisher
- published_at
- retrieved_at
- metadata_json
- created_at
- updated_at
```

再通过 link table 关联到 memory / knowledge：

```
memory_source_links
- source_ref_id
- target_type
- target_id
- evidence_span
- relevance_note
- created_at
```

该设计可支持：

- source-level reuse
- source-level verification
- 查询某个 source 支撑的所有 records
- source quality governance
- refresh 时按 source 重新验证相关 knowledge

---

#### D. Boundary with Other Provenance

`Source Reference` 回答：

```
这条 memory / knowledge 的 evidence 来源是什么？
```

`Session / Message / Run Provenance` 回答：

```
这条 memory / knowledge 是在哪次交互或执行过程中产生的？
```

因此：

- `source_refs` = evidence-level provenance
- `derived_from_session_id` = session-level provenance
- `derived_from_message_ids` = message-level provenance，optional
- `derived_from_run_id` = execution-level provenance

这些字段可以并存，不互相替代。

### 6.4.5 Optional Persistent Trace Schemas

本节定义可选的持久化 trace schemas，用于支持历史回看、debug、audit 和 provenance reconstruction。

这些 schema 不属于 core memory store，也不替代 Redis-backed `Session Memory`。

当前阶段，这些表是 optional：

```
conversation_sessions
message_log
run_execution_log
```

---

#### A. `conversation_sessions`

`conversation_sessions` 保存 session-level metadata，不保存 Session Memory 本体。

| Field | Description |
| --- | --- |
| `session_id` | Primary key，连续多轮 session ID |
| `user_id` | 用户归属边界 |
| `title` | session 标题，可由系统自动生成 |
| `session_status` | `active`, `archived`, `deleted` |
| `created_at` / `updated_at` | 创建与更新时间 |
| `last_message_at` | 最近一条 message 时间 |
| `archived_at` / `deleted_at` | 归档 / 删除时间，可空 |
| `metadata_json` | 可选扩展字段 |

```
Conversation Session = persistent session metadata
Session Memory        = Redis-backed compact working memory
```

---

#### B. `message_log`

`message_log` 保存用户与系统之间的原始或近原始消息历史，用于历史回看、debug、audit 和 provenance reconstruction。

| Field | Description |
| --- | --- |
| `message_id` | Primary key，单条消息 ID |
| `user_id` | 用户归属边界 |
| `session_id` | 所属 session |
| `run_id` | 关联的 Agent execution，可空 |
| `role` | `user`, `assistant`, `system`, `tool` |
| `content` | 消息正文 |
| `content_format` | `text`, `markdown`, `json` |
| `created_at` | 消息创建时间 |
| `parent_message_id` | 父消息 ID，可用于未来支持分支对话 |
| `metadata_json` | 可选扩展字段 |

`Message Log` 不参与主 read path 的低延迟上下文注入，也不替代 Redis 中的 `Session Memory`。

如果启用它，long-term memory 可通过 `derived_from_message_ids` 追溯到具体消息。

---

#### C. `run_execution_log`

`run_execution_log` 保存一次 Agent execution 的执行 trace。

它关注系统“做了什么”，而不是用户和 assistant “说了什么”。

| Field | Description |
| --- | --- |
| `run_id` | Primary key，一次 Agent execution ID |
| `user_id` | 用户归属边界 |
| `session_id` | 所属 session |
| `trigger_message_id` | 触发本次 run 的 user message，可空 |
| `run_type` | `research`, `planning`, `recommendation`, `action` |
| `task_type` | `topic_exploration`, `comparison`, `action_planning` |
| `input_summary` | 本次 run 输入摘要 |
| `plan_json` | 本次 run 的 plan，可选 |
| `tool_calls_json` | 工具调用记录 |
| `retrieved_evidence_refs` | 本次 run 检索到的 evidence refs |
| `intermediate_findings_json` | 中间发现 |
| `memory_candidates_json` | 本次 run 生成的 memory candidates |
| `output_summary` | 最终输出摘要 |
| `run_status` | `started`, `succeeded`, `failed`, `cancelled` |
| `error_message` | 失败原因，可空 |
| `created_at` / `completed_at` | 创建与完成时间 |
| `metadata_json` | 可选扩展字段 |

当前阶段不强制实现完整 run log。

如果未实现完整 run log，`run_id` 仍可作为 provenance identifier 使用。

---

#### D. Design Notes

三类 optional trace schema 的关系是：

```
user_id
  └── session_id / conversation_sessions
        ├── message_log
        └── run_execution_log
```

它们和 `Session Memory` 的边界是：

```
Conversation Session = session metadata
Message Log          = persistent message history
Run Execution Log    = execution trace
Session Memory       = Redis-backed compact working memory
```

这些表是 optional，不影响 core memory storage 的基本运行。

如果启用 `Message Log`，`session_id` 可以从 weak provenance 增强为可回查的 session-level provenance。

如果启用 `Run / Execution Log`，`derived_from_run_id` 可以支持更强的 execution-level audit。

### 6.4.6 Common Field Conventions

本节统一 storage schema 中的通用字段命名和语义，避免不同表中出现同名不同义、同义不同名、status 混用、scope 混用或 provenance 混用。

---

#### A. ID Field Conventions

| Field | Meaning |
| --- | --- |
| `user_id` / `owner_user_id` | 用户归属边界 |
| `session_id` | 连续多轮 session 的边界 |
| `run_id` | 一次具体 Agent execution |
| `message_id` | 单条消息 ID，optional |
| `project_id` | 稳定的逻辑项目 ID |
| `project_profile_id` | 某一版 project profile record |
| `decision_id` | 某条 decision memory |
| `action_id` | 某条 action memory |
| `policy_id` | 某条 preference / policy memory |
| `knowledge_id` | 某条 research knowledge unit |

说明：

```
project_id != project_profile_id
```

`project_id` 表示稳定项目身份；`project_profile_id` 表示该项目下某一版 profile record。初始 profile 可以复用同一个 ID，但系统逻辑不应依赖二者相等。

---

#### B. Status Field Conventions

| Field | Meaning |
| --- | --- |
| `record_status` | Structured Long-term Memory record 的生命周期状态 |
| `status` | Research Knowledge Unit 的生命周期状态 |
| `session_status` | optional conversation session 状态 |
| `run_status` | optional run execution 状态 |
| `freshness_status` | knowledge 当前新鲜度状态 |
| `decision_state` | decision 的业务状态 |
| `action_status` | action 的业务状态 |

需要区分：

```
record_status / status = memory lifecycle state
decision_state / action_status = domain-specific business state
freshness_status = freshness governance state
```

例如：

```
record_status = active
action_status = done
```

二者可以同时成立，不应混用。

---

#### C. Timestamp Field Conventions

| Field | Meaning |
| --- | --- |
| `created_at` | record 创建时间 |
| `updated_at` | record 最近更新时间 |
| `archived_at` | record 被 archive 的时间 |
| `pruned_at` | record 被 prune 的时间 |
| `completed_at` | action 或 run 完成时间 |
| `expires_at` | Redis Session Memory 的逻辑过期时间 |
| `published_at` | source 原始发布时间 |
| `retrieved_at` | source 被系统获取的时间 |
| `last_verified_at` | knowledge 最近一次被 evidence 验证仍成立的时间 |
| `freshness_checked_at` | knowledge 最近一次被系统检查 freshness 的时间 |

说明：

```
last_verified_at = 验证过
freshness_checked_at = 检查过
```

---

#### D. Provenance Field Conventions

| Field | Meaning |
| --- | --- |
| `source_refs` | evidence-level provenance |
| `derived_from_session_id` | session-level provenance |
| `derived_from_message_ids` | message-level provenance，optional |
| `derived_from_run_id` | execution-level provenance |
| `created_by` | record 创建者，例如 `system`, `user`, `llm` |

说明：

```
source_refs = 内容依据来自哪里
derived_from_session_id / derived_from_message_ids / derived_from_run_id
= 这条 memory 是在哪次交互或执行过程中产生的
```

---

#### E. Scope and Visibility Field Conventions

| Field | Meaning |
| --- | --- |
| `project_id` | Structured Long-term Memory 的项目归属 |
| `project_scope_id` | Research Knowledge Unit 的 project-level scope |
| `scope_type` | Preference / Policy 的作用范围类型 |
| `scope_value` | Preference / Policy 的具体 scope 值 |
| `visibility_scope` | Research Knowledge Unit 声明的可见范围 |
| `visibility_scope_effective` | read path 实际使用的可见范围 |

说明：

- `project_id` 主要用于 Structured Long-term Memory
- `project_scope_id` 主要用于 Research Knowledge Memory
- `scope_type + scope_value` 主要用于 Preference / Policy Memory

---

#### F. Embedding Field Conventions

| Field | Meaning |
| --- | --- |
| `embedding_text` | 用于生成 embedding 的文本 |
| `embedding_vector` | 向量字段 |
| `embedding_model` | embedding 模型名称 |
| `embedding_version` | embedding 版本 |

说明：

```
Embedding = retrieval representation
```

Embedding 不是 memory / knowledge 本体。

当 `embedding_text` 对应内容发生实质变化时，需要重新生成 `embedding_vector`。

---

#### G. JSON / Array Field Conventions

JSON / array 字段适合保存灵活、类型专属、低频查询的数据。

典型字段包括：

| Field | Example |
| --- | --- |
| `source_refs` | 来源引用列表 |
| `constraints` | 项目约束 |
| `alternatives` | 决策备选方案 |
| `tradeoffs` | 决策取舍 |
| `conditions` | policy 触发条件 |
| `topic_tags` | knowledge 主题标签 |
| `metadata_json` | 扩展信息 |

原则：

```
Fields used for primary filtering, lifecycle control, ranking, or reconciliation
should be first-class columns.

Flexible, type-specific, or low-frequency queried data
can be stored as JSON / array fields.
```

## 6.5 Indexing and Query Patterns

本节定义 storage layer 的核心查询模式和初始索引方向。

本节不追求完整数据库调优，而是说明 schema 如何支撑主要 read / write path。更多索引应在实现阶段根据真实查询、数据量和 profiling 结果逐步补充。

---

### 6.5.1 Session Memory Access Pattern

`Session Memory` 存储在 Redis 中，主要通过 `user_id + session_id` 做 key-based lookup。

```
session_memory:{user_id}:{session_id}
```

典型访问模式：

```
Before run:
  load session_memory:{user_id}:{session_id}

After run:
  update session_summary / recent_turns / current_focus / open_questions
  refresh TTL
```

由于 Redis key 已直接包含主读取边界，`Session Memory` 不需要额外索引。

TTL 用于清理不再活跃的 compact working memory。

---

### 6.5.2 Structured Long-term Memory Query Patterns

`Structured Long-term Memory` 采用 PostgreSQL multi-table layout。

核心查询以 `user_id`、`project_id`、`record_status` 和各 memory type 的业务状态字段为主。

#### Project Profile

典型查询：

```
Load active project profile:
  user_id + project_id + record_status = active
```

初始索引建议：

```
(user_id, project_id, record_status)
```

同一 `user_id + project_id` 下通常最多只有一条 active profile。

---

#### Decision Memory

典型查询：

```
Load active decisions under a project:
  user_id + project_id + record_status = active

Find similar decisions:
  user_id + project_id + record_status + embedding similarity
```

初始索引建议：

```
(user_id, project_id, record_status)
(user_id, project_id, decision_state)
vector index on embedding_vector
```

---

#### Action Memory

典型查询：

```
Load active actions under a project:
  user_id + project_id + record_status = active

Load actions by domain status:
  user_id + project_id + action_status

Load actions derived from a decision:
  parent_decision_id
```

初始索引建议：

```
(user_id, project_id, record_status)
(user_id, project_id, action_status)
(parent_decision_id)
vector index on embedding_vector
```

---

#### Preference / Policy Memory

典型查询：

```
Load applicable policies:
  user_id + scope_type + scope_value + record_status = active

Load project-level policies:
  user_id + project_id + record_status = active
```

初始索引建议：

```
(user_id, scope_type, scope_value, record_status)
(user_id, project_id, record_status)
(user_id, policy_type, record_status)
vector index on embedding_vector
```

---

### 6.5.3 Research Knowledge Memory Query Patterns

`Research Knowledge Memory` 使用 PostgreSQL + pgvector。

默认 read path 是：

```
metadata pre-filter
  -> vector similarity recall
  -> freshness-aware ranking
  -> bounded selection
```

典型查询条件包括：

```
owner_user_id
visibility_scope_effective
project_scope_id
status
is_canonical
merged_into_id
knowledge_type
```

默认召回集合应满足：

```
owner_user_id matches current user
AND visibility_scope_effective is allowed
AND project_scope_id matches or is allowed
AND status = active
AND is_canonical = true
AND merged_into_id IS NULL
```

初始索引建议：

```
(owner_user_id, visibility_scope_effective, project_scope_id, status)
(status, is_canonical, merged_into_id)
(owner_user_id, knowledge_type, status)
vector index on embedding_vector
```

召回后，系统可以基于以下字段做 reranking 或 filtering：

```
freshness_status
freshness_sensitivity
last_verified_at
confidence
source_type
```

这些字段不一定都需要初始索引，应根据实际查询频率决定。

---

### 6.5.4 Source Reference Query Patterns

MVP 阶段，`source_refs` 以内嵌 JSON / array 形式保存在 memory / knowledge record 中，因此不做独立 source-level 索引。

如果后续将 `Source Reference` 规范化为独立表，则需要支持：

```
Find all memories supported by a source
Find all knowledge units from a source_type
Find records requiring refresh by source
```

未来索引方向：

```
source_references(source_type, source_uri)
memory_source_links(source_ref_id, target_type, target_id)
```

---

### 6.5.5 Optional Trace Query Patterns

如果启用 optional persistent trace schemas，可支持以下查询。

#### Conversation Sessions

```
List sessions by user:
  user_id + session_status + updated_at
```

初始索引建议：

```
(user_id, session_status, updated_at)
```

#### Message Log

```
Load messages under a session:
  user_id + session_id + created_at
```

初始索引建议：

```
(user_id, session_id, created_at)
(run_id)
```

#### Run Execution Log

```
Find runs under a session:
  user_id + session_id + created_at

Find failed runs:
  user_id + run_status + created_at
```

初始索引建议：

```
(user_id, session_id, created_at)
(user_id, run_status, created_at)
```

这些 trace schemas 是 optional，不影响 core memory read path。

---

### 6.5.6 Index Evolution Policy

初始索引只覆盖核心 read path 和明确的 write reconciliation path。

系统不应在 MVP 阶段过度建索引，因为每个索引都会增加写入成本、存储成本和 schema 维护复杂度。

索引演进应基于：

```
actual query patterns
data volume
slow query logs
EXPLAIN / EXPLAIN ANALYZE
production-like workload
```

原则如下：

- 高频 filter / join / sort 字段应优先列化并建立索引。
- JSON / array 字段不应承担核心高频查询。
- pgvector index 类型和参数应根据数据量与 benchmark 决定。
- 如果某类 memory 的数据量或查询复杂度明显增长，可以为该表增加类型专属索引。
- 如果 Research Knowledge Memory 的向量检索成为瓶颈，可考虑从 PostgreSQL + pgvector 演进到 PostgreSQL + Milvus。

## 6.6 Lifecycle and Mutation Support

~~6.6.1 Status Fields~~

~~6.6.2 Supersession / Canonical Fields~~

~~6.6.3 Archive and Prune Fields~~

生命周期与变更策略主要在 `5.4` 和 `5.5` 中定义。

本节只说明 storage schema 如何支撑这些策略，不重新定义策略本身。

- `Session Memory` 通过 Redis TTL 支持短期运行时工作记忆的过期清理。
- `Structured Long-term Memory` 通过 `record_status`、`supersedes_*`、`superseded_by_*` 支持 update、supersession、archive 和 pruning。
- `Research Knowledge Memory` 通过 `status`、`freshness_status`、`last_verified_at`、`canonical_knowledge_id`、`is_canonical`、`merged_into_id` 支持 freshness governance、dedupe、canonical replacement、archive 和 pruning。
- Optional `Message Log` 和 `Run / Execution Log` 可增强 provenance 与 auditability，但不是核心生命周期流转的必要依赖。
- 生命周期状态变更不应散落在各处 SQL 中，而应封装到统一的 repository / service 方法中，确保 archive、supersede、merge、refresh 等操作始终按同一套规则更新相关字段。

# 7. Risks, Trade-offs, and Open Questions  (Optional)

本节只汇总当前 LLD 中已知的主要风险、已接受的取舍和暂缓决策，不重复前文已经展开讨论过的设计细节。

---

## 7.1 Key Risks

- `Session Memory` 存储在 Redis 中，若 Redis 故障或 TTL 过期，当前 session continuity 可能下降，但不会影响 long-term memory 的正确性。
- `Structured Long-term Memory` 采用 multi-table layout，schema 更清晰，但会增加 repository、migration 和公共 mutation logic 的实现复杂度。
- `Research Knowledge Memory` 采用 PostgreSQL + pgvector，能够简化治理字段与向量召回的一致性，但未来在大规模向量检索或高 QPS 场景下可能遇到性能瓶颈。
- freshness、canonical、dedupe、archive / pruning 等治理逻辑依赖应用层正确实现；若规则执行不一致，可能导致 stale knowledge 被过度使用或旧 canonical record 未被正确排除。
- 如果 optional `Message Log` / `Run Execution Log` 暂不实现，则 provenance 和 auditability 能力较弱，`session_id` 只能提供 weak provenance。

---

## 7.2 Accepted Trade-offs

- 选择 Redis 保存 `Session Memory`，优先满足 hot session state 的低延迟、高频读写和 TTL 需求，同时接受额外组件复杂度和较弱持久化语义。
- 选择 PostgreSQL 保存 `Structured Long-term Memory`，优先满足长期结构化记录、状态流转、事务更新和 similarity-assisted candidate resolution 的需求。
- 选择 multi-table layout 保存 structured memory，优先获得更清晰的 schema 和类型内查询能力，同时接受多表和多 repository 的实现成本。
- 选择 PostgreSQL + pgvector 保存 `Research Knowledge Memory`，优先保证 metadata、freshness、canonical / dedupe 字段和 vector recall 位于同一 storage backend 中，同时接受其向量规模能力弱于 Milvus。
- MVP 阶段 `source_refs` 可先以内嵌 JSON / array 形式保存，优先降低 schema 和写入路径复杂度，同时接受较弱的 source-level reuse 和 audit 能力。

---

## 7.3 Open Questions / Deferred Decisions

- 是否在 MVP 中实现持久化 `Conversation Session` 和 `Message Log`。
- 是否实现完整 `Run / Execution Log`，用于 execution-level audit、debug、replay 和 evaluation。
- `Source Reference` 是否长期保持 embedded JSON，还是后续拆成 `source_references` 与 link table。
- 何时从 PostgreSQL + pgvector 演进到 PostgreSQL + Milvus。
- `Session Memory` 的具体 TTL、compaction threshold、recent turns window 大小需要在实现和测试中进一步确定。
- 各类 memory 的具体 index 组合、pgvector index 类型和参数应根据真实数据量、query pattern 和 profiling 结果逐步调整。