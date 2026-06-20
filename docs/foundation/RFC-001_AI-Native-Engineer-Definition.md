# RFC-001: What is an AI Native Engineer?

**Status**: Draft v3.0  
**Date**: 2026-06-19  
**Author**: AI Education OS Project  
**Scope**: 整个项目所有内容（书/课程/面试题/练习）都必须围绕本文档定义的目标人才培养。

---

## Abstract

本文档定义"AI Native Engineer"的完整含义、历史背景、能力模型（L0-L4）、与传统工程师的区别，以及本书和整个系统要培养的目标人才画像。

素材来源：AI原生应用工程师JD、Harness工程师JD、14维度架构审查框架、安全合规审查框架、40章课程课纲（StudyAthena）。

所有后续文档（ADR、SPEC、STD、Prompt、Chapter）都引用本 RFC 中的定义，不允许各自重新定义。

---

## 1. Background — 为什么会出现 AI Native Engineer？

### 1.1 软件工程的三次范式转变

**第一次（1960s-1980s）：汇编 → 高级语言**  
程序员从手写机器指令，转向用接近人类逻辑的语言写程序。生产力提升 10x。

**第二次（1990s-2010s）：单机 → 互联网 + 云计算**  
软件从本地运行转向分布式。催生了 Web 工程师、DevOps、微服务架构师。

**第三次（2020s - 现在）：确定性代码 → AI 驱动系统**  
软件从"写死的逻辑"转向"由大语言模型推理驱动的工作流"。  
催生了 **AI Native Engineer**。

### 1.2 为什么"会用 ChatGPT"不够

ChatGPT 发布后，每个人都能让 AI 帮忙写几行代码。但企业真正需要的是：

- 能**设计完整 AI 工作流**的人（不是调用一个 API）
- 能让 AI **自主完成多步任务**的人（Agent，而不是单轮对话）
- 能**评估 AI 输出质量**并持续改进的人（Evaluation Pipeline）
- 能在**生产环境中稳定运行**AI 系统的人（Harness + Monitoring）
- 能**治理 AI 风险**的人（安全、合规、伦理）

### 1.3 行业现状：窗口期

2023年之前，做到上面这些需要自己训练模型（数百万美元）。  
2023年之后，门槛变成了：会写代码 + 理解 Prompt + 掌握 Agent/RAG/Workflow 设计模式。

**这个窗口期不会长久。现在掌握这些技能的工程师，将在未来5年享有巨大的市场溢价。**

---

## 2. Definition — AI Native Engineer 是什么

> **AI Native Engineer（AI 原生工程师）**：以大语言模型（LLM）为基础组件，设计、开发、评估并维护 AI 驱动软件系统的工程师。其核心工作不是写传统业务逻辑，而是设计人机协作的 Workflow，编排 Agent，构建知识系统（RAG），并持续评估 AI 行为的正确性、安全性和合规性。

### 关键词拆解

| 关键词 | 含义 |
|--------|------|
| **以 LLM 为基础组件** | LLM 不是工具，而是系统的一等公民，和数据库、消息队列同级 |
| **设计 Workflow** | 把业务流程拆解成 AI 可执行的步骤序列，含状态管理和异常恢复 |
| **编排 Agent** | 让多个 AI 角色协同完成复杂任务，含 A2A 协议和 Human-in-the-Loop |
| **构建 RAG** | 给 AI 注入私有知识，减少幻觉，包括知识图谱 RAG |
| **持续评估** | 像 CI/CD 一样，持续测量 AI 输出质量，含 Harness 框架 |
| **安全性和合规性** | FCARS 框架（公平、合规、问责、可靠、安全），AI 治理 |

---

## 3. Difference — AI Native Engineer vs 传统软件工程师

| 维度 | 传统软件工程师 | AI Native Engineer |
|------|--------------|-------------------|
| **核心产出** | 确定性代码（if/else/for） | 概率性 AI 系统（Prompt + Workflow） |
| **调试方式** | 看报错堆栈，找逻辑 bug | 分析 AI 输出偏差，优化 Prompt 和 Evaluation |
| **测试方式** | 单元测试（输入→固定输出） | LLM-as-Judge + Harness 自动化评测 + Chaos Engineering |
| **扩展方式** | 加函数、加模块 | 加 Agent、加 Tool、加 Memory |
| **知识来源** | 写死在代码里 | RAG 从外部知识库实时检索 + 知识图谱 |
| **协作对象** | 同事工程师 | AI Agent + 人类工程师（A2A + Human-in-the-Loop）|
| **关键技能** | 算法、数据结构、系统设计 | Prompt Engineering、Agent 设计、RAG、Evaluation、AI 治理 |
| **风险管理** | 异常处理、回滚 | Hallucination 检测、Bias 评估、Chaos Engineering、安全审计 |
| **成本意识** | 服务器成本 | Token 成本、推理成本、缓存策略、模型分级路由 |
| **合规意识** | 数据安全 | FCARS 框架、AI 伦理、多租户隔离、Guardrails |
| **安全意识** | SQL 注入、XSS | Prompt Injection、Tool Injection、Agent 权限升级、IDOR |

### 他们不是对立的

AI Native Engineer **必须**有扎实的软件工程底盘：

- 后端开发或全栈开发能力
- 系统设计（System Design）：API 设计、异步队列、状态机
- 版本控制（Git + Prompt 版本管理）
- 测试（AI Evaluation 是测试的超集）
- 部署（Docker、K8s、云服务、CI/CD Pipeline）
- 生产环境错误排查与恢复能力

**AI Native Engineer = 软件工程底盘 + AI 系统设计能力 + AI 治理能力**

---

## 4. Capability Model — 核心能力模型（L0-L4）

### 4.1 能力等级定义

