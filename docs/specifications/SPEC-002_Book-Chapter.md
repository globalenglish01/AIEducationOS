# SPEC-002: Book Chapter Generation 规范

**Status**: Accepted  
**Date**: 2026-06-19  
**Type**: Specification  
**ADR**: [ADR-001](../architecture/ADR-001_System-Architecture.md)（决策三：6层分离架构；决策五：多Agent单一职责）  
**Depends on**: [SPEC-001: Knowledge Schema](SPEC-001_Knowledge-Schema.md)  
**Applies to**: `book/` 目录下所有章节生成流程

---

## 1. 最高原则

这不是一本技术参考手册（Reference），也不是 API 文档。

这是一本真正能帮助读者做到：

```
理解 → 学会 → 记住 → 独立完成项目 → 通过面试 → 成为 AI Native Engineer（L2→L3→L4）
```

**本书覆盖 L0→L4 完整路径。** 每章标注目标级别（`[L0-L1]` / `[L1-L2]` / `[L2-L3]` / `[L3-L4]`），读者按自身阶段深入，不需要从头读到尾。

**整本书以"学习体验（Learning Experience）"为中心，而不是"章节内容（Chapter Content）"。**

每一节写完后，读者必须能回答三个问题：

| 问题 | 含义 |
|------|------|
| **What** | 它是什么 |
| **Why** | 为什么需要它 |
| **When** | 什么时候应该用它，什么时候不该用 |

无法回答任意一个 → 该节教学失败 → 必须重写。

---

## 2. 目标读者与章节级别标注

### 2.1 读者画像

| 属性 | 描述 |
|------|------|
| 编程基础 | 会一点 Python（能看懂循环、函数、类） |
| AI 背景 | 从零基础到有 AI 项目经验均可 |
| 职业目标 | 通过面试并胜任 L2/L3/L4 岗位 |
| 学习动机 | 理解 + 记住 + 能用，而不是"看过了" |

**L1-L2 章节**：禁止假设读者知道任何 AI 专业术语，每个术语第一次出现必须解释。  
**L2-L3 章节**：可假设读者已掌握前几站内容，重点放在系统设计和架构判断。  
**L3-L4 章节**：可假设读者有生产经验，重点放在权衡取舍、组织推广、领导力。

### 2.2 章节级别标注规范

每章在标题后必须标注目标级别：

```markdown
# 第6章：为什么 ChatGPT 不能自动完成工作？——Agent 的诞生  `[L1-L2]`
# 第29章：如何对 AI 系统做 14 维度架构审查？  `[L3]`
# 第40章：AI 工程文化：如何让整个团队具备 AI Native 能力？  `[L4]`
```

级别含义：
| 标注 | 适合读者 | 章节侧重 |
|------|---------|---------|
| `[L0-L1]` | 完全零基础 | 概念理解、心智模型、第一个 Demo |
| `[L1-L2]` | 会写代码，没做过 AI | 工程实现、生产注意事项、面试准备 |
| `[L2-L3]` | 有 AI 项目经验 | 系统设计、架构审查、质量保障 |
| `[L3-L4]` | 有生产架构经验 | 平台化、组织推广、技术领导力 |

---

## 3. 写作五大原则

### P1：问题优先（Problem First）

任何概念第一次出现，顺序必须是：

```
❓ 为什么需要它？没有它会怎样？
       ↓
🌍 现实生活中的例子（类比）
       ↓
💡 技术思想（从类比映射到 AI 系统）
       ↓
📖 正式定义
       ↓
💻 代码实现
```

**顺序不能反。先 Why，再 What，最后 How。**

### P2：费曼学习法

任何内容必须做到：一个高中毕业生可以读懂。  
如果一段内容需要反复读三遍才能理解，说明写失败了，必须重写。

### P3：术语必须解释

所有专业术语第一次出现必须解释，包括但不限于：

> State、Node、Agent、Workflow、Embedding、Tool Calling、Memory、  
> Context Window、Checkpoint、Interrupt、Token、Hallucination、  
> Chunk、Reranking、LLM-as-Judge、Guardrails、Tracing、Span……

### P4：短段落

一段最多介绍一个知识点。段落尽量短（≤ 5 行）。  
避免连续大段理论，用代码、表格、图示打断文字。

