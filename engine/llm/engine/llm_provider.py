"""
llm_provider.py
---------------
统一 LLM 抽象层：将 ChatGPT / DeepSeek 的 Playwright 网页自动化封装为标准接口。

接口层级：
  BaseLLM               — 最小抽象（chat / stream_chat / health_check / reset / close）
  ChatGPTBrowserLLM     — chatgpt_bot.py 适配器
  DeepSeekBrowserLLM    — deepseek_bot.py 适配器
  LLMRouter             — provider="both" 时并行调用两个实例

外部暴露：
  create_llm(provider, account)  → BaseLLM 实例
  serve_openai_api(llm, port)     → 启动 OpenAI Compatible FastAPI 服务
                                     POST /v1/chat/completions
                                     GET  /v1/models

使用示例：
  llm = create_llm("chatgpt", account="1")
  answer = llm.chat([{"role": "user", "content": "你好"}])

  # 作为 OpenAI 兼容服务运行
  serve_openai_api(llm, port=8765)
"""
from __future__ import annotations

import asyncio
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import AsyncGenerator, Generator


# ─────────────────────────────────────────────────────────────────────────────
# 数据类
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class LLMResponse:
    content: str
    tool_calls: list = field(default_factory=list)
    finish_reason: str = "stop"


# ─────────────────────────────────────────────────────────────────────────────
# 基类
# ─────────────────────────────────────────────────────────────────────────────

