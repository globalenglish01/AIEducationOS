# 如何在 AIEducationOS 中调用大模型

> 本项目**禁止直接调用 Claude API**。所有大模型调用必须通过本目录的封装（Browser LLM）。

---

## 快速开始

```python
from engine.llm.engine.llm import create_llm

# 创建 LLM 实例（使用 DeepSeek，账号1）
llm = create_llm("deepseek", account="1")

# 调用
answer = llm.chat([{"role": "user", "content": "你的问题"}])
print(answer)

# 用完必须关闭
llm.close()
```

---

## 可用提供商

| provider | 说明 |
|----------|------|
| `"deepseek"` | DeepSeek（推荐用于技术内容、代码生成） |
| `"chatgpt"` | ChatGPT（推荐用于教学设计、故事、润色） |
| `"both"` | 并行调用两者，返回最快结果 |

## 可用账号

账号 `"1"` ~ `"6"`，配置见 `accounts.json`。

---

## 核心方法

```python
# 同步调用（最常用）
answer: str = llm.chat(messages)

# 返回结构化对象（含 tool_calls、finish_reason）
response = llm.chat_response(messages)
content = response.content

# 流式输出
for chunk in llm.stream_chat(messages):
    print(chunk, end="", flush=True)

# 异步调用
answer = await llm.async_chat(messages)

# 健康检查
ok = llm.health_check()
```

## messages 格式

```python
messages = [
    {"role": "system", "content": "你是一位教学专家..."},
    {"role": "user",   "content": "请帮我改写这一章节..."},
]
```

---

## 在 AIEducationOS 中的约定

- `DeepSeek` → 用于技术内容生成、Demo 代码、知识节点草稿
- `ChatGPT` → 用于教学设计、生活例子、面试题、语言润色
- 所有 LLM 调用都通过 `engine/llm/engine/llm.py` 的 `create_llm()` 工厂函数

---

## 注意事项

1. 每次用完必须调用 `llm.close()` 释放 Playwright 浏览器资源
2. 建议用 `try/finally` 包裹
3. 如果遇到账号限速，换下一个账号（`account="2"` 等）
4. 不要在同一进程中同时创建太多 llm 实例（浏览器资源有限）
