# Knowledge Schema 知识模型设计

> 来源：ebook.html Q22~Q23

---

## 核心思想

**书不是知识，书只是知识的一种排列方式。**

知识应该独立存储，所有输出产品（书/课程/PPT/面试题）都是知识的不同视图（View）。

---

## Knowledge Node 类型

```
Concept      # 概念
Pattern      # 模式
Architecture # 架构
Algorithm    # 算法
Tool         # 工具
Protocol     # 协议
Framework    # 框架
Practice     # 最佳实践
Case Study   # 案例研究
Exercise     # 练习
Project      # 项目
```

---

## Knowledge Node Schema（YAML 格式）

```yaml
id: KN-000001
type: Concept
name: AI Native Engineer
version: "1.0"
last_updated: "2026-06-19"

aliases:
  - AI Engineer
  - LLM Engineer

summary: "一句话总结（用于快速回忆）"

definition: "严格定义（用于教材）"

why: "为什么存在（教学最重要的一栏）"

history: "历史演化（帮助建立工程思维）"

problem_it_solves: "它解决了什么问题"

mental_model: |
  # 心智模型（比定义更重要）
  # 示例：
  # LangGraph → 状态机
  # RAG → 开卷考试
  # Memory → 长期记忆

core_principles:
  - "原则1"
  - "原则2"

examples:
  - "正面例子1"
  - "正面例子2"

counter_examples:
  - "什么时候不要用 RAG"
  - "什么时候不要 Fine-tuning"

relationships:
  prerequisites:
    - KN-XXXXXX  # 前置知识
  used_by:
    - KN-XXXXXX  # 被哪些知识使用
  extends:
    - KN-XXXXXX  # 扩展自哪个概念
  related_concepts:
    - KN-XXXXXX  # 相关概念

common_misconceptions:
  - "误区1：很多人认为 Agent = Chatbot（错误）"

best_practices:
  - "最佳实践1"

anti_patterns:
  - "反模式1：Prompt 写 2000 行"

real_world_cases:
  - description: "案例描述"
    company: "公司/场景"

interview_points:
  - "面试高频问题1"
  - "面试高频问题2"

exam_points:
  - "笔试考点1"
  - "笔试考点2"

references:
  - "参考资料链接或书籍"
```

---

## AI Native Engineer 知识域（第一批 ~500-1000 个节点）

### Prompt Engineering 域
- Prompt
- System Prompt
- Few-shot
- Zero-shot
- Chain of Thought (CoT)
- ReAct
- Reflection
- Planning

### Agent 域
- Agent
- Tool Calling / Function Calling
- Planning
- Memory
- Workflow

### RAG 域
- RAG
- Embedding
- Vector DB
- Chunking
- Retrieval
- Reranking

### Workflow 域
- LangChain
- LangGraph
- StateGraph
- Node
- Edge
- Conditional Edge
- Checkpoint
- Interrupt

### MCP 域
- MCP
- Tool
- Resource
- Prompt Template
- Server / Client

### Memory 域
- Short-term Memory
- Long-term Memory
- Working Memory
- Episodic Memory
- Semantic Memory

### Evaluation 域
- LLM Evaluation
- RAG Evaluation
- Agent Evaluation
- RAGAS
- LLM-as-Judge

### Deployment 域
- Containerization
- API Gateway
- Monitoring
- Cost Optimization

---

## AI Native Engineer 能力模型（Competency Model）

```
一级能力
├── AI Thinking（AI 思维）
├── Software Engineering（软件工程）
├── Prompt Engineering
├── Agent Engineering
├── Workflow Engineering
├── RAG Engineering
├── Memory Engineering
├── Evaluation Engineering
├── Deployment
├── Cost Optimization
├── Security
└── Leadership
```

### 能力等级

| 等级 | 描述 |
|------|------|
| L0 | 初学者 |
| L1 | 能完成简单项目 |
| L2 | 独立开发企业级 AI 应用 |
| L3 | 设计复杂多 Agent 系统 |
| L4 | AI 架构师 |

### 毕业标准（本书学完后应能做到）

- 独立设计一个 AI Agent
- 独立完成一个企业级 RAG 系统
- 能解释关键技术为什么存在
- 能通过 AI Native Engineer 面试
- 能阅读并学习新的 AI 框架
- 能独立完成企业级 AI 系统：需求分析 → 设计 → 开发 → 测试 → 部署 → 维护

---

## AI Native Engineer vs 传统软件工程师

| 维度 | 传统软件工程师 | AI Native Engineer |
|------|--------------|-------------------|
| 主要工作 | 写代码 | 设计 AI 系统 |
| 工具调用 | 调用 API | 编排多 Agent |
| 调试 | 调试程序 | 调优 Prompt/Workflow/Evaluation |
| 关注点 | 代码逻辑 | 系统设计 + AI 行为 |
| 核心能力 | 编程能力 | 系统思维 + AI 思维 |

---

## 知识图谱构建步骤

1. 定义 Knowledge Node 类型
2. 定义每种类型的字段（本文档）
3. 定义 Node 之间的关系
4. 制定命名规范（KN-XXXXXX）
5. 制定文件组织规范
6. 批量生成知识节点
7. 基于知识图谱生成书/课程/面试题等