### P5：不堆术语

不要为了显得专业而堆砌术语。真正的高手能把复杂内容讲简单。

---

## 4. 认知冲突原则（Cognitive Conflict First）

**不要直接介绍知识，先制造认知冲突，让新知识成为读者主动需要的解决方案。**

每个重要知识点的引入顺序：

```
1. 提出真实问题（读者能感同身受的痛点）
2. 让读者尝试思考（"你会怎么解决？"）
3. 说明传统方案为什么失败
4. 制造认知冲突（"那怎么办？"）
5. 提出新的解决方案
6. 解释为什么这种方案有效
7. 总结什么时候应该使用
```

**示例对比：**

| ❌ 错误写法 | ✅ 正确写法 |
|-----------|-----------|
| "RAG 是一种检索增强生成技术..." | "为什么 ChatGPT 会一本正经地胡说八道？→ 引出幻觉 → 为什么不能重训模型？→ 引出 RAG" |
| "Agent 是一种能自主完成任务的 AI..." | "为什么 ChatGPT 回答问题很好，却不会自动查资料、写代码、跑测试？→ 引出 Agent" |
| "LangGraph 是一个状态管理框架..." | "当 Agent 需要记住之前做了什么，出错了怎么恢复？→ 引出状态机 → 引出 LangGraph" |

---

## 5. 每章固定结构（15个部分）

每一章必须严格按此结构输出，**顺序和数量不允许删减**。

### Part 1｜为什么要学这一章（≤ 300 字）

回答三个问题：
- 这一章解决什么问题？
- 现实中什么时候会遇到？
- 学完之后能做什么？

**禁止**用"本章将介绍……"开头。必须用读者会遇到的真实场景开头。

### Part 2｜本章学习路线

```
为什么需要 → 核心概念 → 工作原理 → 代码实现 → 实际项目 → 面试考点
```

用 Markdown 流程图（`→` 箭头）或树形结构呈现。

### Part 3｜生活例子

每个核心概念至少一个生活类比。类比池（不要在一章内重复使用同一类比）：

> 快递、医院、餐厅、图书馆、工厂、外卖、导航、银行、学校、  
> 超市、机场、警察局、厨房、乐队、足球队、手术室……

### Part 4｜映射到 AI 系统

将 Part 3 的生活类比显式映射到技术概念：

```
快递站     →  Router（路由器）
快递员     →  Agent
订单       →  Task
货物追踪   →  Tracing
```

### Part 5｜正式技术讲解

每次只讲一个概念，按固定格式：

```
【定义】一句话定义
【作用】解决什么问题
【什么时候用】适用场景（3条以上）
【什么时候不用】不适用场景（2条以上）
【优点】2-3条
【缺点/限制】2-3条
【实际案例】企业真实场景
```

### Part 6｜最小可运行 Demo

要求：
- 可直接复制粘贴运行（无需额外配置）
- **不超过 30 行代码**（复杂功能拆成多个小 Demo）
- 每行关键代码必须有注释
- 输出结果要在代码后面展示

```python
# 示例格式
from engine.llm.engine.llm import create_llm

llm = create_llm("deepseek", account="1")
try:
    # 发送一条消息
    answer = llm.chat([
        {"role": "user", "content": "用一句话解释什么是 RAG"}
    ])
    print(answer)
finally:
    llm.close()  # 必须关闭，释放浏览器资源

# 输出示例：
# RAG 是让 LLM 在回答前先检索外部知识库，用真实资料压制幻觉的技术。
```

### Part 7｜实际项目案例

选择以下真实企业场景之一（每章不重复）：

| 场景 | 描述 |
|------|------|
| 客服 Agent | 接入产品文档，自动回答用户问题 |
| 代码审查 Agent | 接入编码规范，自动标记违规代码 |
| 招聘 Agent | 解析简历，匹配 JD，生成面试问题 |
| 测试 Agent | 读取需求文档，自动生成测试用例 |
| 知识库问答 | 企业内部文档检索与问答系统 |
| 数据分析 Agent | 自然语言查询数据库，生成分析报告 |

每个案例必须包含：问题背景 → 设计思路 → 关键代码（简化版）→ 效果说明。

