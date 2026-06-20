# SPEC-001: Knowledge Node Schema 规范

**Status**: Accepted  
**Date**: 2026-06-19  
**Type**: Specification  
**ADR**: [ADR-001](../architecture/ADR-001_System-Architecture.md)（决策二：One Source of Truth）  
**Applies to**: `knowledge/` 目录下所有知识节点文件

---

## 1. 设计原则

### 核心思想

> 书不是知识，书只是知识的一种排列方式。

`knowledge/` 目录是整个系统的**唯一事实源（Single Source of Truth）**。  
所有输出产品（Book / Course / Interview / Quiz / PPT）都是知识的不同视图，只引用不复制。

### Schema 设计目标

| 目标 | 说明 |
|------|------|
| **教学驱动** | 每个字段都服务于"帮助学生学会"，而非"展示知识全面" |
| **机器可读** | YAML 格式，Agent 可直接解析并注入 Prompt |
| **面试就绪** | 包含面试高频问题和笔试考点，直接支撑 Interview Generator |
| **关系完整** | 节点之间的前置/依赖/扩展关系，支撑课程序列自动规划 |
| **可追溯** | 每个节点有唯一 ID 和版本号，修改可追踪 |

---

## 2. 节点类型（Node Types）

| 类型 | 标识 | 用途 |
|------|------|------|
| `Concept` | C | 核心概念（如 RAG、Agent、Embedding） |
| `Pattern` | P | 设计模式（如 ReAct、Supervisor-Worker） |
| `Architecture` | A | 架构方案（如 6层架构、多Agent编排） |
| `Framework` | F | 框架/库（如 LangGraph、LangChain、AutoGen） |
| `Tool` | T | 具体工具（如 Ollama、VLLM、FAISS） |
| `Protocol` | R | 协议/规范（如 MCP、A2A、OpenAI Function Calling） |
| `Practice` | B | 最佳实践（如 Prompt 版本管理、Eval First） |
| `Anti-Pattern` | X | 反模式（如 God Agent、Prompt 硬编码） |
| `Case Study` | S | 真实案例（如 客服Agent系统设计） |
| `Exercise` | E | 练习项目（如 实现一个 RAG 问答系统） |

---

## 3. 完整 Schema（YAML 格式）

