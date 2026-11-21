#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AstrBot 人类式发言预算插件。

只做生成前提示，不做事后改写。按场景拆分预算：
- 群聊闲谈：一句 10～15 字，短反应优先；
- 被直接对话：20～30 字，正面回答；
- 任务/知识：按需展开，不强行压短。

同时按需提示 keep_silent、表情包兜底、反讽识别、生活经历边界等。

作者：AcceleratorYue
"""

from __future__ import annotations

from typing import Any

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.message_components import At, Reply
from astrbot.api.star import Context, Star

VERSION = "0.6.1"
LOG = "[ReplyBudget]"

DEFAULT_TASK_KEYWORDS = [
    "详细",
    "完整",
    "展开",
    "解释",
    "教程",
    "步骤",
    "代码",
    "排查",
    "分析",
    "对比",
    "为什么",
    "怎么实现",
    "帮我写",
    "查一下",
    "列出",
    "方案",
    "原理",
    "表格",
]

# 这些工具只用于判断“当前模型是否真的能调用”，不会凭空注册。
MEME_TOOL_NAMES = {"search_memes", "send_meme", "qq_react"}


class ReplyBudgetPlugin(Star):
    def __init__(self, context: Context, config: Any = None) -> None:
        super().__init__(context)
        self._config = config
        logger.info(f"{LOG} 插件 v{VERSION} 已加载")

    def _cfg(self, key: str, default: Any = None) -> Any:
        if self._config is None:
            return default
        try:
            return self._config.get(key, default)
        except Exception:
            return default

    def _bool(self, key: str, default: bool) -> bool:
        value = self._cfg(key, default)
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "on", "是", "开"}
        return default if value is None else bool(value)

    def _int(self, key: str, default: int, minimum: int = 0) -> int:
        try:
            value = int(self._cfg(key, default))
        except (TypeError, ValueError):
            return default
        return max(minimum, value)

    def _str(self, key: str, default: str) -> str:
        return str(self._cfg(key, default) or default).strip()

    def _list(self, key: str, default: list[str]) -> list[str]:
        raw = self._cfg(key, default)
        if not isinstance(raw, (list, tuple)):
            return list(default)
        out = [str(item).strip() for item in raw if str(item).strip()]
        return out or list(default)

    def _platform_enabled(self, event: AstrMessageEvent) -> bool:
        try:
            is_group = event.is_private_chat() is False
        except Exception:
            is_group = False
        key = "enable_in_groups" if is_group else "enable_in_private"
        return self._bool(key, True)

    def _debug(self, message: str) -> None:
        if self._bool("debug_log", False):
            logger.info(f"{LOG} {message}")

    # ---------------------------- 场景判断 ---------------------------- #

    @staticmethod
    def _message_chain(event: AstrMessageEvent) -> list[Any]:
        chain = getattr(getattr(event, "message_obj", None), "message", None)
        return chain if isinstance(chain, list) else []

    def _is_direct(self, event: AstrMessageEvent) -> bool:
        try:
            if event.is_private_chat():
                return True
        except Exception:
            pass
        if getattr(event, "is_at_or_wake_command", False):
            return True

        self_id = ""
        try:
            self_id = str(event.get_self_id() or "")
        except Exception:
            pass
        for component in self._message_chain(event):
            try:
                if isinstance(component, At):
                    if self_id and str(component.qq) == self_id:
                        return True
                elif isinstance(component, Reply):
                    if self_id and str(component.sender_id) == self_id:
                        return True
            except Exception:
                continue
        return False

    def _is_task(self, user_text: str) -> bool:
        lowered = str(user_text or "").casefold()
        return any(
            keyword.casefold() in lowered
            for keyword in self._list("task_keywords", DEFAULT_TASK_KEYWORDS)
        )

    def _mode(self, event: AstrMessageEvent, user_text: str) -> str:
        if self._is_task(user_text):
            return "task"
        if self._is_direct(event):
            return "direct"
        return "casual"

    @staticmethod
    def _tool_names(req: Any) -> set[str]:
        """从 ProviderRequest 读取当前真实可用的工具名。"""
        func_tool = getattr(req, "func_tool", None)
        if func_tool is None:
            return set()
        try:
            names = getattr(func_tool, "names", None)
            if callable(names):
                return {str(name) for name in names()}
        except Exception:
            pass
        if isinstance(func_tool, dict):
            return {str(name) for name in func_tool}
        if isinstance(func_tool, (list, tuple, set)):
            return {str(name) for name in func_tool}
        return set()

    # ---------------------------- 提示词 ---------------------------- #

    def _legacy_block(self) -> str:
        budget = self._int("soft_budget_chars", 60, minimum=10)
        return f"""<reply_budget>