### Part 8｜常见错误

至少 3 个初学者最容易犯的错误，格式：

```
❌ 错误：[具体的错误做法或错误理解]
🔍 原因：[为什么这样做是错的]
✅ 正确：[应该怎么做]
```

### Part 9｜面试高频问题（≥ 10 题）

格式：

```
Q: [问题]
（面试官为什么问这个：[考察的核心能力]）

A: [标准回答，150字以内]
```

问题类型分布：
- 原理类（2-3题）：考察"为什么"
- 比较类（2-3题）：A vs B 的区别
- 场景类（2-3题）："如果……你怎么做"
- 设计类（1-2题）：系统设计题

### Part 10｜笔试考点（≥ 10 道）

题型分布：
- 选择题（4道）：4选1
- 判断题（3道）：对/错 + 解析
- 概念辨析（3道）：区分容易混淆的概念

每题格式：

```
【第N题】[题目]
A. ...  B. ...  C. ...  D. ...
答案：X
解析：[为什么选X，为什么其他选项错]
```

### Part 11｜本章必须背下来的知识（≤ 10 条）

每条一句话，口诀化，便于记忆。

```
1. RAG = 开卷考试：先检索再回答，用真实资料压制幻觉
2. Chunk 大小：256-512 tokens，太大噪音多，太小语义碎
3. ...
```

### Part 12｜一分钟速查表

Markdown 表格，4列固定格式：

| 概念 | 作用 | 一句话记忆 | 适用场景 |
|------|------|-----------|---------|
| RAG | 减少幻觉 | 先检索再生成 | 私有知识、最新信息 |

### Part 13｜思维导图

Markdown 树形结构，展示本章知识点的层次关系：

```
RAG
├── 离线阶段（建库）
│   ├── Chunking（分块）
│   ├── Embedding（向量化）
│   └── Vector DB（存储）
└── 在线阶段（检索）
    ├── Query Embedding
    ├── 相似度检索
    ├── Reranking
    └── Prompt 注入 → 生成
```

### Part 14｜本章总结

**不要重复正文内容。** 回答两个问题：
- 这一章最重要的一个思想是什么？
- 学完这章，读者的认知发生了什么改变？

### Part 15｜下一章预告

不只是"下一章我们将学习……"，而是：
- 本章留下了什么悬念或未解决的问题？
- 为什么学完这章自然会需要下一章？

---

## 6. 记忆优化设计（Memory-First Learning）

### 6.1 六层记忆目标

每章内容必须覆盖的认知层次：

| 层次 | 目标 | 对应 Part |
|------|------|----------|
| 理解（Understand） | 当下能看懂 | Part 3-5 |
| 记忆（Remember） | 一天后还记得 | Part 11-13 |
| 应用（Apply） | 能写出代码 | Part 6-7 |
| 分析（Analyze） | 能辨析对错 | Part 8-10 |
| 设计（Design） | 能设计系统 | Part 7、Part 9设计题 |
| 讲解（Explain） | 能讲给别人听 | Part 3（类比）、Part 14（总结）|

### 6.2 Aha Moment 设计

每章至少设计 3 个顿悟时刻（"原来如此"的瞬间）：

```
"原来 RAG 不是为了让模型更聪明，而是为了让它不乱说。"
"原来 LangGraph 就是状态机，Agent 只是状态机上的节点。"
"原来 Eval 不是测试，而是 AI 系统的 CI/CD。"
```

### 6.3 主动回忆（Active Recall）

每个重要知识点后插入：

> 💭 现在，不往前翻。请回答：为什么 RAG 能减少幻觉？（答案在前面）

### 6.4 间隔重复（Spaced Repetition）

新章节必须引用前面的知识（前向引用）：

```
介绍 RAG 时        → 回顾 Embedding（第X章）
介绍 Agent 时      → 回顾 Prompt Engineering（第X章）
介绍 Workflow 时   → 回顾 Agent Loop（第X章）
介绍 Evaluation 时 → 回顾 LLM-as-Judge 概念
```

### 6.5 能力增益声明

每章结束必须明确告诉读者新增了哪些能力：

