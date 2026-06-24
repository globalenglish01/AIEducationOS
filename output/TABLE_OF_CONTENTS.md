# AI Education OS — 完整目录

> 生成日期：2026-06-24
> 总章节数：95章（不含 SUMMARY 文件）
> 说明：⚠️ 标注问题章节，🔁 标注重复主题，📌 标注漂移预告

---

## Part 1：LLM 基础概念（L0-L1）

| 章号 | 文件 | 标题 | 级别 |
|------|------|------|------|
| 第1章 | ch01_KN-C-000001.md | LLM（Large Language Model）——为什么它看起来会思考？ | L0-L1 |
| 第2章 | ch02_KN-C-000002.md | Token——LLM世界里的"计量单位" | L0-L1 |
| 第3章 | ch03_KN-C-000003.md | Context Window——大模型真正的"记忆边界" | L0-L1 |
| 第4章 | ch04_KN-C-000004.md | Hallucination（幻觉） | L0-L1 |
| 第5章 | ch05_KN-C-000005.md | Temperature——为什么同一个问题，模型每次回答都不一样？ | L0-L1 |
| 第6章 | ch06_KN-C-000010.md | Prompt —— 人与 LLM 的接口 | L0-L1 |

---

## Part 2：Prompt 工程（L0-L2）

| 章号 | 文件 | 标题 | 级别 |
|------|------|------|------|
| 第7章 | ch07_KN-P-000001.md | System Prompt——给AI发员工手册 | L0-L1 |
| 第8章 | ch08_KN-P-000002.md | Few-shot Prompting | L0-L1 |
| 第9章 | ch09_KN-P-000003.md | Chain-of-Thought（CoT） | L1-L2 |
| 第10章 | ch10_KN-P-000004.md | ReAct (Reasoning + Acting) | L1-L2 |

---

## Part 3：Agent 体系（L1-L3）

| 章号 | 文件 | 标题 | 级别 | 备注 |
|------|------|------|------|------|
| 第11章 | ch11_KN-C-000020.md | Agent (AI Agent) | L1-L2 | 📌 末尾预告"Multi-Agent"，实际下一章是 Agent Loop |
| 第12章 | ch12_KN-C-000021.md | Agent Loop | L1-L2 | |
| 第13章 | ch13_KN-C-000022.md | Tool Use (Function Calling) | L1-L2 | |
| 第14章 | ch14_KN-C-000023.md | Agent Planning | L2-L3 | |
| 第15章 | ch15_KN-C-000024.md | Human-in-the-Loop (HITL) | L2-L3 | 📌 末尾预告"Agent Governance"，实际下一章是 Embedding |

---

## Part 4：RAG 检索体系（L1-L3）

| 章号 | 文件 | 标题 | 级别 |
|------|------|------|------|
| 第16章 | ch16_KN-C-000030.md | Embedding（向量嵌入） | L1-L2 |
| 第17章 | ch17_KN-C-000031.md | Vector Database（向量数据库） | L1-L2 |
| 第18章 | ch18_KN-C-000032.md | Chunking（文档分块） | L1-L2 |
| 第19章 | ch19_KN-C-000033.md | RAG（检索增强生成） | L1-L2 |
| 第20章 | ch20_KN-C-000034.md | Reranking（重排序） | L2-L3 |
| 第21章 | ch21_KN-C-000035.md | Hybrid Search（混合搜索） | L2-L3 |

---

## Part 5：Agent 状态与流程控制（L2-L3）

| 章号 | 文件 | 标题 | 级别 |
|------|------|------|------|
| 第22章 | ch22_KN-C-000025.md | State Machine（状态机） | L2-L3 |
| 第23章 | ch23_KN-C-000026.md | LangGraph | L2-L3 |
| 第24章 | ch24_KN-C-000027.md | Checkpoint & Resume（检查点与断点续跑） | L2-L3 |
| 第25章 | ch25_KN-C-000028.md | Interrupt（中断与恢复） | L2-L3 |

---

## Part 6：评测体系（L2-L3）

| 章号 | 文件 | 标题 | 级别 |
|------|------|------|------|
| 第26章 | ch26_KN-C-000036.md | LLM-as-Judge（用 LLM 评判输出质量） | L2-L3 |
| 第27章 | ch27_KN-C-000037.md | RAGAS（RAG 评估框架） | L2-L3 |
| 第28章 | ch28_KN-C-000038.md | Eval Dataset（评估数据集） | L2-L3 |
| 第29章 | ch29_KN-C-000039.md | Regression Testing（回归测试） | L2-L3 |