```yaml
# ============================================================
# Knowledge Node — 完整字段定义
# ============================================================

# --- 元数据 ---
id: "KN-C-000001"                # 唯一ID，格式见第4节
type: Concept                    # 节点类型，见第2节
name: "RAG"                      # 正式名称
version: "1.0"                   # 节点版本号
last_updated: "2026-06-19"       # 最后更新日期
status: active                   # active | deprecated | draft
tags:
  - retrieval
  - knowledge
  - hallucination

# --- 名称别名 ---
aliases:
  - "Retrieval-Augmented Generation"
  - "检索增强生成"

# --- 核心内容（教学三件套：一句话 / 定义 / 为什么）---
summary: "让 LLM 在回答时先去外部知识库检索相关内容，再基于检索结果生成回答，从而减少幻觉。"

definition: |
  RAG（Retrieval-Augmented Generation，检索增强生成）是一种将信息检索与语言生成结合的技术架构。
  当用户提问时，系统先从外部知识库中检索最相关的文档片段，
  再将这些片段作为上下文注入 Prompt，由 LLM 基于真实知识生成答案。

why: |
  LLM 的训练数据有截止日期，无法获取最新信息；
  LLM 会"自信地编造"不存在的内容（幻觉）；
  继续训练模型成本极高（百万美元级）。
  RAG 用"检索 + 注入"解决了上述三个问题，且成本远低于重新训练。

# --- 认知建构 ---
mental_model: |
  RAG = 开卷考试
  - 闭卷考试（纯 LLM）：只能用记在脑子里的知识，容易记错
  - 开卷考试（RAG）：可以翻参考资料，答案更准确，但需要知道去哪翻

history: |
  2020年 Facebook AI Research 提出 RAG 论文。
  2023年 LLM 爆发后，RAG 成为企业 AI 落地的标配架构。
  2024年 GraphRAG / LightRAG 出现，将知识图谱引入检索，解决关系推理问题。

problem_it_solves: |
  1. LLM 幻觉：基于检索到的真实文档生成答案，而非凭空捏造
  2. 知识时效性：外部知识库可实时更新，不需要重训模型
  3. 私有知识：公司内部文档、代码、规范可以作为知识库接入
  4. 成本：比 Fine-tuning 便宜 100x 以上

# --- 核心原则 ---
core_principles:
  - "检索质量决定生成质量：Retrieval 是 RAG 的瓶颈，不是 LLM"
  - "Chunk 大小影响检索精度：太大上下文噪音多，太小语义不完整"
  - "相关性 ≠ 有用性：Reranking 负责过滤'相关但没用'的片段"

# --- 工作原理（技术流程）---
how_it_works: |
  1. 离线阶段（知识库构建）：
     文档 → Chunking（分块）→ Embedding（向量化）→ 存入 Vector DB
  2. 在线阶段（查询）：
     用户提问 → Embedding → Vector DB 检索 → Reranking → 注入 Prompt → LLM 生成答案

# --- 示例 ---
examples:
  - scenario: "企业内部知识问答"
    description: "将公司文档、规章制度向量化，员工提问时自动检索相关规定并生成答案"
  - scenario: "代码库问答"
    description: "将代码库向量化，开发者提问时检索相关代码片段，生成带上下文的回答"

counter_examples:
  - "当知识库为空时，RAG 退化为普通 LLM，不解决幻觉问题"
  - "当问题需要跨文档推理时，普通 RAG 不如 GraphRAG"
  - "当知识是程序性的（格式/风格），Fine-tuning 比 RAG 更合适"

# --- 关系图 ---
relationships:
  prerequisites:
    - id: "KN-C-000010"   # Embedding
      note: "必须理解 Embedding 才能理解向量检索"
    - id: "KN-T-000001"   # Vector DB
      note: "需要知道向量数据库是什么"
  used_by:
    - id: "KN-P-000005"   # GraphRAG
      note: "GraphRAG 是 RAG 的图结构升级版"
    - id: "KN-C-000020"   # Agent
      note: "Agent 常将 RAG 作为一个 Tool"
  extends:
    - id: "KN-C-000008"   # Information Retrieval
      note: "RAG 是传统信息检索在 LLM 时代的进化"
  related_concepts:
    - id: "KN-C-000012"   # Chunking
    - id: "KN-C-000013"   # Reranking
    - id: "KN-F-000002"   # RAGAS

# --- 常见误区 ---
common_misconceptions:
  - misconception: "RAG 就是把文档塞进 Prompt"
    correction: "把整个文档塞进 Prompt 是 Stuffing，不是 RAG。RAG 的核心是先检索再注入，只注入最相关的片段。"
  - misconception: "RAG 能解决所有幻觉问题"
    correction: "RAG 只能减少知识性幻觉。如果 LLM 在推理过程中出错，RAG 无法解决。"
  - misconception: "向量相似度高 = 答案有用"
    correction: "语义相似 ≠ 有用。需要 Reranking 进一步过滤。"

# --- 最佳实践 ---
best_practices:
  - "Chunk 大小建议 256-512 tokens，根据文档类型调整"
  - "使用 Hybrid Search（向量 + BM25）提升召回率"
  - "必须用 RAGAS 评测 RAG 系统，不能靠感觉判断质量"
  - "为每个 Chunk 保留 metadata（来源文档、页码），方便溯源"

# --- 反模式 ---
anti_patterns:
  - pattern: "将整个文档作为一个 Chunk"
    consequence: "Context Window 溢出，或关键信息被噪音淹没"
  - pattern: "不做 Reranking，直接用检索 Top-K"
    consequence: "低质量结果进入 Prompt，污染 LLM 输出"
  - pattern: "RAG 系统上线不做 Evaluation"
    consequence: "无法发现检索质量下降，问题积累到用户投诉才知道"

# --- 真实案例 ---
real_world_cases:
  - description: "客服 Agent 接入产品文档知识库，减少客服人工介入 60%"
    company: "典型企业 SaaS 场景"
  - description: "代码审查 Agent 接入内部代码规范知识库，自动标记违规"
    company: "大型软件团队"

# --- 面试 & 考试 ---
interview_points:
  - "RAG 为什么能减少幻觉？（考核：能否解释机制，而不是背定义）"
  - "RAG 和 Fine-tuning 分别适用什么场景？"
  - "Chunk 大小如何选择？有什么 Trade-off？"
  - "如何评估一个 RAG 系统的质量？（RAGAS 指标）"
  - "什么是 HyDE？解决了什么问题？"
  - "Hybrid Search 相比纯向量检索有什么优势？"

exam_points:
  - "RAG 的标准流程：离线建库（Chunk→Embed→存储）+ 在线检索（Query→Embed→检索→Rerank→生成）"
  - "RAGAS 三个核心指标：Context Precision、Faithfulness、Answer Relevancy"
  - "GraphRAG 适合：需要跨文档关系推理的场景（如'A和B有什么关系？'）"

# --- 速查 ---
one_liner: "先检索后生成，用真实知识压制幻觉。"
difficulty: intermediate   # beginner | intermediate | advanced | expert

# --- 参考资料 ---
references:
  - "RAG 原论文: Lewis et al., 2020 (Facebook AI Research)"
  - "LangChain RAG 文档: https://docs.langchain.com/docs/use_cases/question_answering/"
  - "RAGAS: https://docs.ragas.io/"
  - "LightRAG: https://github.com/HKUDS/LightRAG"
```

