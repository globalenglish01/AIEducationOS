# AI Education OS — 项目文档

> 提取自 ChatGPT 问答精华（2026-06-19）

---

## 文档索引

| 文件 | 内容 |
|------|------|
| [system-architecture.md](system-architecture.md) | 系统架构设计：分层架构、目录结构、ADR、Agent 角色、工作流、开发原则 |
| [knowledge-schema.md](knowledge-schema.md) | 知识模型设计：Node Schema（YAML）、知识域列表、能力模型、知识图谱构建步骤 |
| [book-chapter-spec.md](book-chapter-spec.md) | 教材章节规范：教学哲学、15部分章节结构、质量评分、记忆优化设计 |
| [claude-code-prompt.md](claude-code-prompt.md) | Claude Code 提示词：启动提示词、任务拆分、教材重构提示词模板 |
| [references/ai-native-curriculum-analysis.html](references/ai-native-curriculum-analysis.html) | 《AI-Native Engineer 圣经》40章课程完整技术内容分析（含L0→L4能力地图、技术栈、章节结构） |
| [foundation/RFC-001_AI-Native-Engineer-Definition.md](foundation/RFC-001_AI-Native-Engineer-Definition.md) | AI Native Engineer 完整定义：L0-L4能力模型、14维度架构审查、FCARS、Harness、安全治理 |
| [architecture/ADR-001_System-Architecture.md](architecture/ADR-001_System-Architecture.md) | 系统架构决策记录：知识OS定位、SSOT、6层架构、Browser LLM Adapter、多Agent单一职责 |
| [specifications/SPEC-001_Knowledge-Schema.md](specifications/SPEC-001_Knowledge-Schema.md) | 知识节点 Schema 规范：完整 YAML 格式、10种节点类型、13个知识域、命名规范、关系规范、校验规则、Agent消费示例 |
| [specifications/SPEC-002_Book-Chapter.md](specifications/SPEC-002_Book-Chapter.md) | 章节生成规范：15部分结构、12个Writer Agent分工、并行策略、Prompt模板、Quality Gate（95分门槛）、SPEC-001对接规范 |

---

## 核心结论（3句话版本）

1. **这是一个知识操作系统，不是写书工具。** 知识（Knowledge Graph）是唯一事实源，书/课程/面试题/PPT 都是知识的不同视图。

2. **架构优先，Prompt 只占 5%。** 正确顺序：Theory → RFC → ADR → SPEC → STD → GUIDE → TEMPLATE → Workflow → Prompt → Output。

3. **Claude Code 每次只做一个 Task。** 工作流：Vision → PRD → Architecture → RFC/SPEC → Task → Claude Code → Review → Merge。

---

## 快速开始

### 第一步：理解架构
阅读 [system-architecture.md](system-architecture.md)

### 第二步：设计知识模型
参考 [knowledge-schema.md](knowledge-schema.md)，开始建立 `knowledge/` 目录下的知识节点

### 第三步：定义教材规范
参考 [book-chapter-spec.md](book-chapter-spec.md)，建立 `specs/Book_SPEC.md`

### 第四步：给 Claude Code 发第一条提示词
参考 [claude-code-prompt.md](claude-code-prompt.md) 中的"第一条 Prompt（项目启动）"