本轮按真人日常聊天来，默认控制在 {budget} 个汉字左右。
日常闲聊优先短句、口语和省略；语法不完整没关系，只有对方明确要长内容、完整步骤或详细解释时才展开。
先给出自己的判断或态度，不要只复述、附和对方；人类的认同很少，“点赞/贴表情”已经是高程度认可。
如果这轮没有表达欲、插不上话，或少说更自然，可以少说或不接。
</reply_budget>"""

    def _chat_lines(
        self,
        target: int,
        maximum: int,
        has_keep_silent: bool,
        has_meme: bool,
        *,
        direct: bool,
    ) -> list[str]:
        if direct:
            intro = (
                f"对方在直接和你说话，也可能只是闲聊。默认一句 {target} 字左右，"
                f"最多 {maximum} 字；需要时正面回答。"
            )
            reaction = (
                "先给自己的判断或短反应；被明确提问时正面回答，但不要复述、"
                "不要逐条接话。"
            )
        else:
            intro = f"这是群聊闲谈。默认只发一句 {target} 字左右，最多 {maximum} 字。"
            reaction = (
                "先说自己怎么看或给一个短反应；不复述对方，不逐条接话。"
                if self._bool("prefer_own_view", True)
                else "给一个短反应就好，不要复述对方或逐条接话。"
            )

        lines = [
            intro,
            reaction,
            "看不懂梗、有歧义或容易说错时，短反应/表情包就好，不要硬解释。",
        ]
        if self._bool("use_meme_fallback", True) and has_meme:
            lines.append("需要反应时可以用 search_memes / send_meme / qq_react。")

        silence_mode = self._str("silence_mode", "conditional")
        if silence_mode != "off":
            if has_keep_silent:
                if direct:
                    if silence_mode == "aggressive":
                        lines.append(
                            "如果对方是骚扰、无意义或你完全不想接的对话，优先调用 keep_silent。"
                        )
                    else:
                        lines.append(
                            "如果对方是在骚扰、无意义或意义不明，可以调用 keep_silent；"
                            "正常直接提问则优先回复。"
                        )
                elif silence_mode == "aggressive":
                    lines.append("没有明确必要就别回复，优先调用 keep_silent。")
                else:
                    lines.append(
                        "没有表达欲、插不上话或少说更自然时，优先调用 keep_silent。"
                    )
            else:
                lines.append(
                    "没有表达欲或不想接时可以少说，不要为了参与硬找话说。"
                )

        lines.append(
            "不要频繁说“我同意/认同/说得对”；点赞/贴表情已经是很高程度的认可。"
        )
        extra: list[str] = []
        if self._bool("avoid_word_repetition", True):
            extra.append("一句话里尽量别重复同一个词")
        if self._bool("sarcasm_aware", True):
            extra.append("注意反讽，极端夸奖可能在阴阳")
        if self._bool("experience_guard", True):
            extra.append("没有真实经历别编细节，卖萌或不接比强答自然")
        if self._bool("knowledge_fallback", True):
            extra.append("讲知识先给结论，用聊天口吻")
        if extra:
            lines.append("；".join(extra) + "。")
        return lines

    def _task_lines(self) -> list[str]:
        return [
            "对方在要完整内容。按需要展开，不要为了短而省略步骤、代码或关键条件。",
            "先给结论，再按对方要求补充；保持聊天口吻，不要写成客服模板。",
            "不要输出 Markdown 标记：不要使用 **加粗**、*斜体*、- 分点、# 标题或表格；需要分步骤时用普通短句分行写。",
            "正常任务不要调用 keep_silent，必须给出内容；只有明显骚扰、无意义或恶意请求才可以沉默。",
        ]

    def _soft_budget_block(
        self, event: AstrMessageEvent | None = None, req: Any = None
    ) -> str:
        if not self._bool("human_speech_mode", True):
            return self._legacy_block()

        user_text = str(getattr(event, "message_str", "") or "") if event else ""
        mode = self._mode(event, user_text) if event else "casual"
        tools = self._tool_names(req)
        has_keep_silent = "keep_silent" in tools
        has_meme = bool(tools & MEME_TOOL_NAMES)

        if mode == "task":
            lines = self._task_lines()
        elif mode == "direct":
            target = self._int("direct_target_chars", 20, minimum=5)
            maximum = max(target, self._int("direct_max_chars", 30, minimum=10))
            lines = self._chat_lines(
                target, maximum, has_keep_silent, has_meme, direct=True
            )
        else:
            target = self._int("casual_target_chars", 12, minimum=3)
            maximum = max(target, self._int("casual_max_chars", 20, minimum=5))
            lines = self._chat_lines(
                target, maximum, has_keep_silent, has_meme, direct=False
            )
            try:
                active = bool(
                    event and event.get_extra("active_reply_triggered", False)
                )
            except Exception:
                active = False
            if active:
                lines.append(
                    "这轮是主动接话：只补一句最想说的，没必要的细节就省略。"
                )

        self._debug(
            f"注入模式={mode} target={target if mode != 'task' else '-'} "
            f"keep_silent={has_keep_silent} meme={has_meme}"
        )
        return "<reply_budget>\n" + "\n".join(lines) + "\n</reply_budget>"

    @filter.on_llm_request(priority=-100000)
    async def inject_soft_budget(self, event: AstrMessageEvent, req: Any) -> None:
        """在每个聊天请求的系统提示末尾追加当前场景的发言策略。

        使用较低优先级，确保它排在人格、工具提示和场景注入之后，
        避免被后续拼接的大段系统提示稀释。
        """
        if not self._bool("enable", True) or not self._platform_enabled(event):
            return
        try:
            current = str(getattr(req, "system_prompt", "") or "")
            block = self._soft_budget_block(event, req)
            if block in current:
                return
            req.system_prompt = f"{current}\n\n{block}".strip()
        except Exception:
            logger.exception(f"{LOG} 发言预算注入失败")