---

## 4. 节点 ID 命名规范

### 格式

```
KN-{类型代码}-{6位序号}

示例：
KN-C-000001   # Concept 第1个
KN-P-000001   # Pattern 第1个
KN-F-000001   # Framework 第1个
KN-T-000001   # Tool 第1个
```

### 类型代码映射

| 类型 | 代码 | 序号范围 |
|------|------|---------|
| Concept | C | 000001-009999 |
| Pattern | P | 000001-009999 |
| Architecture | A | 000001-009999 |
| Framework | F | 000001-009999 |
| Tool | T | 000001-009999 |
| Protocol | R | 000001-009999 |
| Practice | B | 000001-009999 |
| Anti-Pattern | X | 000001-009999 |
| Case Study | S | 000001-009999 |
| Exercise | E | 000001-009999 |

---

## 5. 文件组织规范

### 目录结构

```
knowledge/
├── concepts/              # Concept 节点
│   ├── ai-basics/         # LLM、Token、Context Window...
│   ├── prompt/            # Prompt Engineering 域
│   ├── agent/             # Agent 域
│   ├── rag/               # RAG 域
│   ├── workflow/          # Workflow 域
│   ├── mcp/               # MCP / Tool Use 域
│   ├── memory/            # Memory 域
│   ├── evaluation/        # Evaluation 域
│   ├── security/          # Security & Guardrails 域
│   ├── observability/     # Observability 域
│   ├── cost/              # Cost Optimization 域
│   ├── deployment/        # 部署与运维域
│   └── governance/        # AI 治理 / FCARS 域
├── patterns/              # Pattern 节点
├── architectures/         # Architecture 节点
├── frameworks/            # Framework 节点（LangGraph、AutoGen...）
├── tools/                 # Tool 节点（Ollama、VLLM、FAISS...）
├── protocols/             # Protocol 节点（MCP、A2A...）
├── practices/             # Best Practice 节点
├── anti-patterns/         # Anti-Pattern 节点
├── case-studies/          # Case Study 节点
└── exercises/             # Exercise 节点
```

### 文件命名规范

```
{kebab-case-名称}.yaml

示例：
knowledge/concepts/rag/rag.yaml
knowledge/concepts/agent/agent-loop.yaml
knowledge/patterns/react-pattern.yaml
knowledge/frameworks/langgraph.yaml
knowledge/tools/ollama.yaml
```

---

## 6. 知识域全景（第一批节点，对齐 RFC-001 v3.0）

### 6.1 AI 基础域（ai-basics）

| 节点名称 | 类型 | 优先级 |
|---------|------|--------|
| LLM（Large Language Model） | Concept | P0 |
| Token | Concept | P0 |
| Context Window | Concept | P0 |
| Temperature | Concept | P0 |
| Attention Mechanism | Concept | P1 |
| Tokenization | Concept | P1 |
| Hallucination（幻觉） | Concept | P0 |
| Model Quantization（量化） | Concept | P1 |

### 6.2 Prompt Engineering 域（prompt）

| 节点名称 | 类型 | 优先级 |
|---------|------|--------|
| Prompt | Concept | P0 |
| System Prompt | Concept | P0 |
| Zero-shot Prompting | Pattern | P0 |
| Few-shot Prompting | Pattern | P0 |
| Chain-of-Thought (CoT) | Pattern | P0 |
| ReAct | Pattern | P0 |
| Self-Consistency | Pattern | P1 |
| Role Prompting | Pattern | P0 |
| Prompt Template | Practice | P0 |
| Prompt Version Control | Practice | P0 |
| Prompt Injection | Anti-Pattern | P0 |
| System/User Prompt Isolation | Practice | P0 |