| 等级 | 名称 | 描述 | 典型能力表现 | 经验参考 |
|------|------|------|------------|---------|
| **L0** | 入门用户 | 理解基本概念，能使用 AI 工具 | 能跑通 Demo，能修改简单 Prompt | — |
| **L1** | AI 从业者 | 独立完成小型 AI 项目 | 能独立做 RAG 问答系统，能设计单 Agent | 1年以下AI项目经验 |
| **L2** | AI 应用工程师 | 独立开发**生产级** AI 应用 | 能设计完整 Agent 系统 + RAG + Evaluation，能 Review AI 代码 | 1年以上**生产环境**AI经验 |
| **L3** | AI 系统架构师 | 设计复杂多 Agent 系统和平台 | 能架构多 Agent 协作，主导内部AI平台/复杂工作流引擎建设，能独立完成14维度架构审查 | 3年以上软件开发+复杂系统经验 |
| **L4** | AI 平台架构师 | 定义 AI 技术方向和平台 | 能设计 AI 基础设施，推动 AI 治理和组织级落地，能定义团队技术规范和工程文化 | — |

> **关键区分**：
> - L1 → L2：**生产环境经验**。Demo 成功 ≠ L2，系统真正跑在生产并解决过真实故障才算 L2。
> - L2 → L3：**系统视角**。L2 能实现，L3 能设计并审查整个系统，能发现别人代码里的架构缺陷。
> - L3 → L4：**组织视角**。L3 管系统，L4 管技术方向和工程文化，能影响整个团队的 AI 工程能力。

**本书的目标**：覆盖 L0 → L4 完整路径。每章标注目标级别，读者可按自身阶段深入。

### 4.2 完整能力树

