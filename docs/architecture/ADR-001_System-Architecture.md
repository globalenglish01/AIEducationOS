# ADR-001: AI Education OS 系统架构决策

**Status**: Accepted  
**Date**: 2026-06-19  
**Deciders**: AI Education OS Project  
**RFC**: [RFC-001](../foundation/RFC-001_AI-Native-Engineer-Definition.md)  
**Supersedes**: —  
**Superseded by**: —

---

## Context — 决策背景

本项目的目标是构建一个能持续生产高质量 AI Native 教育内容的系统。在架构设计阶段，面临若干根本性的架构选择，这些选择一旦确定，后续所有模块、Agent、Prompt 都必须遵守。

本 ADR 记录以下 5 个核心架构决策，每个决策都说明：我们选了什么、为什么、否决了什么、代价是什么。

---

## 决策一：知识操作系统，而非书籍生成器

### 决策

**本系统定位为"知识操作系统（AI Education OS）"，而非"书籍生成器"。**

核心原则：
> 书不是知识，书只是知识的一种排列方式。

系统管理的核心资产是**知识（Knowledge）**，书/课程/面试题/PPT 都是知识在不同维度上的**视图（View）**。

### 否决的方案

**方案 A：书籍生成器**  
直接给定章节列表，让 LLM 逐章生成，拼成一本书。

否决原因：
- 同一个知识点（如 RAG）在不同章节、不同产品（书/课程/面试题）中会被重复定义，导致不一致
- 书的结构决定了知识的组织方式，换一种产品形态（如课程）就要重新组织所有内容
- 无法复用：书改了，课程和面试题不会自动更新

**方案 B：Markdown 文件夹 + 手动维护**  
人工维护一堆 Markdown 文件，手动粘贴到 Prompt 里生成内容。

否决原因：
- 无法扩展：内容量一大，人工维护不可持续
- 无法评估：没有自动化质量门控
- 无法追溯：知识变更无法传播到所有依赖它的输出

### 后果

- `knowledge/` 目录是整个系统的核心资产，必须在所有其他模块之前设计
- 任何新产品形态（如 Quiz、PPT、项目）都是知识的新视图，不需要重新组织知识
- 知识变更自动传播：修改 `knowledge/agent.md` → 所有引用它的 Book 章节、Course、Interview 都需要重新生成

---

## 决策二：One Source of Truth（ADR-000 的正式确认）

### 决策

**所有知识只存储在 `knowledge/` 目录下一份。任何输出（Book/Course/Interview/PPT）只允许引用，不允许复制知识内容。**

```
knowledge/concepts/agent.md   ← 唯一来源

book/ch06_agent.md            → 引用 agent.md，不复制
course/lesson_06.md           → 引用 agent.md，不复制
interview/agent_questions.md  → 引用 agent.md，不复制
```

### 否决的方案

**方案：每个产品维护自己的知识副本**

```
book/knowledge/agent.md
course/knowledge/agent.md      ← 各自一份
interview/knowledge/agent.md
```

否决原因：
- 任何一处更新（如发现 Agent 有第 5 种模式），需要同步修改 3 处，必然出现漂移
- 审查无法自动化：无法判断哪个版本是"正确"的
- 内容量越大，维护成本指数级上升

### 约束

- Agent 生成内容时，**必须从 `knowledge/` 读取**，不允许把知识内容硬编码在 Prompt 里
- Prompt 里出现的知识内容，必须是**动态注入**的（从 `knowledge/` 读取后填入）
- 如果两个输出对同一概念的描述不一致，以 `knowledge/` 为准，修改输出，不修改 `knowledge/`

### 后果

- `knowledge/` 的质量直接决定所有输出的质量上限
- 知识节点的 Schema（YAML 格式）必须在编码之前冻结（见 Knowledge_SPEC）
- 每个知识节点必须有唯一 ID，方便引用和追踪

---

## 决策三：6 层分离架构

### 决策

**系统采用严格的 6 层架构，层与层之间单向依赖，禁止跨层直接调用。**

```
┌─────────────────────────────────────┐
│  Knowledge Layer（知识层）           │  ← 唯一事实源，YAML 知识节点
├─────────────────────────────────────┤
│  Pedagogy Layer（教育学层）          │  ← 教学哲学、学习科学规则
├─────────────────────────────────────┤
│  Curriculum Layer（课程层）          │  ← 学习路径、章节序列、知识映射
├─────────────────────────────────────┤
│  Generation Layer（生成层）          │  ← Agent + Prompt + Workflow
├─────────────────────────────────────┤
│  Evaluation Layer（评估层）          │  ← LLM-as-Judge + Harness + 质量门控
├─────────────────────────────────────┤
│  Publication Layer（发布层）         │  ← Book / Course / Interview / PPT
└─────────────────────────────────────┘
```