### 6.3 Agent 域（agent）

| 节点名称 | 类型 | 优先级 |
|---------|------|--------|
| Agent | Concept | P0 |
| Agent Loop | Concept | P0 |
| Planning | Concept | P0 |
| Tool Use / Function Calling | Concept | P0 |
| Observation | Concept | P0 |
| ReAct Pattern | Pattern | P0 |
| Supervisor-Worker Pattern | Pattern | P0 |
| Pipeline Pattern | Pattern | P1 |
| Multi-Agent Debate | Pattern | P1 |
| A2A Protocol | Protocol | P0 |
| Human-in-the-Loop | Concept | P0 |
| Agent Harness | Architecture | P0 |
| Checkpoint / Resume | Concept | P0 |
| Max Iteration Guard | Practice | P0 |
| God Agent（反模式） | Anti-Pattern | P0 |
| Agent Privilege Escalation | Anti-Pattern | P0 |

### 6.4 RAG 域（rag）

| 节点名称 | 类型 | 优先级 |
|---------|------|--------|
| RAG | Concept | P0 |
| Embedding | Concept | P0 |
| Vector Database | Tool | P0 |
| Chunking | Concept | P0 |
| Hybrid Search | Pattern | P0 |
| Reranking | Concept | P0 |
| HyDE | Pattern | P1 |
| Self-Query | Pattern | P1 |
| GraphRAG | Architecture | P0 |
| LightRAG | Framework | P0 |
| RAGAS | Framework | P0 |
| Context Precision | Concept | P0 |
| Faithfulness | Concept | P0 |
| Answer Relevancy | Concept | P0 |

### 6.5 Workflow 域（workflow）

| 节点名称 | 类型 | 优先级 |
|---------|------|--------|
| Workflow | Concept | P0 |
| State Machine | Concept | P0 |
| State（LangGraph） | Concept | P0 |
| Node（LangGraph） | Concept | P0 |
| Edge / Conditional Edge | Concept | P0 |
| Checkpoint（LangGraph） | Concept | P0 |
| Interrupt | Concept | P0 |
| Subgraph | Concept | P1 |
| Parallel Subgraph | Pattern | P1 |

### 6.6 MCP / Tool Use 域（mcp）

| 节点名称 | 类型 | 优先级 |
|---------|------|--------|
| MCP（Model Context Protocol） | Protocol | P0 |
| Tool | Concept | P0 |
| Resource | Concept | P0 |
| MCP Server / Client | Architecture | P0 |
| Tool Schema Design | Practice | P0 |
| Tool Path Sandbox | Practice | P0 |
| Tool Injection | Anti-Pattern | P0 |
| Browser Automation | Tool | P1 |
| Code Interpreter | Tool | P1 |

### 6.7 Memory 域（memory）

| 节点名称 | 类型 | 优先级 |
|---------|------|--------|
| Short-term Memory | Concept | P0 |
| Long-term Memory | Concept | P0 |
| Working Memory | Concept | P1 |
| Episodic Memory | Concept | P1 |
| Semantic Memory | Concept | P1 |
| Procedural Memory | Concept | P1 |
| Context Compression | Practice | P0 |
| Memory Isolation | Practice | P0 |

### 6.8 Evaluation 域（evaluation）

| 节点名称 | 类型 | 优先级 |
|---------|------|--------|
| LLM Evaluation | Concept | P0 |
| LLM-as-Judge | Pattern | P0 |
| RAGAS | Framework | P0 |
| Eval Dataset | Concept | P0 |
| Ground Truth | Concept | P0 |
| Regression Testing（AI） | Practice | P0 |
| Hallucination Rate | Concept | P0 |
| Before/After Diff | Practice | P0 |
| Load Testing（AI） | Practice | P1 |
| AI Testing Pyramid | Architecture | P0 |

### 6.9 安全与治理域（security / governance）

