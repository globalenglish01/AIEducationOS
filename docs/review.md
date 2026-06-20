一、架构评审维度（即架构师必须掌握的 14 个架构域）
这两份文档合在一起，定义了一个 AI Native 架构师需要能独立评审的所有领域：

架构域	具体内容
系统架构	整体分层、模块边界、依赖关系
Agent 架构	无限循环防护、最大迭代次数、反思节点递归、工具调用失败退出条件、状态在并发请求间的隔离
Workflow 架构	状态持久化、断点续跑、失败恢复、Human-in-the-loop 流程
Prompt 架构	Prompt 版本管理、System Prompt 与 User Input 隔离、Prompt 模板化
Tool Calling 架构	工具封装规范、路径白名单/黑名单、沙箱限制、工具调用失败的降级处理
MCP 兼容性	MCP 协议适配能力
Memory 架构	短期/长期 Memory 设计、Memory 在多请求间的隔离
Evaluation 架构	Eval 数据集构建、回归评测流程、Agent 质量持续量化
Observability 架构	链路追踪（Tracing）、日志监控、LLM 可观测性
Security 架构	Agent 权限升级漏洞、Prompt Injection、Tool Injection、路径沙箱、密钥隔离
Multi-tenant 架构	用户数据隔离（IDOR 防护）、project_id 强制过滤
Scalability 架构	并发 Agent 支持、连接池管理、异步队列
Cost Optimization 架构	Token 成本分析、缓存策略、模型分级使用（大/小模型选型）、上下文裁剪
CI/CD 架构	AI 应用的持续集成/部署流程
二、安全能力（原 RFC-001 完全缺失，现在有具体内容）
Agent 权限升级漏洞（必须能发现并修复）：

Agent 能否读取 .env 文件？
Agent 能否读取 .git/ 目录？
Agent 能否读取 ~/.ssh/？
Agent 能否执行任意 shell 命令？
Agent 能否读取平台自身源码？
Agent 能否访问数据库连接字符串？
Agent 能否访问 API Key？
文件读取路径是否有沙箱限制？
工具是否有路径白名单/黑名单？
Prompt Injection / Tool Injection：

System Prompt 与 User Input 隔离机制
被测网站内容注入恶意指令的防护
OWASP AI Security Top 10 知识
认证/授权：

JWT 校验覆盖率
IDOR（越权访问）防护
project_id 级别的数据隔离
三、可靠性工程（Chaos Engineering 能力）
架构师必须能预判并设计以下故障场景的应对：

故障场景	需要设计的能力
API 超时（>30s）	timeout 设置 + 用户友好提示
速率限制（429）	自动重试 + 账号轮换 + 降级策略
LLM 返回非法 JSON	输出解析容错 + fallback
Playwright 浏览器崩溃	浏览器进程恢复机制
数据库连接池耗尽	连接池监控 + 排队机制
Token 额度耗尽	成本预警 + 模型降级
用户关闭页面但 Agent 仍运行	Agent 生命周期管理
并发多用户同时触发 Agent	并发隔离 + 资源限制
Agent 无限循环	最大迭代次数 + 超时强制终止
四、Cost Optimization 能力（原 RFC-001 只提了一条）
现在有具体的技能点：

识别可缓存但未缓存的调用（相同 System Prompt 重复发送）
识别可用小模型替代的调用（分类/提取任务用了重型模型）
识别可用规则替代的调用（正则/模板能解决却用了 LLM）
识别上下文过长导致的浪费（整个 HTML 塞进 Prompt）
识别失败重试导致的重复计费
给出"成本下降 50%"和"成本下降 80%"的具体方案