```
学完本章，你现在能：
✅ 解释 RAG 为什么能减少幻觉（Why 层）
✅ 设计一个基础 RAG 系统的架构（Design 层）
✅ 用代码实现 Chunking + Embedding + 检索（Apply 层）
✅ 回答"RAG vs Fine-tuning"的面试题（Analyze 层）
```

---

## 7. 章节质量评分标准（Quality Gate）

### 7.1 评分维度

| 评分项 | 满分 | 评分标准 |
|--------|------|---------|
| 教学效果 | 20 | 零基础能看懂？先讲 Why？生活例子清晰？ |
| 技术准确 | 20 | 定义正确？代码可运行？无事实错误？ |
| 工程实践 | 15 | 有真实项目场景？有反模式？有最佳实践？ |
| 可读性 | 10 | 段落短？术语有解释？流畅自然？ |
| 记忆优化 | 10 | 有 Aha Moment？有速查表？有思维导图？ |
| 面试价值 | 10 | 面试题覆盖高频？回答模板清晰？ |
| 知识体系 | 10 | 引用了前章知识？自然引出下一章？ |
| 启发性 | 5 | 读完有新认知？有超越教材的洞见？ |
| **总分** | **100** | — |

### 7.2 评分门槛

```
≥ 95 分  →  通过，进入 Publication Layer
90-94 分  →  Chief Reviewer 指出具体问题 → 指定 Agent 重写失分部分
< 90 分   →  全章重写（不是修改，是重写）
```

### 7.3 自动触发重写的条件（任意一条成立即触发）

```
□ Part 1 用"本章将介绍"开头
□ Part 5 缺少"什么时候不用"
□ Part 6 Demo 超过 30 行且无法直接运行
□ Part 9 面试题少于 10 题
□ Part 10 笔试题少于 10 道
□ Part 11 背诵点超过 10 条
□ 任何术语第一次出现未解释
□ 没有生活类比
□ 没有 Aha Moment
□ Demo 代码有语法错误或无法运行
```

---

## 8. Writer Agent 分工

每一章由多个专职 Agent 协作生成，通过 LangGraph 编排：

| Agent | 负责的 Part | 使用的 LLM | 输入 |
|-------|-----------|-----------|------|
| **Researcher** | — | deepseek | 从 `knowledge/` 加载本章相关知识节点 |
| **Writer** | Part 1, 2, 5, 14, 15 | deepseek | 知识节点 YAML + 章节主题 |
| **Story Designer** | Part 3, 4 | chatgpt | 知识节点 `mental_model` 字段 |
| **Example Designer** | Part 6 | deepseek | 知识节点 `how_it_works` + `best_practices` |
| **Case Study Designer** | Part 7 | chatgpt | 知识节点 `real_world_cases` |
| **Error Analyst** | Part 8 | chatgpt | 知识节点 `anti_patterns` + `common_misconceptions` |
| **Interview Designer** | Part 9 | chatgpt | 知识节点 `interview_points` |
| **Quiz Designer** | Part 10 | deepseek | 知识节点 `exam_points` |
| **Memory Designer** | Part 11, 12, 13 | chatgpt | 全章草稿 |
| **Reviewer** | 技术准确性审核 | deepseek | 全章草稿 |
| **Teacher** | 教学效果审核 | chatgpt | 全章草稿 |
| **Chief Reviewer** | 质量评分（0-100）| chatgpt | 全章终稿 |

### 并行策略

```
Step 1（串行）: Researcher 加载知识节点

Step 2（并行）: Writer + Story Designer + Example Designer
                同时生成各自负责的 Parts

Step 3（并行）: Case Study Designer + Error Analyst
                + Interview Designer + Quiz Designer

Step 4（串行）: Memory Designer 基于全章草稿生成 Part 11-13

Step 5（并行）: Reviewer（技术）+ Teacher（教学）同时审核

Step 6（串行）: Chief Reviewer 评分
                → 分数 ≥ 95: 进入 Publication
                → 分数 < 95: 返回对应 Agent 重写
```

---

## 9. Prompt 模板（各 Agent 使用）

### 9.1 Researcher Agent Prompt