```
AI Native Engineer
│
├── 【L0-L1】AI 基础能力
│   ├── LLM 工作原理（Token、Context Window、Temperature、Attention）
│   ├── Prompt Engineering
│   │   ├── 基础技巧（Few-shot、Zero-shot、Role Prompting）
│   │   ├── 高级技巧（CoT、ReAct、Self-Consistency）
│   │   └── 结构化输出（JSON Mode、Function Calling）
│   ├── AI 产品思维（什么时候用 AI，什么时候不用）
│   └── 本地模型部署（Ollama、模型量化、硬件选型）
│
├── 【L1-L2】Agent 工程
│   ├── 单 Agent 设计（Planning → Tool Use → Observation → Memory）
│   ├── Agent Loop 机制（ReAct Loop、最大迭代次数、无限循环防护）
│   ├── 多 Agent 编排
│   │   ├── Supervisor-Worker 模式
│   │   ├── A2A 协议（Agent-to-Agent 直接通信）
│   │   ├── Pipeline（串行 Agent 流水线）
│   │   └── Debate（多 Agent 辩论决策）
│   ├── Human-in-the-Loop（审核节点、Interrupt 点设计）
│   └── Agent Harness（运行时基建）
│       ├── 任务编排与状态持久化
│       ├── Checkpoint / Resume（断点续跑）
│       ├── 失败恢复与重试策略
│       ├── 动态任务分配与优先级调度
│       ├── Agent 生命周期管理（创建→执行→暂停→恢复→完成→失败）
│       └── Sandbox 沙箱（隔离 Agent 执行环境）
│
├── 【L1-L2】RAG 工程
│   ├── Embedding 与向量检索
│   ├── Chunking 策略（语义分块、滑动窗口、层次分块）
│   ├── Reranking（BGE、Cross-encoder）
│   ├── RAG Evaluation（RAGAS 框架）
│   ├── GraphRAG / LightRAG（知识图谱 RAG、关系推理）
│   └── 混合检索（Hybrid Search：关键词 BM25 + 向量）
│
├── 【L1-L2】Workflow 工程
│   ├── 状态机设计（LangGraph）
│   ├── Checkpoint 与 Resume
│   ├── 条件分支（Conditional Edge）
│   ├── 循环与终止条件
│   └── 并行子图（Parallel Subgraph）
│
├── 【L1-L2】MCP / Tool Use
│   ├── Tool 定义与注册（Schema 设计）
│   ├── MCP 协议（Model Context Protocol）
│   ├── 工具封装（内部系统/DB/API → 安全 Tool）
│   ├── 外部系统集成（数据库、REST API、文件系统）
│   └── 工具安全（路径白名单/黑名单、沙箱限制、调用失败降级）
│
├── 【L1-L2】Memory 系统
│   ├── Short-term Memory（Context Window 管理、上下文裁剪）
│   ├── Long-term Memory（持久化存储）
│   ├── Memory 检索与更新策略
│   ├── 记忆类型（Episodic、Semantic、Procedural）
│   └── 多请求间的 Memory 隔离
│
├── 【L2-L3】Evaluation 与 AI 测试工程
│   ├── LLM-as-Judge 设计（评分 Prompt、偏差控制）
│   ├── Eval 数据集构建（Ground Truth 标注、数据收集策略）
│   ├── 自动化评测 Pipeline（Harness 触发、Before/After Diff）
│   ├── 指标设计（准确率、幻觉率、相关性、忠实度）
│   ├── RAGAS（Context Precision、Faithfulness、Answer Relevancy）
│   ├── 回归测试（Prompt 变更前后对比，防止质量退化）
│   ├── 负载测试与容量规划（压测 AI 服务，发现瓶颈）
│   └── AI 测试策略
│       ├── 单元测试（Tool、Parser、Retriever 的确定性部分）
│       ├── 集成测试（Agent + Tool + Memory 的端到端链路）
│       ├── E2E 测试（完整业务流程验证）
│       └── Eval 测试（AI 输出质量评估，替代传统断言）
│
├── 【L2-L3】可观测性（Observability）
│   ├── 链路追踪（Tracing）
│   │   ├── Agent 每步执行的 Span 记录
│   │   ├── Tool 调用的入参/出参/耗时
│   │   └── LLM 请求的 Token 用量、延迟、模型版本
│   ├── 日志监控（Logging）
│   │   ├── 结构化日志（JSON 格式，含 trace_id、session_id）
│   │   └── 错误分级与告警规则
│   ├── LLM Observability（专项）
│   │   ├── Prompt/Response 记录（可回溯）
│   │   ├── 幻觉率趋势监控
│   │   └── 模型漂移检测（同 Prompt 输出质量随时间变化）
│   └── Metrics 与告警
│       ├── SLO 定义（P95 延迟、成功率、Token 用量）
│       └── 成本告警（Token 超预算自动触发）
│
├── 【L2-L3】安全与治理（Security & Guardrails）
│   ├── Prompt Injection 防御
│   │   ├── System Prompt 与 User Input 严格隔离
│   │   ├── 恶意指令检测（被注入网页/文档的攻击）
│   │   └── OWASP AI Security Top 10
│   ├── Tool Injection 防御
│   │   ├── 工具路径白名单/黑名单
│   │   └── Sandbox 沙箱限制执行权限
│   ├── Agent 权限升级漏洞（必须能发现并修复）
│   │   ├── Agent 能否读取 .env / .git / ~/.ssh 文件？
│   │   ├── Agent 能否执行任意 shell 命令？
│   │   ├── Agent 能否读取平台自身源码？
│   │   ├── Agent 能否访问数据库连接字符串？
│   │   └── Agent 能否获取 API Key？
│   ├── Guardrails 设计
│   │   ├── 输入过滤（PII 检测、有害内容拦截）
│   │   ├── 输出过滤（敏感信息脱敏、有害内容过滤）
│   │   ├── 高风险操作拦截（删除、支付、外发等需二次确认）
│   │   └── 敏感操作审批闭环（Human-in-the-Loop + 审批链）
│   ├── 认证与授权
│   │   ├── JWT 校验覆盖率
│   │   ├── IDOR（越权访问）防护
│   │   └── project_id 级别的强制数据隔离
│   └── 密钥管理（密钥隔离、轮换、最小权限原则）
│
├── 【L2-L3】成本优化（Cost Optimization）
│   ├── 识别可缓存但未缓存的调用（相同 System Prompt 重复发送）
│   ├── 识别可用小模型替代的调用（分类/提取任务用了重型模型）
│   ├── 识别可用规则替代的调用（正则/模板能解决却用了 LLM）
│   ├── 识别上下文过长导致的浪费（整个 HTML/文档塞进 Prompt）
│   ├── 识别失败重试导致的重复计费
│   ├── 模型分级路由（大模型→复杂推理，小模型→分类/提取）
│   └── Token 预算管理（设计 Token 上限 + 超限降级策略）
│
├── 【L2-L3】可靠性工程（Reliability & Chaos Engineering）
│   ├── 故障场景设计与演练
│   │   ├── LLM API 超时（>30s）→ timeout + 用户提示
│   │   ├── 速率限制（429）→ 自动重试 + 账号轮换 + 降级
│   │   ├── LLM 返回非法 JSON → 解析容错 + fallback
│   │   ├── Playwright/浏览器崩溃 → 进程恢复机制
│   │   ├── 数据库连接池耗尽 → 监控 + 排队机制
│   │   ├── Token 额度耗尽 → 成本预警 + 模型降级
│   │   ├── 用户关闭页面但 Agent 仍运行 → 生命周期管理
│   │   ├── 并发多用户同时触发 Agent → 并发隔离 + 资源限制
│   │   └── Agent 无限循环 → 最大迭代次数 + 超时强制终止
│   ├── SLO 定义与监控
│   └── 降级策略（Graceful Degradation）
│
├── 【L2-L3】软件工程（AI 场景专项）
│   ├── Prompt 版本管理（Git 化管理 Prompt，像代码一样 Review）
│   ├── AI 应用的 CI/CD（Prompt 变更 → 自动触发 Eval → 通过才部署）
│   ├── AI Coding Agent（AI 辅助开发、代码生成、技术债识别）
│   └── 主流框架掌握
│       ├── 核心：LangChain、LangGraph
│       ├── 多 Agent：AutoGen、CrewAI、OpenAI Agents SDK
│       ├── 高性能推理：VLLM
│       └── 扩展能力：MCP、browser automation、code interpreter
│
├── 【L2-L3】部署与运维
│   ├── AI 服务容器化（Docker + Kubernetes）
│   ├── 多租户隔离（数据隔离、权限隔离、计费独立）
│   ├── 限流与降级策略
│   ├── Fine-tuning 工程（LoRA、数据集构建、评估）
│   └── 本地模型部署（Ollama、模型量化 Q4/Q8、VRAM 计算）
│
├── 【L3-L4】AI 治理（FCARS 框架）
│   ├── Fairness（公平性：消除偏见，偏见评估数据集）
│   ├── Compliance（合规性：GDPR、数据主权、审计日志）
│   ├── Accountability（问责性：决策链路记录、Trace 可视化）
│   ├── Reliability（可靠性：SLA、故障率、Chaos Engineering）
│   ├── Safety（安全性：内容过滤、Prompt Injection 防御）
│   └── AI 伦理政策制定与监督执行
│
└── 【L3-L4】AI 系统架构（14维度审查能力）
    ├── 系统架构（整体分层、模块边界、依赖关系）
    ├── Agent 架构（循环防护、并发隔离、反思节点）
    ├── Workflow 架构（状态持久化、断点续跑、H-i-t-L）
    ├── Prompt 架构（分层、版本管理、System/User 隔离）
    ├── Tool Calling 架构（封装规范、路径沙箱、失败降级）
    ├── MCP 兼容性（协议适配、扩展点设计）
    ├── Memory 架构（层次化、多请求隔离、一致性）
    ├── Evaluation 架构（数据集、自动化、回归、持续量化）
    ├── Observability 架构（Tracing、Logging、LLM 可观测性）
    ├── Security 架构（权限升级漏洞、Injection 防护、密钥隔离）
    ├── Multi-tenant 架构（IDOR 防护、project_id 隔离）
    ├── Scalability 架构（并发 Agent、连接池、异步队列）
    ├── Cost Optimization 架构（Token 预算、缓存、模型路由）
    └── CI/CD 架构（Prompt 变更 → 自动 Eval → 自动部署）
```

