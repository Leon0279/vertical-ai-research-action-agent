# Research Runtime LLD

# 1. Scope and Positioning

### 1.1 Purpose

本篇文档的目的，是在既定 HLD 之下，对 **Research Stage 的执行机制**做 low-level design 展开。

它重点关注的是：Research Stage 如何执行、如何触发 retrieval 和 tool usage、如何处理 raw results，以及如何将 research 过程推进到可供 downstream conclusion generation 使用的状态。

因此，本篇主要关注：

- research execution
- retrieval triggering and usage
- evidence processing
- stage-internal state flow
- stop / degraded mode / runtime guardrails

---

### 1.2 Position in the Overall Architecture

在整体系统中，本篇主要展开 HLD 中 **Execute Research / Reasoning Loop** 这一部分，以及与其紧密相关的：

- tool selection and invocation
- retrieval triggering
- evidence shaping
- intermediate findings production
- stop / continue / degraded mode control

从 workflow 位置上看，本篇所设计的部分位于：

- `Planning and Decomposition Component` 之后
- `Conclusion Generator` 之前

因此，本篇不是对整个系统的全量实现设计，而是对 **Research Stage 这一段执行路径** 的细化。

---

### 1.3 In-Scope for This LLD

本篇 LLD 主要覆盖以下内容：

- Research Stage 的 execution model
- `Research Executor` 与 `Tool Execution Layer` 的运行时关系
- retrieval 在 Research Stage 中的触发和使用方式
- raw tool / retrieval result 到 usable evidence 的处理流程
- Research Stage 内部的 state and data flow
- stop policy、degraded mode 和 runtime guardrails
- research-stage observability hooks

---

### 1.4 Out-of-Scope for This LLD

本篇不展开以下内容：

- memory 的底层 schema 与存储实现
- `Session Continuity Manager` 的内部设计
- `Conclusion Generator` 的内部生成策略
- 完整的 evaluation framework
- deployment topology、queue / worker、async offloading 等基础设施实现

这些内容要么已经在 HLD 中定义，要么属于其他 LLD 的范围。

---

### 1.5 Relationship to Other Design Documents

HLD 仍然是本篇的顶层 source of truth。

本篇不会修改 HLD 中已经确定的：

- workflow-driven outer architecture + agentic inner loop
- staged single-agent topology
- task-type routing
- stateful, memory-aware execution model
- Core Components 的职责边界

本篇还必须继承 `Context, Memory, and Storage LLD Shared Decisions` 中已经确定的 cross-cutting constraints，例如：

- context should be constructed, not dumped
- memory read does not imply direct context injection
- external retrieved content 默认不是 memory
- session / long-term / research knowledge memory 的职责分工
- scope / freshness / relevance / budget 对 context construction 的约束

---

### 1.6 Positioning Summary

本篇的定位可以概括为：

**它不是整个系统的实现说明，也不是 memory/storage LLD 的延伸，而是对 Research Stage 执行路径的专门细化。**

# 2. Inherited Constraints

本篇 LLD 不从空白状态重新设计 Research Stage，而是在既定 HLD 和已定的 `Context, Memory, and Storage LLD Shared Decisions` 之下展开。因此，以下约束默认成立，并应作为后续所有设计的前提。

### 2.1 HLD Is Still the Top-level Source of Truth

本篇默认接受 HLD 中已经确定的顶层架构方向，包括：

- workflow-driven outer architecture + agentic inner loop
- staged single-agent topology
- task-type routing
- stateful, memory-aware execution model
- Core Components 的职责边界

因此，本篇不重新讨论系统总形态，也不重新打开 multi-agent、fully autonomous agent 或 core component 重划分等顶层问题。

### 2.2 Research Stage Must Respect the Established Context Boundary

本篇必须继承已经确定的上下文边界：

- `RunningState` 是单次 request lifecycle 内的 canonical mutable state
- `SupplementalContext` 是 supporting context
- `ExecutionContext = RunningState + SupplementalContext + Runtime Metadata / Capabilities`
- `StageInput` 是某一 stage 从 `ExecutionContext` 中投影出的输入子集

这意味着：

- `Research Executor` 不直接消费完整 `ExecutionContext`
- `Research Stage` 开始时，从 `ExecutionContext` 构造一次该 stage 的 `StageInput`
- stage 内部迭代主要围绕当前 `StageInput` 及其派生的 **stage-local working state** 推进
- `ExecutionContext` 只在 stage 边界读写；Research Stage 结束后，再统一回写结果

### 2.3 Context Must Be Constructed, Not Dumped

本篇必须继承以下原则：

**Execution Context should be constructed, not dumped.**

因此，在 Research Stage 中：

- memory loading 不是全量导入
- retrieval result 不是自动注入
- tool output 不是天然可直接进入推理输入
- context 的形成必须受 relevance、scope、freshness、budget 和 stage need 约束

Research Stage 不能建立在“拿到什么就直接喂给 LLM”的模式上，而应建立在“先形成候选材料，再做选择、整形和放置决策”的模式上。

### 2.4 Memory Read, Retrieval Result, and Tool Output Are Candidates First

本篇必须继承以下运行时约束：

- memory read result
- retrieval result
- tool output

首先都只是**候选材料**，而不是当前轮 LLM 推理的直接输入。

它们必须先经过：

- filtering
- summarization / compression
- redundancy control
- placement decision

之后，才可能以受控形式进入当前 stage 内部用于推理的输入表示。

因此，`Research Executor` 不应直接消费 raw results，而应消费经过处理后的 evidence representation 或其他 stage-local working input。

### 2.5 Memory Is Not Raw Log

Research Stage 必须继承以下长期原则：

**memory 不是 raw log，不是完整历史归档，而是面向未来复用的信息资产。**

因此，本篇不会把以下内容默认视为 memory：

- raw execution traces
- raw tool payloads
- full conversation dump
- 低价值临时中间结果
- 低置信度弱结论

本篇只定义 Research Stage 如何获取和处理 evidence、形成 intermediate findings，并为 downstream stages 提供结构化输出；memory write-back 仍由 post-response distillation / persistence path 负责。

### 2.6 The Three Memory Types Remain Strictly Separated

Research Stage 必须继承三类 memory 的职责分工：

1. **Session Short-term Memory**：只服务同一 session continuity
2. **Structured Long-term Memory**：保存 project / decision / action / preference 等结构化长期信息
3. **Research Knowledge Memory**：保存可复用 research knowledge，主要通过 semantic / hybrid recall 使用

因此：

- session memory 不被当作 knowledge base
- structured long-term memory 不被当作 raw retrieval corpus
- research knowledge memory 不被当作 project state store

### 2.7 External Retrieved Content Is Not Memory by Default

本篇必须继承以下约束：

**tool-acquired external context 默认不是 memory。**

papers、repos、docs、web search results 和 raw retrieved evidence 在 runtime 中首先都是 external supporting material，而不是 memory record。只有在 request 完成后的 post-response distillation 中，它们才可能被提升为 durable memory。

因此，本篇不会把 external retrieval flow 和 memory write-back flow 混写成同一条链路。

### 2.8 Research Knowledge Memory Does Not Replace External Retrieval

Research Stage 还必须继承一个关键边界：

**Research Knowledge Memory 不替代 retrieval tool。**

当任务需要：

- fresh evidence
- 更细粒度来源
- source traceability
- 当前 knowledge memory 未覆盖的信息

应触发 external retrieval / tool handoff，而不是过度依赖本地 knowledge memory。

因此，本篇默认区分两类 evidence acquisition path：

- memory-based recall
- external retrieval

### 2.9 Scope Boundaries Must Be Enforced

Research Stage 中的 retrieval、tool result usage 和 recommendation support，必须遵守已定 scope 约束，包括：

- user scope
- session scope
- run scope
- project scope
- visibility scope

因此，本篇后续所有 retrieval、context construction 和 evidence placement 设计，都默认受 scope filtering 约束。

### 2.10 Practical Implication

基于以上约束，后续本篇的设计必须满足以下总体要求：

- Research Stage 是 **bounded, stage-aware, context-constructed execution path**
- `StageInput` 在 stage 进入时由 `ExecutionContext` 投影生成
- stage 内部迭代主要更新 **stage-local working state**
- memory read、retrieval result、tool output 先作为候选材料，再经过 processing 后进入当前 stage 的可用 evidence 表示
- `ExecutionContext` 只在 stage 边界读写，不作为 stage 内每轮循环的直接工作对象
- memory / storage 语义继续沿用已定约束，但不会在本篇中重新展开底层实现

---

# 3. Research Stage Responsibilities

### 3.1 Definition

`Research Stage` 是系统中负责执行 research-stage work 的子系统。

它接收上游阶段已经构造好的 stage-specific input，在既定上下文边界和 runtime 约束下，推进 evidence-seeking loop，触发 tool and retrieval usage，处理 raw results，形成 intermediate findings，并在条件满足时结束 research stage，将结构化结果交给 downstream conclusion generation。

换句话说，Research Stage 的职责不是直接生成最终用户响应，而是：

**把当前任务推进到“证据已处理、findings 已形成、足以进入 conclusion generation”的状态。**

---

### 3.2 Role in the Overall Architecture

在整体系统中，Research Stage 位于：

- `Planning and Decomposition Component` 之后
- `Conclusion Generator` 之前

它处于 HLD 的 **Execute Research / Reasoning Loop** 这一段执行路径中，负责把上游已经解释过、分解过并完成 context construction 的任务输入，推进为 downstream 可消费的 research-stage outputs。

因此，Research Stage 既不是一个独立的全局 orchestrator，也不是单纯的 retrieval wrapper，而是：

**围绕 evidence acquisition、evidence shaping 和 intermediate findings production 的执行阶段。**

---

### 3.3 Upstream Inputs

Research Stage 的输入不是完整 `ExecutionContext`，而是从其中投影出来的 stage-specific input。

这些输入通常包括：

- 当前任务目标与 task framing
- relevant project context 和 constraints
- planning artifacts，例如 plan、sub-questions 或 comparison candidates（如果存在）
- 已被选入当前 stage 的 context / memory-derived inputs
- runtime metadata 和 budget-related signals

Research Stage 的起点不是原始信息全集，而是：

**当前 stage 被明确允许看到的那部分输入。**

---

### 3.4 Downstream Outputs

Research Stage 不直接输出最终用户响应，而是向 downstream stages 提供结构化 research-stage outputs。

这些输出通常包括：

- processed evidence
- evidence summary
- intermediate findings
- comparison-ready findings（当任务需要 comparison 时）
- confidence-related signals
- unresolved gaps / caveats
- stop reason 或 degraded mode signal（如适用）

这些输出的作用是让 `Conclusion Generator` 可以在不重新执行 research loop 的前提下，完成最终 conclusion synthesis。

---

### 3.5 Core Responsibilities

Research Stage 的核心职责包括：

1. **Drive the Research Loop**
推进 research-stage execution，而不是把 research 视为一次性静态处理。
2. **Identify Evidence Needs**
判断当前还缺少什么 evidence，以及哪些 gaps 会影响 downstream conclusion quality。
3. **Trigger Tool and Retrieval Usage**
在合适的时候触发 memory-based recall、external retrieval 或 tool usage，并决定当前轮走哪类 evidence path。
4. **Shape Usable Evidence**
将 raw results 处理为当前 stage 可用的 evidence representation，包括 filtering、summarization、compression、redundancy control 和 evidence organization。
5. **Produce Intermediate Findings**
逐步形成 intermediate findings，而不是直接替代 `Conclusion Generator` 产出最终结论。
6. **Decide Stop, Continue, or Degrade**
判断 research 是否已足够结束，是否需要继续下一轮，或是否应进入 degraded mode。

---

### 3.6 Responsibility Boundaries

Research Stage 不负责以下内容：

- **重新解释用户请求**
这属于 `Task Interpretation Component` 的职责。
- **重新选择 workflow pattern**
这属于 `Workflow Router` 的职责。
- **生成最终面向用户的结论表达**
这属于 `Conclusion Generator` 的职责。
- **决定 long-term memory persistence**
是否写入 durable memory 由 `Memory Distillation and Persistence Component` 决定。
- **维护 session continuity state**
这属于 `Session Continuity Manager` 的职责。

---

### 3.7 Summary

Research Stage 的职责可以概括为：

**在既定上下文边界和运行时约束下，驱动 evidence-seeking loop，组织 tool and retrieval usage，处理 raw evidence，形成 intermediate findings，并在适当时机结束 research stage，将结构化结果交给 downstream conclusion generation。**

它既不是全局 orchestrator，也不是单纯的 retrieval wrapper，更不是最终 response generator。

它的核心价值在于：

**把“需要研究的问题”推进成“已经具备结论生成条件的问题”。**

# 4. Research Execution Model

## 4.1 Execution Pattern

Research Stage 采用 **planning-guided, evidence-driven, iterative execution** 的执行模式。

这意味着，Research Stage 既不是一次性静态处理流程，也不是无边界的开放式自主探索，而是在既定 task framing、context boundary 和 runtime budget 约束下，围绕 evidence acquisition 与 findings refinement 逐步推进当前任务。

### Planning-guided

Research Stage 的执行受到上游 planning artifacts 的引导，例如：

- `plan`
- `sub_questions`
- `comparison_candidates`

这些 artifacts 提供高层执行方向、优先级和研究目标，使 runtime 不必从空白状态决定“应该研究什么”。

但它们只起 **guiding structure** 的作用，而不是 rigid script。Research Stage 不要求逐条机械执行 plan，而是允许根据当前 evidence state、remaining gaps 和 runtime budget 动态调整执行重点。因此，本阶段的完成标准仍然是 **evidence sufficiency**，而不是“是否完整走完 plan”。

### Evidence-driven

Research Stage 的推进由当前 evidence state 驱动，而不是由预设结论驱动。

system 应持续围绕以下问题推进：

- 当前已经掌握了哪些 evidence
- 这些 evidence 支持了什么
- 还缺少哪些关键 evidence
- 当前 evidence 是否已经足以支撑 downstream conclusion generation

因此，tool usage、retrieval triggering、evidence processing 和 intermediate findings refinement，都应围绕 **evidence need** 展开。

### Iterative

Research Stage 不是 one-shot execution，而是一个受控的 iterative process。

在每一轮迭代中，system 都会基于当前 stage-local working state：

- 评估当前 research progress
- 识别 remaining evidence gaps
- 决定是否需要新的 retrieval / tool usage
- 将新获得的材料处理为可用 evidence
- 更新 intermediate findings
- 判断是否进入下一轮

这种迭代模式的价值在于：

- 避免在 research 初期无控制地获取过多低价值材料
- 允许 runtime 随 evidence state 的变化及时调整方向
- 在 evidence 已足够时尽早结束
- 在 evidence 不足或冲突较强时进入 degraded mode

### Bounded Execution

虽然 Research Stage 是 iterative 的，但它不是 open-ended exploration。

本设计默认其执行受到以下边界约束：

- context boundary
- scope boundary
- freshness constraint
- runtime budget
- stage need
- stop / degraded mode policy

因此，Research Stage 的运行目标不是“尽可能多地收集信息”，而是：

**在受控边界内，将当前任务推进到足以支持 downstream conclusion generation 的状态。**

### Practical Implication

基于上述执行模式，后续设计应保持以下一致性：

- `Research Executor` 是 loop driver，而不是一次性 processor
- planning artifacts 提供方向，但不替代运行时 evidence-driven decision making
- retrieval 与 tool usage 的触发，应由当前 evidence gap 驱动
- evidence processing 是 iterative execution 的必要组成部分
- stop / continue / degrade decision 是执行模型的一部分，而不是附加逻辑

## 4.2 Stage Entry and Initial Input Construction

Research Stage 不是从空白状态开始执行。

当该 stage 被触发时，上游 stages 已经完成了任务解释、上下文加载、workflow routing，以及必要的 planning / decomposition。因此，Research Stage 的入口不是重新理解用户问题，而是**接管一个已经构造好的 stage-specific task context**。

### 4.2.1 Stage Entry Boundary

Research Stage 位于：

- `Task Interpretation Component`
- `Context and Memory Loader`
- `Workflow Router`
- `Planning and Decomposition Component`

之后。

因此，Research Stage 默认接收的，不是原始用户请求，也不是未经筛选的 memory / retrieval / tool materials，而是上游阶段已经整理过的一组执行前提。

Research Stage 不重新执行：

- 用户请求解释
- task type 判断
- workflow 选择
- 全量 context loading

它的职责起点是：

**在既定 task framing 和已构造上下文之上，开始 evidence-seeking execution。**

### 4.2.2 Source of Initial Input

Research Stage 的初始输入来源于当前 `ExecutionContext`，但并不直接消费完整 `ExecutionContext`。

按照已定约束，本阶段在开始时，应从 `ExecutionContext` 中投影出一个 **stage-specific `StageInput`**，作为当前 stage 的入口输入。

因此：

- `ExecutionContext` 是总体运行上下文
- `StageInput` 是当前 stage 真正需要消费的输入子集
- `Research Executor` 进入 stage 后，首先消费的是 `StageInput`

### 4.2.3 Initial Input Construction

初始 `StageInput` 的构造，应建立在上游已经完成的 context construction 结果之上，而不应在 `Research Stage` 入口重新执行一轮完整的 context loading。

这意味着，`Research Stage` 在开始时不是重新从各类 memory store 或 external retrieval source 中独立选择输入，而是从当前 `ExecutionContext` 中，进一步投影出当前 stage 真正需要消费的输入子集。

在这一过程中，最直接的约束是：

- **scope**：满足既定的 user / session / project / visibility boundary
- **stage need**：与当前 `Research Stage` 的研究目标直接相关
- **input budget**：初始输入规模必须受控，避免在 stage 入口一次性注入过多 supporting material

对于 **relevance** 和 **freshness**，本阶段通常继承上游 `Context and Memory Loader` 已完成的筛选结果，而不是重新做一轮完整评估。当前阶段入口更关心的是：

**在这些已筛选材料中，哪些内容应进入当前 stage 的初始输入。**

因此，初始 `StageInput` 的构造本质上是一次**受控投影**，而不是一次新的全量上下文装载。

### 4.2.4 Initial Input Categories

Research Stage 的初始 `StageInput` 通常由以下几类信息构成：

- **Task Framing**：当前研究目标、task type、user goal 的执行表达
- **Relevant Project Context and Constraints**：project context、constraints、优先级和当前阶段边界
- **Planning Artifacts**：如 `plan`、`sub_questions`、`comparison_candidates`
- **Selected Context / Memory-derived Inputs**：已被选择过的相关 memory/context material
- **Runtime Metadata and Budget Signals**：runtime budget、tool capability context、execution constraints

### 4.2.5 Initialization of Stage-local Working State

`StageInput` 进入 Research Stage 后，stage 应基于其初始化一份 **stage-local working state**，用于支撑后续多轮迭代。

其初始化通常包括：

- 当前 research objective 的执行态表示
- planning guidance 的可执行表示
- 初始 supporting context
- 当前已知 evidence baseline（如果存在）
- unresolved gaps 的初始判断
- 初始 intermediate findings（如有）

需要强调的是：

- `StageInput` 是 stage 的入口输入
- stage-local working state 是 stage 内部迭代所依赖的工作状态

Research Stage 后续每轮迭代主要更新的是 stage-local working state，而不是反复重新生成完整初始输入，也不是在 stage 内不断改写 `ExecutionContext`。

### 4.2.6 Practical Implication

基于上述设计，Research Stage 的入口机制应满足以下要求：

- stage 入口依赖上游已完成的 task interpretation、context construction 和 planning
- `StageInput` 在 stage 开始时由 `ExecutionContext` 投影生成
- 初始输入只包含当前 stage 需要消费的内容，而不是全部可得上下文
- stage 进入后，应基于初始 `StageInput` 初始化 stage-local working state，供后续 research iterations 使用

因此，Research Stage 的入口不是“把所有已有材料交给 executor”，而是：

**为当前研究阶段建立一个受控、相关且可迭代推进的执行起点。**

## 4.3 Canonical Research Loop Structure

Research Stage 在内部采用一个 **canonical research loop** 作为标准执行骨架。

该 loop 的目标，不是一次性完成全部 research work，而是围绕当前 research objective、已有 evidence 和 remaining gaps，逐轮推进当前任务，直到达到 stop condition 或进入 degraded mode。

因此，Research Stage 的执行不是 one-shot processing，而是一个受控的 iterative process。每一轮循环都从当前的 **stage-local working state** 出发，而不是重新读取完整 `ExecutionContext`。

### 4.3.1 Loop Overview

canonical research loop 的基本目标是：

- 评估当前研究进展
- 识别当前最需要补充的 evidence 或最需要推进的 research gap
- 在必要时触发 retrieval 或 tool usage
- 将新材料处理为当前 stage 可用的 evidence representation
- 更新 stage-local working state
- refine intermediate findings
- 判断是否继续、停止或退化

因此，Research Stage 的标准循环不是“不断获取更多材料”，而是：

**围绕 evidence need 的逐轮收敛过程。**

---

### 4.3.2 Canonical Per-iteration Flow

在当前设计中，一轮标准 research iteration 通常包含以下步骤：

#### Step 1. Assess Current Research State

首先评估当前 stage-local working state，明确：

- 当前已经掌握了哪些 evidence
- 当前 findings 已经推进到什么程度
- 当前还存在哪些 unresolved gaps
- 当前 evidence 是否已经接近 sufficiency threshold

#### Step 2. Identify the Next Evidence Need

基于当前 research state，识别这一轮最值得解决的 evidence need 或 research gap。

这一步的目标不是同时推进所有问题，而是确定当前轮次最有价值的下一步。

#### Step 3. Decide Whether External Action Is Needed

在明确当前轮的 evidence need 后，判断是否需要额外动作来推进研究，例如：

- memory-based recall
- external retrieval
- tool usage
- 或在已有 evidence 基础上直接推进 findings refinement

因此，并不是每一轮都必须调用 retrieval 或 tool。

#### Step 4. Acquire Candidate Material

如果当前轮判断需要额外 evidence，则触发相应的 retrieval / tool path，获取新的候选材料。

这里获得的内容仍然只是 candidate material，而不是当前轮可直接用于推理的最终输入。

#### Step 5. Process Candidate Material into Usable Evidence

将当前轮获得的 candidate material 处理为当前 stage 可消费的 evidence representation。

这一步通常包括选择、整形、压缩、去重或组织，但具体机制留在后续 evidence processing 章节展开。

#### Step 6. Update Stage-local Working State

将本轮新形成的 processed evidence、updated gaps 和新的 supporting signals 并入当前 stage-local working state，使其成为下一步判断与推理的基础。

#### Step 7. Produce or Refine Intermediate Findings

基于更新后的 working state，生成或修正当前的 intermediate findings。

这一步的目标不是直接产出最终用户响应，而是逐步形成更完整、更可支撑 downstream conclusion generation 的 research-stage result。

#### Step 8. Evaluate Iteration Outcome

在本轮结束时，判断当前 research stage 下一步应进入哪种状态：

- **continue**：仍有关键 evidence gap，且继续推进有价值
- **stop**：当前 findings 已足以支持 downstream conclusion generation
- **degrade**：当前证据不足、冲突较强、预算受限或外部依赖失败，需要以退化方式收束本阶段

---

### 4.3.3 Mandatory vs Conditional Steps

在上述 loop 中，并非所有步骤都以相同方式出现。

#### Mandatory Steps

以下步骤在概念上是每轮都需要出现的：

- assess current research state
- identify the next evidence need
- update stage-local working state
- evaluate iteration outcome

#### Conditional Steps

以下步骤是条件触发的：

- memory-based recall
- external retrieval
- tool invocation
- additional evidence acquisition
- extra evidence shaping for comparison or conflict resolution

是否进入这些步骤，取决于当前轮的 evidence need，而不是固定脚本强制执行。

---

### 4.3.4 Iteration Outputs

每一轮循环结束后，Research Stage 至少应得到以下几类更新结果：

- updated evidence state
- updated intermediate findings
- updated unresolved gaps
- updated stage-local working state
- iteration outcome signal（continue / stop / degrade）

这些结果主要保留在 stage 内部，用于驱动下一轮循环。只有在 Research Stage 结束时，最终 stage result 才统一回写到 `ExecutionContext`，供 downstream stages 使用。

---

### 4.3.5 Loop Closure Point

canonical research loop 的每一轮都以内置的 outcome evaluation 作为收束点。

也就是说，Research Stage 不是开放式无限循环，而是每轮都必须显式回答：

- 当前 evidence 是否已经足够
- 当前 gaps 是否仍值得继续补充
- 当前预算是否允许继续推进
- 当前是否应以 degraded mode 收束

因此，continue / stop / degrade 决策是 loop 结构的一部分，而不是附加在 loop 之外的事后判断。

---

### 4.3.6 Summary

Research Stage 的 canonical research loop 可以概括为：

**从当前 stage-local working state 出发，评估研究进展，识别下一步 evidence need，在必要时触发 retrieval / tool usage，将新材料处理为可用 evidence，更新 working state，refine intermediate findings，并在每轮末尾判断是否继续、停止或退化。**

## 4.4 **Research State Assessment, Gap Identification, and Prioritization**

### 4.4.1 Purpose

本小节的目标，是定义在每一轮 research iteration 开始时，Research Stage 如何基于当前 **stage-local working state** 评估当前研究进展，并识别当前最值得推进的 **next evidence need**。

这一步的重点不是决定具体调用哪个 tool，也不是立即执行新的 retrieval，而是先回答以下问题：

- 当前 research 已经推进到什么程度
- 当前 evidence 已经支持了什么
- 当前仍然缺少什么
- 哪些 gap 最影响 downstream conclusion quality
- 在当前预算和约束下，下一步最值得补充的 evidence 是什么

因此，`Research State Assessment and Gap Identification` 的作用，是为后续的 **action decision before evidence acquisition** 提供判断基础，而不是直接替代该决策本身。

在本设计中，这一步的核心价值在于：

- 防止 runtime 盲目扩展 research scope
- 防止 system 在 evidence 已经足够时继续低价值检索
- 防止 system 在未明确 gap 的情况下随意触发 retrieval 或 tool usage
- 使每一轮 research loop 都围绕当前最关键的研究缺口推进，而不是围绕静态脚本推进

换句话说，本小节定义的是：

**Research Stage 如何在每一轮开始时“看清当前局面”，并据此确定下一步最值得获取的 evidence。**

### 4.4.2 Assessment Inputs

Research State Assessment 的输入应来自当前 **stage-local working state** 中已经整理好的运行时信息，而不是完整 `ExecutionContext`，也不是 raw retrieval / tool outputs。

为便于实现，建议将 assessment 所需输入收敛为一组明确字段。MVP 阶段至少可包含以下字段。

#### A. Objective and Framing Fields