### 各层职责边界

| 层 | 职责 | 不允许做的事 |
|----|------|------------|
| Knowledge | 存储和组织知识节点 | 不关心如何呈现 |
| Pedagogy | 定义教学原则和学习科学规则 | 不生成内容 |
| Curriculum | 设计学习路径和章节顺序 | 不直接调 LLM |
| Generation | 调用 Agent 生成内容 | 不直接写文件到 Publication |
| Evaluation | 评估生成质量，决定通过/重生成 | 不修改知识 |
| Publication | 格式化并输出最终产品 | 不包含业务逻辑 |

### 否决的方案

**方案：扁平架构（一个大 Agent 做所有事）**

```python
# 反例：所有逻辑混在一起
def generate_chapter(topic):
    knowledge = "Agent 是..."  # 硬编码知识
    prompt = f"写一章关于{topic}，知识：{knowledge}"
    content = llm.chat(prompt)
    # 直接写文件，没有评估
    with open(f"book/{topic}.md", "w") as f:
        f.write(content)
```

否决原因：
- 无法替换单个组件（如换一个评估策略）
- 无法并行：生成和评估必须串行
- 无法追踪质量问题出在哪一层
- 知识、生成、评估、发布耦合，任何一处变更影响全局

### 后果

- 每一层只能调用相邻下层的接口，不能跨层
- Generation Layer 的 Agent 必须通过 Curriculum Layer 获取"要写什么"，不能自己决定
- 质量不达标时，Evaluation Layer 触发重生成，不修改知识和课程设计
- 新增产品形态（如 Quiz）只需在 Publication Layer 新增一个 Formatter，其他层不变

---

## 决策四：Browser LLM Adapter（禁止直接调用 Claude API）

### 决策

**本项目所有 LLM 调用必须通过 `engine/llm/` 中封装的 Browser LLM Adapter，禁止直接调用任何 LLM 的官方 API（包括 Claude API）。**

调用方式：
```python
from engine.llm.engine.llm import create_llm

llm = create_llm("deepseek", account="1")
answer = llm.chat([{"role": "user", "content": "你的问题"}])
llm.close()
```

Provider 分工约定：

| Provider | 用途 |
|----------|------|
| `deepseek` | 技术内容、Demo 代码、知识节点草稿 |
| `chatgpt` | 教学设计、生活例子、面试题、语言润色 |
| `both` | 并行调用，取最快结果（用于对比实验） |

### 否决的方案

**方案 A：直接调用 Claude API（`anthropic.Anthropic()`）**

否决原因：
- 项目明确约束：禁止直接调用 Claude API
- API 调用有成本，Browser Adapter 利用已有账号，成本为零
- 统一入口便于替换 Provider，不需要改业务代码

**方案 B：直接调用 OpenAI/DeepSeek 官方 API**

否决原因：
- 需要管理 API Key，有安全风险
- 有速率限制和费用
- Browser Adapter 已封装好，切换 Provider 只需换参数

**方案 C：每个 Agent 自己管理 LLM 连接**

否决原因：
- 浏览器资源有限，多个 Agent 各自持有浏览器实例会造成资源耗尽
- 无法统一监控 Token 用量和调用日志
- 无法统一实现重试、账号轮换等策略

### Provider 路由规则

```
写故事 / 生活例子 / 教学设计   →  chatgpt
写代码 / Demo / 技术解释       →  deepseek
最终 Review / 一致性检查       →  chatgpt（质量更稳定）
并行对比实验                   →  both
```

### 约束

- 每次调用后**必须** `llm.close()`，否则 Playwright 浏览器进程不释放
- 建议用 `try/finally` 包裹
- 单进程内不超过 3 个并发 llm 实例
- 账号限速时切换：`account="2"`, `account="3"`...（最多 `"6"`）

### 后果

- 所有业务代码对 LLM Provider 透明：换 Provider 只改 `create_llm()` 的参数
- 统一的入口便于后续接入官方 API（只需在 Adapter 层新增实现）
- Playwright 浏览器是有限资源，必须严格管理生命周期

---

## 决策五：多 Agent 单一职责架构

### 决策

**系统采用多 Agent 协作模式，每个 Agent 只承担一种职责（Single Responsibility）。Agent 之间通过 LangGraph Workflow 编排，不直接互相调用。**