---

## 5. Mindset — AI Native 思维模式

### 5.1 从"写代码"到"设计行为"

传统工程师问：**"我怎么写代码实现这个功能？"**  
AI Native Engineer 问：**"我怎么设计这个系统，让 AI 可靠地完成这个任务？"**

### 5.2 从"确定性"到"概率性"

传统系统：输入 A → 输出 B（永远固定）  
AI 系统：输入 A → 输出概率分布（需要 Evaluation 持续监测 + Harness 自动回归）

### 5.3 从"调试代码"到"对齐意图"

AI 出问题不是 bug，而是**意图对齐失败**：
- Prompt 表达不够精确
- 缺少合适的 Example
- Context 信息不足
- 任务分解不合理
- Knowledge 覆盖有盲区

### 5.4 从"Demo 成功"到"生产级交付"

Demo 成功和生产可用之间有一道鸿沟：

| Demo 阶段 | 生产阶段 |
|-----------|---------|
| 理想输入，理想路径 | 边界输入、异常输入、恶意输入 |
| 单用户，无并发 | 多用户并发，资源竞争 |
| 不考虑成本 | Token 成本、运维成本都要算 |
| 不考虑安全 | Prompt Injection、权限升级都要防 |
| 手动触发 | 自动监控、自动告警、自动恢复 |

**L2 的标准：能独立把一个 AI 应用从 Demo 推上生产，并在生产中持续维护。**

### 5.5 第一性原理思维

面对新 AI 框架时，不问"怎么用"，而问：
- **它解决了什么问题？**
- **没有它之前怎么做？**
- **什么时候不应该用它？**

### 5.6 数据飞轮思维

AI 系统不是"上线就完成"，而是：

```
用户交互 → 数据收集 → 质量评估 → 模型/Prompt 优化 → 更好的用户体验 → 更多用户交互
```

**数据飞轮（Data Flywheel）**：每次 AI 服务运行都是一次数据机会，需要系统性地收集、标注、评估、迭代。

### 5.7 企业交付思维

AI 项目不是"Demo 成功就行"，而是有明确的交付阶段：

```
POC（概念验证）→ MVP（最小可行产品）→ V1（生产版本）→ V2（优化版本）→ Platform（平台化）→ Organization（组织级落地）
```

---

## 6. Engineering Principles — 工程原则

AI Native Engineer 的工程实践原则（区别于传统软件工程）：

1. **Prompt 是代码**：Prompt 要版本控制，要 Review，要测试，不允许随意修改生产环境 Prompt
2. **Evaluation First**：没有评估体系的 AI 系统不能上生产；Evaluation 先于功能开发
3. **Human-in-the-Loop**：关键决策节点必须有人工审核机制；Interrupt 节点是一等公民
4. **Fail Gracefully**：AI 输出异常时，系统要有合理的降级策略；Checkpoint/Resume 是必须的
5. **Production First**：所有设计以生产环境为目标——安全、可观测、可恢复。Demo 能跑不等于可以上线
6. **Cost Awareness**：每个设计决策都要考虑 Token 成本；识别浪费，设计 Token 预算和缓存策略
7. **Reproducibility**：同一 Prompt + 同一输入，要能复现问题（Temperature=0 用于调试）
8. **Separation of Concerns**：业务逻辑、Prompt、知识库、评估逻辑要分层管理
9. **FCARS Compliance**：所有 AI 系统必须能回答：公平、合规、问责、可靠、安全五个维度
10. **Chaos Engineering**：定期演练 AI 系统故障场景（LLM 不可用、RAG 失效、Tool 超时、Agent 循环）
11. **Observability by Default**：所有 AI 系统必须有 Trace、Log、Metric，不允许黑盒上线
12. **Architecture Review**：L3+ 工程师必须能对 AI 系统做 14 维度独立架构审查，发现安全漏洞和设计缺陷

---

## 7. Responsibilities — 职责范围

### 7.1 AI Native 应用工程师（L1-L2）的日常职责

| 职责 | 描述 |
|------|------|
| **端到端交付** | 需求分析 → 开发 → 生产部署 → 迭代优化（全链路负责） |
| **Prompt 工程** | 编写、测试、迭代 Prompt；维护 Prompt 版本库 |
| **知识库建设** | 组织、清洗、向量化私有知识；构建知识图谱 |
| **Agent 开发** | 设计 Agent 角色、Tool 列表、Memory 策略、Workflow |
| **工具封装** | 将内部系统（DB/API/文件系统）封装为安全的 Agent Tool |
| **Evaluation** | 构建 Eval 数据集，建立自动化评测 Pipeline |
| **集成与部署** | 容器化、API 集成、监控告警配置 |
| **技术选型** | 评估 LangGraph/AutoGen/CrewAI/MCP 等框架的适用场景 |
| **AI 与业务集成** | 将 AI 能力落地到核心业务流程和自动化场景 |
| **平台复用** | 构建可复用 AI 工具与平台能力（Scalability + Maintainability） |

### 7.2 AI Harness 工程师（L2-L3）的专项职责

