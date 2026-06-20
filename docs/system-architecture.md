# AI Education OS — 系统架构设计

> 来源：ChatGPT 问答精华（ebook.html，Q1~Q24）

---

## 项目定位

**不是一本书生成器，而是一个 AI 教育操作系统（AI Education OS）。**

核心原则：
> 书不是知识，书只是知识的一种排列方式。

---

## 核心架构分层（v1.0 冻结）

```
Knowledge Layer（知识层 — 唯一事实源）
       ↓
Pedagogy Layer（教育学层）
       ↓
Curriculum Layer（课程层）
       ↓
Generation Layer（生成层）
       ↓
Evaluation Layer（评估层）
       ↓
Publication Layer（发布层）
```

---

## 目录结构

```
AI-Knowledge-Factory/
│
├── docs/
│   ├── architecture/        # ADR 架构决策记录
│   ├── foundation/          # Vision / Mission / Philosophy / Principles
│   ├── specifications/      # 各类 Spec 文档
│   └── workflows/
│
├── knowledge/               # 知识库（唯一事实来源）
├── curriculum/              # 课程设计
├── book/                    # 图书生成
├── course/                  # 视频课程生成
├── slides/                  # PPT 生成
├── interview/               # 面试题生成
├── exercises/               # 练习题生成
├── projects/                # 项目生成
├── diagrams/                # 图示生成
├── prompts/                 # 所有 Prompt 模板
├── agents/                  # 多 Agent 角色定义
├── reviewers/               # 审核 Agent
├── evaluators/              # 自动评分
├── workflows/               # LangGraph 工作流
├── outputs/                 # 最终产物
└── tests/                   # 自动化测试
```

---

## 文档体系（RFC / ADR / SPEC / STD / GUIDE / TEMPLATE）

| 类型 | 职责 | 示例 |
|------|------|------|
| **RFC** | 定义"应该是什么" | RFC-001: What is AI Native Engineer? |
| **ADR** | 记录架构决策原因，轻易不改 | ADR-000: One Source of Truth |
| **SPEC** | 规范，告诉 Agent 怎么生成 | Book SPEC / Chapter SPEC |
| **STD** | 标准，告诉 Reviewer 怎么评分 | Writing STD / Code STD / Review STD |
| **GUIDE** | 最佳实践指导 | Story Guide / Teaching Guide |
| **TEMPLATE** | 模板 | Chapter Template / Prompt Template |

开发顺序：
```
Theory → RFC → ADR → SPEC → STD → GUIDE → TEMPLATE → Workflow → Prompt → Output
```

---

## 关键架构决策（ADR-000）

### One Source of Truth（唯一事实源）

- 所有知识只有一份，存于 `knowledge/`
- 任何内容（Book / Course / Interview / PPT）都**引用**知识，不允许复制
- 如果 Book 说 Agent 有 5 种、Course 说 6 种，系统就已失控

```
knowledge/agent.md   ← 唯一来源

Book     → 引用它
Course   → 引用它
Interview → 引用它
PPT      → 引用它
```

---

## 输出产品类型（第一批内置应用）

- 📖 Book Generator（教材）
- 🎓 Course Generator（视频课程）
- 📝 Interview Generator（面试题）
- 🧪 Exercise Generator（练习题）
- 🧩 Project Generator（项目）
- 📊 PPT Generator

共用同一套知识源和教学规范。

---

## 多模型协作分工

| 模型 | 职责 |
|------|------|
| **ChatGPT** | 教学设计、知识组织、例子、类比、故事、面试 |
| **DeepSeek** | 技术内容、Demo、API、代码、工程案例 |
| **Claude Code** | Review、Rewrite、Consistency、Quality Gate、最终出版版 |

模型路由原则（Provider Router）：
```
写故事   → ChatGPT
写代码   → Claude
生成Demo → DeepSeek
最终 Review → Claude
```

---

## LLM 调用分层（Browser LLM Adapter）

```
Application Layer (Book、Course、Interview...)
       ↓
Workflow Layer (LangGraph)
       ↓
Agent Layer (Planner、Writer、Reviewer...)
       ↓
LLM Layer (ChatGPT、DeepSeek、Claude...)
       ↓
Execution Layer (API / Browser(Playwright) / MCP)
```

Provider 优先级：
```
Official API
      ↓
MCP / OpenAI Compatible API
      ↓
Browser Adapter（Playwright）
      ↓
Manual Fallback
```

---

## Agent 角色列表

```
agents/
├── Chief Editor       # 总编辑，最终质量把关
├── Planner            # 章节规划
├── Researcher         # 知识整理
├── Writer             # 内容写作
├── Teacher            # 教学优化
├── Story Designer     # 故事设计
├── Example Designer   # 例子设计
├── Exercise Designer  # 练习题设计
├── Diagram Designer   # 图示设计
├── Quiz Designer      # 笔试题设计
├── Interview Designer # 面试题设计
├── Reviewer           # 内容审核
├── Memory Reviewer    # 记忆优化审核
├── Consistency Reviewer # 一致性审核
└── Chief Reviewer     # 总审核
```

每个 Agent 只有一种职责（单一职责原则）。

---

## 章节生成工作流（像软件 CI/CD）

```
规划
  ↓
资料整理
  ↓
章节生成
  ↓
案例生成
  ↓
图示生成
  ↓
练习题生成
  ↓
技术审核
  ↓
教学审核
  ↓
记忆优化
  ↓
面试审核
  ↓
一致性检查
  ↓
自动评分（低于95分→重新生成）
  ↓
发布
```

---

## 开发原则（给 Claude Code 的工程准则）

1. **Architecture First** — 任何代码必须先有架构设计
2. **Specification First** — 任何功能必须先写 Spec，再写代码
3. **Small Iterations** — 一次只完成一个明确的小任务
4. **Review Before Code** — 先 Review 设计，再开始编码
5. **Maintainability First** — 可维护性高于开发速度
6. **Extensibility First** — 任何设计都要考虑未来扩展
7. **Do Not Over Engineer** — 当前版本只实现真正需要的功能
8. **Follow Clean Architecture** — 业务逻辑不能依赖具体 LLM
9. **Everything Is Replaceable** — 任何 Provider/Workflow/Agent 都应可替换
10. **One Source Of Truth** — 知识只有一份，不允许复制

开发禁止模式：
```
Think → Implement  ❌

正确模式：
Think → Design → Review → Implement → Test → Review → Refactor  ✅
```

---

## Claude Code 使用方式（任务驱动，非超级 Prompt）

```
Vision
  ↓
Requirements (PRD)
  ↓
Architecture
  ↓
RFC
  ↓
Task（每次只做一个 Task）
  ↓
Claude Code
  ↓
Review
  ↓
Merge
```

任务分级：Epic → Feature → Task（每个 Task 能在一天内完成）

**核心结论：不要把 Claude Code 当"程序员"，而要把它当"项目组的一名高级工程师"。**