---

## Part 7：AI 系统安全（L2-L3）

| 章号 | 文件 | 标题 | 级别 | 备注 |
|------|------|------|------|------|
| 第30章 | ch30_KN-C-000040.md | Prompt Injection（提示词注入） | L2-L3 | |
| 第31章 | ch31_KN-C-000041.md | Agent Privilege Escalation（Agent 权限提升） | L2-L3 | |
| 第32章 | ch32_KN-C-000042.md | Guardrails（安全护栏） | L2-L3 | |
| 第33章 | ch33_KN-C-000043.md | Tool Injection（工具注入·攻击面） | L2-L3 | 🔁 与第45章同主题，建议差异化标题 |
| 第79章 | ch79_KN-X-000002.md | IDOR in AI Systems（越权访问反模式） | L2 | |
| 第83章 | ch83_KN-B-000003.md | PII Detection & Masking（个人信息检测与脱敏） | L2-L3 | |
| 第84章 | ch84_KN-B-000004.md | JWT Auth in AI Systems（AI 系统的 JWT 认证） | L2 | |
| 第85章 | ch85_KN-B-000005.md | Secret Management（密钥安全管理） | L1-L2 | |

---

## Part 8：可观测性（L1-L3）

| 章号 | 文件 | 标题 | 级别 |
|------|------|------|------|
| 第34章 | ch34_KN-C-000044.md | Tracing（分布式追踪） | L2-L3 |
| 第35章 | ch35_KN-C-000046.md | LLM Observability（LLM 可观测性） | L2-L3 |
| 第36章 | ch36_KN-C-000047.md | Structured Logging（结构化日志） | L1-L2 |

---

## Part 9：高级主题（L3-L4）

| 章号 | 文件 | 标题 | 级别 | 备注 |
|------|------|------|------|------|
| 第37章 | ch37_KN-C-000050.md | GraphRAG | L3-L4 | 📌 末尾预告"知识图谱验证"，实际下一章是 A2A |
| 第38章 | ch38_KN-C-000051.md | A2A Protocol（Agent-to-Agent 协议） | L3-L4 | 🔁 与第80章同主题，建议差异化 |
| 第39章 | ch39_KN-C-000052.md | FCARS（AI 治理体系） | L3-L4 | 🔁 与第60章同主题 |
| 第40章 | ch40_KN-C-000053.md | Chaos Engineering（混沌工程） | L3-L4 | 🔁 与第59章同主题 |
| 第41章 | ch41_KN-C-000054.md | Fine-tuning（微调·进阶篇） | L3-L4 | 🔁 与第57章同主题，建议加"进阶"区分 |

---

## Part 10：MCP 协议（L1-L3）

| 章号 | 文件 | 标题 | 级别 | 备注 |
|------|------|------|------|------|
| 第42章 | ch42_KN-C-000060.md | MCP（Model Context Protocol） | L1-L2 | |
| 第43章 | ch43_KN-C-000061.md | Tool Schema Design（工具接口设计） | L1-L2 | |
| 第44章 | ch44_KN-C-000062.md | Tool Path Sandbox（工具沙箱隔离） | L2-L3 | |
| 第45章 | ch45_KN-C-000063.md | Tool Injection（工具注入·MCP防护） | L2-L3 | 🔁 与第33章同主题，建议差异化标题 |
| 第46章 | ch46_KN-C-000064.md | MCP Server / Client 架构 | L2-L3 | |

---

## Part 11：记忆与上下文管理（L1-L3）

| 章号 | 文件 | 标题 | 级别 |
|------|------|------|------|
| 第47章 | ch47_KN-C-000065.md | Short-term Memory（短期记忆） | L1-L2 |
| 第48章 | ch48_KN-C-000066.md | Long-term Memory（长期记忆） | L1-L2 |
| 第49章 | ch49_KN-C-000067.md | Context Compression（上下文压缩） | L2-L3 |
| 第50章 | ch50_KN-C-000068.md | Memory Isolation（记忆隔离） | L2-L3 |
| 第51章 | ch51_KN-C-000069.md | Token Budget（Token 预算管理） | L2-L3 |
| 第54章 | ch54_KN-C-000072.md | Context Pruning（上下文裁剪） | L2-L3 |