**字段：`current_research_objective`**

含义：当前 `Research Stage` 正在推进的研究目标，是 assessment 的主判断对象。

**字段：`task_type`**

含义：当前任务类型，用于影响 assessment 时对 evidence sufficiency 和 gap priority 的判断方式。

**字段：`task_framing`**

含义：当前任务的执行表达，用于说明当前研究问题是如何被 framing 的。

**字段：`constraints`**

含义：当前 research 需要遵守的限制条件，例如范围限制、优先级限制或其他执行约束。

---

#### B. Planning Guidance Fields

**字段：`plan`**

含义：当前可用的高层执行计划，用于为 assessment 提供整体推进方向。

**字段：`sub_questions`**

含义：当前任务被拆分出的子问题列表，用于判断 coverage 与 gap 是否集中在某些未解决子问题上。

**字段：`comparison_candidates`**

含义：若任务属于 comparison 类任务，则表示当前待比较对象列表，用于辅助判断 comparison coverage 和 imbalance。

---

#### C. Evidence State Fields

**字段：`processed_evidence`**

含义：当前 stage 内已经整理完成、可供使用的 evidence 集合或 evidence items。

**字段：`evidence_summary`**

含义：对当前 evidence state 的压缩表示，用于快速判断 coverage、support strength 和 unresolved areas。

**字段：`evidence_coverage_map`**

含义：当前 evidence 对 objective、sub-question、candidate 或 dimension 的覆盖情况。

如果 MVP 阶段不单独维护该字段，也可由 `evidence_summary + sub_questions + comparison_candidates` 组合推断。

**字段：`evidence_source_signals`**

含义：当前 evidence 的来源分布或来源摘要，用于辅助判断 support strength、freshness 和 comparison balance。

MVP 阶段可选。

---

#### D. Findings and Gap Fields

**字段：`intermediate_findings`**

含义：当前已经形成的中间研究结论，用于判断当前 findings 的成熟度和稳定性。

**字段：`finding_caveats`**

含义：当前 findings 已附带的 caveats、uncertainty 或 open issues。

MVP 阶段可选，但有助于 assessment 更稳定。

**字段：`identified_gaps`**

含义：当前已经识别出的 unresolved gaps 列表。若本轮不是第一次 assessment，则应优先复用已有 gaps，而不是每轮从零开始。

---

#### E. Runtime Control Fields

**字段：`iteration_index`**

含义：当前是第几轮 iteration，用于辅助判断当前是否仍值得继续扩展 research。

**字段：`remaining_iteration_budget`**

含义：当前还允许进行多少轮 research iteration。

**字段：`input_budget_pressure`**

含义：当前输入上下文压力，用于判断是否仍适合继续引入新 evidence。

推荐枚举值可为：`low / medium / high`

**字段：`available_capabilities`**

含义：当前阶段可用的 retrieval / tool capability 摘要，用于帮助判断某些 gap 是否现实可补。

此字段不直接决定 action path，但会影响 feasibility judgment。

---

#### Recommended Minimum Assessment Input Set

MVP 阶段建议 assessment 至少直接消费以下字段：

```
current_research_objective
task_type
task_framing
constraints
plan
sub_questions
comparison_candidates
processed_evidence
evidence_summary
intermediate_findings
identified_gaps
iteration_index
remaining_iteration_budget
input_budget_pressure
```

这组字段已经足以支持后续判断：

- 当前 objective 是否已被基本覆盖
- 当前 findings 是否仍然 tentative
- 当前最关键的 unresolved gap 是什么
- 当前是否仍值得继续 seek external evidence

---

#### Practical Implementation Note

实现上，不要求这些字段全部由 LLM 自由推断。更现实的方式是：

- **规则 / 程序侧** 提供结构化输入
例如：`sub_questions`、`comparison_candidates`、`remaining_iteration_budget`、`iteration_index`
- **LLM 或 model-assisted logic** 读取这些字段后进行语义 assessment
例如：判断当前 findings 是否稳定、当前最关键的 gap 是什么、下一步最值得补什么 evidence

因此，本小节定义的这些字段，应被理解为：

**Research State Assessment 在每轮开始时应读取的最小运行时输入视图。**

### 4.4.3 Assessment Dimensions

在每一轮 research iteration 开始时，Research Stage 应先基于当前 **stage-local working state** 做一次轻量 assessment。

这一步的目标，是先形成一组对当前 research state 的**状态描述**，供后续 gap identification 使用，而不是在这一节里直接完成 top gap 选择或 action decision。

因此，本小节中的 **Assessment Dimensions** 是：

**用于描述当前研究状态的判断维度，而不是 gap 本身。**

---

#### A. Coverage Assessment

判断：**当前关键问题是否已被 evidence 基本覆盖。**

建议输出字段：

**字段：`coverage_status`**

含义：当前问题的 evidence 覆盖程度。

推荐枚举值：

- `covered`
- `partially_covered`
- `not_covered`

**字段：`coverage_notes`**

含义：简要说明哪些 sub-question 或 comparison dimension 已覆盖，哪些仍为空白。

这一维度回答的是：

**当前问题有没有被证据触达。**

---

#### B. Support Strength Assessment

判断：**当前已有 evidence 的支撑力度是否足够。**

建议输出字段：

**字段：`support_strength`**

含义：当前 evidence 对 findings 的支撑强度。

推荐枚举值：

- `strong_enough`
- `weak_support`
- `conflicting_support`
- `insufficient_support`

**字段：`support_notes`**

含义：简要说明 evidence 偏弱、冲突或间接的原因。

这一维度回答的是：

**当前已有证据够不够支撑 findings。**

---

#### C. Finding Maturity Assessment

判断：**当前 intermediate findings 的成熟度如何。**

建议输出字段：

**字段：`finding_maturity`**

含义：当前 findings 离 downstream conclusion generation 还有多远。

推荐枚举值：

- `tentative`
- `partially_stable`
- `stable`
- `blocked`

**字段：`finding_notes`**

含义：简要说明当前 findings 是否仍依赖关键缺失 evidence，或已接近 downstream-ready。

这一维度回答的是：

**当前 research 结果已经成熟到什么程度。**

---

#### Relationship to Gap Identification

assessment 先输出一组**状态描述字段**，例如：

- `coverage_status`
- `support_strength`
- `finding_maturity`

系统再基于这些状态描述，识别一个或多个 unresolved gaps。

因此，本小节的重点不是列 gap 分类，而是定义：

**系统在识别 gap 之前，应先从哪些维度看清当前 research state。**

---

#### Recommended Minimum Assessment Outputs

MVP 阶段建议 assessment 至少输出：

```
coverage_status
support_strength
finding_maturity
assessment_summary
```

其中：

**字段：`assessment_summary`**

含义：对当前 research state 的 1~3 句总结，用于帮助后续 gap identification 消费 assessment 结果。

---

#### Practical Implementation Note

实现上，更合理的方式是：

- **Assessment** 先输出状态描述
- **Gap Identification** 再基于这些状态描述提炼一个或多个 gaps
- **Gap Prioritization** 再从中选出当前轮的 `top_gap`

因此，这里的 Assessment Dimensions 应被理解为：

**Research Stage 在每轮开始时用于“看清当前局面”的状态判断框架。**

### 4.4.4 Gap Identification and Representation

在当前设计中，Research Stage 不应直接从 assessment 结果跳到 action decision。

在这两者之间，系统需要一个中间步骤：基于当前 research state 的 assessment outputs，识别一个或多个 **unresolved gaps**，并将其表示为结构化对象。

这里的 **gap** 指的是：

**当前 research objective 与当前已支持状态之间，仍未被满足的差距。**

因此，本小节的作用是：

1. 说明系统如何从 assessment outputs 提炼 gaps
2. 定义 gap 在 runtime 中的结构化表示方式

---

#### A. From Assessment Outputs to Gaps

gap identification 的输入不是 raw evidence，而是上一小节已经形成的 assessment outputs，例如：

- `coverage_status`
- `support_strength`
- `finding_maturity`
- `assessment_summary`

系统应基于这些状态描述，识别当前仍然存在的 unresolved gaps。

例如：

- 如果 `coverage_status = not_covered`，则当前可能存在 coverage-related gap
- 如果 `support_strength = weak_support`，则当前可能存在 support-related gap
- 如果 `support_strength = conflicting_support`，则当前可能存在 ambiguity 或 conflict-related gap
- 如果 `finding_maturity = tentative` 或 `partially_stable`，则当前可能存在 readiness-related gap

需要强调的是：

- assessment outputs 描述的是**当前状态**
- gaps 表达的是**当前问题**

因此，gap 不是 assessment dimension 本身，而是系统基于 assessment outputs 提炼出的诊断结果。

---

#### B. Gap as a Structured Object

在当前设计下，gap 不应只用一个扁平标签表示，而应被表示为一个轻量结构化对象。

建议每个 gap 至少包含以下核心字段：

```
gap_scope
gap_nature
gap_severity
gap_summary
```

如有需要，还可以扩展：

```
gap_target
gap_actionability
```

这种表示方式的优点是：

- 可以同时表达多个 gaps
- 可以区分“缺口发生在哪”和“缺口是什么性质”
- 可以为后续 prioritization 提供稳定输入

---

#### C. Core Fields

**字段：`gap_scope`**

含义：缺口主要发生在哪一层对象或研究单元上。

推荐枚举值：

- `objective_level`
- `sub_question_level`
- `comparison_level`
- `candidate_level`
- `dimension_level`
- `finding_level`
- `recommendation_readiness_level`

这个字段回答的是：

**“这个 gap 主要卡在哪一层。”**

---

**字段：`gap_nature`**

含义：缺口的性质是什么。

推荐枚举值：

- `missing`
- `weak`
- `ambiguous`
- `conflicting`
- `imbalanced`
- `stale`
- `not_actionable`
- `none`

这个字段回答的是：

**“这个 gap 本质上是什么问题。”**

---

**字段：`gap_severity`**

含义：该 gap 对当前 Research Stage 的影响程度。

推荐枚举值：

- `blocking`
- `important`
- `optional`
- `none`

这个字段回答的是：

**“这个 gap 有多严重。”**

---

**字段：`gap_summary`**

含义：对当前 gap 的 1~2 句简短说明，通常描述：

- gap 在哪里
- 为什么它重要
- 它如何阻碍当前 research progress

这个字段的作用是提高 gap 的可解释性，并帮助后续 prioritization 更自然地消费 gap 信息。

---

#### D. Optional Fields

**字段：`gap_target`**

含义：gap 具体落在哪个对象上，用于补足 `gap_scope` 的泛化程度。

例如：

- 某个 `sub_question`
- 某个 `candidate`
- 某个 `comparison_dimension`
- 某个 current finding

这个字段回答的是：

**“这个 gap 具体落在谁身上。”**

---

**字段：`gap_actionability`**

含义：该 gap 是否值得在当前轮被优先推进。

推荐枚举值：

- `worth_pursuing_now`
- `pursue_if_budget_allows`
- `defer`
- `not_worth_pursuing`

该字段是可选的。

在更轻的 MVP 中，也可以把这部分判断留到 `4.4.5 Gap Prioritization and Next Evidence Need` 再完成。

---

#### E. Identified Gaps as a Collection

assessment 的结果不应被限制为单一 gap。

更自然的表示方式是：

- 系统可以识别出**多个 unresolved gaps**
- 这些 gaps 以 `identified_gaps` 列表形式存在

例如：

```
identified_gaps = [
  {gap_scope=..., gap_nature=..., gap_severity=..., gap_summary=...},
  {gap_scope=..., gap_nature=..., gap_severity=..., gap_summary=...}
]
```

这里的 `identified_gaps` 表示：

**当前阶段已识别出的缺口集合。**

本小节只定义这些 gaps 如何被识别和表示，不在这里决定哪个 gap 会成为当前轮的 `top_gap`。

---

#### F. Example Gap Objects

以下是几个典型示例。

**1. Missing Evidence on a Sub-question**

```
gap_scope = sub_question_level
gap_nature = missing
gap_severity = blocking
gap_summary = 缺少对某个关键 sub-question 的直接 supporting evidence。
```

**2. Weak Support for a Finding**

```
gap_scope = finding_level
gap_nature = weak
gap_severity = important
gap_summary = 当前 finding 已有方向，但支撑力度不足，仍偏 tentative。
```

**3. Comparison Imbalance on a Dimension**

```
gap_scope = dimension_level
gap_nature = imbalanced
gap_severity = important
gap_summary = 某个 comparison dimension 只对部分 candidate 有材料，导致比较结果不稳定。
```

**4. Freshness Problem**

```
gap_scope = objective_level
gap_nature = stale
gap_severity = important
gap_summary = 当前 evidence 虽相关，但时间上可能过旧，无法可靠支撑当前任务。
```

**5. No Major Gap**

```
gap_scope = objective_level
gap_nature = none
gap_severity = none
gap_summary = 当前没有明显的 blocking 或 important gap。
```

---

#### G. Recommended MVP Representation

如果完整 gap object 对 MVP 仍然偏重，建议至少保留下列结构：

```
identified_gaps
gap_scope
gap_nature
gap_severity
gap_summary
```

也就是说，MVP 阶段至少应支持：

- 基于 assessment outputs 识别多个 gaps
- 每个 gap 使用统一字段表示
- 后续 `4.4.5` 再基于这些 gaps 做 prioritization

这样既比单一 `top_gap_type` 更清楚，也不会一开始就把 gap model 做得太重。

---

#### H. Practical Implementation Note

实现上，不建议系统在每轮都构建完整、长期维护的 gap graph。

更现实的做法是：

1. 先基于 assessment outputs 识别一个轻量的 `identified_gaps` 列表
2. 每个 gap 使用统一字段表示
3. 后续 prioritization 再从中选出当前轮的 `top_gap`

因此，本节定义的 `Gap Identification and Representation` 应被理解为：

**Research Stage 在每轮 assessment 之后，用于提炼并表达多个 unresolved gaps 的轻量结构化中间层。**

### 4.4.5 Gap Prioritization and Next Evidence Need

在每一轮 assessment 之后，Research Stage 可能同时识别出多个 unresolved gaps。

但在 iteration-level execution 中，系统不应让多个 gaps 以同等优先级共同驱动当前轮执行。更合理的做法是：

1. 保留多个 `identified_gaps`
2. 从中选出一个当前轮的 **`top_gap`**
3. 再基于该 `top_gap` 推导出本轮的 **`next_evidence_need`**

这一步的目标，是让当前轮保持单一主目标，避免 retrieval scope 发散和 findings refinement 难以收敛。

---

#### A. Inputs

本步骤通常读取以下输入：

```
identified_gaps
current_research_objective
task_framing
intermediate_findings
finding_maturity
remaining_iteration_budget
input_budget_pressure
available_capabilities
```

其中：

- `identified_gaps` 提供“当前有哪些问题”
- `intermediate_findings` / `finding_maturity` 提供“当前 findings 离可收束还有多远”
- budget / pressure / capabilities 提供“现在值不值得追、追不追得到”

---

#### B. Prioritization Criteria

MVP 阶段建议采用**轻量有序比较**，而不是复杂打分模型。

**1. Severity**

默认优先级：

- `blocking` > `important` > `optional`

**2. Objective Impact**

优先考虑更直接阻塞当前 objective 的 gap，例如：

- 阻止关键 sub-question 被回答
- 让 comparison 结果仍明显不稳定

**3. Downstream Impact**

再看它是否明显影响 downstream conclusion generation，例如：

- findings 还不能形成 recommendation
- research result 还不够 actionable

**4. Expected Gain**

补这个 gap 后，是否有望显著推进当前 research，例如：

- findings 能否从 `tentative` 变 `partially_stable`

**5. Feasibility Under Current Constraints**

最后再看当前是否现实可补，例如：

- 当前预算是否允许
- 当前 input pressure 是否过高
- 当前 capabilities 是否支持

MVP 阶段可采用以下简单规则：

1. 先过滤明显不值得追的 gaps
2. 先比 `gap_severity`
3. 若相同，再比 `objective impact`
4. 若仍相同，再比 `downstream impact`
5. 若仍相同，再比 `expected gain`
6. 若仍相同，再比 `feasibility`
7. 最终选出一个 `top_gap`

---

#### C. Top Gap Selection

Research Stage 应从 `identified_gaps` 中选出当前轮的 **`top_gap`**。

MVP 阶段建议默认只选一个 `top_gap`。只有当两个 gaps 高度耦合、且一次 evidence acquisition 可以同时推进它们时，才允许实现层将其视为一组联动 gap。

建议 `top_gap` 至少输出：

```
top_gap_scope
top_gap_nature
top_gap_severity
top_gap_summary
```

其中：

**字段：`top_gap_summary`**

含义：用 1~2 句说明为什么该 gap 被选为当前轮的主要推进对象。

---

#### D. From Top Gap to Next Evidence Need

`top_gap` 仍然是“问题表达”，后续 action decision 更需要“证据目标表达”。

因此，系统应基于 `top_gap` 生成一个结构化的 **`next_evidence_need`**。

它应回答：

- 当前轮要补哪类 evidence
- 这类 evidence 要服务于哪个对象
- 它要解决 missing、weak、ambiguous、stale，还是 not_actionable 问题
- 是否需要 external evidence

---

#### E. Next Evidence Need Structure

MVP 阶段建议 `next_evidence_need` 至少包含以下字段：

```
need_scope
need_target
need_purpose
desired_evidence_kind
freshness_requirement
minimum_support_requirement
need_summary
```

字段建议如下：

**字段：`need_scope`**

含义：这次 evidence need 主要作用在哪一层。

推荐枚举值：

- `objective_level`
- `sub_question_level`
- `comparison_level`
- `candidate_level`
- `dimension_level`
- `finding_level`
- `recommendation_readiness_level`

**字段：`need_target`**

含义：需要补证据的具体对象，例如某个 `sub_question`、`candidate`、`comparison_dimension` 或 current finding。

**字段：`need_purpose`**

含义：补证据的直接目的。

推荐枚举值：

- `establish_coverage`
- `strengthen_support`
- `resolve_ambiguity`
- `resolve_conflict`
- `rebalance_comparison`
- `refresh_status`
- `improve_actionability`

**字段：`desired_evidence_kind`**

含义：当前更希望获得哪种 evidence。

推荐枚举值：

- `direct_fact`
- `stronger_supporting_evidence`
- `disambiguating_evidence`
- `comparison_evidence`
- `fresh_status_evidence`
- `decision_supporting_evidence`

**字段：`freshness_requirement`**

含义：这次 evidence 对时效性的要求。

推荐枚举值：

- `normal`
- `fresh_preferred`
- `fresh_required`

**字段：`minimum_support_requirement`**

含义：本轮对证据支撑强度的最低要求。

推荐枚举值：

- `any_relevant_signal`
- `moderate_support`
- `strong_support`

**字段：`need_summary`**

含义：用 1~2 句总结当前轮最值得补什么 evidence，以及为什么。

---

#### F. Recommended Outputs

本步骤建议至少输出：

```
top_gap_scope
top_gap_nature
top_gap_severity
top_gap_summary
next_evidence_need
```

如需更实用，可再增加：

```
prioritization_summary
```

---

#### G. Practical Prioritization Flow

MVP 阶段可采用以下轻量流程：

1. Read `identified_gaps`
2. Drop gaps that are clearly out of scope or not worth pursuing now
3. Compare remaining gaps by:
    - severity
    - objective impact
    - downstream impact
    - expected gain
    - feasibility
4. Select one `top_gap`
5. Translate `top_gap` into structured `next_evidence_need`
6. Emit outputs for downstream action decision

实现上，更现实的方式是：

- **规则 / 程序逻辑** 先处理明显确定的约束
- **LLM 或 model-assisted logic** 再做语义优先级判断和 `next_evidence_need` 生成

---

#### H. Practical Implementation Note

在 MVP 中，Gap Prioritization 和 Next Evidence Need derivation 在逻辑上是两个子步骤，但实现上可以通过**一次结构化 LLM 调用**联合产出：

- `top_gap`
- `next_evidence_need`
- `prioritization_summary`

本小节的核心要求是：

**系统应先从多个 gaps 中选出一个当前轮的 `top_gap`，再将其转换为一个结构化的 `next_evidence_need`，用于驱动后续 action decision。**

### 4.4.6 Outputs

本小节前面的几个步骤，最终应产出一组可被后续 `4.5 Action Decision Before Evidence Acquisition` 直接消费的结构化结果。

这些输出不应只是大段自然语言分析，而应尽量收敛为少量、稳定、可传递的字段。

在当前设计下，`4.4 Research State Assessment and Gap Identification` 的输出可分为三层。

#### A. State Description Outputs

这一层用于描述当前 research state 本身，主要来自 assessment。

建议至少包括：

```
coverage_status
support_strength
finding_maturity
assessment_summary
```

其中：

**字段：`coverage_status`**

含义：当前关键问题的 evidence 覆盖程度。

推荐枚举值：

- `covered`
- `partially_covered`
- `not_covered`

**字段：`support_strength`**

含义：当前 evidence 对 findings 的支撑强度。

推荐枚举值：

- `strong_enough`
- `weak_support`
- `conflicting_support`
- `insufficient_support`

**字段：`finding_maturity`**

含义：当前 intermediate findings 的成熟度。

推荐枚举值：

- `tentative`
- `partially_stable`
- `stable`
- `blocked`

**字段：`assessment_summary`**

含义：对当前 research state 的 1~3 句总结，用于帮助后续 gap identification 和 action decision 更自然地消费 assessment 结果。

---

#### B. Gap Identification Outputs

这一层用于表达 assessment 之后识别出的 unresolved gaps。

建议至少包括：

```
identified_gaps
```

其中：

**字段：`identified_gaps`**

含义：当前已识别出的 unresolved gaps 列表。

每个 gap 建议至少包含：

```
gap_scope
gap_nature
gap_severity
gap_summary
```

如果实现需要，也可扩展：

```
gap_target
gap_actionability
```

这一层的作用是：

**保留系统对多个问题的整体认识，而不是在识别 gap 后立即丢失其他未被当前轮优先处理的缺口。**

---

#### C. Iteration-driving Outputs

这一层用于把多个 gaps 收敛为当前轮的主目标，并为后续 action decision 提供直接输入。

建议至少包括：

```
top_gap_scope
top_gap_nature
top_gap_severity
top_gap_summary
next_evidence_need
```

其中：

**字段：`top_gap_scope` / `top_gap_nature` / `top_gap_severity`**

含义：当前轮最高优先级 gap 的结构化表示。

**字段：`top_gap_summary`**

含义：用 1~2 句说明为什么该 gap 被选为当前轮的主要推进对象。

**字段：`next_evidence_need`**

含义：当前轮最值得补充的 evidence objective。

建议使用结构化对象，而不是单一字符串。

其最小结构建议包括：

```
need_scope
need_target
need_purpose
desired_evidence_kind
freshness_requirement
minimum_support_requirement
need_summary
```

---

#### Recommended Minimum Output Set

MVP 阶段，建议 `4.4` 整体至少输出以下字段：

```
coverage_status
support_strength
finding_maturity
assessment_summary
identified_gaps
top_gap_scope
top_gap_nature
top_gap_severity
top_gap_summary
next_evidence_need
```

如果希望更便于后续 action decision，也可增加：

```
prioritization_summary
```

**字段：`prioritization_summary`**

含义：用 1~3 句总结为什么当前轮选择了这个 `top_gap`，以及为什么当前的 `next_evidence_need` 最值得优先推进。

---

### 4.4.7 High-level Flow

本小节前面的步骤可以概括为以下高层流程：

1. Read assessment inputs from the current stage-local working state.
2. Produce a small set of state descriptors, such as `coverage_status`, `support_strength`, and `finding_maturity`.
3. Identify one or more `identified_gaps` based on these state descriptors.
4. Prioritize the identified gaps and select a single `top_gap` for the current iteration.
5. Translate the `top_gap` into a structured `next_evidence_need`.
6. Emit structured outputs for downstream action decision.

因此，`4.4` 的整体作用可以概括为：

**从当前 research state 出发，先形成状态判断，再提炼 gaps，随后选出当前轮最值得优先推进的 gap，并将其转换为下一步的 evidence objective。**

## 4.5 Action Decision Before Evidence Acquisition

### 4.5.1 Purpose and Positioning

本小节的目标，是定义在当前轮的 `top_gap` 和 `next_evidence_need` 已形成之后，Research Stage 如何决定：

- 当前轮是否需要新的 evidence acquisition
- 如果需要，应进入哪类高层 action mode
- 如果需要进一步执行 acquisition，应向 Tool Execution Layer 传递什么样的 `action_request`

因此，`4.5 Action Decision Before Evidence Acquisition` 的职责，不是重新执行 assessment、gap identification 或 gap prioritization，而是基于这些上游结果，做一次**面向执行的动作决策**。

在整体链路中，本小节位于：

- `4.4 Research State Assessment and Gap Identification` 之后
- `5. Tooling and Retrieval Model` 之前

它的作用，是将上游已经形成的“问题表达”和“证据目标表达”进一步转化为：

- 高层动作路径选择
- 面向执行层的 request 构造

因此，本小节主要回答的是：

**当前轮接下来应该如何推进，而不是当前轮还缺什么。**

本小节只负责：

- 选择高层 action mode
- 构造执行请求的上层表示

它不负责：

- 重新判断 `top_gap`
- 重新生成 `next_evidence_need`
- 展开具体 tool registry、query construction 或底层调用细节

---

### 4.5.2 Inputs

本小节的输入，来自当前 stage-local working state 中已经形成的 assessment 和 prioritization 结果，以及当前轮的运行约束。

这些输入的作用，不是重新描述当前研究状态，而是支持当前轮的 **action decision**。

在当前设计下，MVP 阶段建议至少读取以下输入字段。

#### A. Prioritization Outputs

**字段：`top_gap_scope`**

含义：当前轮最高优先级 gap 所在层级。

**字段：`top_gap_nature`**

含义：当前轮最高优先级 gap 的性质，例如 `missing`、`weak`、`ambiguous`、`stale` 等。

**字段：`top_gap_severity`**

含义：当前轮最高优先级 gap 的严重程度，例如 `blocking`、`important`、`optional`。

**字段：`top_gap_summary`**

含义：对当前 top gap 的简短说明。

**字段：`next_evidence_need`**

含义：当前轮最值得补充的 evidence objective，是本小节的核心输入之一。

---

#### B. Current State Summary Fields

**字段：`coverage_status`**

含义：当前关键问题的 evidence 覆盖程度。

**字段：`support_strength`**

含义：当前 evidence 对 findings 的支撑强度。

**字段：`finding_maturity`**

含义：当前 intermediate findings 的成熟度。

**字段：`assessment_summary`**

含义：对当前 research state 的简短总结。

MVP 阶段可选。