```python
RESEARCHER_SYSTEM = """
你是 AI Education OS 的 Researcher Agent。
你的唯一职责是：从知识库中收集与本章相关的所有知识节点，
整理成结构化数据，供其他 Agent 使用。
不要生成任何教材内容。
"""

def researcher_prompt(chapter_topic: str, node_ids: list[str]) -> list:
    nodes_yaml = "\n---\n".join(
        load_knowledge_node(nid) for nid in node_ids
    )
    return [
        {"role": "system", "content": RESEARCHER_SYSTEM},
        {"role": "user", "content": f"""
本章主题：{chapter_topic}
相关知识节点：
{nodes_yaml}

请输出：
1. 核心知识节点列表（按学习顺序排列）
2. 前置知识（读者需要先理解什么）
3. 本章结束后，读者应该理解什么
4. 本章最容易犯的错误（从 anti_patterns 提取）
"""}
    ]
```

### 9.2 Writer Agent Prompt

```python
WRITER_SYSTEM = """
你是世界顶级的 AI 技术教材作者，同时是认知心理学专家。
你写的内容必须让一个只会一点 Python 的读者完全理解。
你必须先讲 Why，再讲 What，最后讲 How。
不允许用"本章将介绍……"开头。
"""

def writer_prompt(chapter_num: int, topic: str, research: dict) -> list:
    return [
        {"role": "system", "content": WRITER_SYSTEM},
        {"role": "user", "content": f"""
请写教材第 {chapter_num} 章。

章节主题：{topic}
核心知识：{research['core_nodes']}
前置知识（读者已知）：{research['prerequisites']}
本章目标（读者应学会）：{research['learning_goals']}

请输出：
- Part 1：为什么要学这一章（≤300字，禁止"本章将介绍"开头）
- Part 2：本章学习路线（流程图）
- Part 5：正式技术讲解（按每个概念分节，每节含定义/作用/使用场景/不用场景）
- Part 14：本章总结（不重复正文，回答"真正应该记住什么"）
- Part 15：下一章预告（解释为什么自然出现）
"""}
    ]
```

### 9.3 Chief Reviewer Prompt

```python
CHIEF_REVIEWER_SYSTEM = """
你是 AI Education OS 的 Chief Reviewer。
你的职责是：对章节内容按评分标准打分，给出具体改进意见。
评分必须严格：低于 95 分必须返回重写，不允许降低标准。
"""

def chief_reviewer_prompt(chapter_content: str) -> list:
    return [
        {"role": "system", "content": CHIEF_REVIEWER_SYSTEM},
        {"role": "user", "content": f"""
请对以下章节内容评分：

{chapter_content}

评分标准：
- 教学效果（20分）：零基础能看懂？先讲Why？生活例子清晰？
- 技术准确（20分）：定义正确？代码可运行？无事实错误？
- 工程实践（15分）：有真实项目场景？有反模式？有最佳实践？
- 可读性（10分）：段落短？术语有解释？流畅？
- 记忆优化（10分）：有Aha Moment？有速查表？有思维导图？
- 面试价值（10分）：面试题≥10题？回答模板清晰？
- 知识体系（10分）：引用前章？自然引出下一章？
- 启发性（5分）：有超越教材的洞见？

请输出 JSON：
{{
  "scores": {{
    "teaching_effect": <0-20>,
    "technical_accuracy": <0-20>,
    "engineering_practice": <0-15>,
    "readability": <0-10>,
    "memory_optimization": <0-10>,
    "interview_value": <0-10>,
    "knowledge_system": <0-10>,
    "inspiration": <0-5>
  }},
  "total": <0-100>,
  "pass": <true|false>,
  "issues": ["具体问题1", "具体问题2"],
  "rewrite_parts": ["Part X", "Part Y"],
  "rewrite_agent": ["Writer", "Interview Designer"]
}}
"""}
    ]
```

---

## 10. 与 SPEC-001 的对接规范

### 10.1 知识节点加载规则

每章生成前，Researcher Agent 必须加载对应的知识节点：

```python
# 章节 → 知识节点映射（在 Curriculum Layer 中定义）
CHAPTER_NODE_MAP = {
    "ch06_agent": ["KN-C-000020", "KN-C-000021", "KN-P-000001"],
    "ch11_rag":   ["KN-C-000030", "KN-C-000010", "KN-T-000001"],
    # ...
}
```

### 10.2 字段使用规范