---

## Part 12：生产工程（L2-L3）

| 章号 | 文件 | 标题 | 级别 |
|------|------|------|------|
| 第52章 | ch52_KN-C-000070.md | Semantic Cache（语义缓存） | L2-L3 |
| 第53章 | ch53_KN-C-000071.md | Model Routing（模型路由） | L2-L3 |
| 第55章 | ch55_KN-C-000073.md | Graceful Degradation（优雅降级） | L2-L3 |
| 第56章 | ch56_KN-C-000074.md | Multi-tenancy（多租户架构） | L2-L3 |
| 第57章 | ch57_KN-C-000075.md | Fine-tuning（微调·基础篇） | L2-L3 | 🔁 与第41章同主题，建议加"基础"区分 |
| 第58章 | ch58_KN-C-000076.md | Ollama（本地模型部署） | L1-L2 |
| 第59章 | ch59_KN-C-000077.md | Chaos Engineering for AI（AI 系统混沌工程） | L2-L3 | 🔁 与第40章同主题 |
| 第90章 | ch90_KN-S-000005.md | Multi-tenancy 代码演示（续第56章） | — | ⚠️ 无独立标题，是第56章的代码延伸 |

---

## Part 13：AI 治理与合规（L3-L4）

| 章号 | 文件 | 标题 | 级别 | 备注 |
|------|------|------|------|------|
| 第60章 | ch60_KN-C-000078.md | FCARS 框架（AI 治理框架） | L3-L4 | 🔁 与第39章同主题 |
| 第61章 | ch61_KN-C-000079.md | AI Compliance（AI 合规性） | L3-L4 | |
| 第62章 | ch62_KN-C-000080.md | AI Fairness（AI 公平性） | L3-L4 | 📌 末尾预告"Accountability"，实际下一章是 ReAct Pattern |

---

## Part 14：设计模式（L1-L3）

| 章号 | 文件 | 标题 | 级别 | 备注 |
|------|------|------|------|------|
| 第63章 | ch63_KN-P-000005.md | ReAct Pattern（推理-行动循环） | L1-L2 | 📌 末尾预告"Agent Loop"，实际下一章是 Supervisor-Worker |
| 第64章 | ch64_KN-P-000006.md | Supervisor-Worker Pattern（主从多 Agent 模式） | L2-L3 | |
| 第65章 | ch65_KN-P-000007.md | Pipeline Pattern（串行 Agent 流水线） | L1-L2 | |
| 第66章 | ch66_KN-P-000008.md | Semantic Cache Pattern（语义缓存模式） | L2-L3 | |
| 第67章 | ch67_KN-P-000009.md | Model Routing Pattern（模型路由模式） | L2-L3 | |

---

## Part 15：框架与工具（L1-L3）

| 章号 | 文件 | 标题 | 级别 | 备注 |
|------|------|------|------|------|
| 第68章 | ch68_KN-F-000001.md | LangChain | L1-L2 | |
| 第69章 | ch69_KN-F-000002.md | LangGraph | L2-L3 | 🔁 与第23章同主题，第23章是概念篇，本章是框架实践篇 |
| 第70章 | ch70_KN-F-000003.md | AutoGen | L2-L3 | |
| 第71章 | ch71_KN-F-000004.md | CrewAI | L2 | |
| 第72章 | ch72_KN-F-000005.md | OpenAI Agents SDK | L1-L2 | |
| 第73章 | ch73_KN-T-000001.md | vLLM（高吞吐 LLM 推理引擎） | L3 | |
| 第74章 | ch74_KN-T-000002.md | 向量数据库（FAISS / Chroma / Pinecone） | L1-L2 | |
| 第75章 | ch75_KN-T-000003.md | Browser Automation（Playwright / Browser-Use） | L2-L3 | |

---

## Part 16：Agent 工程脚手架（L2-L3）