---

#### C. Runtime Constraint Fields

**字段：`remaining_iteration_budget`**

含义：当前 research loop 还允许继续多少轮 iteration。

**字段：`input_budget_pressure`**

含义：当前输入上下文压力。

推荐枚举值：

- `low`
- `medium`
- `high`

**字段：`available_capabilities`**

含义：当前阶段可用的 acquisition-related capabilities 摘要。

该字段不直接决定具体 tool，但会影响当前 action mode 是否现实可行。

---

#### Recommended Minimum Input Set

MVP 阶段，建议本小节至少直接消费以下字段：

```
top_gap_scope
top_gap_nature
top_gap_severity
top_gap_summary
next_evidence_need
coverage_status
support_strength
finding_maturity
remaining_iteration_budget
input_budget_pressure
available_capabilities
```

如需更多语义上下文，可再补充：

```
assessment_summary
```

---

#### Practical Implementation Note

实现上，本小节不要求重新读取完整 `processed_evidence` 或重新执行 assessment。

更现实的做法是：

- `4.4` 先把当前轮最重要的判断结果压缩成少量结构化输出
- `4.5` 再基于这些输出和 runtime constraints，做 action mode decision 与 `action_request` 构造

因此，本小节的输入，应被理解为：

**当前轮用于决定“如何推进”的最小决策输入视图。**

---

### 4.5.3 High-level Action Modes

在当前设计中，`4.5` 的第一层决策结果不是具体 tool 名，也不是最终执行参数，而是一个**高层动作模式**（`action_mode`）。

它表示：在当前轮中，Research Stage 决定采用哪一类总体推进路径来响应当前 `top_gap` 和 `next_evidence_need`。

因此，`action_mode` 的作用是：

- 给当前轮提供一个清晰的高层执行分支
- 约束后续 `action_request` 的构造范围
- 将“研究层决策”与“执行层落实”分开

`action_mode` 回答的是：

**“这一轮准备走哪条大路？”**

而不是：

**“这一轮最终调用哪个具体 tool？”**

---

#### A. Recommended Action Modes

MVP 阶段，建议先保留以下三类高层动作模式。

**1. `refine_from_existing_state`**

表示当前轮不发起新的 evidence acquisition，而是基于已有 state 继续推进 research。

适用情况通常包括：

- 当前 evidence 已基本足够，当前更适合 refine findings
- 当前 `top_gap` 不值得继续追
- 当前 findings 已接近可收束状态
- 当前预算或上下文压力不适合继续扩 acquisition

---

**2. `memory_backed_acquisition`**

表示当前轮需要补充证据，但优先通过 memory path 获取，而不是直接走外部 acquisition。

适用情况通常包括：

- 当前 gap 可能由已有 session memory、long-term memory 或 research knowledge 补足
- 当前 evidence need 对 freshness 要求不高
- 当前有较高概率通过已有内部 knowledge 低成本推进 research

在该模式下，后续 `action_request` 应主要约束在 memory-related action family 内。

---

**3. `external_acquisition`**

表示当前轮需要通过外部 source 或更明确的 tool-assisted path 获取新 evidence。

适用情况通常包括：

- 当前 `top_gap` 属于 `missing`、`stale`、`imbalanced` 等更依赖新 evidence 的类型
- memory path 不足以解决当前问题
- 当前 evidence need 需要更细粒度、更新鲜或更可追溯的外部材料

在该模式下，后续 `action_request` 应主要约束在 external acquisition family 内。

---

#### B. What Action Modes Do and Do Not Decide

`action_mode` 只决定当前轮的**高层路径**，不直接决定：

- 最终使用哪个具体 tool
- query 如何构造
- retrieval 参数如何设置
- fallback 如何具体执行

这些内容应由后续 `action_request` 构造和 Tool Execution Layer 消费。

因此：

- `action_mode` 决定当前轮的大方向
- `action_request` 将这一方向细化为可执行请求
- Tool Execution Layer 负责执行该请求，而不是重新做高层研究决策

---

#### C. Relationship to Available Capabilities

`action_mode` 的选择应受 `available_capabilities` 约束。

例如：

- 没有可用的 external capability 时，不应选择 `external_acquisition`
- memory path 不足以满足当前 `next_evidence_need` 时，不应机械地选择 `memory_backed_acquisition`
- 当前没有必要引入新 evidence 时，应优先考虑 `refine_from_existing_state`

因此，`action_mode` 是：

**在当前 `top_gap`、`next_evidence_need` 与当前可用能力共同约束下，Research Executor 做出的高层动作选择。**

---

#### D. Recommended Output Field

MVP 阶段，建议本小节至少产出以下字段：

**字段：`action_mode`**

含义：当前轮的高层动作模式。

推荐枚举值：

- `refine_from_existing_state`
- `memory_backed_acquisition`
- `external_acquisition`

---

#### E. Practical Design Principle

本设计建议：

- 由 **Research Executor** 负责 `action_mode` 的选择
- 由 **Research Executor** 进一步构造与该模式一致的 `action_request`
- 由 **Tool Execution Layer** 负责执行 `action_request`

因此，本小节中的 `High-level Action Modes` 应被理解为：

**Research Executor 在 evidence acquisition 之前做出的高层路径决策。**

### 4.5.4 Action Mode Decision Criteria

`action_mode` 的选择不应完全依赖纯规则，也不应完全依赖无约束的 LLM 判断。

更合理的做法是采用 **“规则预筛 + LLM 语义判断”** 的两阶段方式：

1. **先由规则** 基于 capability、budget 和明显条件筛掉不成立的模式
2. **再由 LLM** 在剩余候选模式中选择最合适的 `action_mode`

MVP 阶段，候选模式为：

- `refine_from_existing_state`
- `memory_backed_acquisition`
- `external_acquisition`

---

#### A. Stage 1: Rule-based Gating

这一阶段由**规则**完成，目标是形成：

```
candidate_action_modes
```

**1. 保留 `refine_from_existing_state` 的条件**

**由规则判断**

当出现以下情况时，应保留该模式：

- `finding_maturity = stable`
- `top_gap_severity = optional`
- `top_gap_nature = none`
- `remaining_iteration_budget` 已较低
- `input_budget_pressure = high`

---

**2. 保留 `memory_backed_acquisition` 的条件**

**由规则判断**

当出现以下情况时，应保留该模式：

- `available_capabilities` 中存在 memory-related capabilities
- `next_evidence_need.freshness_requirement != fresh_required`
- `top_gap_nature` 不明显要求外部新证据
- 当前问题有可能由已有 memory 补足

---

**3. 保留 `external_acquisition` 的条件**

**由规则判断**

当出现以下情况时，应保留该模式：

- `available_capabilities` 中存在 external acquisition capabilities
- `top_gap_nature` 更依赖新外部 evidence，例如：
    - `missing`
    - `stale`
    - `imbalanced`
- `next_evidence_need.freshness_requirement = fresh_required`
- memory path 明显不满足当前 evidence need

---

**4. Hard Exclusion Rules**

**由规则判断**

以下情况可直接排除某些模式：

- 无 memory capability
→ 排除 `memory_backed_acquisition`
- 无 external capability
→ 排除 `external_acquisition`
- `remaining_iteration_budget <= 0`
→ 排除 acquisition 类模式，只保留 `refine_from_existing_state`
- `input_budget_pressure = high` 且 `top_gap_severity != blocking`
→ acquisition 类模式降权，优先保留 `refine_from_existing_state`

---

#### B. Stage 2: Model-assisted Selection

如果规则筛完后只剩一个候选模式，则**直接由规则**选定。

只有当多个候选模式同时成立时，才由 **LLM** 在候选集合中做最终选择。

**由 LLM 判断的重点包括：**

- 哪种模式最可能解决当前 `top_gap`
- 哪种模式最匹配当前 `next_evidence_need`
- 哪种模式最可能推进当前 findings
- external acquisition 是否真的必要，而不只是“可用”

这里的关键是：

**LLM 只在候选集合内做语义判断，不突破规则约束。**

---

#### C. Default Preference Order

当多个模式都可行，且 LLM 没有明显偏好时，建议采用以下默认顺序：

1. `refine_from_existing_state`
2. `memory_backed_acquisition`
3. `external_acquisition`

这体现了当前设计的基本倾向：

- 先避免不必要 acquisition
- 需要 acquisition 时，优先 memory path
- 只有 memory 不足或不适配时，才升级到 external acquisition

---

#### D. Recommended Output Fields

本小节至少应产出：

```
action_mode
action_rationale
```

**字段：`action_mode`**

含义：当前轮最终选定的高层动作模式。

推荐枚举值：

- `refine_from_existing_state`
- `memory_backed_acquisition`
- `external_acquisition`

**字段：`action_rationale`**

含义：用 1~3 句说明为什么当前轮选择该模式。

如果由规则直接确定，也应给出简短规则化说明；如果由 LLM 选出，也应给出简短语义理由。

---

#### E. Practical Decision Flow

MVP 阶段可采用以下流程：

1. Read `top_gap`, `next_evidence_need`, findings state, and runtime constraints
2. **Apply rule-based gating** to form `candidate_action_modes`
3. If only one candidate remains, **select it by rule**
4. If multiple candidates remain, **ask LLM to choose among them**
5. Emit `action_mode` and `action_rationale`

因此，本小节的核心原则是：

**硬约束与明显条件由规则控制，语义匹配与候选模式间权衡由 LLM 辅助完成。**

### 4.5.5 Action Request Construction

在当前设计中，`4.5.4` 已选定当前轮的 `action_mode`。

因此，`4.5.5` 的职责不再是重新判断走哪条路径，而是把该结果转换成传给 Tool Execution Layer 的执行输入对象，即 **`action_request`**。

这里的层次应区分为：

- **`action_mode`**：高层路径决策
- **`action_request`**：执行层输入对象
- **`evidence_acquisition_intent`**：`action_request` 中的核心 payload，用于表达本轮 acquisition 的意图

---

#### A. When `action_request` Is Needed

如果：

- `action_mode = refine_from_existing_state`

则：

```
action_request = null
```

如果：

- `action_mode = memory_backed_acquisition`
- `action_mode = external_acquisition`

则应构造 `action_request`。

---

#### B. Recommended Request Envelope

MVP 阶段，建议：

```
action_request = {
  action_mode,
  evidence_acquisition_intent,
  fallback_policy,
  preferred_tool
}
```

其中：

- `action_mode`：当前轮已选定的高层动作模式
- `evidence_acquisition_intent`：本轮 acquisition 的结构化意图
- `fallback_policy`：失败时允许的 fallback 策略
- `preferred_tool`：若已明确偏好某个 tool，可选传入

---

#### C. Evidence Acquisition Intent

MVP 阶段，建议 `evidence_acquisition_intent` 至少包含：

```
target_scope
target_problem
gap_context
evidence_goal
evidence_shape
constraints
success_hint
```

其中：

**`target_scope`**：这轮 acquisition 服务于哪个研究单元

例如某个 `sub_question`、`candidate`、`comparison_dimension` 或 `finding`

**`target_problem`**：这轮到底要回答什么问题

应是明确的问题表达，而不是泛泛主题

**`gap_context`**：当前为什么要查

建议至少包含：

```
gap_scope
gap_nature
gap_severity
```

**`evidence_goal`**：本轮 acquisition 的直接目标

推荐枚举值：

- `establish_coverage`
- `strengthen_support`
- `resolve_ambiguity`
- `resolve_conflict`
- `refresh_status`
- `rebalance_comparison`
- `improve_actionability`

**`evidence_shape`**：希望拿回什么类型的 evidence

建议至少包含：

```
desired_evidence_kind
freshness_requirement
breadth
```

例如：

- `desired_evidence_kind`：`direct_fact` / `supporting_evidence` / `disambiguating_evidence` / `comparison_evidence` / `status_evidence`
- `freshness_requirement`：`normal` / `fresh_preferred` / `fresh_required`
- `breadth`：`narrow` / `normal` / `broad`

**`constraints`**：执行层必须遵守的硬约束

建议至少包含：

```
allowed_source_families
preferred_source_families
blocked_source_families
max_results
```

**`success_hint`**：什么样的结果算对当前轮有帮助

它只是结果偏好提示，不是最终质量裁判

---

#### D. Mode-specific Constraints

如果：

- `action_mode = memory_backed_acquisition`

则 `constraints.allowed_source_families` 应限制在 memory families 内，例如：

- `session_memory_lookup`
- `long_term_memory_lookup`
- `research_knowledge_recall`

如果：

- `action_mode = external_acquisition`

则 `constraints.allowed_source_families` 应限制在 external families 内，例如：

- `docs_search`
- `paper_search`
- `github_lookup`
- `web_search`

---

#### E. Validation Rules

执行前至少检查：

- `action_mode` 与 `action_request` 是否一致
- `allowed_source_families` 是否与 `action_mode` 一致
- `preferred_tool` 若存在，是否属于允许 family
- `blocked_source_families` 是否与 allowed/preferred 配置冲突
- `freshness_requirement` 是否与允许的 source family 相容
- `target_problem`、`evidence_goal` 与 `next_evidence_need` 是否一致

---

#### F. Practical Note

Research Executor 负责构造 `action_request`。

Tool Execution Layer 负责在该 request 给定的边界内：

- 选择具体 tool
- 生成 query
- 执行
- fallback
- 标准化结果

因此，本小节的核心是：

**把上游的研究决策，转成下游可执行的 acquisition intent。**

#### G. Example

```json
{
  "action_mode": "external_acquisition",
  "evidence_acquisition_intent": {
    "target_scope": "sub_question: retrieval_baseline_need",
    "target_problem": "What is the recommended retrieval baseline for this use case?",
    "gap_context": {
      "gap_scope": "sub_question_level",
      "gap_nature": "missing",
      "gap_severity": "blocking"
    },
    "evidence_goal": "establish_coverage",
    "evidence_shape": {
      "desired_evidence_kind": "direct_fact",
      "freshness_requirement": "fresh_preferred",
      "breadth": "narrow"
    },
    "constraints": {
      "allowed_source_families": ["docs_search", "web_search"],
      "preferred_source_families": ["docs_search"],
      "blocked_source_families": [],
      "max_results": 5
    },
    "success_hint": "At least one direct official guidance statement is preferred."
  },
  "fallback_policy": "fallback_within_same_family",
  "preferred_tool": null
}
```

### 4.5.6 Outputs

本小节前面的步骤，最终应产出一组可被后续执行层直接消费的结构化结果。

MVP 阶段，建议至少输出以下字段：

```
action_mode
action_request
action_rationale
```

---

**字段：`action_mode`**

含义：当前轮最终选定的高层动作模式。

推荐枚举值：

- `refine_from_existing_state`
- `memory_backed_acquisition`
- `external_acquisition`

该字段主要供 Research Executor / runtime control flow 使用，用于决定当前轮后续分支。

---

**字段：`action_request`**

含义：传给 Tool Execution Layer 的执行输入对象。

如果：

- `action_mode = refine_from_existing_state`

则：

```
action_request = null
```

如果：

- `action_mode = memory_backed_acquisition`
- `action_mode = external_acquisition`

则应输出结构化的 `action_request`。

其具体结构定义见 `4.5.5 Action Request Construction`。

该字段主要供 Tool Execution Layer 使用，用于：

- 生成 query
- 选择具体 tool
- 执行
- fallback
- 标准化结果

---

**字段：`action_rationale`**

含义：用 1~3 句说明为什么当前轮选择该 `action_mode`。

如果当前 mode 由规则直接确定，应给出简短规则化说明；

如果由 LLM 在候选模式中选出，应给出简短语义理由。

该字段主要用于：

- observability
- tracing
- debugging
- evaluation

---

#### Optional Outputs

如需增强可观测性，可再增加：

```
candidate_action_modes
decision_summary
```

其中：

- `candidate_action_modes`：规则预筛后保留的候选 modes
- `decision_summary`：对本轮 action decision 的简短总结

MVP 阶段可选。

---

#### Recommended Minimum Output Set

MVP 阶段，建议 `4.5` 整体至少输出：

```
action_mode
action_request
action_rationale
```

这组字段已经足以支持：

- 当前轮控制流分支
- 执行层落地
- 基本可观测性

---

#### Practical Output Principle

`4.5` 的输出应满足：

- **可执行**：执行层能直接消费 `action_request`
- **可控制**：运行时能基于 `action_mode` 决定分支
- **可解释**：能通过 `action_rationale` 理解当前轮决策

因此，本小节的输出应被理解为：

**Research Executor 对当前轮“如何推进”的正式结构化决策结果。**

### 4.5.7 High-level Decision Flow

本小节前面的步骤可以概括为以下高层流程：

1. Read `top_gap`, `next_evidence_need`, current findings state, and runtime constraints.
2. Apply rule-based gating to form `candidate_action_modes`.
3. If only one candidate remains, select it directly.
4. If multiple candidates remain, use LLM-assisted judgment to select the final `action_mode`.
5. If `action_mode = refine_from_existing_state`, emit `action_request = null`.
6. If `action_mode` is an acquisition mode, construct `action_request` with a structured `evidence_acquisition_intent`.
7. Emit `action_mode`, `action_request`, and `action_rationale` for downstream execution.

因此，`4.5` 的整体作用可以概括为：

**在 `top_gap` 和 `next_evidence_need` 已形成之后，先决定当前轮是否进入 acquisition，以及进入哪类 acquisition path，再将该决策转换为执行层可消费的结构化请求。**

## 4.6 Relationship Between Planning Artifacts and Execution

在当前设计中，planning artifacts 会被 Research Execution 阶段读取并持续参考，但它们更适合被视为 **planning baseline**，而不是执行期频繁修改的 working state。

它们的作用，是为 runtime 提供初始结构、问题边界和推进参考；但实际执行中，Research Executor 仍应根据新 evidence、新 gaps、当前 findings 和 runtime constraints 做动态调整。

因此，本节的核心原则是：

**planning artifacts 应指导 execution，但不应僵化决定 execution。**

### 4.6.1 Planning Artifacts Read by Execution

execution 阶段主要会读取以下 planning artifacts：

- `plan`
- `sub_questions`
- `comparison_candidates`

其中：

- `plan` 更偏 **执行推进框架**
- `sub_questions` 更偏 **问题分解结构**
- `comparison_candidates` 更偏 **comparison 任务的对象边界**

### 4.6.2 How Planning Artifacts Guide Execution

这些 planning artifacts 在 execution 中主要起结构化指导作用。

**`plan`**

用于提供整体推进方向，帮助 runtime 理解当前任务大致应如何推进。

**`sub_questions`**

用于表达复杂问题的分解结构，帮助 execution：

- 做 coverage assessment
- 判断哪些子问题仍未回答
- 识别当前 gap 主要落在哪个子问题上

**`comparison_candidates`**

用于表达 comparison 任务的对象集合，帮助 execution：

- 判断不同 candidate 是否都得到了基本覆盖
- 识别 comparison imbalance
- 判断当前 findings 是否对不同 candidate 足够公平和可比

### 4.6.3 Planning Artifacts Are Normally Stable During Execution

在当前设计中，planning artifacts 默认应视为 **稳定的 baseline artifacts**，而不是执行期频繁原地修改的字段。

通常情况下：

- `plan` 不会在每轮 runtime 中反复改写
- `sub_questions` 不会因临时新问题频繁追加或重排
- `comparison_candidates` 也不应作为 runtime working list 被持续修改

如果 execution 中出现新的问题或关注点，更合适的做法通常不是直接修改 planning artifacts，而是通过以下 runtime objects 表达：

- `identified_gaps`
- `next_evidence_need`
- `finding_caveats`
- 其他 stage-local working state

因此，runtime 新问题通常应先被视为：

**gap-driven execution signal**，而不是 planning baseline 的原地变更。

### 4.6.4 Planning Artifacts Are Not Rigid Scripts

虽然 planning artifacts 对 execution 有指导作用，但它们不应被解释为强制执行脚本。

具体来说：

- `plan` 不是必须逐项严格照做的步骤表
- `sub_questions` 不是必须按原顺序逐个完成的 checklist
- `comparison_candidates` 也不意味着所有 candidate 必须始终被平均推进

因此，planning artifacts 的角色更接近：

**execution guidance**，而不是 **execution lock-in**。

### 4.6.5 Controlled Deviation During Execution

Research Executor 在执行过程中，应允许基于当前 runtime state 对 planning baseline 做受控偏离。

这种偏离通常不通过直接修改 planning artifacts 实现，而是通过当前轮的 gap prioritization、action decision 和 findings progression 体现出来。

常见的偏离形式包括：

**1. Priority Deviation**

原计划中的推进顺序，与 runtime 当前选出的 `top_gap` 不一致。

例如，原计划先处理 A，再处理 B；但 runtime 发现 B 才是当前 blocking gap，因此当前轮先处理 B。

**2. Scope Narrowing**

原本计划覆盖更宽范围，但 runtime 判断当前只值得围绕较小范围推进。

例如，comparison plan 原本包含多个 candidates，但当前轮只聚焦于最 relevant 的两个。

**3. Reduced Investment in Planned Items**

某些原计划中的子问题仍存在，但当前价值较低，因此暂不优先推进。

这不意味着这些子问题被删除，而是意味着当前轮不会继续为其投入 acquisition 成本。

**4. Early Convergence**

原计划仍有后续步骤，但 runtime 发现 findings 已较稳定，因此提前进入收束，而不再继续按原计划扩展。

**5. Gap-driven Detours**

runtime 中新识别出的 gap 需要被临时优先处理，即使它不是原计划中最显眼的一项。

此时 execution 可以临时插入一轮 gap-driven work，而不是机械遵循原始顺序。

因此，execution 对 planning artifacts 的偏离，主要通过：

- `identified_gaps`
- `top_gap`
- `next_evidence_need`
- `action_mode`
- `intermediate_findings`

这些 runtime objects 来实现，而不是通过直接重写 planning baseline。

### 4.6.6 Practical Design Implication

在实现上，planning artifacts 更适合作为：

- assessment 的参考输入
- gap identification 的结构化线索
- execution drift 的对照基线

而不适合作为：

- 每轮硬编码的执行顺序
- 不可偏离的固定任务列表
- 与 runtime working state 混合更新的 mutable fields

综上，planning artifacts 与 execution 的关系可以概括为：

**它们为 execution 提供初始结构、问题边界和推进参考；但 execution 的实际推进顺序与投入深度，仍应由 runtime state 决定。**

## 4.7 Iteration Outcome Evaluation

### 4.7.1 Purpose

本小节的目标，是在单轮 research execution 结束后，对本轮结果做一次**面向控制流的判断**，以决定当前 stage 的下一步应当是：

- 继续下一轮 iteration
- 进入收束
- 降级收束

因此，`Iteration Outcome Evaluation` 的职责，不是重新执行 state assessment、gap identification 或 action decision，而是基于本轮执行后的结果，判断：

- 当前轮是否有效推进了本轮开始时的 `top_gap`
- 当前 findings 是否更成熟
- 当前是否仍存在值得继续处理的关键 uncertainty 或 unresolved gap
- 在当前 runtime constraints 下，继续 loop 是否仍有价值

在整体链路中，本小节位于：

- `4.5 Action Decision Before Evidence Acquisition` 之后
- 下一轮 `4.4 Research State Assessment and Gap Identification` 之前

它的作用，是把“本轮做了什么”转化为“下一步该怎么办”。

### 4.7.2 Inputs

本小节的输入，来自本轮 execution 结束后的结果状态，以及本轮开始前的关键参考信息。

这些输入的作用，是支持对**本轮是否产生了有效推进**的判断。

#### A. Iteration-start Reference Fields

**字段：`top_gap_scope`**

含义：本轮开始时最高优先级 gap 所在层级。

**字段：`top_gap_nature`**

含义：本轮开始时最高优先级 gap 的性质。

**字段：`top_gap_severity`**

含义：本轮开始时最高优先级 gap 的严重程度。

**字段：`top_gap_summary`**

含义：对本轮开始时 `top_gap` 的简短说明。

这组字段用于提供“本轮原本要推进什么”的参考基线。

---

#### B. Current Result Fields

**字段：`action_mode`**

含义：本轮实际采用的高层动作模式。

**字段：`acquisition_result_summary`**

含义：对本轮 acquisition 或 execution 结果的简短总结。

例如是否拿到新材料、是否基本无结果、是否发生明显失败或 fallback。

**字段：`updated_evidence_summary`**

含义：本轮执行后更新过的 evidence summary。

**字段：`updated_intermediate_findings`**

含义：本轮执行后更新过的 intermediate findings。

---

#### C. Updated State Fields

**字段：`updated_support_strength`**

含义：本轮执行后当前 evidence 对 findings 的支撑强度。

**字段：`updated_finding_maturity`**

含义：本轮执行后当前 findings 的成熟度。

**字段：`remaining_unresolved_gaps`**

含义：本轮执行后仍保留的 unresolved gaps。

MVP 阶段可选。

---

#### D. Runtime Constraint Fields

**字段：`remaining_iteration_budget`**

含义：当前 research loop 还允许继续多少轮 iteration。

**字段：`input_budget_pressure`**

含义：当前输入上下文压力。

推荐枚举值：

- `low`
- `medium`
- `high`

---

#### Recommended Minimum Input Set

MVP 阶段，建议本小节至少直接消费以下字段：

```
top_gap_scope
top_gap_nature
top_gap_severity
top_gap_summary
action_mode
acquisition_result_summary
updated_evidence_summary
updated_intermediate_findings
updated_support_strength
updated_finding_maturity
remaining_iteration_budget
input_budget_pressure
```

如需更强可观测性，可再补充：

```
remaining_unresolved_gaps
```

---

#### Practical Implementation Note

实现上，本小节不应重新读取完整 raw materials 再从头分析。

更现实的做法是：

- 以本轮开始时的 `top_gap` 作为参考基线
- 结合本轮 acquisition / execution 的结果摘要
- 再结合更新后的 evidence、findings 和 runtime constraints
- 判断本轮是否产生了足够推进，以及 loop 是否仍值得继续

因此，本小节的输入，应被理解为：

**当前轮用于判断“推进得怎么样，以及下一步该怎么办”的最小结果输入视图。**

### 4.7.3 Evaluation Dimensions

在单轮 execution 结束后，Research Executor 不应只笼统判断“本轮是否有帮助”，而应从若干明确维度评估本轮 outcome。

这些维度的作用，是为后续 `continue / stop / degrade` 提供依据，而不是直接产出最终控制流结果。

MVP 阶段，建议至少评估以下四个维度。

#### A. Top-gap Progress

判断：**本轮是否有效推进了本轮开始时的 `top_gap`。**

**主要输入：**

- `top_gap_scope`
- `top_gap_nature`
- `top_gap_severity`
- `top_gap_summary`
- `acquisition_result_summary`
- `updated_evidence_summary`
- `updated_intermediate_findings`