| 职责 | 描述 |
|------|------|
| **Harness 平台设计** | 设计任务编排系统，支持复杂 Agent Workflow |
| **状态持久化** | 实现 Checkpoint/Resume，保证长任务断点续跑不丢失 |
| **失败恢复** | 实现重试机制、错误分类、人工介入触发 |
| **动态任务分配** | 根据任务优先级和资源状态动态调度 Agent |
| **沙箱构建** | 实现 Sandbox 隔离 Agent 执行环境，防止越权 |
| **Guardrails 设计** | 高风险操作拦截、敏感操作审批机制、输入/输出过滤 |
| **链路追踪** | 实现完整的 Tracing（每步 Span），支持问题定位 |
| **负载测试** | 对 AI 系统做压测，发现容量瓶颈 |
| **成本优化** | Token 用量追踪、缓存策略、模型路由优化 |
| **Chaos Engineering** | AI 系统故障演练，验证降级策略有效性 |

### 7.3 AI 架构师（L3-L4）的系统职责

| 职责 | 描述 |
|------|------|
| **14维度架构审查** | 对 AI 系统做全面架构审查，输出审查报告和改进方案 |
| **安全漏洞识别** | 发现并修复 Agent 权限升级漏洞、Injection 漏洞 |
| **FCARS 治理** | 制定 AI 伦理政策，监督合规执行 |
| **数据飞轮设计** | 设计数据收集、标注、评估、反馈的完整闭环 |
| **平台化规划** | 将 AI 能力抽象为平台，供多团队复用 |
| **组织级推广** | 制定 AI 工程最佳实践，培训团队 |
| **Fine-tuning 决策** | 判断何时需要 Fine-tuning，何时 RAG 足够 |
| **多模态系统设计** | 集成文本、图像、语音等多模态 AI 能力 |

---

## 8. Core Technical Domains — 核心技术领域详解

### 8.1 Prompt Engineering（全栈）

- 基础：Zero-shot、Few-shot、System Prompt
- 进阶：Chain-of-Thought（CoT）、ReAct、Self-Consistency
- 工程化：Prompt 版本管理、A/B 测试、回归测试
- 安全：System Prompt 与 User Input 隔离（防 Injection）

### 8.2 Agent 架构

- **单 Agent**：Planning → Tool Use → Observation → Memory（ReAct Loop）
- **Agent Loop 防护**：最大迭代次数限制、超时强制终止、反思节点递归保护
- **多 Agent**：
  - Supervisor-Worker（主从模式）
  - Peer-to-Peer（A2A 协议，Agent 直接通信）
  - Pipeline（串行 Agent 流水线）
  - Debate（多 Agent 辩论决策）
- **Agent Harness**：任务生命周期管理（创建→执行→暂停→恢复→完成→失败）

### 8.3 RAG 工程（检索增强生成）

- **基础 RAG**：分块 → Embedding → 向量存储 → 检索 → 生成
- **高级 RAG**：
  - HyDE（假设文档 Embedding）
  - Self-Query（自动生成查询条件）
  - Hybrid Search（向量 + BM25）
  - Reranking（BGE、Cross-encoder）
- **GraphRAG / LightRAG**：
  - 知识图谱构建与检索
  - 关系推理（找到"间接相关"的知识）
  - 适合结构化知识领域

### 8.4 LangGraph / Workflow

- State（状态对象设计）
- Node（节点函数设计）
- Edge（条件路由）
- Checkpoint（状态持久化）
- Interrupt（Human-in-the-Loop 暂停点）
- Subgraph（模块化子图）

### 8.5 MCP 与工具生态

- MCP 协议规范（Tool、Resource、Prompt 三类服务）
- 服务器实现（Python、Node.js SDK）
- 权限模型（工具级别权限控制）
- 安全隔离（沙箱、超时、资源限制、路径白名单）
- 扩展能力：browser automation（网页自动化）、code interpreter（代码执行）

### 8.6 主流框架全景

| 框架 | 定位 | 适用场景 |
|------|------|---------|
| LangChain | AI 应用开发基础库 | RAG、Chain、基础 Agent |
| LangGraph | 状态机 Workflow 引擎 | 复杂 Agent、多步骤任务 |
| AutoGen | 多 Agent 对话框架 | 多 Agent 协作、角色扮演 |
| CrewAI | 面向任务的多 Agent | 结构化任务分解 |
| OpenAI Agents SDK | OpenAI 官方 Agent 框架 | OpenAI 生态 Agent |
| VLLM | 高性能 LLM 推理引擎 | 本地/私有化部署、高吞吐 |
| MCP | 工具调用协议标准 | 工具集成、跨框架互通 |

### 8.7 AI 安全（Security）

- **Prompt Injection 防御**：System Prompt 与 User Input 隔离、意图检测、OWASP AI Security Top 10
- **Tool Injection 防御**：工具路径白名单/黑名单、Sandbox 沙箱执行
- **Agent 权限升级漏洞排查**：
  - Agent 能否读取 `.env` / `.git` / `~/.ssh`？
  - Agent 能否执行任意 shell 命令？
  - Agent 能否访问数据库连接字符串或 API Key？
- **Guardrails**：输入/输出过滤、高风险拦截、敏感操作审批闭环
- **数据泄露防御**：PII 检测、输出脱敏、密钥隔离
- **多租户安全**：IDOR 防护、project_id 强制隔离、JWT 校验

### 8.8 可观测性（Observability）

- **Tracing**：Agent 每步的 Span 记录，含 Tool 调用的入参/出参/耗时
- **Logging**：结构化日志（JSON，含 trace_id、session_id），错误分级
- **LLM Observability**：Prompt/Response 可回溯、幻觉率趋势、模型漂移检测
- **Metrics**：SLO 定义（P95 延迟、成功率、Token 用量）、成本告警

### 8.9 成本优化（Cost Optimization）

五类常见浪费及对策：