| 节点名称 | 类型 | 优先级 |
|---------|------|--------|
| Prompt Injection | Anti-Pattern | P0 |
| Tool Injection | Anti-Pattern | P0 |
| Guardrails | Architecture | P0 |
| Agent Privilege Escalation | Anti-Pattern | P0 |
| IDOR（越权访问） | Anti-Pattern | P0 |
| PII Detection | Practice | P0 |
| Sandbox | Architecture | P0 |
| JWT / Auth | Practice | P0 |
| Secret Management | Practice | P0 |
| FCARS Framework | Architecture | P0 |
| Fairness（公平性） | Concept | P1 |
| Compliance（合规性） | Concept | P1 |
| Accountability（问责性） | Concept | P1 |
| Reliability（可靠性） | Concept | P0 |
| Safety（安全性） | Concept | P0 |
| OWASP AI Security Top 10 | Practice | P0 |

### 6.10 可观测性域（observability）

| 节点名称 | 类型 | 优先级 |
|---------|------|--------|
| Tracing | Concept | P0 |
| Span | Concept | P0 |
| Structured Logging | Practice | P0 |
| LLM Observability | Concept | P0 |
| SLO / SLA | Concept | P0 |
| Model Drift Detection | Concept | P1 |
| Token Usage Monitoring | Practice | P0 |
| Cost Alerting | Practice | P0 |

### 6.11 成本优化域（cost）

| 节点名称 | 类型 | 优先级 |
|---------|------|--------|
| Token Budget | Practice | P0 |
| Semantic Cache | Pattern | P0 |
| Model Routing | Pattern | P0 |
| Context Pruning | Practice | P0 |
| Checkpoint（防重复计费） | Practice | P0 |

### 6.12 部署与运维域（deployment）

| 节点名称 | 类型 | 优先级 |
|---------|------|--------|
| Containerization（Docker） | Tool | P0 |
| Kubernetes | Tool | P1 |
| Multi-tenancy | Architecture | P0 |
| Rate Limiting | Practice | P0 |
| Graceful Degradation | Practice | P0 |
| Chaos Engineering | Practice | P0 |
| Fine-tuning | Concept | P0 |
| LoRA | Concept | P1 |
| Ollama | Tool | P0 |
| VLLM | Tool | P1 |

### 6.13 框架域（frameworks）

| 节点名称 | 类型 | 优先级 |
|---------|------|--------|
| LangChain | Framework | P0 |
| LangGraph | Framework | P0 |
| AutoGen | Framework | P1 |
| CrewAI | Framework | P1 |
| OpenAI Agents SDK | Framework | P1 |

---

## 7. 节点关系规范

### 7.1 关系类型定义

| 关系类型 | 含义 | 示例 |
|---------|------|------|
| `prerequisites` | 学这个节点，必须先学哪些 | Agent 的前置：Prompt、Tool Use |
| `used_by` | 哪些其他节点依赖本节点 | Embedding 被 RAG 使用 |
| `extends` | 本节点是哪个节点的扩展/进化 | GraphRAG extends RAG |
| `related_concepts` | 相关但非依赖的概念 | Checkpoint 和 Resume 相关 |
| `conflicts_with` | 互斥的选择（用了A就不用B） | Fine-tuning conflicts_with RAG（在某些场景） |

### 7.2 关系填写规范

- `prerequisites` 必须填写：确保学习路径可以自动推导
- `used_by` 由系统自动反向填充，手动填写时注意保持一致
- 每个关系必须附 `note`，说明为什么有这个关系
- 关系 ID 必须指向已存在的节点，不允许"悬空引用"

---

## 8. 字段说明与填写规范

### 必填字段（Missing → 节点不合法）

| 字段 | 说明 |
|------|------|
| `id` | 唯一标识，不允许重复 |
| `type` | 节点类型，见第2节 |
| `name` | 正式名称（英文，或中英双语） |
| `version` | 从 "1.0" 开始 |
| `summary` | 一句话总结，≤ 50 字，用于快速回忆 |
| `definition` | 严格定义，≥ 50 字 |
| `why` | 为什么存在这个概念，≥ 30 字 |
| `interview_points` | 至少 3 条面试高频问题 |
| `exam_points` | 至少 3 条笔试考点 |
| `one_liner` | 一句话记忆口诀 |

### 推荐填写字段

| 字段 | 说明 |
|------|------|
| `mental_model` | 心智模型（类比）—— 比定义更重要 |
| `common_misconceptions` | 至少 1 条常见误区 |
| `anti_patterns` | 至少 1 条反模式 |
| `best_practices` | 至少 2 条最佳实践 |
| `relationships` | 前置/被使用/扩展关系 |

### 选填字段