**关注点：**

- 本轮新增 evidence 是否直接作用于当前 `top_gap`
- 当前 `top_gap` 是被解决、部分推进，还是基本未推进

**建议输出字段：**

- `top_gap_progress`
    - `resolved`
    - `partially_advanced`
    - `not_advanced`
    - `regressed`

---

#### B. Evidence Gain

判断：**本轮是否带来了有新增价值的 evidence。**

**主要输入：**

- `acquisition_result_summary`
- `updated_evidence_summary`

**关注点：**

- 是否拿到了新材料
- 新材料是否与当前问题直接相关
- acquisition 是否基本无结果或失败

**建议输出字段：**

- `evidence_gain`
    - `meaningful_gain`
    - `limited_gain`
    - `no_meaningful_gain`
    - `failed_acquisition`

---

#### C. Finding Progress

判断：**当前 findings 是否比本轮开始前更稳定或更成熟。**

**主要输入：**

- `updated_intermediate_findings`
- `updated_support_strength`
- `updated_finding_maturity`

**关注点：**

- findings 是否更接近收束
- 是否因为本轮 evidence 变得更稳定
- 是否反而因冲突 evidence 变得更不确定

**建议输出字段：**

- `finding_progress`
    - `improved_to_stable`
    - `improved_but_not_stable`
    - `no_material_change`
    - `became_less_certain`

---

#### D. Residual Uncertainty

判断：**本轮结束后，是否仍存在值得继续处理的关键 unresolved uncertainty。**

**主要输入：**

- `updated_finding_maturity`
- `remaining_unresolved_gaps`
- `updated_evidence_summary`
- `remaining_iteration_budget`
- `input_budget_pressure`

**关注点：**

- 当前是否仍有关键 unresolved gap
- 这些不确定性是否足以支撑继续下一轮
- 在当前约束下继续是否仍现实可行

**建议输出字段：**

- `residual_uncertainty`
    - `high`
    - `moderate`
    - `low`
    - `minimal`

---

#### Relationship to Outcome Decision

这些 evaluation dimensions 的作用，是为后续 outcome decision 提供依据。

一般来说：

- `top_gap_progress` 明显、`finding_progress` 明显、`residual_uncertainty` 较低
→ 更接近 `stop`
- `top_gap_progress` 有限，但 `residual_uncertainty` 仍高
→ 更接近 `continue`
- `evidence_gain` 很低、`top_gap_progress` 不明显，且 constraints 不支持继续
→ 更接近 `degrade`

---

#### Recommended Minimum Evaluation Outputs

MVP 阶段建议至少输出：

```
top_gap_progress
evidence_gain
finding_progress
residual_uncertainty
```

这几个字段的重点是：

**描述本轮推进效果，而不是直接替代最终 outcome decision。**

### 4.7.4 Outcome Decision

在 `4.7.3` 中，Research Executor 已形成一组 iteration-end evaluation state，例如：

- `top_gap_progress`
- `evidence_gain`
- `finding_progress`
- `residual_uncertainty`

本小节的职责，是基于这些 evaluation state 和当前 runtime constraints，将本轮结果收敛为最终控制流结果：

- `continue`
- `stop`
- `degrade`

在当前设计中，LLM **不是每轮 outcome decision 的必选路径**。

如果确定性的 runtime signals 已足以推出稳定结果，系统可以直接短路生成 `iteration_outcome`；只有在规则无法稳定决定时，才引入 LLM 做语义判断。

#### A. Outcome Target

MVP 阶段，本小节的核心输出为：

```
iteration_outcome
outcome_rationale
```

其中：

**字段：`iteration_outcome`**

推荐枚举值：

- `continue`
- `stop`
- `degrade`

**字段：`outcome_rationale`**

含义：用 1~3 句说明为什么当前轮得到该 outcome。

---

#### B. Step 0. Rule-based Short-circuit Check

**由规则执行**

系统应先检查是否命中可直接决定 outcome 的特殊情况。

典型信号包括：

```
did_acquisition_fail
did_new_evidence_arrive
remaining_iteration_budget
input_budget_pressure
```

例如：

- `remaining_iteration_budget <= 0`，且本轮没有明显新增价值
    
    → 直接偏向 `degrade`
    
- `did_acquisition_fail = true`，`did_new_evidence_arrive = false`，且 `input_budget_pressure = high`
    
    → 直接偏向 `degrade`
    
- 已存在明确 stop 条件
    
    → 直接偏向 `stop`
    

如果命中短路条件，则直接输出 `iteration_outcome`，无需调用 LLM。

---

#### C. Step 1. Derive Evaluation State

**仅在 short-circuit 未命中时，由 LLM / model-assisted judgment 产出**

如果 Step 0 无法直接决定 outcome，则由 LLM 基于更新后的 state 和 runtime signals，产出：

```
top_gap_progress
evidence_gain
finding_progress
residual_uncertainty
```

这一步回答的是：

**本轮推进得怎么样。**

---

#### D. Step 2. Propose Iteration Outcome

**由 LLM / model-assisted judgment 产出**

在 Step 1 已形成 evaluation state 之后，LLM 应进一步给出：

```
proposed_iteration_outcome
```

推荐枚举值：

- `continue`
- `stop`
- `degrade`

判断逻辑可按以下方式理解：

**更偏 `stop`**

当以下信号组合出现时：

- `top_gap_progress = resolved`
- `finding_progress = improved_to_stable` 或接近该状态
- `residual_uncertainty = low` 或 `minimal`

这表示：当前关键 gap 已基本解决，findings 已较稳定，继续下一轮的收益较低。

**更偏 `continue`**

当以下信号组合出现时：

- `top_gap_progress = partially_advanced`
- `evidence_gain = meaningful_gain` 或 `limited_gain`
- `finding_progress = improved_but_not_stable` 或 `no_material_change`
- `residual_uncertainty = moderate` 或 `high`

这表示：本轮虽未收束，但仍有现实推进，继续下一轮可能有价值。

**更偏 `degrade`**

当以下信号组合出现时：

- `top_gap_progress = not_advanced`
- `evidence_gain = no_meaningful_gain` 或接近失败态
- `finding_progress = no_material_change` 或 `became_less_certain`
- `residual_uncertainty` 仍高，但继续投入的价值已不明显

这表示：当前问题仍未解决，但继续理想路径上的扩展已不划算。

若信号不完全一致，则可采用以下倾向：

- `top_gap_progress` 和 `finding_progress` 都明显偏正向 → 优先考虑 `stop`
- 本轮有真实推进，但 `residual_uncertainty` 仍高 → 优先考虑 `continue`
- 本轮几乎无推进，且 findings 没改善 → 优先考虑 `degrade`

---

#### E. Step 3. Apply Rule-based Guardrails

**由规则执行**

在 `proposed_iteration_outcome` 产出后，系统再施加最终 guardrail。

例如：

- `remaining_iteration_budget <= 0`
    
    → 不允许 `continue`
    
- `top_gap_progress = resolved` 且 `residual_uncertainty = minimal`
    
    → 通常应收敛到 `stop`
    
- `did_acquisition_fail = true` 且 `top_gap_progress = not_advanced` 且 `input_budget_pressure = high`
    
    → 通常不应继续，偏向 `degrade`
    

规则在这里的作用不是重做语义判断，而是：

**约束 outcome 的合法空间。**

---

#### F. Step 4. Produce Final Outcome

经过 guardrail 后，系统产出最终：

- `iteration_outcome`
- `outcome_rationale`

因此，MVP 阶段可采用以下流程：

1. **规则** 检查 short-circuit 条件
2. 若命中，直接输出 `iteration_outcome`
3. 若未命中，**LLM** 产出 evaluation state 和 `proposed_iteration_outcome`
4. **规则** 施加最终 guardrails
5. 输出最终 `iteration_outcome` 和 `outcome_rationale`

这套流程的核心原则是：

**明显条件由规则优先处理；语义不确定时，再由 LLM 参与结果收敛。**

### 4.7.5 Outputs

本小节前面的步骤，最终应产出一组可被后续控制流直接消费的结构化结果。

MVP 阶段，建议至少输出以下字段：

```
iteration_outcome
outcome_rationale
```

---

**字段：`iteration_outcome`**

含义：本轮 iteration 的最终控制流结果。

推荐枚举值：

- `continue`
- `stop`
- `degrade`

该字段主要供 runtime control flow 使用，用于决定当前 stage 的下一步是：

- 进入下一轮 iteration
- 进入收束 / stage exit
- 进入降级收束

---

**字段：`outcome_rationale`**

含义：用 1~3 句说明为什么当前轮得到该 outcome。

如果 outcome 由规则短路直接确定，应给出简短规则化说明；

如果 outcome 经过 LLM 判断后再由 guardrail 收敛，也应给出简短语义理由。

该字段主要用于：

- observability
- tracing
- debugging
- evaluation

---

#### Optional Outputs

如需增强可观测性，可再增加：

```
proposed_iteration_outcome
```

其中：

**字段：`proposed_iteration_outcome`**

含义：LLM 在 guardrail 施加前给出的候选 outcome。

该字段主要用于 trace 和 debug。

MVP 阶段可选。

---

#### Recommended Minimum Output Set

MVP 阶段，建议 `4.7` 整体至少输出：

```
iteration_outcome
outcome_rationale
```

这组字段已经足以支持：

- 下一步控制流分支
- 基本可观测性
- decision review

---

#### Practical Output Principle

`4.7` 的输出应满足：

- **可控制**：runtime 能直接基于 `iteration_outcome` 决定下一步
- **可解释**：能通过 `outcome_rationale` 理解本轮判断
- **可裁剪**：MVP 可先保留最小字段集，后续再增加 trace 字段

因此，本小节的输出应被理解为：

**Research Executor 对本轮 iteration 是否继续、停止或降级的正式结构化判断结果。**

### 4.7.6 High-level Evaluation Flow

本小节前面的步骤可以概括为以下高层流程：

1. Read iteration-start reference fields, iteration-end result fields, and runtime constraints.
2. Apply rule-based short-circuit checks using deterministic runtime signals.
3. If a stable outcome can be determined directly, emit `iteration_outcome`.
4. Otherwise, use LLM-assisted judgment to derive evaluation state and propose `proposed_iteration_outcome`.
5. Apply final rule-based guardrails to ensure the outcome is consistent with hard constraints.
6. Emit final `iteration_outcome` and `outcome_rationale`.

因此，`4.7` 的整体作用可以概括为：

**在单轮 execution 结束后，先判断是否存在可直接决定的特殊情况；若没有，再结合 evaluation state 对本轮结果做语义收敛，并最终生成下一步控制流结果。**

### 4.7.7 Runtime Guardrails and Degraded-mode Policy （原来是第8节的内容，与其他节的思考不连贯，尽供参考和补充）

在当前设计中，`4.7 Iteration Outcome Evaluation` 已负责将单轮执行结果收敛为：

- `continue`
- `stop`
- `degrade`

但为避免 runtime 在 evidence 不足、外部依赖不稳定或预算受限时继续低价值扩展，Research Stage 还需要一组更明确的 **runtime guardrails** 和 **degraded-mode policy**，用于约束 loop 的继续条件，并为 `degrade` 提供统一语义。

#### A. Runtime Guardrails

MVP 阶段，Research Stage 至少应受以下几类 guardrail 约束：

**1. Iteration Budget Guardrail**

用于限制当前 stage 可继续推进的 iteration 次数。

典型信号包括：

- `remaining_iteration_budget`
- 当前是否已连续多轮低增益
- 当前是否已连续多轮没有新增 evidence

当 iteration budget 已接近耗尽，且当前轮未产生明显新增价值时，system 不应继续默认扩展 loop。

**2. Acquisition / Tool Guardrail**

用于限制当前 stage 在 evidence acquisition 上的继续投入。

典型信号包括：

- acquisition 是否连续失败
- 当前轮是否没有拿到新 evidence
- 外部 capability 是否仍可用
- 当前 action mode 是否仍存在现实可行路径

当 acquisition path 持续无产出或外部依赖反复失败时，system 不应仅因 gap 仍存在而机械继续。

**3. Evidence Growth Guardrail**

用于限制 stage-local evidence state 的无控制膨胀。

典型信号包括：

- 当前轮新增 evidence 是否主要是重复发现
- evidence state 是否持续增长但信息增量有限
- 当前 evidence richness 是否只是条数增长，而非独立 signal 增长

当 evidence accumulation 已明显偏向重复堆积而非有效推进时，system 应降低继续扩展的倾向。

#### B. Degraded-mode Trigger

`degrade` 不应被理解为系统失败，而应被理解为：

**当前 stage 无法在现有预算、依赖和 evidence 条件下继续高质量推进，因此需要以带限制条件的结果收束。**

MVP 阶段，以下情形通常可触发 `degrade`：

- 关键 evidence gap 仍存在，但继续推进已缺乏现实高价值路径
- evidence 长期不足，且多轮后仍无明显新增支撑
- evidence 冲突仍显著存在，且在当前预算内无法有效 resolve
- acquisition / tool path 反复失败，导致当前 stage 难以继续依赖外部动作推进
- runtime budget 已接近耗尽，继续 loop 的预期收益明显低于成本

#### C. Relationship to `continue` / `stop`

在当前设计下：

- **`continue`** 表示当前仍存在高价值推进空间，且 runtime guardrails 未触发强约束
- **`stop`** 表示当前 findings 已足以支持 downstream conclusion generation，即使仍存在残余小 gap，也不再值得继续扩展
- **`degrade`** 表示当前 stage 既不适合正常 `stop`，又不适合继续高成本推进，因此应以受限结果收束

因此，runtime guardrails 的作用，不是替代 outcome decision，而是：

**为 `continue / stop / degrade` 提供更稳定的运行边界。**

#### D. Practical Implication

当 runtime guardrails 表明继续推进已不再合理时，Research Stage 应优先考虑 `degrade`，而不是在 evidence 不足、工具失败或 state 增量有限的情况下继续开放式循环。

这样可以确保：

- `continue` 保留给仍有高价值推进空间的情况
- `degrade` 成为受限条件下的正式收束路径
- runtime 不会因 gap 未完全消失而失去边界

---

## 4.8 Stage Exit and Result Finalization

`4.8` 的职责，是在 `iteration_outcome` 已确定为退出时，正式结束当前 Research Stage，并将 working state 收束为稳定的 stage-level result。

本节只在以下情况下进入：

- `iteration_outcome = stop`
- `iteration_outcome = degrade`

如果：

- `iteration_outcome = continue`

则不进入 stage exit。

### 4.8.1 Finalization Responsibilities

进入 stage exit 后，Research Executor 应完成以下收尾工作：

**1. Freeze Further Expansion**

停止继续 acquisition 和新一轮 iteration。

**2. Finalize Findings**

将当前 `intermediate_findings` 收束为 `finalized_findings`。

**3. Finalize Evidence Summary**

将当前 evidence state 收束为 `finalized_evidence_summary`。

**4. Finalize Caveats**

将当前仍未解决的不确定性、限制条件和未完成部分整理为 `finalized_caveats`。

### 4.8.2 Stop Exit vs Degrade Exit

**`stop`**

表示正常收束。此时：

- `finalized_findings` 可作为相对稳定的结果保留
- 未解决问题只作为 caveat 保留
- 最终结果可以更直接地供下游消费

**`degrade`**

表示保守收束。此时：

- `finalized_findings` 仍可输出，但表达应更保守
- `finalized_caveats` 应更突出
- 最终结果应明确反映其不完整性或较低确定性

因此，`degrade` 不是不输出结果，而是：

**输出一个带有更强边界说明的降级版本 stage result。**

### 4.8.3 Finalized Stage Result

MVP 阶段，建议 stage exit 至少产出以下字段：

```
stage_exit_status
finalized_findings
finalized_evidence_summary
finalized_caveats
stage_result_summary
```

如果想更精简，MVP 也至少应保留：

```
stage_exit_status
finalized_findings
finalized_caveats
stage_result_summary
```

### 4.8.4 High-level Exit Flow

1. Enter stage exit when `iteration_outcome` is `stop` or `degrade`.
2. Freeze further research expansion.
3. Finalize findings, evidence summary, and caveats.
4. Adjust finalization style according to exit type (`stop` or `degrade`).
5. Emit stable stage-level outputs for downstream consumption.

因此，`4.8` 的核心作用可以概括为：

**在当前 stage 被判定退出后，将 working state 收束为可下游消费的 finalized stage result。**

---

## 4.9 Cross-round Evidence Merge

本节定义 **Research Executor** 如何将**当前轮 evidence result** 并入已有的 **stage-local evidence state**。

其目标不是再次做 evidence processing，而是完成 **state-level evidence integration**，使 stage-local evidence state 更稳定、更干净，并更接近真实的信息增量。

---

### A. Position in the Loop

Cross-round Evidence Merge 发生在 `4.3.2` 的：

- **Step 5. Process Candidate Material into Usable Evidence** 之后
- **Step 6. Update Stage-local Working State** 之内

也就是说：

- 当前轮内部 evidence shaping 已结束
- 当前轮内部重复 evidence 已在 `6.5 Evidence-level Consolidation` 中处理
- 本节只负责把**当前轮 round-level evidence** 并入**已有 stage-local evidence state**

---

### B. Inputs

本节主要读取：

- `round_consolidated_evidence_units`
- `existing_stage_evidence_state`
- `current_round_context`

其中，`current_round_context` MVP 阶段建议至少包含：

- `target_problem`
- `target_scope`
- `evidence_goal`
- `sub_question`（若有）
- `comparison_candidate`（若有）
- `gap`（若有）

---

### C. Why Cross-round Merge Is Needed

Cross-round merge 主要解决以下问题：

**1. 防止 stage-local evidence state 越积越脏**

Research Executor 是多轮 loop 的。若每一轮都将当前轮 evidence 直接追加到 stage-local evidence state，而不做跨轮 merge，则 state 中会逐渐积累越来越多语义重复的 evidence，降低后续 state 的可维护性和可用性。

**2. 区分“真正新增 evidence”和“已有 evidence 的再次命中”**

同一核心 signal 可能在不同 loop 中被多次命中。若不做 cross-round merge，系统会将这些重复发现持续记为新增 evidence，从而难以判断本轮是否真正推进了 research state，以及当前轮到底新增了什么。

**3. 支持更稳定的 sufficiency judgment 和 iteration decision**

Evidence sufficiency 的判断应尽量基于信息增量，而不是 evidence 条数。若 stage-local evidence state 中存在大量跨轮重复 evidence，系统容易高估当前 evidence richness，从而影响对 unresolved gaps、confidence 以及 continue / stop / degrade 决策的判断。

因此，Cross-round merge 的核心作用不是单纯压缩 state 大小，而是：

**保持 stage-local evidence state 干净、稳定，并使其更接近真实的信息增量。**

---

### D. Merge Boundary

本节只处理：

**当前轮 evidence 与已有 stage-local evidence state 的合并。**

本节不负责：

- 当前轮内部 evidence unit 之间的合并
    
    （这属于 `6.5 Evidence-level Consolidation`）
    
- retrieval-level deduplication
- 重新做 evidence extraction
- final reasoning or recommendation

需要强调：

**`target_problem` 不应作为跨轮 merge 的硬条件。**

在跨轮 merge 中：

- `target_problem` 更适合作为 **usage metadata**
- `target_scope` 更适合作为 merge 约束

---

### E. Merge Principle

本节应遵循以下原则：

- **Conservative merge**：宁可少合并，也不要误合并
- **Same-type only**：默认只在同一 `evidence_type` 内尝试 merge
- **Scope-aware merge**：只有 `target_scope` 相同或兼容时，才考虑 merge
- **Preserve usage history**：merge 后仍应保留当前轮 evidence 的使用上下文

---

### F. Merge Rules

MVP 阶段，建议采用**保守规则**，默认不依赖 LLM。

在执行规则前，先对 `content` 做轻量 normalize：

- 小写化
- 去除首尾空白和多余空格
- 统一连续空白
- 忽略轻量标点差异（可选）

建议按以下顺序执行：

**Rule 1. Exact match under same type and compatible scope**

若满足以下条件，则可直接 merge：

- `evidence_type` 相同
- `target_scope` 相同或兼容
- normalize 后的 `content` 完全相同

---

**Rule 2. Containment of the same evidence wording variant**

若满足以下条件，则可 merge：

- `evidence_type` 相同
- `target_scope` 相同或兼容
- 较短 evidence 被较长 evidence 完整包含
- 较长 evidence 未引入新的独立信息、限制条件、适用边界或补充结论

---

**Rule 3. When in doubt, keep both**

若无法稳定满足以上规则，则默认不 merge。

---

### G. Outputs

本节建议至少产出以下结果：

```
updated_stage_evidence_state
new_evidence_count
merged_into_existing_count
cross_round_merge_summary
```

其中：

- `updated_stage_evidence_state`：更新后的 stage-local evidence state
- `new_evidence_count`：本轮真正新增进入 state 的 evidence 数量
- `merged_into_existing_count`：本轮被合并进已有 evidence 的数量
- `cross_round_merge_summary`：跨轮 merge 摘要

---

### H. Practical Design Principle

本节的核心作用可以概括为：

**将当前轮 evidence 稳定地并入 stage-local evidence state，并尽量让 state 中的 evidence 数量更接近真实的信息增量，而不是重复发现的累积。**

# 5. Tooling and Retrieval Model

这一节把 tool 和 retrieval 放在一起讲，会比较自然。

建议包含：

- tool categories
- tool capability metadata
- `Research Executor` 如何选择 tool
- `Tool Execution Layer` 的职责边界
- memory-based recall 与 external retrieval 的区别
- retrieval 何时触发
- retrieval request 如何构造
- freshness / scope / budget 对 retrieval 的约束
- tool / retrieval 的 fallback 行为

这一节重点是讲：

**Research Stage 如何决定去哪里拿 evidence。**

---

## 5.1 Purpose and Boundary

本节的目标，是定义 Tool Execution Layer 如何将上游已确定的 acquisition intent 转换为具体、可执行的 tool / retrieval 行为，并产出标准化的 `retrieval_result`。

因此，`5. Tooling and Retrieval Model` 的职责，不是重新做高层 research decision，而是负责：

- 接收 `action_request`
- 做 family / tool 路由
- 生成 query / execution request
- 执行 retrieval
- 在允许范围内执行 retry / fallback
- 将 raw tool result 标准化为稳定的输出结构

在整体链路中，本节位于：

- `4.5 Action Request Construction` 之后
- `6. Evidence Processing Model` 之前

它的作用，是将上游已经形成的 acquisition intent 落成实际的 retrieval execution，并将执行结果转换为下游可消费的标准化 retrieval result。

本节只负责：

- retrieval execution
- tool / family routing
- query / request construction
- retry / fallback
- normalized retrieval output

它不负责：

- 重新定义 `top_gap`
- 重新选择 `action_mode`
- 重新解释用户意图
- 判断 retrieved material 是否已构成高质量 evidence
- 判断 findings 是否成立

这些内容分别属于：

- `4.4` 和 `4.5` 的高层研究决策
- `6. Evidence Processing Model` 的 evidence-level semantic processing

需要特别强调的是，Tool Execution Layer 的职责是：

**保证在 bounded execution policy 内完成结构化 retrieval execution，并交付稳定的 `retrieval_result`；但它不保证一定检索到有用 evidence。**

也就是说，本节保证的是：

- **结构化执行结果的交付**
    
    而不是：
    
- **语义上成功的 evidence 产出**

因此，`5. Tooling and Retrieval Model` 的核心问题可以概括为：

**在 acquisition intent 已确定之后，系统应如何以受控、可回溯、可标准化的方式完成 retrieval execution。**

## 5.2 Inputs

本小节的输入，不是整份高层 research state，而是 Tool Execution Layer 为完成当前轮 retrieval execution 所直接消费的输入。

本节不直接重读：

- `top_gap`
- `intermediate_findings`
- `evidence_summary`

这类高层 research state。

这些信息应先被上游收敛进 `action_request`，再由本节间接消费。

---

### A. Inputs from Research Executor

#### A.1 `action_request`

**来源：Research Executor**

含义：Research Executor 传给 Tool Execution Layer 的执行输入对象，是本节最核心的输入。

建议至少包含：

- `action_mode`
- `evidence_acquisition_intent`
- `fallback_policy`
- `preferred_tool`

其中：

**`action_mode`**

表示当前轮的高层动作模式。

推荐枚举值：

- `memory_backed_acquisition`
- `external_acquisition`

`refine_from_existing_state` 不应进入 Tool Execution Layer。

---

**`evidence_acquisition_intent`**

表示当前轮 acquisition 的结构化意图，是 Tool Execution Layer 最核心的业务输入。

建议至少包含：

- `target_scope`
- `target_problem`
- `gap_context`
- `evidence_goal`
- `evidence_shape`
- `constraints`
- `success_hint`

其中：

**`target_scope`**

表示当前 retrieval 服务于哪个研究单元。

建议字段：

- `scope_type`
- `scope_id`

`scope_type` 推荐枚举值：

- `objective`
- `sub_question`
- `candidate`
- `comparison_dimension`
- `finding`

**Example**

```json
"target_scope": {
  "scope_type": "sub_question",
  "scope_id": "retrieval_baseline_need"
}
```

**`target_problem`**

表示这轮要回答的具体问题。

**Example**

```json
"target_problem": "What is the recommended retrieval baseline for this use case?"
```

**`gap_context`**

表示当前为什么要查。

建议字段：

- `gap_scope`
- `gap_nature`
- `gap_severity`

`gap_scope` 推荐枚举值：

- `objective_level`
- `sub_question_level`
- `candidate_level`
- `comparison_level`
- `finding_level`

`gap_nature` 推荐枚举值：

- `missing`
- `weak`
- `ambiguous`
- `conflicting`
- `stale`
- `imbalanced`

`gap_severity` 推荐枚举值：

- `blocking`
- `important`
- `optional`

**Example**

```json
"gap_context": {
  "gap_scope": "sub_question_level",
  "gap_nature": "missing",
  "gap_severity": "blocking"
}
```

**`evidence_goal`**

表示当前轮 retrieval 的直接目标。

推荐枚举值：

- `establish_coverage`
- `strengthen_support`
- `resolve_ambiguity`
- `resolve_conflict`
- `refresh_status`
- `rebalance_comparison`
- `improve_actionability`

**Example**

```json
"evidence_goal": "establish_coverage"
```

**`evidence_shape`**

表示期望拿回什么类型的 evidence。

建议字段：

- `desired_evidence_kind`
- `freshness_requirement`
- `breadth`

`desired_evidence_kind` 推荐枚举值：

- `direct_fact`
- `supporting_evidence`
- `disambiguating_evidence`
- `comparison_evidence`
- `status_evidence`