| 浪费类型 | 表现 | 对策 |
|---------|------|------|
| 重复调用未缓存 | 相同 System Prompt 反复发送 | 实现语义缓存 |
| 模型选择过重 | 分类/提取任务用了 GPT-4 | 小模型路由（分类→小模型，推理→大模型）|
| 规则可替代 | 正则/模板能解决却用 LLM | 先规则后 LLM 的混合策略 |
| Context 过长 | 整个 HTML/文档塞进 Prompt | 上下文裁剪 + 摘要压缩 |
| 重试重复计费 | 失败重试没有 Checkpoint | 断点续跑，避免从头重算 |

### 8.10 Evaluation 与 AI 测试工程

- **AI 测试策略（测试金字塔变形）**：
  - 底层：单元测试（Tool、Parser、Retriever 的确定性逻辑）
  - 中层：集成测试（Agent + Tool + Memory 链路）
  - 顶层：Eval 测试（LLM-as-Judge 评分，替代传统断言）
- **Eval 数据集构建**：Ground Truth 标注、覆盖边界用例、持续收集生产数据
- **回归测试**：Prompt 变更 → 自动触发 Eval → 对比 Before/After → 通过才部署
- **负载测试**：并发 Agent 压测、Token 吞吐量测试、容量规划

### 8.11 FCARS 框架（AI 治理）

| 维度 | 英文 | 含义 | 工程实现 |
|------|------|------|---------|
| 公平性 | Fairness | AI 输出不应有不当偏见 | 偏见评估数据集、公平性指标监控 |
| 合规性 | Compliance | 符合法律法规（GDPR 等） | 数据主权、审计日志、用户知情权 |
| 问责性 | Accountability | 决策可追溯、可解释 | 决策链路记录、Trace 可视化 |
| 可靠性 | Reliability | SLA 保障、故障率控制 | Chaos Engineering、SLO 定义 |
| 安全性 | Safety | 防止 AI 被滥用或造成伤害 | 内容过滤、Prompt Injection 防御 |

### 8.12 Fine-tuning 工程

- **何时 Fine-tuning，何时 RAG**：
  - RAG：知识频繁更新、知识量大、需要可溯源
  - Fine-tuning：风格/格式固定、推理速度要求高、保密知识
- **Fine-tuning 流程**：数据收集 → 清洗标注 → LoRA 训练 → 评估 → 部署
- **数据集质量**：脏数据比模型选择影响更大

### 8.13 本地模型部署（Ollama）

- 模型量化（Q4、Q8，VRAM 计算）
- 服务化部署（REST API）
- 性能对比（本地 vs 云端 Trade-off）

### 8.14 多模态 AI

- 图文理解（Vision + Text）
- 语音识别（ASR）+ 语音合成（TTS）
- 多模态 Agent（能看图、听音频、读文档）

### 8.15 AI Coding Agent

- 代码生成 + 测试 + 重构自动化
- 技术债务识别与修复
- AI 辅助 Code Review

---

## 9. Architecture Review Dimensions — 14维度架构审查

AI Native Engineer（L3+）必须能对 AI 系统进行完整的 14 维度架构审查：

| # | 维度 | 核心问题 | 关键检查点 |
|---|------|---------|-----------|
| 1 | **系统架构** | 整体分层是否合理？ | 模块边界清晰？依赖关系正确？可扩展性？ |
| 2 | **Agent 架构** | 循环和并发是否安全？ | 最大迭代次数？并发状态隔离？工具失败退出条件？ |
| 3 | **Workflow 架构** | 状态机设计是否健壮？ | 状态持久化？断点续跑？Human-in-the-Loop 节点？ |
| 4 | **Prompt 架构** | Prompt 是否被工程化管理？ | 版本管理？System/User 隔离？模板化？测试覆盖？ |
| 5 | **Tool Calling** | 工具调用是否安全可控？ | 路径白名单/黑名单？沙箱限制？调用失败降级？ |
| 6 | **MCP 兼容性** | 协议是否符合规范？ | MCP 适配能力？扩展点设计？安全隔离？ |
| 7 | **Memory 架构** | Memory 是否正确隔离？ | 多请求间隔离？层次化设计？一致性保证？ |
| 8 | **Evaluation 架构** | AI 质量是否持续量化？ | Eval 数据集？自动化触发？回归对比？ |
| 9 | **Observability** | 是否有完整可观测性？ | Tracing 覆盖？Log 结构化？LLM 可观测？Metric 告警？ |
| 10 | **Security** | 是否存在权限升级漏洞？ | Agent 能读 .env？能执行 shell？Injection 防护？密钥隔离？ |
| 11 | **Multi-tenant** | 数据是否彻底隔离？ | IDOR 防护？project_id 强制过滤？计费独立？ |
| 12 | **Scalability** | 能否支撑并发 Agent？ | 连接池管理？异步队列？无状态设计？ |
| 13 | **Cost Optimization** | Token 成本是否受控？ | 缓存策略？模型路由？上下文裁剪？重试计费？ |
| 14 | **CI/CD** | AI 应用是否持续交付？ | Prompt 变更自动触发 Eval？部署自动化？回滚策略？ |

---

## 10. Learning Path — 本书学习路径