| 章号 | 文件 | 标题 | 级别 | 备注 |
|------|------|------|------|------|
| 第76章 | ch76_KN-A-000001.md | Agent Harness（Agent 工程脚手架） | L2-L3 | |
| 第77章 | ch77_KN-A-000002.md | AI Testing Pyramid（AI 测试金字塔） | L2-L3 | 🔁 与第78章同主题，标题和编号重复 |
| 第78章 | ch78_KN-X-000001.md | ⚠️ 【标题错误：写的是"第77章"】AI Testing Pyramid | L2-L3 | ⚠️ 章内编号应为第78章，需修复 |
| 第80章 | ch80_KN-R-000001.md | A2A Protocol（Agent-to-Agent 通信协议） | L2-L3 | 🔁 与第38章同主题，第38章是协议规范，本章是工程实现 |

---

## Part 17：工程最佳实践（L1-L3）

| 章号 | 文件 | 标题 | 级别 |
|------|------|------|------|
| 第81章 | ch81_KN-B-000001.md | Prompt Version Control（提示词版本控制） | L1-L2 |
| 第82章 | ch82_KN-B-000002.md | Max Iteration Guard（最大迭代守卫） | L1-L2 |

---

## Part 18：系统案例（L2-L3）

| 章号 | 文件 | 标题 | 级别 |
|------|------|------|------|
| 第86章 | ch86_KN-S-000001.md | Cursor AI — AI Native IDE 架构剖析 | L2-L3 |
| 第87章 | ch87_KN-S-000002.md | Perplexity AI — 实时 RAG 搜索引擎架构 | L2 |
| 第88章 | ch88_KN-S-000003.md | 企业客服 Agent 系统设计 | L2-L3 |
| 第89章 | ch89_KN-S-000004.md | AI 代码审查流水线 | L2-L3 |

---

## Part 19：实战项目（L1-L3）

| 章号 | 文件 | 标题 | 级别 |
|------|------|------|------|
| 第91章 | ch91_KN-E-000001.md | 项目一：构建 RAG 问答系统 | L1 |
| 第92章 | ch92_KN-E-000002.md | 项目二：构建 ReAct Agent | L2 |
| 第93章 | ch93_KN-E-000003.md | 项目三：设计 Supervisor-Worker 多 Agent 系统 | L2-L3 |
| 第94章 | ch94_KN-E-000004.md | 项目四：AI 系统安全加固 | L3 |
| 第95章 | ch95_KN-E-000005.md | 项目五：生产级 Agent Harness | L3 |

---

## 问题汇总

### ⚠️ 需要修复的问题

| 优先级 | 问题类型 | 涉及章节 | 说明 |
|--------|---------|---------|------|
| 高 | 标题编号错误 | ch78 | 文件是第78章，但章内标题写的是"第77章" |
| 高 | 无独立标题 | ch90 | Multi-tenancy 代码延伸，无章节标题 |
| 中 | 主题重复 | ch33 / ch45 | 都叫 Tool Injection，应差异化：攻击面 vs MCP防护 |
| 中 | 主题重复 | ch41 / ch57 | 都叫 Fine-tuning，应差异化：进阶篇 vs 基础篇 |
| 中 | 主题重复 | ch77 / ch78 | 都叫 AI Testing Pyramid，需差异化内容 |
| 中 | 主题重复 | ch38 / ch80 | 都是 A2A Protocol，应差异化：协议规范 vs 工程实现 |
| 中 | 主题重复 | ch39 / ch60 | 都是 FCARS，应差异化：治理体系 vs 框架实现 |
| 中 | 主题重复 | ch40 / ch59 | 都是 Chaos Engineering，应差异化：理论 vs AI专项 |
| 低 | 末尾预告漂移 | ch11 | 预告 Multi-Agent，实际是 Agent Loop |
| 低 | 末尾预告漂移 | ch15 | 预告 Agent Governance，实际是 Embedding |
| 低 | 末尾预告漂移 | ch37 | 预告 知识图谱验证，实际是 A2A |
| 低 | 末尾预告漂移 | ch62 | 预告 Accountability，实际是 ReAct Pattern |
| 低 | 末尾预告漂移 | ch63 | 预告 Agent Loop，实际是 Supervisor-Worker |

### 🔁 重复主题说明

重复主题不一定需要删除。有些重复是有意义的——同一主题在不同层次（L1 vs L3）或不同视角（概念 vs 实践）下展开。建议保留内容，只做标题差异化区分，让读者知道两章的关系。

---

*生成工具：Claude Code | 项目：AI Education OS*