`freshness_requirement` 推荐枚举值：

- `normal`
- `fresh_preferred`
- `fresh_required`

`breadth` 推荐枚举值：

- `narrow`
- `normal`
- `broad`

**Example**

```json
"evidence_shape": {
  "desired_evidence_kind": "direct_fact",
  "freshness_requirement": "fresh_preferred",
  "breadth": "narrow"
}
```

**`constraints`**

表示当前轮允许、偏好或禁止哪些 retrieval families，以及结果规模上限。

建议字段：

- `allowed_source_families`
- `preferred_source_families`
- `blocked_source_families`
- `max_results`

推荐 `source_family` 值示例：

- `session_memory_lookup`
- `long_term_memory_lookup`
- `research_knowledge_recall`
- `docs_search`
- `paper_search`
- `github_lookup`
- `web_search`

说明：

- `allowed_source_families` 通常应是 `available_capabilities` 中可用 family 的子集。

**Example**

```json
"constraints": {
  "allowed_source_families": ["docs_search", "web_search"],
  "preferred_source_families": ["docs_search"],
  "blocked_source_families": ["paper_search"],
  "max_results": 5
}
```

**`success_hint`**

表示什么样的结果算对当前轮有帮助。

它不是最终 evidence 裁判，只是执行层的结果偏好提示。

**Example**

```json
"success_hint": "At least one direct official guidance statement is preferred."
```

---

**`fallback_policy`**

表示当前轮允许的 fallback 策略。

推荐枚举值：

- `no_fallback`
- `fallback_within_same_family`
- `fallback_to_broader_search`

**Example**

```json
"fallback_policy": "fallback_within_same_family"
```

---

**`preferred_tool`**

如果上游已明确偏好某个具体 tool，可在此指定；否则为空。

**Example**

```json
"preferred_tool": null
```

---

#### A.2 `available_capabilities`

**来源：Research Executor**

含义：当前 stage 原则上可用的 family 级能力边界。

它不是底层 tool config，而是一个由上游传入、供 Research Executor 和 Tool Execution Layer 共享使用的 capability view。

它回答的是：

**当前 stage 里，哪些 retrieval families 原则上可用。**

建议结构：

- key：`action_family`
- value：
    - `status`
    - `reason`，可选

`status` 推荐枚举值：

- `available`
- `unavailable`
- `degraded`

**Example**

```json
"available_capabilities": {
  "docs_search": { "status": "available" },
  "paper_search": { "status": "available" },
  "github_lookup": { "status": "unavailable", "reason": "connector_not_enabled" },
  "web_search": { "status": "available" }
}
```

---

#### A.3 Runtime Execution Controls

**来源：Research Executor**

含义：Research Executor 传给 Tool Execution Layer 的执行控制信息，用于约束当前轮 retrieval execution。

建议至少包含：

- `retry_budget`
- `timeout_limit_ms`
- `~~max_results_limit~~`

其中：

**`retry_budget`**

表示当前轮允许的 retry 次数上限。

**Example**

```json
"retry_budget": 1
```

**`timeout_limit_ms`**

表示当前轮执行的超时限制。

**Example**

```json
"timeout_limit_ms": 8000
```

**`~~max_results_limit~~`**

~~表示当前轮允许返回的最大结果规模。~~

**~~Example~~**

```json
~~"max_results_limit": 8~~
```

---

#### A.4 `recent_retrieval_attempts`

**来源：Research Executor**

**原始来源：过去若干轮 Tool Execution Layer 的 outputs**

含义：最近若干次 retrieval 尝试的结构化 retrieval 轨迹。

它不是 raw history，而是经过保留和压缩后的执行轨迹输入。

它通常来自以下闭环：

1. Tool Execution Layer 在前一轮输出 `attempted_paths`
2. 上游运行时保存这些 retrieval 轨迹
3. Research Executor 在新一轮读取这些 retrieval 轨迹，并据此调整：
    - `allowed_source_families`
    - `preferred_source_families`
    - retrieval 方向
4. 上游再把仍 relevant 的 retrieval 轨迹压缩为 `recent_retrieval_attempts`，重新传入 Tool Execution Layer

每条 attempt 建议至少包含：

- `action_family`
- `tool_used`
- `target_problem`
- `query_fingerprint`
- `result_status`
- `result_utility`
- `fallback_applied`

其中：

`result_status` 推荐枚举值：

- `success`
- `partial_success`
- `no_result`
- `failed`

`result_utility` 推荐枚举值：

- `useful`
- `weakly_useful`
- `not_useful`

**Example**

```json
"recent_retrieval_attempts": [
  {
    "action_family": "docs_search",
    "tool_used": "openai_docs_search_v1",
    "target_problem": "What is the recommended retrieval baseline for this use case?",
    "query_fingerprint": "retrieval_baseline_openai_docs_v1",
    "result_status": "partial_success",
    "result_utility": "weakly_useful",
    "fallback_applied": false
  }
]
```

该字段主要用于：

- 避免重复走已失败路径
- 避免重复 query pattern
- 辅助 retry / fallback 决策

它不应直接决定高层 `top_gap`，而主要影响 retrieval path selection 和执行层优化。

---

### B. Inputs Not from Research Executor

#### B.1 `tool_registry`

**来源：Tool Execution Layer system config**

含义：当前可用具体 tools 及其 capability metadata。

它定义系统里有哪些具体 tool，以及每个 tool 的基本能力特征。

建议字段：

- `tool_id`
- `family`
- `status`
- `supports_freshness`
- `supports_filters`

`status` 推荐枚举值：

- `active`
- `disabled`

**Example**

```json
"tool_registry": [
  {
    "tool_id": "openai_docs_search_v1",
    "family": "docs_search",
    "status": "active",
    "supports_freshness": true,
    "supports_filters": true
  },
  {
    "tool_id": "web_search_v1",
    "family": "web_search",
    "status": "active",
    "supports_freshness": true,
    "supports_filters": false
  }
]
```

---

#### B.2 `family_tool_mapping`

**来源：Tool Execution Layer system config**

含义：`action_family` 到具体 tool 集合的映射关系。

它定义 family 如何落到具体可执行工具。

**Example**

```json
"family_tool_mapping": {
  "docs_search": ["openai_docs_search_v1", "docs_keyword_search_v1"],
  "web_search": ["web_search_v1"],
  "paper_search": ["paper_search_v1"]
}
```

---

#### B.3 `fallback_map`

**来源：Tool Execution Layer system config**

含义：family 之间允许的 fallback 路径映射。

**Example**

```json
"fallback_map": {
  "docs_search": ["docs_search", "web_search"],
  "paper_search": ["paper_search", "web_search"],
  "github_lookup": ["github_lookup", "web_search"],
  "web_search": ["web_search"]
}
```

---

### Recommended Minimum Input Set

MVP 阶段，建议本小节至少直接消费以下输入：

- `action_request`
- `available_capabilities`
- `tool_registry`
- `family_tool_mapping`
- `fallback_map`
- `retry_budget`
- `timeout_limit_ms`
- `~~max_results_limit~~`

如需支持路径规避和避免重复低价值检索，可再补充：

- `recent_retrieval_attempts`

---

### Overall Input Example

下面是一份 Tool Execution Layer 的整体输入示例，包含：

- **来自 Research Executor 的 inputs**
- **不来自 Research Executor 的 inputs**

```json
{
  "from_research_executor": {
    "action_request": {
      "action_mode": "external_acquisition",
      "evidence_acquisition_intent": {
        "target_scope": {
          "scope_type": "sub_question",
          "scope_id": "retrieval_baseline_need"
        },
        "target_problem": "What is the recommended retrieval baseline for this use case?",
        "gap_context": {
          "gap_scope": "sub_question_level",
          "gap_nature": "missing",
          "gap_severity": "blocking"
        },
        "evidence_goal": "establish_coverage",
        "evidence_shape": {
          "desired_evidence_kind": "direct_fact",
          "freshness_requirement": "fresh_preferred",
          "breadth": "narrow"
        },
        "constraints": {
          "allowed_source_families": ["docs_search", "web_search"],
          "preferred_source_families": ["docs_search"],
          "blocked_source_families": ["paper_search"],
          "max_results": 5
        },
        "success_hint": "At least one direct official guidance statement is preferred."
      },
      "fallback_policy": "fallback_within_same_family",
      "preferred_tool": null
    },
    "available_capabilities": {
      "docs_search": { "status": "available" },
      "paper_search": { "status": "available" },
      "github_lookup": { "status": "unavailable", "reason": "connector_not_enabled" },
      "web_search": { "status": "available" }
    },
    "retry_budget": 1,
    "timeout_limit_ms": 8000,
    ~~"max_results_limit": 8,~~
    "recent_retrieval_attempts": [
      {
        "action_family": "docs_search",
        "tool_used": "openai_docs_search_v1",
        "target_problem": "What is the recommended retrieval baseline for this use case?",
        "query_fingerprint": "retrieval_baseline_openai_docs_v1",
        "result_status": "partial_success",
        "result_utility": "weakly_useful",
        "fallback_applied": false
      }
    ]
  },
  "not_from_research_executor": {
    "tool_registry": [
      {
        "tool_id": "openai_docs_search_v1",
        "family": "docs_search",
        "status": "active",
        "supports_freshness": true,
        "supports_filters": true
      },
      {
        "tool_id": "web_search_v1",
        "family": "web_search",
        "status": "active",
        "supports_freshness": true,
        "supports_filters": false
      }
    ],
    "family_tool_mapping": {
      "docs_search": ["openai_docs_search_v1", "docs_keyword_search_v1"],
      "web_search": ["web_search_v1"],
      "paper_search": ["paper_search_v1"]
    },
    "fallback_map": {
      "docs_search": ["docs_search", "web_search"],
      "paper_search": ["paper_search", "web_search"],
      "github_lookup": ["github_lookup", "web_search"],
      "web_search": ["web_search"]
    }
  }
}
```

---

### Practical Input Principle

本小节的核心作用可以概括为：

**为 Tool Execution Layer 提供执行请求、共享能力边界、底层工具配置、执行控制和 recent retrieval 轨迹，使其能够以受控方式完成 retrieval execution。**

## 5.3 Tooling Abstraction and Family Model

在当前设计中，Tool Execution Layer 不应直接从 `action_request` 跳到某个具体 tool，而应先经过一层更稳定的能力抽象。

该抽象层的核心单位是 **family**。

引入 family 的目的，是在 retrieval execution 中提供统一的：

- **路径选择单位**
- **可用性检查单位**
- **回退策略单位**

因此，本节的核心原则是：

**Tool Execution Layer 应先在 family 层完成路径选择，再解析到具体 tool。**

### A. Core Abstraction Units

**1. `action_family`**

表示一类具有相似执行方式和相似 source 特征的 retrieval / lookup path，是 Tool Execution Layer 的主要抽象单位。

典型示例包括：

- `session_memory_lookup`
- `long_term_memory_lookup`
- `research_knowledge_recall`
- `docs_search`
- `paper_search`
- `github_lookup`
- `web_search`

在当前设计中，family 同时表达“怎么查”和“去哪类 source 查”，因此可将其理解为：

**source-aware action family**

---

**2. Concrete Tool**

表示 family 下具体可调用的执行实现，是 Tool Execution Layer 最终实际调用的工具实例。

例如：

- `openai_docs_search_v1`
- `docs_keyword_search_v1`
- `paper_search_v1`
- `web_search_v1`

在当前设计中：

- family 负责表达“走哪类路径”
- concrete tool 负责表达“调用哪一个具体实现”

---

**3. Family-level Capability**

表示某个 family 在当前 stage 中是否原则上可用。

它通常通过 `available_capabilities` 表达，而不是通过底层 tool config 直接表达。

例如：

- `docs_search = available`
- `github_lookup = unavailable`

### B. Relationship Between Family and Tool

在当前设计中，family 和具体 tool 之间通常是：

**one family → many candidate tools**

因此，Tool Execution Layer 的执行顺序应为：

1. 在 family 层确定当前轮准备走哪类 retrieval path
2. 再在该 family 下解析可用的 concrete tool
3. 最终生成 request 并执行具体 tool

### C. Role of Family in Execution

在当前设计中，family 至少承担以下三类作用：

**1. Path Selection Unit**

Tool Execution Layer 先根据 intent 选择 candidate families，再在 family 内选择具体 tool。

---

**2. Availability Check Unit**

`available_capabilities` 是 family-level capability view，因此 family 也是可用性检查的基本单位。

例如：

- `docs_search = available`
- `github_lookup = unavailable`

这意味着：

- `docs_search` 可进入候选集合
- `github_lookup` 不应被当前轮 routing 选中

---

**3. Fallback Unit**

fallback 默认在 family 层表达，例如：

- `fallback_within_same_family`
- `fallback_to_broader_search`

也就是说，系统先决定是否在当前 family 内继续尝试，或是否退到更宽的 family，再由具体 tool 执行对应路径。

### D. Design Implication

综上，在当前设计中：

- `action_family` 是 Tool Execution Layer 的主要能力抽象
- concrete tool 是 family 下的具体执行实现
- 路径选择、可用性检查和回退策略都应优先在 family 层完成
- 具体 tool 的选择应在 family 已确定之后再进行

因此，本节的核心结论可以概括为：

**Tool Execution Layer 主要按 family 级组织能力，并在 family 级完成路径选择与约束控制；具体 tool 解析属于 family 之后的执行细化步骤。**

## 5.4 Supported Retrieval and Tool Families

在当前设计中，Tool Execution Layer 通过 family 级能力抽象组织 retrieval paths。

本小节说明当前系统支持哪些 retrieval / tool families，以及每类 family 的：

- 适用场景
- 典型输入
- 典型输出
- 局限性

本小节不展开：

- family 抽象定义（见 `5.3`）
- routing 规则（见 `5.5`）
- query construction 细节（见 `5.6`）
- fallback / retry 逻辑（见 `5.7`）

---

### A. Memory-oriented Families

**1. `session_memory_lookup`**

用于检索当前 session / 当前 stage 内已经出现过的信息，主要服务于短期连续性和避免重复 retrieval。

- **典型输入**：`target_problem`、topic / entity / recent decision signal
- **典型输出**：当前 session 内相关记录、已出现的事实 / 约束 / 局部结论
- **局限性**：不能提供真正新的外部 evidence，不适合 freshness-sensitive 问题

---

**2. `long_term_memory_lookup`**

用于检索跨 session 保留的长期背景信息，例如用户长期偏好、项目背景或稳定约束。

- **典型输入**：`target_problem`、project / user / topic recall signal
- **典型输出**：长期背景信息、稳定项目上下文、历史偏好或约束
- **局限性**：信息可能不够新，不能替代针对当前问题的外部 retrieval

---

**3. `research_knowledge_recall`**

用于检索过去已沉淀的 research knowledge，例如历史研究结论、知识单元或之前的比较结果。

- **典型输入**：`target_problem`、topic / decision / comparison recall signal
- **典型输出**：历史知识记录、研究结论、可复用 research assets
- **局限性**：依赖已有沉淀质量，不一定适合回答全新的外部问题

---

### B. External Retrieval Families

**1. `docs_search`**

用于检索文档型资料，尤其适合官方文档、技术指南和实现规范。

- **典型输入**：`target_problem`、docs-oriented query、freshness / breadth constraints
- **典型输出**：文档片段、说明性段落、API / feature / config guidance
- **局限性**：覆盖面窄于开放 web，更适合 direct fact 和 implementation guidance

---

**2. `paper_search`**

用于检索论文、研究方法和学术资料，适合理论背景、方法比较和 research supporting evidence。

- **典型输入**：`target_problem`、method / paper-oriented query、topic / comparison signal
- **典型输出**：论文 metadata、摘要片段、方法描述、研究结论
- **局限性**：工程落地细节通常不足，可操作性和现实约束表达较弱

---

**3. `github_lookup`**

用于检索 repository、代码实现和工程示例，适合 code-level lookup 和 implementation evidence。

- **典型输入**：`target_problem`、code-oriented query、repo / org / path scope（若存在）
- **典型输出**：repo / file / snippet、实现线索、工程示例
- **局限性**：覆盖的是代码世界，不能替代 docs 或 broader web info；connector 不可用时能力受限

---

**4. `web_search`**

用于检索公开 web 信息，适合更宽范围的信息需求，也可作为 broader fallback path。

- **典型输入**：`target_problem`、open-web query、freshness / breadth preference
- **典型输出**：网页结果、公开页面片段、博客 / 公告 / 文档页内容
- **局限性**：噪音更高，source quality 更不稳定，后续 evidence filtering 成本更高

---

### C. Comparative Notes

在当前设计中，各 family 的定位可粗略理解为：

- **memory-oriented families**：回忆已有上下文，不提供真正新的外部 evidence
- **`docs_search`**：高精度、低噪音的文档型事实和实现 guidance
- **`paper_search`**：方法背景、研究比较和学术 supporting evidence
- **`github_lookup`**：代码实现、repo evidence 和工程示例
- **`web_search`**：广覆盖 retrieval，也常作为 broader fallback path

因此，后续 routing、query construction 和 fallback policy，应建立在这些 family 的能力差异之上，而不是将所有 retrieval paths 视为等价路径。

## 5.5 Intent-to-Tool Routing

本小节的目标，是将 `action_request` 中已确定的 acquisition intent，解析为当前轮可执行的 **family-level path**，并进一步收敛到具体的 **tool path**。

在当前设计中，routing 应被视为一个**受约束的两层解析过程**，而不是自由发挥式的 tool 选择。其核心原则是：

- 先在 **family** 层完成路径选择
- 再在选定的 family 内解析具体 tool
- `recent_retrieval_attempts` 优先作用于 **tool** 级别；只有当某个 family 下的可行 tool 已被低价值历史尝试基本耗尽时，才进一步影响 **family** 级候选集

---

### A. Routing Goal

本小节建议至少产出：

- `candidate_families`
- `ranked_candidate_families`
- `selected_family`
- `candidate_tools`
- `selected_tool`

本小节只负责：

- family 级候选收敛
- family 级优先级判断
- tool 级候选收敛
- tool 级优先级判断

本小节不负责：

- 重新定义 `target_problem`
- 重新决定 `action_mode`
- 生成最终 query / execution request
- 执行 retrieval
- retry / fallback 的实际执行

---

### B. Routing Inputs

本小节主要读取以下输入：

- `action_request`
- `available_capabilities`
- `tool_registry`
- `family_tool_mapping`
- `fallback_map`
- `recent_retrieval_attempts`（可选）

其中最关键的字段包括：

- `action_mode`
- `evidence_acquisition_intent.evidence_goal`
- `evidence_acquisition_intent.evidence_shape`
- `allowed_source_families`
- `preferred_source_families`
- `blocked_source_families`
- `preferred_tool`

---

### C. Family-level Routing

family-level routing 的目标，是形成当前轮合法且相对合适的 `candidate_families`。

**1. Initial Family Scope**

先根据 `action_mode` 决定初始 family 作用域：

- `memory_backed_acquisition` → 仅 memory-oriented families
- `external_acquisition` → 仅 external retrieval families

**2. Constraint-based Filtering**

在初始作用域之上，再应用：

- `allowed_source_families`
- `blocked_source_families`
- `available_capabilities`

经过过滤后，得到：

```
candidate_families
```

**3. Family Preference and Ranking**

在 `candidate_families` 已形成后，再按以下因素排序：

- `preferred_source_families`
- `evidence_goal` 与 family 的匹配性
- `evidence_shape` 与 family 的匹配性
- `recent_retrieval_attempts` 的 family-level 局部修正

---

### `evidence_goal` 与 family 的匹配性

MVP 阶段可采用以下启发式规则：

- **`establish_coverage`**
    
    通常优先 `docs_search`；若问题偏已有上下文 recall，可提升 memory-oriented families；若 docs 覆盖不足，再考虑 `web_search`
    
- **`strengthen_support`**
    
    通常优先最能为当前 finding 补强的 family；实现或产品事实偏 `docs_search`，工程实现偏 `github_lookup`，方法或研究结论偏 `paper_search`，多来源补强可提升 `web_search`
    
- **`resolve_ambiguity`**
    
    优先能提供区分性证据的 family；官方语义不清时优先 `docs_search`，公开上下文消歧可提升 `web_search`，实现差异可提升 `github_lookup`，概念或方法边界可提升 `paper_search`
    
- **`resolve_conflict`**
    
    优先高权威或能提供独立对照的 family；官方行为冲突优先 `docs_search`，实现细节冲突优先 `github_lookup`，公开说法冲突可提升 `web_search`，研究结论冲突可提升 `paper_search`
    
- **`refresh_status`**
    
    优先 freshness 更强的 external families；通常优先 `docs_search` 或 `web_search`；memory-oriented families 不应作为主路径
    
- **`rebalance_comparison`**
    
    优先最能补齐 comparison 弱边的 family；功能或配置比较偏 `docs_search`，工程复杂度比较偏 `github_lookup`，方法或效果比较偏 `paper_search`，更宽公开资料可提升 `web_search`
    
- **`improve_actionability`**
    
    优先更利于落地执行的 family；通常优先 `docs_search`，需要实现参考时提升 `github_lookup`
    

---

### `evidence_shape` 与 family 的匹配性

`evidence_shape` 主要影响 family 排序，不替代硬约束过滤。MVP 阶段建议至少考虑以下维度。

**1. `desired_evidence_kind`**

- **`direct_fact`**
    
    通常优先 `docs_search`；若需要公开最新事实，可提升 `web_search`
    
- **`supporting_evidence`**
    
    `docs_search`、`paper_search`、`web_search` 均可进入候选；工程实现可提升 `github_lookup`
    
- **`disambiguating_evidence`**
    
    优先能提供区分性信号的 family；通常先看 `docs_search`，不足时提升 `web_search`
    
- **`comparison_evidence`**
    
    功能 / 配置比较偏 `docs_search`；实现复杂度比较偏 `github_lookup`；方法 / 效果比较偏 `paper_search`
    
- **`status_evidence`**
    
    优先 freshness 更强的 external families，通常优先 `web_search` 和 `docs_search`
    

**2. `freshness_requirement`**

- **`normal`**
    
    freshness 不构成主导因素
    
- **`fresh_preferred`**
    
    提升 `docs_search` 和 `web_search`；降低 long-term memory families 的优先级
    
- **`fresh_required`**
    
    应优先 freshness 更强的 external families；memory-oriented families 不应作为主路径
    

**3. `breadth`**

- **`narrow`**
    
    优先高精度、低噪音的 family，通常优先 `docs_search`
    
- **`normal`**
    
    由 `evidence_goal` 和 `desired_evidence_kind` 主导
    
- **`broad`**
    
    提升 `web_search`；若问题偏研究比较，也可提升 `paper_search`
    

---

### Practical Heuristic Examples

MVP 阶段可直接采用以下组合启发式：

- `establish_coverage + direct_fact + narrow`
    
    → 优先 `docs_search`，其次 `web_search`
    
- `improve_actionability + supporting_evidence + narrow`
    
    → 优先 `docs_search`，其次 `github_lookup`
    
- `resolve_conflict + comparison_evidence + broad`
    
    → 优先 `paper_search` 或 `web_search`
    
- `refresh_status + status_evidence + fresh_required`
    
    → 优先 `web_search`，其次 `docs_search`
    

经过排序后，得到：

```
ranked_candidate_families
selected_family
```

---

### D. Tool-level Resolution

在 `selected_family` 已确定后，系统再进入 tool-level resolution。

**1. Candidate Tool Expansion**

根据：

- `family_tool_mapping`
- `tool_registry`

展开为：

```
candidate_tools
```

**2. Tool-level Validity Filtering**

过滤掉：

- `tool_registry.status = disabled`
- 与当前 `evidence_shape` 不兼容的 tool
- 不属于 `selected_family` 的 tool

**3. Applying `preferred_tool`**

只有在以下条件都满足时，`preferred_tool` 才可优先生效：

- 属于 `selected_family`
- 在 `tool_registry` 中存在
- 当前状态可用
- 未被 `recent_retrieval_attempts` 判定为当前轮应规避的低价值路径

**4. Tool-level Ranking by Recent Retrieval Attempts**

`recent_retrieval_attempts` 在 tool 级别应优先发挥作用：

- 若某个具体 tool 最近针对相同或高度相似的 `target_problem`、`query_fingerprint` 已多次返回
    
    `failed / no_result / not_useful`
    
    → 应优先降权或排除该 tool
    
- 仅在 family 下可行 tool 基本耗尽时，才进一步影响 family 级候选集

**5. Final Tool Selection**

完成上述步骤后，选出：

```
selected_tool
```

若当前 `selected_family` 下不存在任何可执行 tool，则应：

- 将该 family 标记为当前轮不可执行
- 转向下一个 candidate family
- 或交由 `5.7 Fallback and Retry Policy` 处理

---

### E. Routing Outputs

本小节建议至少产出以下结构化结果：

```
candidate_families
ranked_candidate_families
selected_family
candidate_tools
selected_tool
```

如需增强可观测性，可再补充：

```
excluded_families
excluded_tools
routing_rationale
```

---

### F. Practical Routing Principle

本小节的核心作用可以概括为：

**将 acquisition intent 解析为受约束的 family-level path，并在合法 family 内进一步解析到具体 tool path。**

因此，intent-to-tool routing 不应被理解为自由工具选择，而应被理解为：

- 先根据 request、capability 和 config 收缩 family 候选集
- 再在选定 family 下收缩 tool 候选集
- 最终形成一个可执行、可解释、可受控的 retrieval path

综上，本节的核心结论可以概括为：

**Intent-to-tool routing is a constrained two-level resolution process: family first, tool second, with recent retrieval traces acting primarily as tool-level modifiers and only secondarily as family-level eliminators.**

## 5.6 Query Generation and Retrieval Request Construction

### 5.6.1 Purpose and Boundary

本小节的目标，是在 `5.5 Intent-to-Tool Routing` 已确定：

- `selected_family`
- `selected_tool`

之后，将当前轮 acquisition intent 转换为可执行的 retrieval request。

本小节负责：

- 生成 retrieval-oriented query
- 按 selected family 组织 request 构造原则
- 按 selected tool 生成最终 payload
- 结合 recent retrieval 轨迹避免重复低价值 query pattern

本小节不负责：

- 重新决定 `selected_family` 或 `selected_tool`
- 执行 retrieval
- 决定 retry / fallback
- 判断 retrieval result 是否已构成高质量 evidence

因此，本小节中的 query generation 应被理解为：

**在当前轮 intent 和已选路径约束下的受控转换步骤。**

### 5.6.2 Inputs

本小节主要读取已收敛的 intent、selected path、执行约束和 recent retrieval 轨迹，而不直接重读整份高层 research state。

#### A. Routing Outputs

**`selected_family`**

来源：`5.5 Intent-to-Tool Routing`