```
━━━━━━━━━━━━━━━━ L0→L1 区（入门）━━━━━━━━━━━━━━━━

【第一站】AI 基础（CH01-CH05）
LLM 原理 → Token → Context Window → Hallucination → Prompt Engineering → AI 产品思维

━━━━━━━━━━━━━━━━ L1→L2 区（工程师）━━━━━━━━━━━━━━━━

【第二站】Agent 基础（CH06-CH10）
单 Agent → Tool Use → Memory → Human-in-the-Loop → Agent Loop 机制 → Agent Harness 入门
        ↓
【第三站】RAG 系统（CH11-CH15）
Embedding → 向量检索 → Chunking → Hybrid Search → RAG Evaluation → GraphRAG/LightRAG
        ↓
【第四站】复杂 Workflow（CH16-CH20）
LangGraph 状态机 → Checkpoint/Resume → 多 Agent → A2A 协议 → Harness 编排
        ↓
【第五站】MCP 与工具集成（CH21-CH25）
MCP 协议 → Tool 封装 → 外部系统接入 → 安全隔离 → Guardrails 设计

━━━━━━━━━━━━━━━━ L2 毕业检验点 ━━━━━━━━━━━━━━━━
✅ 能独立交付生产级 AI 应用：设计 + 开发 + Evaluation + 安全 + 可观测性

━━━━━━━━━━━━━━━━ L2→L3 区（架构师）━━━━━━━━━━━━━━━━

【第六站】Evaluation 与测试工程（CH26-CH29）
LLM-as-Judge → RAGAS → Eval 数据集构建 → 自动化评测 Pipeline → AI 测试金字塔 → 负载测试
        ↓
【第七站】生产部署与成本（CH30-CH33）
Fine-tuning 决策 → LoRA 实战 → 本地模型(Ollama/VLLM) → 多模态 → 负载测试与容量规划
        ↓
【第八站】安全、可观测性、成本优化（CH34-CH36）
Prompt Injection 防御 → Agent 权限审计 → Tracing/LLM Observability → 成本优化（5类浪费）→ Chaos Engineering

━━━━━━━━━━━━━━━━ L3→L4 区（技术领导者）━━━━━━━━━━━━━━━━

【第九站】架构审查与治理（CH37-CH40）
14维度架构审查实战 → FCARS 治理 → 数据飞轮设计 → AI 产品设计原则 → AI Coding Agent

━━━━━━━━━━━━━━━━ 毕业项目 ━━━━━━━━━━━━━━━━

L2 毕业项目：端到端企业级 AI 应用（RAG + Agent + Evaluation + 安全 + 可观测性）
L3 毕业项目：对一个真实 AI 系统完成 14 维度架构审查报告 + Chaos Engineering 演练报告
L4 毕业项目：为一个团队/产品线设计 AI 能力建设路线图（含规范、平台、组织推广方案）
```

**每一站都回答同一个问题：为什么这个能力是必须的？**

---

## 11. Graduation Criteria — 毕业标准

> 本书覆盖 L0→L4 完整路径。毕业标准按级别分层，读者选择自己的目标级别。
> **L2 是就业基准线，L3 是架构师门槛，L4 是技术负责人水准。**

---

### 11.1 L2 毕业标准（AI 应用工程师，可独立交付生产级 AI 应用）

**RAG 系统**
- [ ] 设计并实现完整 RAG 问答系统（含 Chunking、Embedding、Reranking、Evaluation）
- [ ] 实现 GraphRAG 或 LightRAG 知识图谱检索
- [ ] 用 RAGAS 跑完整 RAG 评测报告并能解读结果

**Agent 系统**
- [ ] 设计并实现有 Memory 和 Tool Use 的单 Agent（含 Agent Loop 防护）
- [ ] 实现 Human-in-the-Loop 审核节点
- [ ] 用 LangGraph 实现含循环、条件分支、并行子图的 Workflow
- [ ] 实现 Checkpoint/Resume 断点续跑机制

**Evaluation**
- [ ] 构建 Eval 数据集（含 Ground Truth 标注、边界用例）
- [ ] 设计 LLM-as-Judge 评测方案并实现自动化评测 Pipeline
- [ ] 建立 Prompt 变更的回归测试机制（变更前后 Diff）

**安全**
- [ ] 能独立排查 Agent 权限升级漏洞（.env、shell、API Key 等）
- [ ] 实现 Prompt Injection 防御（System/User 严格隔离）
- [ ] 设计并实现 Guardrails（输入过滤 + 输出过滤 + 高风险拦截）

**可观测性**
- [ ] 实现完整 Tracing（每步 Span，含 Tool 调用入参/出参/耗时/Token 用量）
- [ ] 实现结构化日志（含 trace_id 关联，错误分级）

**成本优化**
- [ ] 对 AI 系统做 Token 成本分析，识别至少 3 类浪费，给出"成本下降 50%"方案
- [ ] 实现语义缓存或模型路由策略

**Chaos Engineering**
- [ ] 设计并演练至少 5 个故障场景（LLM 超时、Agent 循环、429 限流、Token 耗尽、连接池耗尽）

**L2 面试题清单**
- [ ] 回答"RAG 为什么能减少幻觉？"（机制层，不是定义层）
- [ ] 回答"什么时候用 Fine-tuning，什么时候用 RAG？"（给判断框架）
- [ ] 回答"GraphRAG 比普通 RAG 好在哪？什么时候用？"
- [ ] 完成系统设计题：设计客服 Agent 系统（含 RAG + Evaluation + 安全 + 可观测性）
- [ ] 解释 Agent vs Chatbot 的本质区别
- [ ] 解释 A2A vs MCP 的区别和适用场景
- [ ] 解释 Demo 和生产之间的 3 个具体差距
- [ ] 给出把 Token 成本降低 50% 的具体方案（不是泛泛而谈）

---

### 11.2 L3 毕业标准（AI 系统架构师，能设计并独立审查复杂 AI 系统）

**架构设计**
- [ ] 独立设计一个多 Agent 协作系统（含角色分工、A2A 协议、Harness 编排）
- [ ] 设计完整的 Agent Harness 平台（任务编排、状态持久化、失败恢复、动态调度）
- [ ] 设计数据飞轮方案（数据收集→标注→评估→Prompt/模型迭代的完整闭环）
- [ ] 设计多租户 AI 平台（数据隔离、权限隔离、计费独立）

**14维度架构审查**
- [ ] 对一个真实 AI 系统完成 14 维度架构审查，输出书面报告（含发现问题 + 改进方案）
- [ ] 发现并修复至少 3 个 Agent 权限升级漏洞（.env / shell / DB 连接串等）
- [ ] 能在 Code Review 中识别：Prompt 设计缺陷、评估体系缺失、安全漏洞、成本浪费