```
agents/
├── Planner            # 只负责：把任务拆解为步骤
├── Researcher         # 只负责：从 knowledge/ 读取相关知识
├── Writer             # 只负责：生成初稿内容
├── Teacher            # 只负责：优化教学表达
├── Story Designer     # 只负责：设计生活类比和故事
├── Example Designer   # 只负责：设计代码示例
├── Exercise Designer  # 只负责：设计练习题
├── Diagram Designer   # 只负责：设计思维导图和流程图
├── Quiz Designer      # 只负责：设计笔试题
├── Interview Designer # 只负责：设计面试题
├── Reviewer           # 只负责：技术准确性审核
├── Memory Reviewer    # 只负责：记忆优化审核
├── Consistency Reviewer # 只负责：跨章节一致性检查
└── Chief Reviewer     # 只负责：最终质量把关（95分门槛）
```

### 否决的方案

**方案 A：一个全能 Agent（"写好一章"）**

```python
# 反例
agent = SuperAgent("写好第6章，包括故事、代码、面试题、思维导图...")
```

否决原因：
- 单次 Context Window 装不下所有要求，输出质量降低
- 无法针对某一环节（如面试题质量差）单独优化
- 无法并行：所有产出必须串行生成
- 无法替换：改一个环节影响整个 Agent

**方案 B：固定 Pipeline（线性串行执行）**

```
Writer → Teacher → Reviewer → Publisher（固定顺序，不可跳过）
```

否决原因：
- 不同章节可能需要不同的生成策略（代码密集章节 vs 概念章节）
- 质量门控触发重生成时，无法只重跑失败的步骤
- 无法应对"这章不需要故事"等特殊情况

### 编排方式

所有 Agent 通过 **LangGraph Workflow** 编排：
- 每个 Agent 是一个 LangGraph Node
- 路由（哪些 Agent 需要运行）由 Curriculum Layer 决定
- Checkpoint 保存每个 Agent 的输出，失败时从断点恢复
- 质量不达标（< 95分）时，Chief Reviewer 触发指定 Agent 重跑

### 后果

- 新增产品形态（如 Podcast 脚本）只需新增对应的 Designer Agent，其他 Agent 不变
- Agent 可以并行运行（Story Designer 和 Example Designer 同时工作）
- 单个 Agent 失败不影响其他 Agent 的输出（Checkpoint 保护）
- Agent 的 Prompt 可以独立版本管理和测试

---

## 架构约束汇总（所有后续开发必须遵守）

| 编号 | 约束 | 违反后果 |
|------|------|---------|
| C-01 | 知识只存储在 `knowledge/`，其他目录只引用 | 内容不一致，系统失控 |
| C-02 | 禁止直接调用 Claude API，必须用 Browser LLM Adapter | 违反项目约束 |
| C-03 | 层与层之间单向依赖，禁止跨层调用 | 耦合上升，无法单独测试 |
| C-04 | 每个 Agent 只有一种职责 | 难以优化、难以替换 |
| C-05 | 所有 LLM 调用后必须 `llm.close()` | Playwright 资源泄露 |
| C-06 | 质量低于 95 分必须重生成，不允许手动降低标准 | 教材质量不达标 |
| C-07 | Agent 编排必须通过 LangGraph，不允许 Agent 直接互调 | 无法 Checkpoint，无法重试 |
| C-08 | Prompt 必须版本控制（存入 `prompts/`），禁止硬编码在业务代码 | 无法追踪质量变化 |

---

## 开发顺序（由本 ADR 约束）

根据以上架构决策，正确的开发顺序为：

```
1. Knowledge Schema（知识节点格式）    ← 最先做，其他一切依赖它
2. Pedagogy Rules（教学规则定义）
3. Curriculum Design（课程结构）
4. Agent 定义（角色 + Prompt 模板）
5. LangGraph Workflow（编排逻辑）
6. Evaluation 体系（LLM-as-Judge + 评分规则）
7. Publication Formatter（输出格式）
8. 集成测试 + Harness
```

**禁止**：先写 Workflow 再补 Schema；先生成内容再定规范。

---

## 相关文档

- [RFC-001: AI Native Engineer 定义](../foundation/RFC-001_AI-Native-Engineer-Definition.md)
- [system-architecture.md](../system-architecture.md)（系统架构概览）
- [knowledge-schema.md](../knowledge-schema.md)（知识节点 Schema）
- [book-chapter-spec.md](../book-chapter-spec.md)（章节生成规范）
- `engine/llm/HOW_TO_USE.md`（Browser LLM Adapter 使用指南）

---

## Changelog

| 版本 | 日期 | 变更 |
|------|------|------|
| v1.0 | 2026-06-19 | 初稿：5个核心架构决策（知识OS、SSOT、6层架构、Browser LLM Adapter、多Agent单一职责） |