含义：当前轮最终选定的 family，用于决定 request construction 的总体构造原则。

**Example**

```json
"selected_family": "docs_search"
```

**`selected_tool`**

来源：`5.5 Intent-to-Tool Routing`

含义：当前轮最终选定的具体 tool，用于决定最终 payload 的接口形式。

**Example**

```json
"selected_tool": "openai_docs_search_v1"
```

---

#### B. Intent Inputs

**`target_problem`**

来源：`action_request.evidence_acquisition_intent.target_problem`

含义：这轮要回答的具体问题，是 query generation 的核心输入。

**Example**

```json
"target_problem": "What is the recommended retrieval baseline for this use case?"
```

**`evidence_goal`**

来源：`action_request.evidence_acquisition_intent.evidence_goal`

含义：这轮 retrieval 的直接目标，用于影响 query 风格和 request 构造重点。

推荐枚举值：

- `establish_coverage`：优先补齐当前问题是否已被基本覆盖
- `strengthen_support`：优先为已有判断补充更强支撑
- `resolve_ambiguity`：优先消除当前存在的歧义
- `resolve_conflict`：优先处理彼此冲突的证据或说法
- `refresh_status`：优先获取更新、更接近当前状态的信息
- `rebalance_comparison`：优先补齐 comparison 中证据较弱的一侧
- `improve_actionability`：优先获取更利于落地执行的材料

**Example**

```json
"evidence_goal": "establish_coverage"
```

**`evidence_shape`**

来源：`action_request.evidence_acquisition_intent.evidence_shape`

含义：定义当前轮期望拿回什么形态的 evidence。

其中：

- `desired_evidence_kind`：希望拿回哪类 evidence
- `freshness_requirement`：对信息新鲜度的要求
- `breadth`：希望检索范围更窄还是更宽

建议至少包含：

- `desired_evidence_kind`
- `freshness_requirement`
- `breadth`

**`desired_evidence_kind` 推荐枚举值：**

- `direct_fact`：优先拿可直接回答问题的事实型材料
- `supporting_evidence`：优先拿用于支撑已有判断的补充材料
- `disambiguating_evidence`：优先拿可区分相近解释的材料
- `comparison_evidence`：优先拿可用于比较多个候选的材料
- `status_evidence`：优先拿描述当前状态或最新变化的材料

**`freshness_requirement` 推荐枚举值：**

- `normal`：新鲜度不是当前轮的重点约束
- `fresh_preferred`：信息越新越好，但不是硬要求
- `fresh_required`：信息必须尽量新，旧材料不应作为主路径

**`breadth` 推荐枚举值：**

- `narrow`：优先高精度、低噪音的聚焦检索
- `normal`：使用默认范围的检索广度
- `broad`：允许更宽覆盖和更高噪音以换取更多候选材料

**Example**

```json
"evidence_shape": {
  "desired_evidence_kind": "direct_fact",
  "freshness_requirement": "fresh_preferred",
  "breadth": "narrow"
}
```

**`success_hint`**

来源：`action_request.evidence_acquisition_intent.success_hint`

含义：对“什么样的结果算有帮助”的轻量提示，可影响 query objective framing。

**Example**

```json
"success_hint": "At least one direct official guidance statement is preferred."
```

---

#### C. Constraint Inputs

**`constraints.max_results`**

来源：`action_request.evidence_acquisition_intent.constraints.max_results`

含义：当前轮允许返回的目标结果规模上限。

**Example**

```json
"max_results": 5
```

**`timeout_limit_ms`**

来源：Research Executor 传入的 runtime execution control

含义：当前轮 retrieval request 的超时限制。

**Example**

```json
"timeout_limit_ms": 8000
```

---

#### D. Recent Retrieval Trace Inputs

**`recent_retrieval_attempts`**

来源：Research Executor

原始来源：过去若干轮 Tool Execution Layer 的 outputs

含义：最近若干次 retrieval 尝试的结构化 retrieval 轨迹。

本小节主要用它来：

- 识别重复 query pattern
- 避免同 tool 的低价值立即重试
- 支持轻量 reformulation

每条 attempt 建议至少包含：

- `action_family`
- `tool_used`
- `target_problem`
- `query_fingerprint`
- `result_status`
- `result_utility`
- `fallback_applied`

**`result_status` 推荐枚举值：**

- `success`：本次检索执行成功并返回结果
- `partial_success`：本次检索部分成功，但结果不完整或质量有限
- `no_result`：本次检索执行完成，但没有返回有效结果
- `failed`：本次检索因执行错误或调用失败而未完成

**`result_utility` 推荐枚举值：**

- `useful`：本次结果对当前轮有明确帮助
- `weakly_useful`：本次结果有一定帮助，但增益有限
- `not_useful`：本次结果对当前轮几乎没有帮助

**Example**

```json
"recent_retrieval_attempts": [
  {
    "action_family": "docs_search",
    "tool_used": "openai_docs_search_v1",
    "target_problem": "What is the recommended retrieval baseline for this use case?",
    "query_fingerprint": "retrieval_baseline_openai_docs_v1",
    "result_status": "partial_success",
    "result_utility": "weakly_useful",
    "fallback_applied": false
  }
]
```

---

#### E. Tool Capability Inputs

**`tool_registry`**

来源：Tool Execution Layer system config

含义：当前可用具体 tools 及其 capability metadata。

本小节主要用它判断 selected tool 支持哪些 payload 字段，例如 freshness、filters 和 result limits。

**Example**

```json
"tool_registry": [
  {
    "tool_id": "openai_docs_search_v1",
    "family": "docs_search",
    "status": "active",
    "supports_freshness": true,
    "supports_filters": true
  }
]
```

---

#### Recommended Minimum Input Set

MVP 阶段，建议本小节至少直接消费以下输入：

```
selected_family
selected_tool
target_problem
evidence_goal
evidence_shape
success_hint
constraints.max_results
timeout_limit_ms
tool_registry
```

如需支持 query 去重和轻量 reformulation，可再补充：

```
recent_retrieval_attempts
```

---

#### Practical Input Principle

本小节的输入应满足以下原则：

- 以已收敛的 intent 和 selected path 为主
- 不重新解释整份高层 research state
- recent retrieval 轨迹只用于 query 去重和轻量 reformulation
- tool capability metadata 只用于 payload 合法性和字段支持判断

因此，`5.6.2 Inputs` 的核心作用可以概括为：

**为 query generation 和 request construction 提供已选路径、当前轮 intent、执行约束和 recent retrieval 轨迹，使系统能够生成可执行且不过度重复的 retrieval request。**

### 5.6.3 Query Generation

本小节的目标，是在 `selected_family` 和 `selected_tool` 已确定后，将当前轮 retrieval intent 转换为适合当前路径的初始 `generated_query`。

系统不应直接将 `target_problem` 原样作为最终 query，主要原因是：

- `target_problem` 更偏待回答的问题表达，不总适合作为检索表达
- query 必须受当前轮 `evidence_goal` 和 `evidence_shape` 约束
- query 必须适配 `selected_family`
- 系统需要在生成阶段显式规避最近在同一 tool、同一问题上下文下已证明低价值的 query phrasing

因此，Query Generation 应被理解为：

**在当前轮 intent、selected family 和 recent low-value query 约束下，将问题表达转换为初始可执行 query 的受控步骤。**

需要强调的是：

- 本小节只负责生成**初始 query**
- 不负责开放式搜索策略生成
- 不重新定义 `target_problem`
- 不重新选择 `selected_family` 或 `selected_tool`

---

### A. Inputs

本小节主要读取：

- `target_problem`
- `evidence_goal`
- `evidence_shape`
- `selected_family`
- `success_hint`
- `recent_low_value_queries`（可选）

其中：

**`target_problem`**

定义当前轮要回答的具体问题，是 query generation 的语义起点。

**`evidence_goal`**

定义当前轮为什么查，用于决定 query 的检索重点。

例如，当前轮更偏 coverage、support、disambiguation、conflict resolution、status refresh 还是 actionability。

**`evidence_shape`**

定义当前轮希望拿回什么形态的 evidence。

其中：

- `desired_evidence_kind`：希望拿回哪类 evidence
- `freshness_requirement`：对信息新鲜度的要求
- `breadth`：希望检索范围更窄还是更宽

**`selected_family`**

定义当前轮已选定的 retrieval path，用于约束 query 的表达风格。

**`success_hint`**

提供对“什么样的结果算有帮助”的轻量提示，可辅助 query phrasing。

**`recent_low_value_queries`**

表示最近在**同一 `selected_tool` 且同一 `target_problem`** 下，已被证明低价值的旧 query 列表。

本小节用它作为负例 phrasing 约束，避免生成与这些旧 query 过于接近的表达。

---

### B. Generation Principle

MVP 阶段，建议通过**一次受约束的 LLM 调用**直接生成初始 `generated_query`。

在这次调用内部，LLM 应完成以下受控转换：

- 保留 `target_problem` 中不可漂移的问题核心
- 根据 `evidence_goal` 决定当前轮检索重点
- 根据 `evidence_shape` 调整 query 的聚焦程度、freshness 表达和证据风格
- 根据 `selected_family` 采用更适合当前路径的 query phrasing
- 参考 `recent_low_value_queries`，避免重复近期已证明低价值的 phrasing

该过程不要求拆分为多个独立 LLM 步骤。

换言之，诸如“query objective framing”这类逻辑步骤，可以作为本小节内部的隐式 reasoning 存在，但在 MVP 阶段不要求它们成为独立字段或独立调用。

---

### C. Query Formulation Rules

MVP 阶段，建议至少遵循以下规则。

**1. Preserve core terms**

query 应尽量保留高信息密度术语，例如：

- feature 名
- method 名
- config 名
- API 名
- comparison 对象名

这些术语不应在改写中被随意删除或弱化。

---

**2. Be family-sensitive**

不同 family 下，query 风格不应相同：

- `docs_search`：偏精确术语、官方表达、文档风格
- `paper_search`：偏 topic / concept / method phrase
- `github_lookup`：偏 implementation / code-oriented phrase
- `web_search`：偏开放表达、公共信息和 freshness-sensitive 表达
- memory-oriented families：偏 topic / entity recall

---

**3. Reflect evidence goal**

`evidence_goal` 应继续影响 query 的检索重点。MVP 阶段，建议至少遵循以下启发式：

- `establish_coverage`
query 应优先指向基础 guidance、基础说明或基础背景材料，而不是一开始就展开更宽的比较或实现细节
- `strengthen_support`
query 应优先指向可为已有判断补强的 supporting material
- `resolve_ambiguity`
query 应优先突出存在歧义的术语、对象或边界，以便检索到更具区分性的材料
- `resolve_conflict`
query 应优先突出冲突对象、冲突说法或对照关系，以便检索到可用于冲突消解的材料
- `refresh_status`
query 应优先体现 `current`、`latest`、`recent` 等 freshness 导向表达
- `rebalance_comparison`
query 应优先体现 comparison 对象或 comparison 维度，以便补齐较弱一侧的证据
- `improve_actionability`
query 应优先体现 implementation、guidance、example、usage 等更利于落地执行的表达

---

**4. Reflect evidence shape**

`evidence_shape` 应继续影响 query 表达：

- `desired_evidence_kind = direct_fact`
query 应更精确、低歧义
- `desired_evidence_kind = supporting_evidence`
query 可更偏 supporting/background phrasing
- `desired_evidence_kind = comparison_evidence`
query 应体现比较对象或比较维度
- `desired_evidence_kind = status_evidence`
query 应更偏状态 / 最新表达
- `freshness_requirement = fresh_required`
可显式加入 `latest`、`current`、`recent` 等 freshness 导向词
- `breadth = narrow`
query 应更聚焦、更高 precision
- `breadth = broad`
query 可适当放宽，以换取更高覆盖

---

**5. Avoid recent low-value phrasing**

若提供了 `recent_low_value_queries`，则生成 query 时应尽量避开这些旧 query 的 phrasing。

这里的“避开”指的是：

- 不直接复用这些旧 query 的表述
- 不生成与其过于接近的 wording
- 允许做小幅 phrasing 区分，例如术语收敛、词序调整、问句转短语、轻量 precision / breadth 调整

但不得因此：

- 改变 `target_problem`
- 改变 `evidence_goal`
- 改变 `selected_family`
- 引入新的 sub-question
- 扩展为更宽的 topic

因此，`recent_low_value_queries` 的作用是：

**作为负例 phrasing 约束，而不是改变当前检索意图的依据。**

---

**6. Do not expand scope**

query generation 不得：

- 改变 `target_problem` 的核心语义
- 引入新的 sub-question
- 扩展为更宽的 topic
- 脱离当前 `selected_family`

因此，Query Generation 的本质是：

**bounded reformulation，而不是 scope expansion。**

---

### D. Low-value Query Admission Rule

`recent_low_value_queries` 不应包含所有历史 query，而只应包含**最近在当前 tool 和当前问题上下文下已被证明低价值的 query**。

MVP 阶段，建议一条历史 query 进入 `recent_low_value_queries` 时至少满足以下条件：

- `tool_used == selected_tool`
- `target_problem == current target_problem`
- 该 query 已被真实执行过
- 且满足以下任一低价值条件：
    - `result_status = no_result`
    - `result_status = failed`
    - `result_utility = not_useful`

同时建议：

- 仅保留最近 1 到 3 条
- 不纳入 `partial_success` 或 `weakly_useful` 的 query
- 不纳入不同 `target_problem` 下的 query
- 不纳入不同 `selected_tool` 下的 query

因此，`recent_low_value_queries` 应被理解为：

**当前 tool、当前问题上下文中的近期负例 query 列表。**

---

### E. Outputs

本小节建议至少产出以下结构化结果：

```
generated_query
query_focus
preserved_terms
```

其中：

**`generated_query`**

表示当前轮在当前 family 下生成的初始 query 表达。

**`query_focus`**

表示当前 query 主要聚焦的检索方向，用于解释这轮 query 为什么这样写。

MVP 阶段可采用轻量枚举，例如：

- `official_guidance`
- `implementation_example`
- `latest_status`
- `comparison_signal`
- `supporting_background`
- `conflict_resolution`

**`preserved_terms`**

表示当前 query 保留的核心高信息密度术语，用于校验 query 是否丢失关键对象或关键限定词。

需要强调的是：

- 本小节只负责生成**初始 query**
- 后续是否仍需额外运行时 guardrail，由更下游执行逻辑处理

---

### F. Practical Design Principle

本小节的核心作用可以概括为：

**在已选定 family 的前提下，将当前轮 retrieval intent 转换为适合当前路径的初始 query，并通过最近同 tool、同问题下的低价值 query 负例约束，避免机械重复低价值 phrasing。**

MVP 阶段，推荐采用：

- **一次受约束的 LLM 调用**生成初始 `generated_query`
- 同时输出少量轻量中间结果，如 `query_focus` 和 `preserved_terms`
- 仅将最近 1 到 3 条同 tool、同问题下的低价值 query 作为负例输入

这样可以在不增加额外 LLM 调用的前提下，降低 Query Generation 的黑盒程度，并减少明显重复的低价值 phrasing。

---

#### Appendix Example: Query Generation Prompt Template

下面是一版可放在附录里的**中文提示词模板**，对应当前这版 `5.6.3 Query Generation`。

```
你现在负责为检索系统生成当前轮的初始 retrieval query。

你的任务是：根据当前轮问题、证据目标、证据形态、已选定的 retrieval family，以及最近在相同问题上下文中表现不佳的旧 query，生成一个适合当前路径的初始 query。

注意：
1. 你现在只负责生成“初始 query”。
2. 你不负责做开放式搜索策略规划。
3. 你不负责改变检索任务本身。
4. 你不负责决定 selected_family 或 selected_tool。
5. `recent_low_value_queries` 中的旧 query 都来自同一个 target_problem，并且是在当前 tool 下近期效果不佳的 query。你应尽量避开与这些旧 query 过于接近的 phrasing，但不能因此改变当前问题边界。

你必须遵守以下要求：

1. 不要改变 target_problem 的核心语义。
2. 不要引入新的 sub-question。
3. 不要把问题扩展成更宽的 topic。
4. query 必须适配 selected_family 的风格：
   - docs_search：偏精确术语、官方表达、文档风格
   - paper_search：偏 topic / concept / method phrase
   - github_lookup：偏 implementation / code-oriented phrase
   - web_search：偏开放表达、公共信息、freshness-sensitive 表达
   - memory families：偏 topic / entity recall
5. query 必须尽量保留高信息密度术语，例如 feature 名、method 名、config 名、API 名或 comparison 对象名。
6. evidence_goal 决定当前轮检索重点：
   - establish_coverage：优先补齐基础覆盖
   - strengthen_support：优先补强已有判断
   - resolve_ambiguity：优先突出歧义点或边界
   - resolve_conflict：优先突出冲突对象或对照关系
   - refresh_status：优先体现最新状态
   - rebalance_comparison：优先体现 comparison 对象或 comparison 维度
   - improve_actionability：优先体现 implementation、guidance、example、usage 等更利于落地执行的表达
7. evidence_shape 决定 query 风格：
   - desired_evidence_kind：决定更偏 direct fact、support、comparison 或 status
   - freshness_requirement：决定是否显式体现 latest/current/recent
   - breadth：决定 query 更聚焦还是更宽
8. 如果提供了 recent_low_value_queries：
   - 不要直接重复这些旧 query 的 phrasing
   - 可以做小幅 phrasing 区分，例如术语收敛、词序调整、问句转短语、轻量 precision/breadth 调整
   - 但不得改变 target_problem、evidence_goal 或 selected_family
9. 你还需要显式输出：
   - query_focus：说明当前 query 主要聚焦的检索方向
   - preserved_terms：列出 query 中保留的核心高信息密度术语
10. 不要输出解释，不要输出推理过程，只输出 JSON。

输出字段必须且只能包含：
- generated_query
- query_focus
- preserved_terms

其中：
- generated_query：当前轮生成的初始 query
- query_focus：当前 query 的主要检索方向
- preserved_terms：query 中保留的核心术语列表

输入示例：
{
  "target_problem": "What is the recommended retrieval baseline for this use case?",
  "evidence_goal": "establish_coverage",
  "evidence_shape": {
    "desired_evidence_kind": "direct_fact",
    "freshness_requirement": "fresh_preferred",
    "breadth": "narrow"
  },
  "selected_family": "docs_search",
  "selected_tool": "openai_docs_search_v1",
  "success_hint": "At least one direct official guidance statement is preferred.",
  "recent_low_value_queries": [
    {
      "query": "retrieval baseline official guidance",
      "result_status": "no_result",
      "result_utility": "not_useful"
    },
    {
      "query": "official guidance for retrieval baseline",
      "result_status": "no_result",
      "result_utility": "not_useful"
    }
  ]
}

期望输出示例：
{
  "generated_query": "recommended retrieval baseline documentation",
  "query_focus": "official_guidance",
  "preserved_terms": [
    "retrieval baseline",
    "use case"
  ]

```

### 5.6.4 Retrieval Request Construction

本小节的目标，是将 `5.6.3 Query Generation` 生成的 `generated_query` 与当前轮少量执行参数组合为统一的 `retrieval_request`，供后续 retrieval execution 使用。

在当前设计中，`generated_query` 是检索请求的核心内容，但通常不等于完整执行请求。系统仍需要补充少量执行字段，例如结果规模和超时限制，才能形成可执行 request。

因此，本小节的核心问题不是“query 写什么”，而是：

**在 query 已确定后，如何将其组织成当前轮可执行的 retrieval request。**

---

#### A. Inputs

本小节主要读取以下输入：

- `generated_query`
- `selected_family`
- `selected_tool`
- `constraints.max_results`
- `timeout_limit_ms`
- `tool_registry`

其中：

**`generated_query`**

表示当前轮最终生成的检索表达，是 request construction 的核心输入。

**`selected_family`**

表示当前轮已选定的 retrieval path，用于为 request 提供路径上下文。

**`selected_tool`**

表示当前轮已选定的具体 tool，用于确定最终 request 应面向哪个执行器。

**`constraints.max_results`**

表示当前轮允许返回的目标结果规模上限。

**`timeout_limit_ms`**

表示当前轮 retrieval request 的超时限制。

**`tool_registry`**

提供 selected tool 的 capability metadata，用于判断某些执行字段是否受支持。

---

#### B. Construction Principle

当前阶段，Retrieval Request Construction 采用轻量设计。

在本设计中：

- family 差异主要已经体现在 `5.6.3 Query Generation`
- 本小节不重新决定 query 风格
- 本小节主要负责将 `generated_query` 与少量执行控制字段组合为统一 request

因此，本小节不应被写成复杂的 family-specific 或 tool-specific 参数系统，而应以轻量执行请求为主。

---

#### C. Retrieval Request Structure

MVP 阶段，建议 `retrieval_request` 至少包含以下字段：

```
selected_family
selected_tool
generated_query
max_results
timeout_limit_ms
```

其中：

**`selected_family`**

用于记录当前 request 所属的 retrieval path。

**`selected_tool`**

用于标识当前 request 的执行目标工具。

**`generated_query`**

用于提供当前轮的检索表达。

**`max_results`**

用于限制当前轮最多返回多少结果。

**`timeout_limit_ms`**

用于限制当前轮请求的最长执行时间。

可选地，若 selected tool 支持额外执行参数，也可在 request 中补充轻量扩展字段；但当前阶段不要求统一引入复杂 filter 或 scope schema。

---

#### D. Tool-facing Construction

在当前设计中，`retrieval_request` 是逻辑上的统一执行请求，而最终可执行 payload 仍由 selected tool 的 adapter 负责落地。

因此，本小节的职责是：

- 构造统一的逻辑 request
- 保证必需字段齐全
- 保证 request 与 selected tool 的基本能力相容

而不是：

- 直接展开为具体 SDK 参数表
- 在正文中描述每个 tool 的字段编码细节

若 selected tool 不支持某些可选字段，则 adapter 可在最终落地时忽略这些字段，或按 tool 能力做最小兼容处理。

---

#### E. Outputs

本小节建议至少产出以下结构化结果：

```
retrieval_request
```

其最小示例结构如下：

```json
{
  "selected_family": "docs_search",
  "selected_tool": "openai_docs_search_v1",
  "generated_query": "recommended retrieval baseline documentation",
  "max_results": 5,
  "timeout_limit_ms": 8000
}
```

---

#### F. Practical Design Principle

本小节的核心作用可以概括为：

**在 query 已确定后，将其与少量执行参数组合为统一的 retrieval request。**

当前阶段，系统应保持该步骤轻量，避免过早引入复杂的 request schema。

因此，`5.6.4 Retrieval Request Construction` 的重点不是复杂参数设计，而是：

- 统一 request 结构
- 保持执行字段最小充分
- 为后续 retrieval execution 提供稳定输入

### 5.6.5 Outputs

本小节定义 `5.6 Query Generation and Retrieval Request Construction` 的输出结果。

在当前设计中，`5.6` 的目标不是只生成一条 query，而是同时产出：

- 可解释的 query generation 结果
- 可直接进入后续执行的 retrieval request

因此，本小节建议至少输出以下结构化结果：

```
generated_query
query_focus
preserved_terms
retrieval_request
```

---

#### A. Query Outputs

**`generated_query`**

表示当前轮生成的初始检索表达。

它是 `5.6` 的核心中间结果，也是后续 `retrieval_request` 的核心内容。

**`query_focus`**

表示当前 query 主要聚焦的检索方向，用于降低 Query Generation 的黑盒程度，并帮助后续观察系统为什么生成该 query。

MVP 阶段可采用轻量枚举，例如：

- `official_guidance`
- `implementation_example`
- `latest_status`
- `comparison_signal`
- `supporting_background`
- `conflict_resolution`

**`preserved_terms`**

表示当前 query 保留的核心高信息密度术语，用于校验 query 是否丢失关键对象或关键限定词。

该字段主要服务于可解释性和调试，不要求承载复杂下游逻辑。

---

#### B. Execution Output

**`retrieval_request`**

表示最终可进入后续 retrieval execution 的统一执行请求。

在当前设计中，它是 `5.6` 的最终落地输出。

MVP 阶段，建议其最小结构至少包含：

```
selected_family
selected_tool
generated_query
max_results
timeout_limit_ms
```

其中：

- `selected_family`：当前 request 所属的 retrieval path
- `selected_tool`：当前 request 的执行目标工具
- `generated_query`：当前轮生成的检索表达
- `max_results`：当前轮允许返回的目标结果规模上限
- `timeout_limit_ms`：当前轮 retrieval request 的超时限制

其最小示例结构如下：

```
{
  "selected_family":"docs_search",
  "selected_tool":"openai_docs_search_v1",
  "generated_query":"recommended retrieval baseline documentation",
  "max_results":5,
  "timeout_limit_ms":8000
}
```

---

#### C. Output Principle

本小节的输出应满足以下原则：

- `generated_query` 用于保留 query generation 的直接结果
- `query_focus` 和 `preserved_terms` 用于保留最小必要的可解释性
- `retrieval_request` 作为统一执行输出，供后续 retrieval execution 直接消费

因此，`5.6` 的输出不应只是一条 query，而应同时保留：

- **query 本身**
- **query 的最小解释信息**
- **最终执行请求**

综上，`5.6.5 Outputs` 的核心作用可以概括为：

**将 query generation 结果与最终执行请求统一收束为一组最小充分的结构化输出。**

## 5.7 Retrieval Execution

本小节定义 retrieval execution 的输出结构、统一执行状态，以及**执行级降级信号**的判定规则，供后续 `5.8 Fallback and Retry Policy` 和 `5.9 Normalized Retrieval Output` 使用。

### A. Execution Outputs

MVP 阶段，建议 retrieval execution 至少返回以下结构化结果：

```
raw_retrieval_result
execution_status
failure_reason
returned_count
execution_metadata
```

其中：

**`raw_retrieval_result`**

selected tool 的原始返回结果集合，尚未进入 normalized retrieval output。

**`execution_status`**

当前 retrieval execution 的统一执行状态。

推荐枚举值：

- `success`
- `partial_success`
- `no_result`
- `failed`

**`failure_reason`**

执行失败类型。仅当 `execution_status = failed` 时有值；否则为空。

**`returned_count`**

当前 execution 返回的有效结果条数。

“有效结果”指至少通过 adapter 最小结构校验的 result item。

**`execution_metadata`**

轻量执行元信息。MVP 阶段建议至少包含：

```
tool_used
latency_ms
response_truncated
dropped_item_count
```

---

### B. Execution-level Degradation Signals

**执行级降级信号**指：tool 调用已完成，且返回了至少一部分可解析结果，但 execution 过程中存在明确迹象表明结果集可能不完整。

它强调的是 **execution 不完整**，而不是 **evidence 不够好**。