**FCARS 治理**
- [ ] 设计 FCARS 合规检查表并完整应用于一个项目
- [ ] 能解释 AI 系统在公平性/合规性/问责性维度的具体工程实现方式

**可靠性工程**
- [ ] 完成完整 Chaos Engineering 演练并输出报告（故障场景 × 触发机制 × 验证结果）
- [ ] 定义系统 SLO（P95 延迟、成功率、Token 用量），并实现对应告警规则

**Fine-tuning 决策**
- [ ] 能给出一个业务场景下"RAG vs Fine-tuning"的完整决策过程（含数据量、成本、效果评估）
- [ ] 实现完整 Fine-tuning 流程：数据集构建 → LoRA 训练 → Evaluation → 部署

**L3 面试题清单**
- [ ] 完成架构设计题：设计一个企业级多 Agent 平台（含 Harness、安全、多租户、成本控制）
- [ ] 回答"你怎么做 AI 系统的架构审查？"（能说出 14 个维度及每个维度的关键检查点）
- [ ] 回答"你怎么发现并修复 Agent 权限升级漏洞？"（给出具体的排查清单）
- [ ] 回答"Chaos Engineering 在 AI 系统中怎么做？"（给出具体故障场景和验证方式）
- [ ] 回答"数据飞轮是什么？你在项目里怎么实现的？"
- [ ] 回答"如何把一个 AI 系统的 Token 成本降低 80%？"（给出 5 类优化手段）
- [ ] 回答"你怎么设计 AI 系统的 SLO？"（P95/成功率/Token 预算各自的阈值设计）
- [ ] 回答"FCARS 框架每个维度的工程实现方式是什么？"

---

### 11.3 L4 毕业标准（AI 平台架构师，能定义技术方向和工程文化）

**平台化能力**
- [ ] 设计并实现一套可供多团队复用的 AI 基础设施（知识库、Harness、Eval 平台）
- [ ] 制定团队 AI 工程规范（Prompt 管理规范、Eval 标准、安全基线）
- [ ] 将 AI 能力从单点应用推广到组织级落地（至少覆盖 3 个业务场景）

**技术判断与领导力**
- [ ] 能从商业目标反推 AI 技术选型（给出"为什么选这个框架/模型/架构"的完整论据）
- [ ] 能识别团队的 AI 工程能力短板并设计提升路径
- [ ] 主导过 0→1 AI 产品或 AI 平台建设

**L4 面试题清单**
- [ ] 回答"你怎么推动一个组织完成 AI 转型？"（给出 POC→MVP→V1→Platform→Organization 的具体打法）
- [ ] 回答"你怎么评估一个 AI 工程团队的成熟度？"（给出评估维度和改进路径）
- [ ] 回答"你制定过哪些 AI 工程规范？解决了什么问题？"
- [ ] 回答"当 AI 系统出现伦理/合规问题时，你怎么处理？"（FCARS 框架的实际应用）
- [ ] 完成战略设计题：为一家公司设计 18 个月的 AI 能力建设路线图

---

## 12. Out of Scope — 本书不覆盖的内容

为保持聚焦，以下内容本书不深入讲解（但会在适当位置提及并给出学习指引）：

- 模型预训练（Pre-training 的实现细节，需要 GPU 集群）
- 深度学习理论（Transformer 数学推导）
- GPU 集群管理与分布式训练
- AI 硬件（芯片、推理加速卡）
- 非 Python 语言的实现（Java、Go 等）
- 强化学习（RLHF 的数学原理）

---

## 13. References

- [LangGraph 官方文档](https://langchain-ai.github.io/langgraph/)
- [LangChain 官方文档](https://docs.langchain.com/)
- [Anthropic MCP 规范](https://modelcontextprotocol.io/)
- [RAGAS — RAG Evaluation Framework](https://docs.ragas.io/)
- [LightRAG](https://github.com/HKUDS/LightRAG)
- [Ollama](https://ollama.ai/)
- [VLLM](https://github.com/vllm-project/vllm)
- [AutoGen](https://github.com/microsoft/autogen)
- [CrewAI](https://github.com/crewAIInc/crewAI)
- [OpenAI Agents SDK](https://openai.github.io/openai-agents-python/)
- [OWASP AI Security Top 10](https://owasp.org/www-project-top-10-for-large-language-model-applications/)
- AI Native System（本地封装，见 `engine/llm/`）
- StudyAthena 40章课纲（见 `docs/references/ai-native-curriculum-analysis.html`）

---

## Changelog

| 版本 | 日期 | 变更 |
|------|------|------|
| v1.0 | 2026-06-19 | 初稿（基础能力模型） |
| v2.0 | 2026-06-19 | 全量重写：增加 Harness、A2A、GraphRAG、FCARS、Fine-tuning、Ollama、多模态、AI Coding Agent、14维度架构审查、数据飞轮、企业交付阶段、完整 L0-L4 能力模型 |
| v3.0 | 2026-06-19 | 补全遗漏：Guardrails、Agent 权限升级漏洞（10项）、可观测性独立展开（LLM Observability）、成本优化5类浪费识别、AI 测试工程（测试金字塔）、Chaos Engineering 9个故障场景、框架全景（AutoGen/CrewAI/VLLM/OpenAI Agents SDK）、"Demo vs 生产"思维模式、工程原则+2条、职责范围补全（端到端交付/沙箱/Guardrails）、毕业标准补全（安全/可观测性/成本/Chaos） |
| v3.1 | 2026-06-19 | 目标升级：书的覆盖范围从 L0→L2 扩展到 L0→L4；能力等级表新增 L2→L3、L3→L4 的本质区分；学习路径按级别分区（L0→L1/L1→L2/L2→L3/L3→L4）；毕业标准拆分为 L2/L3/L4 三个独立清单，各含动手标准和专项面试题清单 |