class BaseLLM(ABC):
    """统一大模型接口。子类只需实现 _raw_invoke 即可。"""

    @abstractmethod
    def _raw_invoke(self, prompt: str) -> str:
        """向底层 LLM 发送单条 Prompt，返回完整回复文本。同步阻塞。"""

    def chat(self, messages: list[dict]) -> str:
        """ChatCompletion 风格接口：接受 messages 列表，返回 assistant 文本。"""
        prompt = _messages_to_prompt(messages)
        return self._raw_invoke(prompt)

    def chat_response(self, messages: list[dict]) -> LLMResponse:
        """返回 LLMResponse 对象（content + tool_calls）。"""
        content = self.chat(messages)
        tool_calls = _extract_tool_calls(content)
        clean = _strip_tool_calls(content) if tool_calls else content
        return LLMResponse(content=clean, tool_calls=tool_calls)

    def stream_chat(self, messages: list[dict]) -> Generator[str, None, None]:
        """伪流式输出：在底层回复到达前轮询页面，实时 yield 增量文本。
        子类可覆盖以实现真正的流式抓取。"""
        content = self.chat(messages)
        # 简单实现：按句子分段 yield
        buf = ""
        for ch in content:
            buf += ch
            if ch in ("。", "！", "？", "\n") and len(buf) > 20:
                yield buf
                buf = ""
        if buf:
            yield buf

    async def async_chat(self, messages: list[dict]) -> str:
        """异步包装（在线程池中运行同步 chat）。"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.chat, messages)

    async def async_stream_chat(
        self, messages: list[dict]
    ) -> AsyncGenerator[str, None]:
        """异步伪流式输出。"""
        loop = asyncio.get_event_loop()
        queue: asyncio.Queue = asyncio.Queue()

        def _run():
            for chunk in self.stream_chat(messages):
                loop.call_soon_threadsafe(queue.put_nowait, chunk)
            loop.call_soon_threadsafe(queue.put_nowait, None)

        threading.Thread(target=_run, daemon=True).start()
        while True:
            chunk = await queue.get()
            if chunk is None:
                break
            yield chunk

    def health_check(self) -> bool:
        """检查底层浏览器/页面是否就绪。默认实现：始终返回 True。"""
        return True

    def reset_conversation(self) -> None:
        """开启新会话（清除上下文）。"""

    def new_session(self) -> None:
        """重启底层浏览器。"""

    def close(self) -> None:
        """关闭底层资源。"""


# ─────────────────────────────────────────────────────────────────────────────
# ChatGPT 适配器
# ─────────────────────────────────────────────────────────────────────────────

class ChatGPTBrowserLLM(BaseLLM):
    """封装 chatgpt_bot.py 的 Playwright 自动化。

    所有 Playwright 操作在专用 worker 线程里执行——该线程永远没有 asyncio loop，
    避免 Windows ProactorEventLoop 污染导致的 "Playwright Sync API inside asyncio loop" 错误。
    """

    def __init__(self, account: str = "1"):
        self._account = account
        self._playwright = None
        self._ctx = None
        self._page = None
        self._chrome_proc = None
        self._lock = threading.Lock()

        # 专用 Playwright worker 线程：所有 page 操作只在这个线程里执行
        import queue as _queue
        self._task_queue: _queue.Queue = _queue.Queue()
        self._worker = threading.Thread(target=self._worker_loop, daemon=True,
                                        name=f"chatgpt-playwright-{account}")
        self._worker.start()

    def _worker_loop(self) -> None:
        """专用线程主循环：从 queue 取 (fn, result_holder) 并执行，永不设置 asyncio loop。"""
        import asyncio as _asyncio
        try:
            _asyncio.set_event_loop(None)
        except Exception:
            pass
        while True:
            try:
                item = self._task_queue.get()
                if item is None:
                    break  # shutdown signal
                fn, result_holder = item
                try:
                    result_holder[0] = fn()
                except Exception as e:
                    result_holder[1] = e
                finally:
                    result_holder[2].set()  # signal done
            except Exception:
                pass

    def _run_in_worker(self, fn, timeout: int = 700):
        """在 worker 线程里运行 fn()，阻塞等待结果，timeout 秒后抛出 TimeoutError。"""
        import threading as _th
        done_event = _th.Event()
        result_holder = [None, None, done_event]  # [result, exception, event]
        self._task_queue.put((fn, result_holder))
        if not done_event.wait(timeout=timeout):
            raise TimeoutError(f"ChatGPT worker 超时（{timeout}秒）")
        if result_holder[1] is not None:
            raise result_holder[1]
        return result_holder[0]

    # ── 懒启动 ──────────────────────────────────────────────────────────────

    def _ensure_browser(self) -> None:
        import chatgpt_bot as bot

        # 任何 Playwright sync API 调用都不能在有 running asyncio loop 的线程中执行，
        # 包括 _page.url / _page.is_closed() 等已有 page 的检查，因此无条件清除
        try:
            asyncio.set_event_loop(None)
        except Exception:
            pass

        # 已有浏览器：检查页面是否仍然可用
        if self._page is not None:
            try:
                if self._page.is_closed():
                    raise RuntimeError("page closed")
                url = self._page.url or ""
                if any(k in url for k in ("login", "auth/", "signin")):
                    print(f"  [Browser] ChatGPT 页面跳到登录页，重新导航...")
                    self._page.goto("https://chatgpt.com", timeout=30000)
                    self._page.wait_for_load_state("domcontentloaded", timeout=20000)
                return
            except Exception as e:
                print(f"  [Browser] ChatGPT 页面失效（{e}），重新打开浏览器...")
                self._reset_browser()

        from playwright.sync_api import sync_playwright

        account_dir = bot.ACCOUNTS.get(self._account)
        if not account_dir:
            raise ValueError(f"ChatGPT 账号 {self._account} 不存在")

        self._playwright = sync_playwright().start()
        result = bot.open_browser(self._playwright, account_dir)
        # open_browser 返回 (browser/ctx, ctx, page, chrome_proc)
        _, self._ctx, self._page, self._chrome_proc = result

    # ── BaseLLM 实现 ─────────────────────────────────────────────────────────

    def _raw_invoke(self, prompt: str) -> str:
        def _do():
            import chatgpt_bot as bot
            with self._lock:
                for attempt in range(2):
                    try:
                        self._ensure_browser()
                        msg_before = bot.get_assistant_msg_count(self._page)
                        bot.send_prompt(self._page, prompt)
                        answer = bot.wait_for_answer(self._page, min_msg_count=msg_before + 1)
                        return answer or ""
                    except Exception as e:
                        err_str = str(e)
                        is_cdp_error = any(kw in err_str.lower() for kw in
                                           ("closed", "target", "context", "cdp 连接断开"))
                        if is_cdp_error and attempt == 0:
                            print(f"  🔄 ChatGPT 浏览器连接断开，重启后重试... ({err_str[:80]})")
                            self._reset_browser()
                            continue
                        raise
                return ""
        return self._run_in_worker(_do)

    def chat_multipart(self, system_prompt: str, user_message: str,
                       chunk_size: int = 12000) -> str:
        """在专用 worker 线程里运行所有 Playwright 操作，避免 asyncio loop 污染。"""
        return self._run_in_worker(
            lambda: self._chat_multipart_sync(system_prompt, user_message, chunk_size),
            timeout=900,
        )

    def _chat_multipart_sync(self, system_prompt: str, user_message: str,
                             chunk_size: int = 12000) -> str:
        """
        等待模式多段发送：将超长内容拆成 ≤chunk_size 的段，
        每段用「这是第N部分，共M部分」等待模式包装，最后发 ===START=== 触发生成。
        总长度不超过 chunk_size 时也走多段发送（system prompt 作为第1段），
        保证 ChatGPT 处于正确的"准备写长文"状态，避免单次发送导致输出截断。
        生成完后若检测到内容截断（缺少 Part 15），自动追问最多 3 次继续。
        """
        import re
        import chatgpt_bot as bot

        def _is_truncated_inner(text: str) -> bool:
            return len(re.findall(
                r'(?:^|\n)(?:##\s*)?(?:\*\*)?Part\s*\d+(?:\*\*)?[\s：:：]', text
            )) < 15

        def _count_parts_inner(text: str) -> int:
            return len(re.findall(
                r'(?:^|\n)(?:##\s*)?(?:\*\*)?Part\s*\d+(?:\*\*)?[\s：:：]', text
            ))

        first_chunk = f"[系统指令]\n{system_prompt}"
        total_chars = len(first_chunk) + len(user_message)

        # 内容短时直接单段发送，不走多段等待模式（避免ack干扰）
        if total_chars <= chunk_size:
            print(f"  [单段发送] 总长{total_chars}字符 ≤ {chunk_size}，直接单段发送...")
            with self._lock:
                for attempt in range(2):
                    try:
                        self._ensure_browser()
                        combined = first_chunk + "\n\n" + user_message
                        msg_before = bot.get_assistant_msg_count(self._page)
                        bot.send_prompt(self._page, combined, new_conversation=True)
                        print(f"  [单段发送] 等待新回复（当前{msg_before}条消息，需≥{msg_before+1}条）...")
                        answer = bot.wait_for_answer(self._page, min_msg_count=msg_before + 1) or ""
                        import chatgpt_bot as _cgb
                        if str(answer).strip() == "FREE_QUOTA_EXCEEDED" or "FREE_QUOTA_EXCEEDED" in str(answer):
                            raise _cgb.SessionExpired("单段回复 FREE_QUOTA_EXCEEDED，切换账号")
                        if "CHATGPT_ERROR" in str(answer) or str(answer).strip() == "CHATGPT_ERROR":
                            raise _cgb.SessionExpired("单段回复 CHATGPT_ERROR")
                        if str(answer).strip() == "RATE_LIMITED":
                            print(f"  ⚠️  单段回复 RATE_LIMITED，等待30秒后重试...")
                            import time as _time; _time.sleep(30)
                            raise Exception("单段回复 RATE_LIMITED，触发重试")
                        # 截断检测：缺 Part 则追问继续
                        all_parts = [answer]
                        for cont_round in range(3):
                            combined_text = "\n".join(all_parts)
                            if not _is_truncated_inner(combined_text):
                                break
                            parts_found = _count_parts_inner(combined_text)
                            missing = [str(i) for i in range(1, 16)
                                       if not re.search(rf'Part\s*{i}[\s：:：]', combined_text)]
                            cont_prompt = (
                                f"⚠️ 输出截断（{len(combined_text)}字符，{parts_found}/15 Parts），"
                                f"第{cont_round+1}次追问继续..."
                            )
                            print(f"    ⚠️  {cont_prompt}")
                            if missing:
                                cont_msg = (
                                    f"请继续输出剩余的 Part，从断点之后接续（不重复已有内容），"
                                    f"直到 Part 15 完整结束。\n\n"
                                    f"缺少的Part: {', '.join(missing)}\n\n"
                                    f"---（已输出的最后部分）---\n{combined_text[-500:]}\n"
                                    f"---（请从这里之后继续）---"
                                )
                            else:
                                break
                            msg_before2 = bot.get_assistant_msg_count(self._page)
                            bot.send_prompt(self._page, cont_msg)
                            cont_answer = bot.wait_for_answer(self._page, min_msg_count=msg_before2 + 1) or ""
                            if str(cont_answer).strip() == "FREE_QUOTA_EXCEEDED":
                                raise _cgb.SessionExpired("追问回复 FREE_QUOTA_EXCEEDED，切换账号")
                            if str(cont_answer).strip() == "RATE_LIMITED":
                                print(f"  ⚠️  追问回复 RATE_LIMITED，停止追问")
                                break
                            if cont_answer and "CHATGPT_ERROR" not in cont_answer:
                                all_parts.append(cont_answer)
                            else:
                                break
                        return "\n".join(all_parts)
                    except Exception as e:
                        err_str = str(e)
                        is_cdp = any(kw in err_str.lower() for kw in ("closed", "target", "context", "cdp"))
                        if is_cdp and attempt == 0:
                            print(f"  🔄 ChatGPT 连接断开，重启后重试...")
                            self._reset_browser()
                            continue
                        raise
            return ""

        # 把 user_message 按 chunk_size 分段（仅在内容真的超长时走多段）
        user_chunks: list[str] = []
        current_lines: list[str] = []
        current_len = 0

        for line in user_message.splitlines(keepends=True):
            if current_len + len(line) > chunk_size and current_lines:
                user_chunks.append("".join(current_lines))
                current_lines = [line]
                current_len = len(line)
            else:
                current_lines.append(line)
                current_len += len(line)
        if current_lines:
            user_chunks.append("".join(current_lines))

        # 所有段：system_prompt 段 + user_message 段
        all_chunks = [first_chunk] + user_chunks
        total = len(all_chunks)
        print(f"  [多段发送] 共 {total} 段（system+{len(user_chunks)} user），总长约 {total_chars} 字符")

        def _is_truncated(text: str) -> bool:
            """检测章节输出是否被截断（缺少 Part 15 即认为不完整）。"""
            import re
            # 匹配多种格式: ## Part 1, ## Part 1：, ## Part 1:, Part 1：, **Part 1**等
            parts_found = len(re.findall(
                r'(?:^|\n)(?:##\s*)?(?:\*\*)?Part\s*\d+(?:\*\*)?[\s：:：]',
                text
            ))
            if parts_found < 15:
                # 二次检测：直接搜索 Part 数字
                nums = re.findall(r'Part\s*(\d+)', text)
                if nums:
                    parts_found = len(set(nums))
            return parts_found < 15

        with self._lock:
            for attempt in range(2):
                try:
                    self._ensure_browser()

                    msg_count_before_last = 0  # 发最后段前的 assistant 消息数
                    for i, chunk in enumerate(all_chunks):
                        part_num = i + 1
                        is_last = (i == len(all_chunks) - 1)
                        if is_last:
                            # 记录发送前消息数，用于 wait_for_answer 等待新回复出现
                            msg_count_before_last = bot.get_assistant_msg_count(self._page)
                            # 最后一段：末尾附上 ===START=== 一起发，触发生成
                            wait_header = (
                                f"这是第{part_num}部分，共{total}部分。\n\n"
                                "当前部分内容如下：\n\n"
                            )
                            full_chunk = wait_header + chunk + "\n\n===START===\n以上是完整内容。请现在开始执行第1段中的指令，直接输出完整的 Markdown 章节内容。"
                            print(f"  [多段发送] 第 {part_num}/{total} 段（最后段+START，{len(full_chunk)} 字符）...")
                            bot.send_prompt(self._page, full_chunk, new_conversation=(i == 0))
                        else:
                            wait_header = (
                                f"这是第{part_num}部分，共{total}部分。\n\n"
                                "不要回答。不要分析。不要总结。不要开始执行。\n"
                                "请仅回复：收到，请继续发送下一部分。\n\n"
                                "当前部分内容如下：\n\n"
                            )
                            full_chunk = wait_header + chunk
                            print(f"  [多段发送] 第 {part_num}/{total} 段（{len(full_chunk)} 字符）...")
                            bot.send_prompt(self._page, full_chunk, new_conversation=(i == 0))
                            ack = bot.wait_for_answer(self._page, ack_only=True)
                            print(f"  [多段发送] 确认: {str(ack)[:80]}")
                            # session 过期：ack 返回 CHATGPT_ERROR，立即抛出让外层切换账号
                            if str(ack).strip() in ("CHATGPT_ERROR", "") or "CHATGPT_ERROR" in str(ack):
                                import chatgpt_bot as _cgb
                                raise _cgb.SessionExpired(
                                    f"第{part_num}段 ack 返回 CHATGPT_ERROR，session 已过期"
                                )
                            time.sleep(1)

                    # min_msg_count = 发送前数量+1，确保等到真正的新回复出现
                    min_count = msg_count_before_last + 1 if msg_count_before_last > 0 else 0
                    print(f"  [多段发送] 等待新回复（当前{msg_count_before_last}条消息，需≥{min_count}条）...")
                    answer = bot.wait_for_answer(self._page, min_msg_count=min_count) or ""
                    # 最后一段回复是 CHATGPT_ERROR → session 过期，立即切换账号
                    if "CHATGPT_ERROR" in str(answer) or str(answer).strip() == "CHATGPT_ERROR":
                        import chatgpt_bot as _cgb
                        raise _cgb.SessionExpired(
                            f"最后段回复 CHATGPT_ERROR，session 已过期"
                        )

                    # ── 截断检测：缺 Part 则追问继续 ─────────────────────────
                    all_parts = [answer]
                    for cont_round in range(3):
                        combined = "\n".join(all_parts)
                        if not _is_truncated(combined):
                            break
                        import re as _re
                        parts_found = len(_re.findall(r'## Part\s*\d+', combined))
                        print(f"  ⚠️  输出截断（{len(combined)} 字符，{parts_found}/15 Parts），第{cont_round+1}次追问继续...")
                        time.sleep(3)
                        tail = combined[-800:] if len(combined) > 800 else combined
                        cont_prompt = (
                            "请继续输出剩余的 Part，从断点之后接续（不重复已有内容），"
                            "直到 Part 15 完整结束。\n\n"
                            "---（已输出的最后部分）---\n"
                            f"{tail}\n"
                            "---（请从这里之后继续）---\n"
                        )
                        bot.send_prompt(self._page, cont_prompt, new_conversation=False)
                        cont = bot.wait_for_answer(self._page) or ""
                        if not cont.strip() or cont == answer:
                            print(f"  ⚠️  追问无新内容，停止")
                            break
                        all_parts.append(cont)
                        answer = cont

                    return "\n".join(all_parts)

                except Exception as e:
                    err_str = str(e)
                    is_cdp_error = any(kw in err_str.lower() for kw in
                                       ("closed", "target", "context", "cdp 连接断开"))
                    if is_cdp_error and attempt == 0:
                        print(f"  🔄 ChatGPT 连接断开，重启后重试... ({err_str[:80]})")
                        self._reset_browser()  # 仅重置浏览器，不停止 worker 线程
                        continue
                    raise
        return ""

    def stream_chat(self, messages: list[dict]) -> Generator[str, None, None]:
        """stream_chat 通过 _raw_invoke 实现（同步收集结果后伪流式 yield）。"""
        content = self.chat(messages)
        for ch in content:
            yield ch

    def health_check(self) -> bool:
        def _do():
            if self._page is None:
                return False
            return not self._page.is_closed()
        try:
            return self._run_in_worker(_do, timeout=10)
        except Exception:
            return False

    def reset_conversation(self) -> None:
        def _do():
            import chatgpt_bot as bot
            if self._page:
                try:
                    bot._new_conversation(self._page)
                except Exception:
                    pass
        try:
            self._run_in_worker(_do, timeout=30)
        except Exception:
            pass

    def close(self) -> None:
        """章节结束时调用：只开启新对话，不关闭浏览器。"""
        def _do():
            import chatgpt_bot as bot
            if self._page and not self._page.is_closed():
                try:
                    bot._new_conversation(self._page)
                    print("  [Browser] 开启新对话（浏览器保持运行）")
                except Exception:
                    pass
        try:
            self._run_in_worker(_do, timeout=30)
        except Exception:
            pass

    def _reset_browser(self) -> None:
        """仅关闭浏览器进程，不停止 worker 线程（在 worker 线程内调用）。"""
        try:
            if self._ctx:
                self._ctx.close()
        except Exception:
            pass
        try:
            if self._chrome_proc:
                self._chrome_proc.terminate()
                try:
                    self._chrome_proc.wait(timeout=8)
                except Exception:
                    pass
        except Exception:
            pass
        try:
            if self._playwright:
                self._playwright.stop()
        except Exception:
            pass
        self._page = self._ctx = self._playwright = self._chrome_proc = None

    def shutdown(self) -> None:
        """真正关闭浏览器进程（程序退出时调用）。"""
        try:
            self._run_in_worker(self._reset_browser, timeout=30)
        except Exception:
            pass
        # 停止 worker 线程
        try:
            self._task_queue.put(None)
        except Exception:
            pass


# ─────────────────────────────────────────────────────────────────────────────
# DeepSeek 适配器
# ─────────────────────────────────────────────────────────────────────────────

class DeepSeekBrowserLLM(BaseLLM):
    """封装 deepseek_bot.py 的 Playwright 自动化。"""

    def __init__(self, account: str = "1"):
        self._account = account
        self._playwright = None
        self._ctx = None
        self._page = None
        self._chrome_proc = None
        self._lock = threading.Lock()

    def _ensure_browser(self) -> None:
        import deepseek_bot as bot

        # 任何 Playwright sync API 调用都不能在有 running asyncio loop 的线程中执行，
        # 包括 _page.url / _page.is_closed() 等已有 page 的检查，因此无条件清除
        try:
            asyncio.set_event_loop(None)
        except Exception:
            pass

        # 已有浏览器：检查页面是否仍然可用（未关闭、未跳登录页）
        if self._page is not None:
            try:
                if self._page.is_closed():
                    raise RuntimeError("page closed")
                url = self._page.url or ""
                # 跳到登录页或空白页：需要重新导航
                if any(k in url for k in ("login", "signin", "auth/", "about:blank", "".__class__())):
                    print(f"  [Browser] DeepSeek 页面跳到 {url[:60]}，重新导航...")
                    self._page.goto("https://chat.deepseek.com", timeout=30000)
                    self._page.wait_for_load_state("domcontentloaded", timeout=20000)
                return
            except Exception as e:
                print(f"  [Browser] DeepSeek 页面失效（{e}），重新打开浏览器...")
                self._reset_browser()

        from playwright.sync_api import sync_playwright

        account_dir = bot.ACCOUNTS.get(self._account)
        if not account_dir:
            raise ValueError(f"DeepSeek 账号 {self._account} 不存在")

        self._playwright = sync_playwright().start()
        result = bot.open_browser(self._playwright, account_dir)
        _, self._ctx, self._page, self._chrome_proc = result

    def _raw_invoke(self, prompt: str) -> str:
        # 检测是否在 asyncio 事件循环中（Python 3.10+ 在主线程默认有 loop）
        # Playwright sync API 不能在 asyncio loop 里调用，改到独立线程执行
        try:
            loop = asyncio.get_running_loop()
            in_async = loop is not None
        except RuntimeError:
            in_async = False

        if in_async:
            result_holder = [None, None]  # [result, exception]

            def _run_in_thread():
                try:
                    result_holder[0] = self._raw_invoke_sync(prompt)
                except Exception as e:
                    result_holder[1] = e

            t = threading.Thread(target=_run_in_thread, daemon=True)
            t.start()
            t.join(timeout=600)
            if result_holder[1] is not None:
                raise result_holder[1]
            return result_holder[0] or ""
        else:
            return self._raw_invoke_sync(prompt)

    def _raw_invoke_sync(self, prompt: str) -> str:
        import deepseek_bot as bot
        with self._lock:
            for attempt in range(2):
                try:
                    self._ensure_browser()
                    bot.send_prompt(self._page, prompt)
                    answer = bot.wait_for_answer(self._page)
                    return answer or ""
                except Exception as e:
                    if "BrowserRestartNeeded" in type(e).__name__ and attempt == 0:
                        print(f"  🔄 浏览器需要重启，关闭后重试... ({e})")
                        self.close()
                        self._page = self._ctx = self._playwright = self._chrome_proc = None
                        continue
                    raise
            return ""

    def stream_chat(self, messages: list[dict]) -> Generator[str, None, None]:
        import deepseek_bot as bot
        prompt = _messages_to_prompt(messages)
        with self._lock:
            self._ensure_browser()
            bot.send_prompt(self._page, prompt)
            prev = ""
            deadline = time.time() + 300
            while time.time() < deadline:
                time.sleep(1.5)   # DeepSeek 思考模式有长停顿，放宽
                current = bot.get_last_answer(self._page)
                if current and current != prev:
                    delta = current[len(prev):]
                    if delta:
                        yield delta
                    prev = current
                if _is_deepseek_done(self._page):
                    final = bot.get_last_answer(self._page)
                    if final and final != prev:
                        yield final[len(prev):]
                    break

    def health_check(self) -> bool:
        try:
            if self._page is None:
                return False
            return not self._page.is_closed()
        except Exception:
            return False

    def reset_conversation(self) -> None:
        import deepseek_bot as bot
        if self._page:
            try:
                bot.new_conversation(self._page)
            except Exception:
                pass

    def close(self) -> None:
        """
        章节结束时调用：只开启新对话，不关闭浏览器。
        浏览器进程保持常驻，避免每章重新启动触发安全检测或 session 失效。
        真正退出时调用 shutdown()。
        """
        import deepseek_bot as bot
        if self._page and not self._page.is_closed():
            try:
                bot.new_conversation(self._page)
                print("  [Browser] DeepSeek 开启新对话（浏览器保持运行）")
            except Exception:
                pass

    def shutdown(self) -> None:
        """真正关闭浏览器进程（程序退出时调用）。"""
        try:
            if self._ctx:
                self._ctx.close()
        except Exception:
            pass
        try:
            if self._chrome_proc:
                self._chrome_proc.terminate()
                try:
                    self._chrome_proc.wait(timeout=8)
                except Exception:
                    pass
        except Exception:
            pass
        try:
            if self._playwright:
                self._playwright.stop()
        except Exception:
            pass
        self._page = self._ctx = self._playwright = self._chrome_proc = None


# ─────────────────────────────────────────────────────────────────────────────
# 路由器：provider="both" 时并行调用两个实例
# ─────────────────────────────────────────────────────────────────────────────

class LLMRouter(BaseLLM):
    """并行调用多个 LLM 实例，返回最快的那个。"""

    def __init__(self, llms: list[BaseLLM]):
        self._llms = llms

    def _raw_invoke(self, prompt: str) -> str:
        results: list[str | None] = [None] * len(self._llms)
        errors: list[Exception | None] = [None] * len(self._llms)

        def _call(i: int, llm: BaseLLM) -> None:
            try:
                results[i] = llm._raw_invoke(prompt)
            except Exception as e:
                errors[i] = e

        threads = [
            threading.Thread(target=_call, args=(i, llm), daemon=True)
            for i, llm in enumerate(self._llms)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # 优先返回第一个成功结果
        for r in results:
            if r is not None:
                return r
        # 全部失败
        raise RuntimeError(f"所有 LLM 均失败: {errors}")

    def health_check(self) -> bool:
        return any(llm.health_check() for llm in self._llms)

    def close(self) -> None:
        for llm in self._llms:
            try:
                llm.close()
            except Exception:
                pass


# ─────────────────────────────────────────────────────────────────────────────
# 工厂函数
# ─────────────────────────────────────────────────────────────────────────────

def create_llm(provider: str = "chatgpt", account: str = "1") -> BaseLLM:
    """
    创建 LLM 实例。

    provider:
      "chatgpt"  → ChatGPTBrowserLLM
      "deepseek" → DeepSeekBrowserLLM
      "both"     → LLMRouter（并行）

    account: 账号编号（"1"~"4"），或 "auto" 时外层自行选择
    """
    if provider == "chatgpt":
        return ChatGPTBrowserLLM(account=account)
    elif provider == "deepseek":
        return DeepSeekBrowserLLM(account=account)
    elif provider == "both":
        return LLMRouter([
            ChatGPTBrowserLLM(account=account),
            DeepSeekBrowserLLM(account=account),
        ])
    else:
        raise ValueError(f"未知 provider: {provider}（可选 chatgpt/deepseek/both）")


# ─────────────────────────────────────────────────────────────────────────────
# OpenAI Compatible API 服务
# ─────────────────────────────────────────────────────────────────────────────

def serve_openai_api(llm: BaseLLM, port: int = 8765, host: str = "127.0.0.1") -> None:
    """
    启动 OpenAI 兼容 HTTP 服务（阻塞）。

    外部工具（OpenHands / Aider / LangGraph / AutoGen）可通过以下配置接入：
      base_url = "http://127.0.0.1:8765/v1"
      api_key  = "browser-llm"
      model    = "browser-llm"

    支持接口：
      POST /v1/chat/completions  （普通 + stream=True）
      GET  /v1/models
    """
    try:
        from fastapi import FastAPI
        from fastapi.responses import JSONResponse, StreamingResponse
        import uvicorn
    except ImportError:
        raise ImportError("serve_openai_api 需要 fastapi 和 uvicorn：pip install fastapi uvicorn")

    app = FastAPI(title="BrowserLLM OpenAI Compatible API")

    # ── GET /v1/models ────────────────────────────────────────────────────────
    @app.get("/v1/models")
    def list_models():
        return JSONResponse({
            "object": "list",
            "data": [{"id": "browser-llm", "object": "model", "owned_by": "studyathena"}],
        })

    # ── POST /v1/chat/completions ─────────────────────────────────────────────
    @app.post("/v1/chat/completions")
    async def chat_completions(body: dict):
        messages = body.get("messages", [])
        stream = body.get("stream", False)
        model = body.get("model", "browser-llm")

        if stream:
            async def _event_stream():
                import json
                chunk_id = f"chatcmpl-{int(time.time())}"
                async for delta in llm.async_stream_chat(messages):
                    data = {
                        "id": chunk_id,
                        "object": "chat.completion.chunk",
                        "model": model,
                        "choices": [{
                            "index": 0,
                            "delta": {"role": "assistant", "content": delta},
                            "finish_reason": None,
                        }],
                    }
                    yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
                # 结束标记
                done = {
                    "id": chunk_id,
                    "object": "chat.completion.chunk",
                    "model": model,
                    "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
                }
                yield f"data: {json.dumps(done)}\n\n"
                yield "data: [DONE]\n\n"

            return StreamingResponse(_event_stream(), media_type="text/event-stream")

        # 非流式
        content = await llm.async_chat(messages)
        return JSONResponse({
            "id": f"chatcmpl-{int(time.time())}",
            "object": "chat.completion",
            "model": model,
            "choices": [{
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        })

    # ── GET /health ────────────────────────────────────────────────────────────
    @app.get("/health")
    def health():
        return {"status": "ok" if llm.health_check() else "degraded"}

    print(f"[BrowserLLM] OpenAI Compatible API 启动：http://{host}:{port}/v1")
    uvicorn.run(app, host=host, port=port, log_level="warning")


# ─────────────────────────────────────────────────────────────────────────────
# 内部工具函数
# ─────────────────────────────────────────────────────────────────────────────

def _messages_to_prompt(messages: list[dict]) -> str:
    """把 ChatCompletion messages 列表拼成单条 Prompt 字符串。"""
    parts = []
    for m in messages:
        role = m.get("role", "user")
        content = m.get("content", "")
        if role == "system":
            parts.append(f"[系统指令]\n{content}")
        elif role == "assistant":
            parts.append(f"[上一轮回复]\n{content}")
        else:
            parts.append(content)
    return "\n\n".join(parts)


def _extract_tool_calls(text: str) -> list:
    """从回复文本中解析 ACTION/ARGS 格式的 tool_calls（可选功能）。

    格式示例：
      ACTION: read_file
      ARGS: main.py
    """
    import re
    tool_calls = []
    pattern = re.compile(
        r"ACTION:\s*(\w+)\s*\nARGS:\s*(.+?)(?=\nACTION:|\Z)", re.DOTALL
    )
    for m in pattern.finditer(text):
        tool_calls.append({"name": m.group(1).strip(), "args": m.group(2).strip()})
    return tool_calls


def _strip_tool_calls(text: str) -> str:
    """移除文本中的 ACTION/ARGS 块，保留其余内容。"""
    import re
    return re.sub(r"ACTION:\s*\w+\s*\nARGS:\s*.+?(?=\nACTION:|\Z)", "", text, flags=re.DOTALL).strip()


def _is_chatgpt_done(page) -> bool:
    """检测 ChatGPT 是否已停止生成。"""
    try:
        # 发送按钮可见 = 生成完毕
        selectors = [
            'button[data-testid="send-button"]',
            'button[aria-label="Send prompt"]',
            'button[aria-label="发送提示"]',
        ]
        for sel in selectors:
            loc = page.locator(sel)
            if loc.count() > 0 and loc.first.is_visible(timeout=200):
                return True
        # 停止按钮不可见 = 生成完毕
        stop = page.locator('[data-testid="stop-button"]')
        if stop.count() == 0:
            return True
    except Exception:
        pass
    return False


def _is_deepseek_done(page) -> bool:
    """检测 DeepSeek 是否已停止生成。"""
    try:
        stop_sels = [
            'button[aria-label*="Stop" i]',
            'button:has-text("停止生成")',
            '[data-testid="stop-button"]',
        ]
        for sel in stop_sels:
            loc = page.locator(sel)
            if loc.count() > 0 and loc.first.is_visible(timeout=200):
                return False  # 停止按钮可见 = 仍在生成
        return True
    except Exception:
        return False