| 字段 | 说明 |
|------|------|
| `history` | 历史演化 |
| `real_world_cases` | 真实案例 |
| `how_it_works` | 工作原理（技术流程） |
| `references` | 参考资料 |

---

## 9. 校验规则（Quality Gate）

生成或修改知识节点后，必须通过以下校验：

```
必填字段完整性检查
  ✓ id 是否唯一？
  ✓ summary 是否 ≤ 50 字？
  ✓ interview_points 是否 ≥ 3 条？
  ✓ exam_points 是否 ≥ 3 条？

内容质量检查
  ✓ why 字段是否回答了"为什么需要它"（而不是"它是什么"）？
  ✓ mental_model 是否有清晰的生活类比？
  ✓ common_misconceptions 是否指出了"最容易错的理解"？

关系完整性检查
  ✓ prerequisites 中的 ID 是否都存在？
  ✓ 有 prerequisites 的节点是否可以推导出完整学习路径？
```

---

## 10. 使用方式（Agent 如何消费知识节点）

### 10.1 Writer Agent 注入知识

```python
import yaml

def load_knowledge_node(node_id: str) -> dict:
    """从 knowledge/ 目录加载知识节点"""
    path = f"knowledge/{resolve_path(node_id)}.yaml"
    with open(path) as f:
        return yaml.safe_load(f)

def build_writer_prompt(node_id: str, chapter_num: int) -> list:
    node = load_knowledge_node(node_id)
    system = "你是一位顶级 AI 教材作者..."
    user = f"""
请根据以下知识节点，写教材第{chapter_num}章。

【知识节点】
- 名称：{node['name']}
- 定义：{node['definition']}
- 为什么：{node['why']}
- 心智模型：{node['mental_model']}
- 常见误区：{node['common_misconceptions']}
- 反模式：{node['anti_patterns']}
- 面试题：{node['interview_points']}

【输出要求】
按 book-chapter-spec.md 的 15 部分结构输出。
"""
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user}
    ]
```

### 10.2 Interview Generator 消费知识

```python
def build_interview_prompt(node_ids: list[str]) -> list:
    nodes = [load_knowledge_node(nid) for nid in node_ids]
    points = []
    for node in nodes:
        points.extend(node['interview_points'])
    # 基于 interview_points 生成完整面试题...
```

### 10.3 Quiz Generator 消费知识

```python
def build_quiz_prompt(node_id: str) -> list:
    node = load_knowledge_node(node_id)
    # 基于 exam_points 生成选择题/判断题...
```

---

## 11. 第一批节点生成顺序（P0 优先）

按学习路径依赖顺序生成，前置节点必须先生成：

```
第一批（AI 基础，无前置）
  LLM → Token → Context Window → Temperature → Hallucination

第二批（Prompt，前置：LLM）
  Prompt → System Prompt → Zero-shot → Few-shot → CoT → ReAct

第三批（Agent，前置：Prompt）
  Agent → Agent Loop → Tool Use → Planning → Human-in-the-Loop

第四批（RAG，前置：LLM + Embedding）
  Embedding → Vector DB → Chunking → RAG → Reranking → Hybrid Search

第五批（Workflow，前置：Agent）
  State Machine → LangGraph State/Node/Edge → Checkpoint → Interrupt

第六批（Evaluation，前置：Agent + RAG）
  LLM-as-Judge → RAGAS → Eval Dataset → Regression Testing

第七批（Security，前置：Agent + Tool Use）
  Prompt Injection → Tool Injection → Guardrails → Agent Privilege Escalation

第八批（Observability，前置：Agent + Workflow）
  Tracing → Span → LLM Observability → Structured Logging

第九批（高级，前置：以上全部）
  GraphRAG → A2A Protocol → FCARS → Chaos Engineering → Fine-tuning
```

---

## 相关文档

- [ADR-001: 系统架构决策](../architecture/ADR-001_System-Architecture.md)
- [RFC-001: AI Native Engineer 定义](../foundation/RFC-001_AI-Native-Engineer-Definition.md)
- [SPEC-002: Book Chapter Spec](SPEC-002_Book-Chapter.md)（待写）
- [knowledge-schema.md](../knowledge-schema.md)（旧版概览，以本文档为准）

---

## Changelog

| 版本 | 日期 | 变更 |
|------|------|------|
| v1.0 | 2026-06-19 | 初稿：完整 Schema 定义、命名规范、文件组织、全13个知识域、关系规范、校验规则、Agent 消费示例、P0 节点生成顺序 |