| Knowledge Node 字段 | 注入到章节的位置 |
|--------------------|----------------|
| `summary` | Part 11（背诵点第一条） |
| `definition` | Part 5（正式定义） |
| `why` | Part 1（为什么学） + Part 5 |
| `mental_model` | Part 3（生活例子） |
| `how_it_works` | Part 6（Demo 设计依据） |
| `common_misconceptions` | Part 8（常见错误） |
| `anti_patterns` | Part 8（常见错误） |
| `best_practices` | Part 5（实际案例）+ Part 7 |
| `real_world_cases` | Part 7（实际项目） |
| `interview_points` | Part 9（面试题种子） |
| `exam_points` | Part 10（笔试题种子） |
| `one_liner` | Part 11（背诵点）+ Part 12（速查表） |

### 10.3 禁止行为

- **禁止** Writer Agent 自行"发明"知识点（所有知识必须来自 `knowledge/`）
- **禁止** 在章节中硬编码知识定义（必须从节点动态加载）
- **禁止** 跳过 Researcher Agent 直接生成内容

---

## 11. 输出格式规范

### 11.1 文件命名

```
book/
├── ch01_why_ai_native/
│   ├── chapter.md          # 完整章节内容
│   ├── demo/               # 本章所有 Demo 代码
│   │   ├── demo_01.py
│   │   └── demo_02.py
│   ├── review.json         # Chief Reviewer 评分结果
│   └── metadata.yaml       # 章节元数据
```

### 11.2 metadata.yaml 格式

```yaml
chapter_num: 6
title: "为什么 ChatGPT 不能自动完成工作？——Agent 的诞生"
level: "L1-L2"        # L0-L1 | L1-L2 | L2-L3 | L3-L4
knowledge_nodes:
  - KN-C-000020   # Agent
  - KN-C-000021   # Agent Loop
  - KN-P-000001   # ReAct Pattern
prerequisite_chapters: [1, 2, 3]
next_chapter: 7
essential_question: "为什么 ChatGPT 不能自动完成复杂工作，而 Agent 可以？"
capability_gain:
  - "能解释 Agent 和 Chatbot 的本质区别"
  - "能用 ReAct 模式设计单 Agent"
  - "能识别 Agent 无限循环的风险并设置防护"
review_score: 96
review_pass: true
generated_at: "2026-06-19T10:00:00"
```

### 11.3 输出前自检清单

```
必须全部通过，缺一项不得进入 Publication Layer：

内容完整性
□ Part 1-15 全部存在且顺序正确
□ Part 9 面试题 ≥ 10 题
□ Part 10 笔试题 ≥ 10 道
□ Part 11 背诵点 ≤ 10 条
□ 至少 3 个 Aha Moment

质量门控
□ Part 6 Demo 可直接运行（无语法错误）
□ 没有未解释的专业术语
□ Chief Reviewer 评分 ≥ 95 分

知识溯源
□ 所有知识内容可追溯到 knowledge/ 节点
□ metadata.yaml 中 knowledge_nodes 已填写

记忆优化
□ 有速查表（Part 12）
□ 有思维导图（Part 13）
□ 有能力增益声明
```

---

## 相关文档

- [ADR-001: 系统架构决策](../architecture/ADR-001_System-Architecture.md)
- [SPEC-001: Knowledge Schema](SPEC-001_Knowledge-Schema.md)
- [RFC-001: AI Native Engineer 定义](../foundation/RFC-001_AI-Native-Engineer-Definition.md)
- [book-chapter-spec.md](../book-chapter-spec.md)（旧版，以本文档为准）
- `engine/llm/HOW_TO_USE.md`（LLM 调用方式）

---

## Changelog

| 版本 | 日期 | 变更 |
|------|------|------|
| v1.0 | 2026-06-19 | 初稿：在 book-chapter-spec.md 基础上补入 Agent 分工、并行策略、Prompt 模板、Quality Gate 触发逻辑、SPEC-001 对接规范、输出格式规范 |
| v1.1 | 2026-06-19 | 目标升级：书覆盖 L0→L4；新增章节级别标注规范（[L0-L1]/[L1-L2]/[L2-L3]/[L3-L4]）；目标读者按级别分层描述；metadata.yaml 新增 level 字段 |