MVP 阶段，建议至少将以下情况视为执行级降级信号：

- **`response_truncated = true`**
    
    表示 tool 或 adapter 已明确检测到响应被截断，当前结果集可能不完整。
    
- **backend 明确返回 partial / incomplete 标记**
    
    表示 provider 或 connector 已显式声明本次返回不是完整结果集。
    
- **`dropped_item_count > 0` 且 `returned_count > 0`**
    
    表示原始响应中存在部分 item 无法通过 adapter 解析或校验，被执行层丢弃；虽然仍有结果保留，但结果集可能不完整。
    
- **tool 在部分结果已返回后中断，但剩余结果未完成**
    
    例如 partial page / partial stream 已被消费，但 execution 未完整结束；只要已有可用结果保留，则应视为 execution-level degradation。
    

以下情况**不单独视为执行级降级信号**：

- **`returned_count < max_results`**
    
    返回条数少于 `max_results`，不自动表示 execution 降级；可能只是可检索到的有效结果本来就少。
    
- **结果内容相关性弱或不足以支撑结论**
    
    这是 evidence-level 问题，不属于 execution-level degradation。
    
- **`returned_count = 0`**
    
    这应判定为 `no_result`，而不是降级信号。
    

---

### C. Execution Status Model

**`success`**

满足以下条件时判定为 `success`：

- tool 调用完成
- 原始响应可被 adapter 成功解析
- `returned_count > 0`
- 且不存在任何执行级降级信号

也就是说：

**成功获得至少 1 条有效结果，且 execution 本身没有明显不完整信号。**

---

**`partial_success`**

满足以下条件时判定为 `partial_success`：

- tool 调用完成
- 原始响应可被 adapter 成功解析
- `returned_count > 0`
- 且存在至少一个执行级降级信号

也就是说：

**有结果，但 execution 过程存在明确不完整迹象，因此当前结果集不能视为完整成功执行的产物。**

---

**`no_result`**

满足以下条件时判定为 `no_result`：

- tool 调用完成
- 原始响应可被 adapter 成功解析
- `returned_count = 0`
- 且没有 execution failure

也就是说：

**工具正常执行完成，但没有返回任何有效结果。**

---

**`failed`**

满足以下条件时判定为 `failed`：

- tool 调用未成功完成
    
    **或**
    
- 原始响应无法被 adapter 解析成可用结果集

也就是说：

**execution 未形成可用结果集，不是“没查到”，而是“没执行成”。**

---

### D. Failure Reason Classification

当 `execution_status = failed` 时，建议进一步给出 `failure_reason`。

MVP 阶段可采用以下枚举：

- `timeout`
- `tool_error`
- `auth_error`
- `invalid_request`
- `malformed_response`
- `rate_limited`
- `tool_unavailable`
- `unknown_error`

---

### E. Output Usage

- `execution_status`：作为 `5.8 Fallback and Retry Policy` 的主触发信号
- `failure_reason`：用于细化 retry / fallback 决策
- `raw_retrieval_result`：作为 `5.9 Normalized Retrieval Output` 的直接输入
- `returned_count` 和 `execution_metadata`：用于判断 execution 是否完整、是否值得补救

---

### F. Minimal Example

```json
{
  "raw_retrieval_result": [
    {
      "source_id": "doc_123",
      "snippet": "Recommended retrieval baseline is hybrid retrieval with reranking."
    }
  ],
  "execution_status": "success",
  "failure_reason": null,
  "returned_count": 1,
  "execution_metadata": {
    "tool_used": "openai_docs_search_v1",
    "latency_ms": 842,
    "response_truncated": false,
    "dropped_item_count": 0
  }
}
```

```json
{
  "raw_retrieval_result": [
    {
      "source_id": "doc_456",
      "snippet": "Hybrid retrieval is commonly used."
    }
  ],
  "execution_status": "partial_success",
  "failure_reason": null,
  "returned_count": 1,
  "execution_metadata": {
    "tool_used": "openai_docs_search_v1",
    "latency_ms": 1420,
    "response_truncated": true,
    "dropped_item_count": 2
  }
}
```

```json
{
  "raw_retrieval_result": [],
  "execution_status": "failed",
  "failure_reason": "timeout",
  "returned_count": 0,
  "execution_metadata": {
    "tool_used": "openai_docs_search_v1",
    "latency_ms": 8000,
    "response_truncated": false,
    "dropped_item_count": 0
  }
}
```

## 5.8 Fallback and Retry Policy

本小节定义 Tool Execution Layer 内部的 fallback 与 retry 策略。其职责，是在 Research Executor 已给定的执行约束内，针对当前 `retrieval_request` 做有限恢复，以尽量将该 request 执行到完成状态。

需要明确的是，Fallback / Retry 属于 **execution-level recovery**，而不是新的外围 agent iteration。

它不负责：

- 重新定义 `target_problem`
- 重新决定 `evidence_goal`
- 穷尽当前 `target_problem` 的所有潜在材料
- 发起新的高层 retrieval round

若高层仍认为当前 gap 未解决，外围 Agent Loop 可以在后续再次携带相同或相似的 `target_problem` 进入 Tool Execution Layer；此类重新进入应被视为 **Research Executor 发起的新 retrieval round**，而不是内部 retry。

---

### A. Recovery Boundary

本小节中的 retry / continue 只服务于**当前 `retrieval_request`**。

其目标不是“尽量把所有相关材料都搜出来”，而是：

- 尽量把当前 request 执行到完成状态
- 在预算内修复当前 request 的局部失败或局部不完整
- 在允许范围内切换到更可行的执行路径

因此，是否继续 retry / fallback 的判断标准，不是“当前 `target_problem` 还值不值得继续搜”，而是：

**当前 `retrieval_request` 是否仍未完成，且是否仍存在值得继续尝试的恢复路径。**

---

### B. Recovery Triggers

本小节主要基于 `5.7 Retrieval Execution` 的以下输出触发恢复逻辑：

- `execution_status`
- `failure_reason`
- `returned_count`
- `execution_metadata`

其中：

**`execution_status = success`**

一般不触发恢复，直接进入后续 normalized output。

**`execution_status = partial_success`**

可触发恢复，但仅当 execution-level degradation signals 表明当前 request 仍未完整执行时。

**`execution_status = no_result`**

通常触发恢复，因为当前 request 已执行完成，但未拿到有效结果。

**`execution_status = failed`**

通常触发恢复，但具体动作取决于 `failure_reason`。

---

### C. Allowed Recovery Actions

MVP 阶段，建议仅允许以下恢复动作：

**`continue`**

继续执行当前 `retrieval_request`。

仅当 execution metadata 明确表明当前 request 仍未完整执行时使用，例如：

- 存在分页 continuation token
- `response_truncated = true`
- backend 明确返回 partial / incomplete continuation 信号

**`retry_same_tool`**

在同一 `selected_tool` 上重试当前 request。

仅适用于少量可恢复的执行失败，例如：

- `timeout`
- 瞬时 `tool_error`
- `rate_limited`

**`fallback`**

在允许范围内切换执行路径。

可表现为：

- fallback 到同 family 下的另一个 tool
- fallback 到 `fallback_policy` 允许的其他 family

该动作必须受以下约束：

- `fallback_policy`
- `allowed_source_families`
- `preferred_source_families`
- `blocked_source_families`

**`stop`**

结束当前 request，不再继续补救。

---

### D. Recovery Heuristics

MVP 阶段，建议按以下启发式处理。

**1. `success`**

直接 `stop`。

当前 request 已完成，不再继续补救。

**2. `partial_success`**

若 execution metadata 表明当前 request 仍存在明确 continuation 信号，则优先 `continue`。

若仅存在部分降级信号，但没有明确 continuation 依据，则默认 `stop`，由外围 Agent Loop 决定是否围绕相同问题再发起新 round。

**3. `no_result`**

一般不建议在完全相同 request 上机械重试。

优先考虑：

- same-family fallback
- 或 cross-family fallback

若无合法 fallback 路径，则 `stop`。

**4. `failed`**

按 `failure_reason` 进一步处理：

- `timeout`
    
    可优先尝试一次 `retry_same_tool`；若仍失败，再考虑 `fallback`
    
- `tool_error`
    
    一般不建议多次 same-tool retry；优先考虑 `fallback`
    
- `rate_limited`
    
    可允许一次受限 retry；若预算不足，则直接 `fallback` 或 `stop`
    
- `malformed_response`
    
    一般优先 `fallback`
    
- `tool_unavailable`
    
    不应 same-tool retry；优先 `fallback`
    
- `auth_error`
    
    不应机械 retry，直接 `stop`
    
- `invalid_request`
    
    不应机械 retry，直接 `stop`
    
- `unknown_error`
    
    可允许一次保守 retry；若仍失败，则 `fallback` 或 `stop`
    

---

### E. Request Completion Criteria

本小节中的“完成当前 request”指以下任一情况成立：

- 已达到 `max_results`
- execution metadata 明确表明无更多结果可继续获取
- 当前 request 已完整执行完成，且无 continuation signal
- `retry_budget` 已耗尽
- `timeout_limit_ms` 总执行预算已耗尽
- 合法 fallback 路径已耗尽
- 当前 failure reason 不值得继续恢复

需要特别强调：

**当前 request 完成，并不等于当前 `target_problem` 的材料已经穷尽。**

若外围 Agent Loop 之后仍认为 evidence 不足，它可以再次携带相同或相似的 `target_problem` 进入 Tool Execution Layer。这属于新的 retrieval round，而不是本小节内部的 retry。

---

### F. Budget Guards

恢复动作必须同时受以下预算约束：

- `retry_budget`
- `fallback_policy`
- `allowed_source_families`
- `preferred_source_families`
- `blocked_source_families`
- `max_results`
- `timeout_limit_ms`

其中：

**`retry_budget`**

限制当前 request 允许进行的恢复动作总次数。

**`max_results`**

限制当前 request 允许返回的最大有效结果数；一旦达到该上限，应停止继续拉取结果。

**`timeout_limit_ms`**

表示当前 request 在 Tool Execution Layer 内的总执行时间预算，而不是单次 tool call 的独立预算。

因此，initial execution、retry、continue 和 fallback 都应共同消耗该总预算。

---

### G. Outputs

本小节建议至少产出以下结构化结果：

```
recovery_action
fallback_applied
retry_count
request_completion_status
next_retrieval_request
```

其中：

**`recovery_action`**

表示本轮恢复决策。

推荐枚举值：

- `continue`
- `retry_same_tool`
- `fallback`
- `stop`

**`fallback_applied`**

表示当前 request 是否已经发生过 fallback。

**`retry_count`**

表示当前 request 已进行的恢复动作次数。

**`request_completion_status`**

表示当前 request 是否已完成。

推荐枚举值：

- `complete`
- `incomplete_recoverable`
- `incomplete_unrecoverable`

**`next_retrieval_request`**

若恢复决策需要继续执行，则给出下一步 request；否则为空。

---

### H. Practical Design Principle

本小节的核心作用可以概括为：

**在高层约束已确定的前提下，对当前 `retrieval_request` 做有限恢复，以尽量将该 request 执行到完成状态。**

因此，`5.8 Fallback and Retry Policy` 不应被理解为新的搜索规划层，而应被理解为：

- 基于 execution result 的局部恢复机制
- 受预算约束的有限补救策略
- 面向当前 request completion 的执行层策略

而不是面向 `target_problem` 材料穷尽的高层研究决策。

## 5.9 End-to-End Tool Execution Flow

本小节从整体上描述 Tool Execution Layer 内部从接收请求到返回结果的完整执行链路。

其目的，是将前面各小节串联为一个受控闭环，而不是重复各小节的局部规则。

在当前设计中，Tool Execution Layer 的职责边界是：

- 接收外围传入的 retrieval intent 与 execution constraints
- 在当前约束下完成一次受控的 tool execution
- 返回 retrieval result、execution summary 与必要的运行轨迹
- 不负责重新定义高层问题，也不负责判断当前 `target_problem` 是否已被研究层面充分解决

---

### A. End-to-End Flow

Tool Execution Layer 的端到端流程建议统一为以下步骤：

**Step 1. Receive execution request**

接收 retrieval intent、routing constraints、retry / fallback constraints、execution budget 和 recent retrieval traces。

**Step 2. Route to source family and tool**

选择：

- `selected_family`
- `selected_tool`

对应 `5.5 Intent-to-Tool Routing`。

**Step 3. Generate initial query**

基于当前 retrieval intent 与约束生成：

- `generated_query`
- `query_focus`
- `preserved_terms`

对应 `5.6.3 Query Generation`。

**Step 4. Construct retrieval request**

将 query 与执行参数组合为：

- `retrieval_request`

对应 `5.6.4 Retrieval Request Construction`。

**Step 5. Execute retrieval request**

执行当前 request，并返回：

- `raw_retrieval_result`
- `execution_status`
- `failure_reason`
- `returned_count`
- `execution_metadata`

对应 `5.7 Retrieval Execution`。

**Step 6. Evaluate request completion and recovery need**

根据 execution outputs 判断当前 request：

- 是否已完成
- 是否需要 continue / retry / fallback
- 是否必须 stop

对应 `5.8 Fallback and Retry Policy`。

**Step 7. Apply continue / retry / fallback if needed**

若当前 request 仍可恢复，则执行：

- `continue`
- `retry_same_tool`
- `fallback`

否则执行：

- `stop`

**Step 8. Normalize retrieval result**

当前 request 停止后，将最终原始结果转换为 normalized retrieval output。

**Step 9. Return result to Research Executor**

返回 normalized retrieval output、execution summary 与运行轨迹，供外围 Agent Loop 后续继续使用。

---

### B. Flow Control Principle

当前端到端流程应遵循以下原则：

**1. Route once, then execute under current request boundary**

一旦当前轮 `selected_family` / `selected_tool` 已选定，后续动作默认围绕当前 request 展开。

**2. Retry / fallback serve request completion, not problem exhaustion**

内部恢复机制只服务于当前 `retrieval_request` 的执行完整性，而不负责穷尽当前 `target_problem` 的所有潜在材料。

**3. Stop when current request is complete or unrecoverable**

当当前 request 已完成、预算耗尽、恢复路径耗尽，或 failure reason 不值得继续恢复时，系统应停止当前 flow，并将结果返回上层。

---

### C. High-Level ASCII Flow

```
Receive execution request
        |
        v
Route to selected_family / selected_tool
        |
        v
Generate initial query
        |
        v
Construct retrieval_request
        |
        v
Execute retrieval_request
        |
        v
Evaluate execution result
        |
        +------------------------------+
        |                              |
        | request incomplete           | request complete /
        | and recoverable              | unrecoverable
        v                              v
Continue / Retry / Fallback        Normalize retrieval result
        |                              |
        +--------------->--------------+
                       |
                       v
Return result to Research Executor
```

---

### D. Practical Design Principle

本小节的核心作用可以概括为：

**将 routing、query generation、request construction、execution、recovery 和 result return 串联为一个受控的 Tool Execution Layer 内部闭环。**

这个闭环的终止条件，不是“当前 `target_problem` 的所有材料都已穷尽”，而是：

**当前 `retrieval_request` 已完成，或当前 request 已不值得继续恢复。**

## 5.10 Normalized Retrieval Output

本小节的目标，是将不同 tool 返回的 `raw_retrieval_result` 整理成统一结构，供后续 Evidence Processing 和 Research Executor 使用。

其本质是：

**把不同 tool 返回的原始结果，转换成后续模块统一可消费的材料列表。**

本小节不负责：

- 判断材料是否足以支撑结论
- 做高层 relevance 判断
- 做 evidence synthesis
- 重新生成 query 或触发 fallback / retry

---

### A. What This Step Does

本小节主要做四件事：

**1. Field mapping**

将不同 tool 的原始字段映射到统一字段。

**2. Content extraction**

从原始响应中抽出后续真正要消费的内容文本。

**3. Provenance preservation**

保留最小必要的来源信息，确保后续仍可追溯原始来源。

**4. Malformed item filtering**

丢弃无法被正常消费的结果项。

这里的 malformed item 指：

- 缺少最小 source identity
- 缺少 `content`
- 关键字段类型错误
- 结构异常，无法映射到统一 schema

需要强调的是，malformed 属于**结构问题**，不是内容质量问题。

---

### B. Inputs

本小节主要读取：

- `raw_retrieval_result`
- `execution_status`
- `selected_family`
- `selected_tool`
- `execution_metadata`

---

### C. Normalized Item Schema

MVP 阶段，建议每个 normalized item 至少包含以下字段：

```
item_id
source_family
source_type
source_ref
content
content_type
metadata
```

其中：

- `item_id`：内部唯一标识
- `source_family`：来源 family，例如 `docs_search`、`paper_search`、`github_lookup`、`web_search`、`memory_lookup`
- `source_type`：来源类型，例如 `document`、`paper`、`webpage`、`code_file`、`memory_record`
- `source_ref`：原始来源引用，例如 URL、doc id、repo/file path、memory id
- `content`：后续层实际消费的文本内容
- `content_type`：内容类型，例如 `text_snippet`、`document_chunk`、`code_snippet`、`memory_entry`
- `metadata`：轻量附加信息，例如 `title`、`timestamp`、`repo`、`path`、`page`、`rank`、`score`

---

### D. Outputs

本小节建议至少产出以下结构化结果：

```
normalized_items
dropped_item_count
source_summary
```

其中：

**`normalized_items`**

标准化后的统一材料列表，是后续 Evidence Processing 的直接输入。

**`dropped_item_count`**

在标准化阶段被丢弃的 item 数量。

主要用于 observability，以及判断原始结果中有多少 item 因结构问题未进入后续流程。

**`source_summary`**

当前 normalized result 的来源概览。MVP 阶段建议至少包含：

- `selected_family`
- `selected_tool`
- `normalized_count`

其中 `normalized_count` 表示最终进入 `normalized_items` 的 item 数量。

---

### E. Minimal Example

假设原始结果里有 3 条 item，其中 2 条结构正常，1 条缺少内容字段，则标准化后可得到：

```json
{
  "normalized_items": [
    {
      "item_id": "item_001",
      "source_family": "docs_search",
      "source_type": "document",
      "source_ref": "doc_123",
      "content": "Recommended retrieval baseline is hybrid retrieval with reranking.",
      "content_type": "text_snippet",
      "metadata": {
        "title": "Retrieval Baseline Guide"
      }
    },
    {
      "item_id": "item_002",
      "source_family": "github_lookup",
      "source_type": "code_file",
      "source_ref": "repo_x/src/search.py",
      "content": "def hybrid_retrieve(...): ...",
      "content_type": "code_snippet",
      "metadata": {
        "repo": "repo_x",
        "path": "src/search.py"
      }
    }
  ],
  "dropped_item_count": 1,
  "source_summary": {
    "selected_family": "docs_search",
    "selected_tool": "openai_docs_search_v1",
    "normalized_count": 2
  }
}
```

---

### F. Practical Design Principle

本小节的核心作用可以概括为：

**将 tool-specific raw retrieval result 整理成后续模块统一可消费的材料列表。**

## 5.11 Outputs

本小节定义 Tool Execution Layer 对外返回给 Research Executor 的最终输出。

这些输出不再表示层内中间产物，而表示：

- 本轮 retrieval 最终拿到了什么材料
- 本轮 acquisition 最终状态如何
- 本轮执行摘要是什么
- 哪些 retrieval 轨迹应回传给上层，用于后续 continuity

因此，Tool Execution Layer 的最终输出建议至少包含：

```
normalized_items
acquisition_status
dropped_item_count
source_summary
execution_summary
retrieval_trace
```

---

### A. Primary Outputs

**`normalized_items`**

表示本轮 retrieval 最终返回的标准化材料列表。

它是 Tool Execution Layer 最核心的主输出，也是后续 Evidence Processing 的直接输入。

**`acquisition_status`**

表示本轮 Tool Execution Layer 的最终 acquisition 状态。

它反映的是**整层最终状态**，而不是某一次 execution attempt 的局部状态。

MVP 阶段，推荐枚举值：

- `success`
- `partial_success`
- `no_result`
- `failed`

其中：

- `success`：最终获得了可用材料，且本轮 acquisition 无明显未恢复的不完整问题
- `partial_success`：最终获得了可用材料，但本轮 acquisition 伴随 fallback / partial execution / dropped items 等不完整信号
- `no_result`：本轮 acquisition 已完成，但没有获得任何可用材料
- `failed`：本轮 acquisition 未形成可用材料列表，且属于执行失败而非单纯“查无结果”

---

### B. Supporting Outputs

**`dropped_item_count`**

表示在 normalization 阶段被丢弃的 item 数量。

该字段主要用于 observability，以及帮助上层理解本轮 raw result 中有多少 item 因结构问题未进入后续流程。

**`source_summary`**

表示本轮结果来源概览。

MVP 阶段建议至少包含：

- `selected_family`
- `selected_tool`
- `normalized_count`

其中：

- `selected_family`：本轮最终使用的 source family
- `selected_tool`：本轮最终使用的 tool
- `normalized_count`：最终进入 `normalized_items` 的 item 数量

**`execution_summary`**

表示本轮 Tool Execution Layer 的执行摘要。

MVP 阶段建议至少包含：

- `selected_family`
- `selected_tool`
- `fallback_applied`
- `retry_count`

其中：

- `fallback_applied`：本轮是否发生过 fallback
- `retry_count`：本轮发生过多少次内部恢复动作

**`retrieval_trace`**

表示应回传给上层 state 的 retrieval 轨迹摘要，用于后续 continuity。

该字段的目标，不是完整执行日志，而是记录本轮 retrieval 的最小事实性轨迹。

MVP 阶段建议至少包含：

- `target_problem`
- `selected_family`
- `selected_tool`
- `generated_query`
- `acquisition_status`

该字段后续可被上层用于：

- 维护 recent retrieval history
- 构造后续 `recent_low_value_queries`
- 支持下一轮 retrieval context continuity

---

### C. Output Principle

本小节输出应满足以下原则：

**1. 面向上层消费，而非层内调试**

`5.11` 只保留上层真正需要消费的最终结果，不重复暴露所有层内中间对象。

**2. 主结果与辅助摘要分离**

`normalized_items` 和 `acquisition_status` 是主输出；其余字段用于解释来源、执行情况和后续 continuity。

**3. 返回当前轮结果，不替上层做高层判断**

Tool Execution Layer 负责返回“本轮拿到了什么、怎么拿到的、最终状态如何”，但不负责判断当前 `target_problem` 是否已被充分解决。

---

### D. Minimal Example

```json
{
  "normalized_items": [
    {
      "item_id": "item_001",
      "source_family": "docs_search",
      "source_type": "document",
      "source_ref": "doc_123",
      "content": "Recommended retrieval baseline is hybrid retrieval with reranking.",
      "content_type": "text_snippet",
      "metadata": {
        "title": "Retrieval Baseline Guide",
        "rank": 1
      }
    },
    {
      "item_id": "item_002",
      "source_family": "docs_search",
      "source_type": "document",
      "source_ref": "doc_456",
      "content": "Hybrid retrieval is commonly used as a practical baseline.",
      "content_type": "text_snippet",
      "metadata": {
        "title": "Practical Retrieval Notes",
        "rank": 2
      }
    }
  ],
  "acquisition_status": "partial_success",
  "dropped_item_count": 1,
  "source_summary": {
    "selected_family": "docs_search",
    "selected_tool": "openai_docs_search_v1",
    "normalized_count": 2
  },
  "execution_summary": {
    "selected_family": "docs_search",
    "selected_tool": "openai_docs_search_v1",
    "fallback_applied": false,
    "retry_count": 1
  },
  "retrieval_trace": {
    "target_problem": "What is the recommended retrieval baseline for this use case?",
    "selected_family": "docs_search",
    "selected_tool": "openai_docs_search_v1",
    "generated_query": "recommended retrieval baseline documentation",
    "acquisition_status": "partial_success"
  }
}
```

---

### E. Practical Design Principle

本小节的核心作用可以概括为：

**将 Tool Execution Layer 本轮执行结果收束为一组最小充分的对外输出，供后续 Evidence Processing 与 Research Executor 继续使用。**

如果你愿意，下一步我们可以继续看 `5.11 Practical Design Constraints` 要不要保留，以及怎么写。

## 5.12 Practical Design Constraints

# 6. Evidence Processing Model

这一节专门讲 evidence 从 raw material 变成 usable evidence 的过程。

建议包含：

- raw result normalization
- deduplication / redundancy control
- summarization / compression
- comparison alignment
- evidence gap detection
- conflict detection
- evidence placement

这一节重点是讲：

**拿回来的材料如何变成当前 stage 真正可用的 evidence。**

## 6.1 Purpose and Boundary

本节定义 **Evidence Processing Model** 的职责边界。其目标，是将来自 Tool Execution Layer 的 candidate materials 处理为当前轮可直接消费的 **processed evidence set**，供后续 state update、intermediate findings 和 sufficiency judgment 使用。

在当前设计中，本层主要负责：

- material-level deduplication
- evidence structuring
- evidence-level consolidation

因此，本层可被理解为：

**从 candidate materials 到 round-level evidence result 的转换层。**

只有当上游 `acquisition_status` 为：

- `success`
- `partial_success`

时，本层才进入完整处理链。

若上游 `acquisition_status` 为：

- `no_result`
- `failed`

则本层应短路返回空的 evidence result，并保留 acquisition outcome 给后续 Research Executor 使用。

本层不负责：

- retrieval routing
- query generation
- retrieval execution
- fallback / retry
- final reasoning or recommendation

## 6.2 Inputs

Evidence Processing Model 只消费 **Tool Execution Layer 在 `5.11 Outputs` 中正式对外返回的结果**。

因此，本层输入应严格对齐 `5.11 Outputs`，而不额外引入未在上游定义过的新输入字段。

---

### A. Direct Inputs

**`normalized_items`**

- **出处**：`5.11 Outputs.normalized_items`
- **含义**：本轮 retrieval 最终返回的标准化材料列表，是本层最核心的输入。
- **用途**：作为后续 relevance filtering、material-level deduplication、evidence structuring 和 evidence-level consolidation 的主要处理对象。

**`acquisition_status`**

- **出处**：`5.11 Outputs.acquisition_status`
- **含义**：本轮 Tool Execution Layer 的最终 acquisition 状态。
- **用途**：帮助本层理解当前输入的整体结果背景，例如当前轮是 `success`、`partial_success`、`no_result` 还是 `failed`。

**`dropped_item_count`**

- **出处**：`5.11 Outputs.dropped_item_count`
- **含义**：在 normalization 阶段被丢弃的 item 数量。
- **用途**：用于 observability，并帮助本层理解当前 `normalized_items` 是否已经历过一定程度的结构过滤。

**`source_summary`**

- **出处**：`5.11 Outputs.source_summary`
- **含义**：本轮结果来源概览。
- **用途**：帮助本层理解当前 candidate materials 的来源背景，例如本轮最终使用了哪个 family、哪个 tool，以及最终保留下来的材料数量。

**`execution_summary`**

- **出处**：`5.11 Outputs.execution_summary`
- **含义**：本轮 Tool Execution Layer 的执行摘要。
- **用途**：帮助本层理解当前结果是否经历过 fallback / retry，以及本轮材料是沿哪条执行路径获得的。

**`retrieval_trace`**

- **出处**：`5.11 Outputs.retrieval_trace`
- **含义**：本轮 retrieval 的最小事实性轨迹。
- **用途**：为本层提供当前轮 evidence processing 所需的问题上下文与 retrieval 背景。

---

### B. Derived Processing Context

以下 processing context 不作为独立上游输入存在，而是**从 `retrieval_trace` 中读取**：

**`target_problem`**

- **出处**：`5.11 Outputs.retrieval_trace.target_problem`
- **用途**：作为本轮 evidence processing 的核心问题边界，用于 relevance filtering、evidence typing 和 evidence linkage。

**`selected_family`**

- **出处**：`5.11 Outputs.retrieval_trace.selected_family`
- **用途**：帮助本层理解当前材料来自哪类 source family。

**`selected_tool`**

- **出处**：`5.11 Outputs.retrieval_trace.selected_tool`
- **用途**：帮助本层理解当前材料的具体 retrieval path。

**`generated_query`**

- **出处**：`5.11 Outputs.retrieval_trace.generated_query`
- **用途**：帮助本层理解当前 candidate materials 是围绕什么 query 获取的，可辅助判断 retrieval scope 与 evidence relevance。

---

### C. Input Principle

本层输入应满足以下原则：

**1. Only consume finalized outputs from Section 5**

本层只消费第 5 节正式对外返回的结果，而不直接消费 Tool Execution Layer 内部中间对象。

**2. Treat `normalized_items` as candidate materials, not final evidence**

即使经过了 normalization，`normalized_items` 仍只是 candidate materials；本层仍需进一步完成 evidence shaping。

**3. No new upstream fields should be introduced implicitly**

若未来需要让新的 memory-derived results 或其他输入进入本层，则这些结果必须先在上游章节中被显式定义并输出，再进入本层输入范围。

## 6.3 Material-level Deduplication

本节的目标，是在 evidence extraction 之前，对 `normalized_items` 做**轻量、确定、source-aware** 的材料级去重，去除明显重复或高度重叠的原材料，避免同一 source 片段被重复进入后续 evidence structuring。

本节只处理 **material-level duplicate**，不处理 claim-level 或 evidence-level 的语义合并。

---

### A. Deduplication Rule Scope

本节的去重规则只应作用于：

- 当前批次中的 `normalized_items`
- 或当前批次与同一 retrieval round 内已保留 materials 的比较

本节默认只在 **同一 source_ref 内** 做高重叠去重，不在不同 source 间做 material-level deduplication。

---

### B. Deduplication Rules

MVP 阶段，建议按以下顺序执行。

**Rule 1. Same item identity**

若两个 item 满足以下任一条件，则直接视为重复：

- `item_id` 相同
- `source_ref` 相同，且定位字段完全相同，例如：
    - 同一 `page`
    - 同一 `section`
    - 同一 `path`
    - 同一 `span`

这类重复应直接删除其一，不需要进一步判断。

---

**Rule 2. Same source + same normalized content**

若两个 item 满足以下条件，则视为 exact duplicate：

- `source_ref` 相同
- `content` 在 normalize 后完全相同

其中 `content normalize` 建议至少包括：

- 小写化
- 去除首尾空白和多余空格
- 统一连续空白
- 忽略轻量标点差异（可选）

这类重复应直接删除其一。

---

**Rule 3. Same source + containment**

若两个 item 满足以下条件，则视为高重叠重复：

- `source_ref` 相同
- 其中一个 item 的 normalized content 基本被另一个 item 包含

典型场景包括：

- 同一文档片段只是窗口边界略有差异
- 同一网页 snippet 长短不同，但核心文本相同
- 同一 code excerpt 被不同 retrieval attempt 以略微不同范围命中

这类情况下，原则上保留信息更完整的一条。

---

**Rule 4. Same source + high overlap ratio**

若两个 item 满足以下条件，则视为 high-overlap duplicate：

- `source_ref` 相同
- normalized content 的 overlap ratio 高于预设阈值

MVP 阶段可采用轻量 overlap 计算，例如：

- token overlap
- character containment ratio
- longest common subsequence ratio（若实现简单）

该规则只应用于**同一 source 内**，不用于跨 source 材料去重。

---

**Rule 5. Retry / fallback duplicate replay**

若同一 source 片段因 retry / fallback 被重复命中，则仍按 Rule 1 ~ Rule 4 去重。

换言之，retrieval path 不同并不会阻止本节将其视为重复 material。

---

### C. Keep Rule

当多个 item 被判定为 duplicate 时，建议按以下优先级保留：

1. 保留 `content` 更完整的一条
2. 若完整度相近，保留 `metadata` 更丰富的一条
3. 若仍相近，保留 rank 更高的一条（若有）
4. 若仍无法区分，保留首次出现的一条

该规则的目标，是在不引入复杂判断的前提下，尽量保留更适合后续 evidence extraction 的材料。

---

### D. Constraints

本节去重规则应满足以下约束：

- 仅处理 **material-level** 重复
- 仅做 **cheap, deterministic** 判断
- 不使用 LLM
- 不做跨 source 的重语义 merge
- 不在本节判断“两个 item 是否表达同一个结论”

因此，本节的去重应被理解为：

**evidence extraction 前的轻量减噪，而不是 evidence-level consolidation。**

---

### E. Outputs

本节建议至少产出以下结构化结果：

```
deduped_materials
removed_duplicate_count
dedup_summary
```

其中：

- `deduped_materials`：去重后保留的 material 列表
- `removed_duplicate_count`：被移除的 duplicate material 数量
- `dedup_summary`：去重摘要，建议至少包含：
    - `input_count`
    - `output_count`
    - `exact_duplicate_removed`
    - `high_overlap_removed`

---

## 6.4 Evidence Structuring

本节的目标，是将 dedup 后的 `normalized_items` 转换为后续可直接消费的 **typed evidence units**。

这是从“材料”到“证据”的关键转换步骤。

本节主要负责：

- 判断当前 material 是否值得进入 evidence set
- 从保留的 material 中抽取 `1..n` 个 evidence unit
- 为每个 evidence unit 标注 `evidence_type`
- 将当前轮已知上下文直接附着到 evidence unit 上

本节不负责：

- material-level deduplication
- evidence-level consolidation
- final reasoning or recommendation

---

### A. Inputs

本节主要读取：

- `deduped_materials`
- `target_problem`
- `target_scope`
- `evidence_goal`
- `sub_question`（若有）
- `comparison_candidate`（若有）
- `gap`（若有）

其中：

- `deduped_materials` 是本节的直接处理对象
- 其余字段是当前轮已知上下文，用于指导 evidence extraction
- 这些上下文字段由上游直接提供，不需要 LLM 重新判断

---

### B. Structuring Logic

MVP 阶段，建议对每条 material 在**同一个 LLM call**中同时完成以下三项判断：

**1. Relevance decision**

判断当前 material 是否值得进入 evidence set。

推荐枚举值：

- `keep`
- `drop`

若 `decision = drop`，则不产生 evidence unit。

**2. Evidence extraction**

若 `decision = keep`，则从当前 material 中抽取 `1..n` 个 evidence unit。

需要强调：

- 一个 material 可能抽不出任何有效 evidence，因此最终可被丢弃
- 一个 material 也可能包含多个不同 signal，因此允许抽出多个 evidence unit

**3. Evidence type assignment**

对每个抽出的 evidence unit 直接标注 `evidence_type`。

MVP 阶段建议采用轻量枚举：

- `direct_fact`
- `supporting_signal`
- `comparison_signal`
- `status_signal`
- `background_signal`

---

### C. Structuring Principle

本节应遵循以下原则：

**1. Source-grounded**

evidence extraction 必须保持 source-grounded。

当前任务上下文可以影响“抽取哪些信号”，但不能改变原始材料本身的含义。

**2. Task-aware**

同一个 material 在不同 `target_problem`、`sub_question` 或 `evidence_goal` 下，抽取重点可以不同。

因此，evidence unit 是面向当前任务的抽取结果，而不是对 material 的静态唯一解释。

**3. No mechanical re-chunking**

本节不再对 `normalized_items` 做机械二次 chunking。

其目标是抽取 evidence signal，而不是重新切分 retrieval unit。

---

### D. Evidence Unit Schema

MVP 阶段，建议每个 evidence unit 至少包含以下字段：

```
evidence_unit_id
source_ref
source_family
source_type
content
evidence_type
support_refs
target_problem
target_scope
evidence_goal
sub_question
comparison_candidate
gap
```

其中：

- `evidence_unit_id`：内部唯一标识
- `source_ref` / `source_family` / `source_type`：来源信息
- `content`：当前轮抽取出的 evidence 内容
- `evidence_type`：evidence 类型
- `support_refs`：支撑该 evidence 的最小来源引用
- `target_problem` / `target_scope` / `evidence_goal` / `sub_question` / `comparison_candidate` / `gap`：当前轮上下文标签，直接从上游附着

---

### E. Outputs

本节建议至少产出以下结构化结果：

```
structured_evidence_units
dropped_material_count
structuring_summary
```

其中：

**`structured_evidence_units`**

本节输出的 typed evidence units，供后续 `6.5 Evidence-level Consolidation` 使用。

**`dropped_material_count`**

在本节被判定为 `drop`，或未能产出有效 evidence unit 的 material 数量。

**`structuring_summary`**

本节处理摘要。MVP 阶段建议至少包含：

- `input_material_count`
- `kept_material_count`
- `dropped_material_count`
- `output_evidence_unit_count`

---

### F. Practical Design Principle

本节的核心作用可以概括为：

**将 dedup 后的 candidate materials 转换为 source-grounded、task-aware、typed evidence units。**

因此，本节是第 6 节中从“材料处理”进入“证据处理”的关键分界点。

### G. 提示词Example

```json
你现在负责执行 Evidence Structuring。

你的任务是：针对一条 dedup 后的 material，判断它是否值得进入当前轮 evidence set；如果值得，则从中抽取 1 到多个 source-grounded 的 evidence unit，并为每个 evidence unit 标注 evidence_type。

你必须遵守以下要求：

1. 你的输入 material 已经完成了 material-level deduplication。
2. 你现在不负责做 evidence-level consolidation。
3. 你不负责做 final reasoning、recommendation 或 action planning。
4. 你不负责重新判断 target_problem、target_scope、evidence_goal、sub_question、comparison_candidate、gap，这些字段由上游直接提供。
5. 你必须保持 source-grounded：
   - 只能抽取原材料中明确表达或可直接支持的内容
   - 不要夸大原文含义
   - 不要把弱提示改写成强结论
6. 你当前只需要做三件事：
   - 判断当前 material 是 keep 还是 drop
   - 如果 keep，则抽取 1..n 个 evidence_unit
   - 为每个 evidence_unit 标注 evidence_type
7. 不要做机械摘要，不要输出解释过程，只输出 JSON。

evidence_type 只能从以下枚举中选择：
- direct_fact
- supporting_signal
- comparison_signal
- status_signal
- background_signal

判断标准：
- keep：当前 material 对当前轮问题有继续处理价值，并且能抽取出至少一个有效 evidence unit
- drop：当前 material 对当前轮问题没有继续处理价值，或无法抽取出有效 evidence unit

输出 JSON 必须且只能包含以下字段：
- decision
- evidence_units

其中：
- decision: "keep" 或 "drop"
- evidence_units: 数组
  - 若 decision = "drop"，则必须返回空数组 []
  - 若 decision = "keep"，则返回 1..n 个 evidence unit

每个 evidence unit 必须包含以下字段：
- content
- evidence_type
- support_refs

其中：
- content: 当前抽取出的 evidence 内容，要求简洁、source-grounded、面向当前任务
- evidence_type: 从给定枚举中选择
- support_refs: 指向当前 material 的最小来源引用；如果只有一个 source_ref，则直接复用该 source_ref

下面是当前轮上下文：
- target_problem: {target_problem}
- target_scope: {target_scope}
- evidence_goal: {evidence_goal}
- sub_question: {sub_question}
- comparison_candidate: {comparison_candidate}
- gap: {gap}

下面是当前待处理 material：
- source_ref: {source_ref}
- source_family: {source_family}
- source_type: {source_type}
- content: {content}
- metadata: {metadata}

期望输出示例 1：keep
{
  "decision": "keep",
  "evidence_units": [
    {
      "content": "Hybrid retrieval is commonly used as a practical baseline.",
      "evidence_type": "direct_fact",
      "support_refs": ["doc_123"]
    },
    {
      "content": "Hybrid retrieval improves recall but adds reranking cost.",
      "evidence_type": "comparison_signal",
      "support_refs": ["doc_123"]
    }
  ]
}

期望输出示例 2：drop
{
  "decision": "drop",
  "evidence_units": []
}
```

## 6.5 Evidence-level Consolidation

本节的目标，是对 **当前轮** `6.4 Evidence Structuring` 输出的 typed evidence units 做**保守的轻量合并**，形成更稳定的 round-level evidence set，供后续 state update 和 reasoning 使用。

本节需要存在，主要有以下原因：

- 不同 material 可能抽取出表达同一信息的 evidence unit
- 若不合并，同一轮内同一信息可能被重复计数
- evidence 条数增加，并不等于信息增量增加
- 重复 evidence 会抬高后续 reasoning 成本，并制造“证据很多”的假象

因此，本节的作用不是单纯减少 evidence 数量，而是：

**让当前轮的 evidence set 更接近独立 evidence signal 的集合，而不是重复表达的堆积。**

---

### A. Scope

本节只处理**当前轮内部**的 evidence-level consolidation。

其输入是 `6.4 Evidence Structuring` 输出的 typed evidence units。

本节不负责：

- 与前几轮已累计 evidence state 的跨轮合并
- 不同 `evidence_type` 之间的 merge
- 重语义推断型 consolidation
- 复杂 claim clustering

其中，**跨轮合并**更适合由 Research Executor 在 `Step 6. Update Stage-local Working State` 中完成，因为那属于 stage-local evidence state integration，而不是当前轮内部的 evidence shaping。

---

### B. Consolidation Principle

本节应遵循以下原则：

**1. Consolidation is about evidence identity, not text compression**

本节要判断的不是“哪段文本更长”，而是“两条 evidence 是否应视为同一条 evidence”。

**2. Conservative merge**

宁可少合并，也不要误合并。

错误合并会吞掉细微差异，而漏合并通常只会带来轻微冗余。

**3. Same-type only**

默认只在**同一 `evidence_type`** 内尝试 consolidation。

不同类型 evidence 在后续 reasoning 中角色不同，不应在本节混合合并。

**4. Current-round only**

本节只整合当前轮新形成的 evidence，不处理历史 evidence state。

**5. Preserve support diversity**

合并后应保留所有 `support_refs`，避免“合并”演化为“丢失来源信息”。

---

### C. Consolidation Rules

MVP 阶段，建议仅对**同一 `evidence_type`** 的 evidence unit 执行 consolidation。

在执行规则前，先对 `content` 做轻量 normalize：

- 小写化
- 去除首尾空白和多余空格
- 统一连续空白
- 忽略轻量标点差异（可选）

在此基础上，建议按以下顺序执行。

**Rule 1. Exact match**

若两个 evidence unit 满足以下条件，则直接合并：

- `evidence_type` 相同
- normalize 后的 `content` 完全相同

此时保留一条 canonical evidence，并聚合两者的 `support_refs`。

---

**Rule 2. Containment of a longer wording variant**

若两个 evidence unit 满足以下条件，则可合并：

- `evidence_type` 相同
- 较短 evidence 的 `content` 被较长 evidence 完整包含
- 较长 evidence 仅表现为轻微措辞扩展，而未引入新的独立信息、限制条件、适用边界或补充结论

该规则只用于处理**同一条 evidence 的轻微长短版本**。

#### **例子**

**可合并**

- A: `Hybrid retrieval is a practical baseline.`
- B: `Hybrid retrieval is commonly used as a practical baseline.`

B 只是轻微扩展表达，没有新增独立信息。

**不可合并**

- A: `Hybrid retrieval is a practical baseline.`
- B: `Hybrid retrieval is a practical baseline, but it adds reranking cost.`

B 新增了 limitation / cost 信息，不应合并。

---

**Rule 3. No cross-type merge**

若两个 evidence unit 的 `evidence_type` 不同，则默认不合并，即使文本相近也分别保留。

---

**Rule 4. When in doubt, keep both**

若任一 pair 无法稳定满足以上规则，则默认不合并。

MVP 阶段应优先避免误合并，而不是追求最大化压缩。

---

### D. Keep Rule

当多个 evidence unit 被判定为可合并时，建议按以下优先级保留 canonical evidence：

1. 保留信息更完整的一条
2. 若完整度相近，保留表达更清晰的一条
3. 若仍相近，保留首次出现的一条

合并时应聚合所有 `support_refs`。

---

### E. Outputs

本节建议至少产出以下结构化结果：

```
round_consolidated_evidence_units
merged_evidence_count
consolidation_summary
```

其中：

**`round_consolidated_evidence_units`**

当前轮内部完成 consolidation 后的 evidence units，供后续 state update 和 reasoning 使用。

**`merged_evidence_count`**

本节中被成功合并的 evidence 数量。

**`consolidation_summary`**

本节处理摘要。MVP 阶段建议至少包含：

- `input_evidence_count`
- `output_evidence_count`
- `exact_match_merged`
- `containment_merged`

---

### F. Practical Design Principle

本节的核心作用可以概括为：

**对当前轮新形成的 typed evidence units 做保守的轻量 consolidation，减少明显重复 evidence，并形成更稳定的 round-level evidence set。**

因此，本节解决的不是单纯的数量压缩问题，而是：

- 避免同一信息被重复计数
- 降低后续 reasoning 的冗余输入
- 让 evidence 条数更接近真实的信息增量

如果你愿意，下一步我建议继续把 **跨轮 merge** 放回 `4.3.2 Step 6` 里单独定义清楚。

## 6.6 Outputs

本节定义 **Evidence Processing Model** 对外返回给 Research Executor 的最终输出。

这些输出表示本轮 candidate materials 经过去重、evidence structuring 和 current-round consolidation 后形成的 round-level evidence result。

本节建议至少产出以下结构化结果：

```
processed_evidence_units
evidence_summary
evidence_processing_summary
```

---

### A. Output Fields

**`processed_evidence_units`**

本轮最终形成的 evidence units，是后续 state update 和 reasoning 的直接输入。

**`evidence_summary`**

本轮 evidence result 的轻量摘要，用于帮助后续 reasoning 快速把握本轮新增 evidence。

**`evidence_processing_summary`**

本节内部处理摘要，用于 observability 和上层理解本轮 evidence processing 的主要变化。

---

### B. Field Details

**`processed_evidence_units`**

表示本轮最终保留下来的 round-level evidence units。

若上游 `acquisition_status` 为 `no_result` 或 `failed`，则该字段应返回空列表 `[]`。

**`evidence_summary`**

表示本轮 evidence result 的概览。

MVP 阶段建议至少包含：

- `new_evidence_count`：本轮最终形成的 evidence unit 数量
- `evidence_type_breakdown`：各 `evidence_type` 的数量分布
- `source_coverage_summary`：本轮 evidence 覆盖的 source family / source type 概览

**`evidence_processing_summary`**

表示本节处理过程的简要统计。

MVP 阶段建议至少包含：

- `input_material_count`：进入第 6 节的 material 数量
- `deduped_material_count`：material-level dedup 后保留的 material 数量
- `structured_evidence_count`：structuring 后得到的 evidence unit 数量
- `merged_evidence_count`：在 current-round consolidation 中被合并的 evidence 数量
- `output_evidence_count`：最终输出的 evidence unit 数量

---

### C. Output Principle

本节输出应满足以下原则：

- 返回第 6 节最终 evidence result，而不是中间对象
- `processed_evidence_units` 是主输出，其余字段是辅助摘要
- 若上游未形成可处理材料，本节应返回空的 evidence result，而不是制造伪 evidence

---

### D. Minimal Example

```json
{
  "processed_evidence_units": [
    {
      "evidence_unit_id": "ev_001",
      "source_ref": "doc_123",
      "source_family": "docs_search",
      "source_type": "document",
      "content": "Hybrid retrieval is commonly used as a practical baseline.",
      "evidence_type": "direct_fact",
      "support_refs": ["doc_123"],
      "target_problem": "What is the recommended retrieval baseline for this use case?",
      "target_scope": {
        "scope_type": "use_case",
        "scope_id": "retrieval_baseline"
      },
      "evidence_goal": "establish_coverage",
      "sub_question": null,
      "comparison_candidate": null,
      "gap": "baseline_recommendation"
    }
  ],
  "evidence_summary": {
    "new_evidence_count": 1,
    "evidence_type_breakdown": {
      "direct_fact": 1
    },
    "source_coverage_summary": {
      "source_families": ["docs_search"],
      "source_types": ["document"]
    }
  },
  "evidence_processing_summary": {
    "input_material_count": 3,
    "deduped_material_count": 2,
    "structured_evidence_count": 2,
    "merged_evidence_count": 1,
    "output_evidence_count": 1
  }
}
```

# ~~7. Research Stage State and Data Flow~~

~~这一节讲 state 和数据流转，但只讲和本篇直接相关的部分。~~

~~建议包含：~~

- ~~Research Stage 读哪些 state fields~~
- ~~写哪些 state fields~~
- `~~StageInput` 和 stage-local working state 的关系~~
- ~~intermediate findings 如何形成和更新~~
- ~~processed evidence 如何在 stage 内流转~~
- ~~stage 结束时哪些结果回写到 `ExecutionContext`~~

~~这一节重点是讲：~~

**~~Research Stage 内部的数据是怎么流动的。~~**

---

# ~~8. Stop, Degraded Mode, and Guardrails~~

~~这一节很重要，讲清楚：~~

- ~~stop condition~~
- ~~continue condition~~
- ~~evidence insufficient 时怎么办~~
- ~~evidence conflicting 时怎么办~~
- ~~tool failure 时怎么办~~
- ~~degraded mode 的触发条件~~
- ~~runtime budgets~~
- ~~iteration / tool call / evidence injection guardrails~~

~~这一节重点是讲：~~

**~~Research Stage 何时收束，何时退化，以及如何避免失控。~~**

---

# ~~9. Observability Hooks~~

~~这一节不用写完整 observability 体系，只写本篇需要暴露哪些信号。~~

~~建议包含：~~

- ~~request-level runtime trace~~
- ~~iteration count~~
- ~~selected tools~~
- ~~retrieval source usage~~
- ~~evidence count / evidence summary signals~~
- ~~stop / continue decision signals~~
- ~~degraded mode reason~~
- ~~stage latency breakdown~~

~~这一节重点是讲：~~

**~~Research Stage 运行时哪些东西要可见。~~**

---

# 10. Open Questions / Re-evaluable Items

这一节保留少量仍可后续评估的问题。

例如：

- future 是否引入 selective parallel retrieval
- query rewrite 是否进入 baseline
- evidence compression 粒度是否调整
- contradiction handling 是否需要更强机制
- 是否需要 evaluator-style refinement

这一节的作用是：

**明确哪些已经定了，哪些还可以以后再调整。**

---

本节记录当前设计中**已做出阶段性选择，但未来仍可能重新评估**的部分。

其目的，是明确哪些方向是当前版本先这样定下来的，而不是永久固定的。

---

### 10.1 Cross-round Evidence Merge Strategy

**Current Direction**

Cross-round merge 放在 `Research Executor / Step 6` 中处理，并采用保守的规则式 merge，默认不依赖 LLM。

**Why Not Finalized**

随着 stage-local evidence state 增长，规则式 merge 可能留下更多语义重复 evidence。

**When to Re-evaluate**

当 evidence state 膨胀明显，或“本轮新增了什么”越来越难判断时。

---

### 10.2 Evidence Structuring Granularity

**Current Direction**

`6.4 Evidence Structuring` 直接从 dedup 后的 material 抽取 `1..n` 个 evidence unit，不做机械 re-chunking。

**Why Not Finalized**

evidence unit 的抽取粒度仍可能偏粗或偏细。

**When to Re-evaluate**

当单个 evidence unit 经常包含多个独立 signal，或 evidence 粒度明显不稳定时。

---

### 10.3 Evidence Type Taxonomy

**Current Direction**

当前采用轻量 `evidence_type` 枚举，例如：

- `direct_fact`
- `supporting_signal`
- `comparison_signal`
- `status_signal`
- `background_signal`

**Why Not Finalized**

后续若 comparison、conflict handling 或 actionability judgment 变复杂，现有 taxonomy 可能不足。

**When to Re-evaluate**

当现有 `evidence_type` 已无法稳定支撑 consolidation、reasoning 或 sufficiency judgment 时。

---

### 10.4 Continue / Stop / Degrade Thresholds

**Current Direction**

当前设计已明确 `continue / stop / degrade` 的判定原则，但未锁定具体 operational thresholds。

**Why Not Finalized**

前期更适合先明确语义边界，而不是过早固定数值阈值。

**When to Re-evaluate**

当 runtime 中频繁出现低价值循环、degrade 触发不稳定，或实现需要更明确控制规则时。

---

### 10.5 Stage-local Evidence State Shape and Usage Metadata

**Current Direction**

`stage-local evidence state` 持续累积 evidence，并将 `target_problem` 更偏向视为 usage metadata，而不是 evidence identity 的硬条件。

**Why Not Finalized**

usage metadata 的保留粒度与组织方式仍未完全锁定。

**When to Re-evaluate**

当 evidence 使用历史开始显著影响 findings refinement、state explainability 或 cross-round merge 稳定性时。

---

### 10.6 Runtime Observability Scope

**Current Direction**

当前设计未单独展开完整 observability 体系，而是将相关 runtime signals 分散定义在 iteration、action、evidence processing、stage exit 和 cross-round merge 的输出中。

**Why Not Finalized**

这有助于控制 LLD 长度，但后续实现时，可能仍需要进一步收束为更系统的 tracing 结构。

**When to Re-evaluate**

当 runtime 行为难以调试、degraded mode 原因不易定位，或 evaluation / tracing 需求明显上升时。

---

### 10.7 Practical Note

本节中的条目不表示当前设计不可实现，而表示：

**当前版本已经做出明确选择，但这些选择仍具有阶段性，后续可随着实现反馈和 runtime behavior 变化而重新评估。**