import json
import asyncio
from loguru import logger
from app.runtime.provider.llm.adapter import llm_adapter
from app.utils.tool_executor import execute_tool_by_name
from app.runtime.plugin.skill.registry import SkillRegistry


def get_all_tools_schema() -> list[dict]:
    try:
        return SkillRegistry.get_openai_tools()
    except Exception as e:
        logger.warning(f"[ToolLoop] get_all_tools_schema failed: {e}")
        return []


# ─── 上下文压缩 ───────────────────────────────────────────────

def _estimate_messages_tokens(messages: list[dict]) -> int:
    """粗略估算 messages 的 token 数（中文约 1.5 字/token）"""
    total = 0
    for msg in messages:
        content = msg.get("content") or ""
        if isinstance(content, str):
            total += len(content)
        elif isinstance(content, list):
            for part in content:
                if isinstance(part, dict):
                    total += len(part.get("text", ""))
        for tc in msg.get("tool_calls", []):
            fn = tc.get("function", {})
            total += len(fn.get("name", "")) + len(fn.get("arguments", ""))
    return total // 2  # 粗略折算


def _compress_messages(messages: list[dict], max_tokens: int = 8000) -> list[dict]:
    """压缩 messages 历史，保留 system + 最近几轮对话

    策略：
      1. 始终保留第一条 system 消息
      2. 始终保留最近 2 轮完整对话（assistant + tool results）
      3. 更早的 tool 结果替换为摘要
      4. 更早的 assistant 消息（含 tool_calls）替换为简短描述
    """
    if _estimate_messages_tokens(messages) <= max_tokens:
        return messages

    if len(messages) <= 4:
        return messages

    # 分离 system 消息和其余消息
    system_msgs = []
    other_msgs = []
    for msg in messages:
        if msg.get("role") == "system" and not other_msgs:
            system_msgs.append(msg)
        else:
            other_msgs.append(msg)

    # 从末尾往前找最近 2 轮完整对话边界
    # 一轮 = assistant(含 tool_calls) + 对应的 tool 消息
    recent_boundary = len(other_msgs)
    rounds_found = 0
    for i in range(len(other_msgs) - 1, -1, -1):
        if other_msgs[i].get("role") == "assistant" and other_msgs[i].get("tool_calls"):
            rounds_found += 1
            if rounds_found >= 2:
                recent_boundary = i
                break

    # 压缩 recent_boundary 之前的消息
    compressed = []
    for i, msg in enumerate(other_msgs):
        if i >= recent_boundary:
            compressed.append(msg)
            continue

        role = msg.get("role", "")

        if role == "tool":
            # 旧 tool 结果压缩为一行摘要
            content = msg.get("content", "")
            summary = content[:80] + "..." if len(content) > 80 else content
            compressed.append({
                "role": "tool",
                "tool_call_id": msg.get("tool_call_id", ""),
                "content": f"[已压缩] {summary}",
            })
        elif role == "assistant" and msg.get("tool_calls"):
            # 旧 assistant 消息保留 tool_calls 但精简 arguments
            simplified_calls = []
            for tc in msg["tool_calls"]:
                fn = tc.get("function", {})
                simplified_calls.append({
                    "id": tc.get("id", ""),
                    "type": "function",
                    "function": {
                        "name": fn.get("name", ""),
                        "arguments": "{}",
                    },
                })
            compressed.append({
                "role": "assistant",
                "content": msg.get("content") or None,
                "tool_calls": simplified_calls,
            })
        else:
            compressed.append(msg)

    result = system_msgs + compressed
    saved = _estimate_messages_tokens(messages) - _estimate_messages_tokens(result)
    logger.info(f"[ToolLoop] 上下文压缩: {len(messages)} → {len(result)} 条消息, 节省约 {saved} tokens")
    return result


# ─── 并行工具执行 ───────────────────────────────────────────────

async def _execute_single_tc(
    tc: dict,
    step: int,
    duplicate_counter: dict[str, int],
    provider_name: str = "",
    model: str = "",
) -> tuple[str, dict]:
    """执行单个 tool_call，返回 (tool_call_id, tool_result_message)

    返回元组方便调用方直接 append 到 messages。
    """
    tc_id = tc.get("id", f"call_{step}")
    fn = tc.get("function", {})
    tool_name = fn.get("name", "")
    args_str = fn.get("arguments", "{}")

    try:
        args = json.loads(args_str) if args_str else {}
    except json.JSONDecodeError:
        args = {}

    # 重复调用检测
    duplicate_counter[tool_name] = duplicate_counter.get(tool_name, 0) + 1
    if duplicate_counter[tool_name] >= 3:
        logger.warning(f"[ToolLoop] {tool_name} called {duplicate_counter[tool_name]} times, injecting warning")
        return tc_id, {
            "role": "tool",
            "tool_call_id": tc_id,
            "content": f"[警告] 你已经连续调用 {tool_name} {duplicate_counter[tool_name]} 次了。如果信息仍然不足，请直接根据已有信息回答用户。",
        }

    logger.info(f"[ToolLoop] calling {tool_name} with params: {sorted(args.keys())}")

    try:
        result = await execute_tool_by_name(
            tool_name, args,
            provider_name=provider_name, model=model,
        )
    except Exception as e:
        logger.warning(f"[ToolLoop] {tool_name} 执行异常: {e}")
        result = f"工具 '{tool_name}' 执行出错: {e}"

    if len(result) > 2000:
        result = result[:2000] + "...(结果已截断)"

    logger.info(f"[ToolLoop] {tool_name} → {len(result)} chars")
    return tc_id, {
        "role": "tool",
        "tool_call_id": tc_id,
        "content": result,
    }


async def _execute_tool_calls_parallel(
    tool_calls: list[dict],
    step: int,
    duplicate_counter: dict[str, int],
    provider_name: str = "",
    model: str = "",
) -> list[tuple[str, dict]]:
    """并行执行多个 tool_calls，返回 [(tc_id, result_msg), ...]"""
    if len(tool_calls) <= 1:
        if not tool_calls:
            return []
        tc_id, result = await _execute_single_tc(
            tool_calls[0], step, duplicate_counter,
            provider_name=provider_name, model=model,
        )
        return [(tc_id, result)]

    tasks = [
        _execute_single_tc(tc, step, duplicate_counter, provider_name=provider_name, model=model)
        for tc in tool_calls
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    final = []
    for i, r in enumerate(results):
        tc = tool_calls[i]
        tc_id = tc.get("id", f"call_{step}_{i}")
        if isinstance(r, Exception):
            tool_name = tc.get("function", {}).get("name", "unknown")
            final.append((tc_id, {
                "role": "tool",
                "tool_call_id": tc_id,
                "content": f"工具 '{tool_name}' 执行出错: {type(r).__name__}: {str(r)[:200]}",
            }))
        else:
            final.append(r)
    return final


# ─── 子代理委托 ───────────────────────────────────────────────

async def delegate_sub_task(
    task_description: str,
    provider_name: str,
    model: str,
    tools: list[dict] | None = None,
    max_steps: int = 3,
    **kwargs,
) -> str:
    """启动子代理执行独立子任务，返回结果文本

    子代理拥有独立的 messages 上下文，不会污染主对话。
    """
    sub_tools = tools or get_all_tools_schema()
    sub_messages = [
        {"role": "system", "content": "你是一个专注于完成特定子任务的助手。请高效完成以下任务，直接给出结果。"},
        {"role": "user", "content": task_description},
    ]

    result = await tool_loop(
        messages=sub_messages,
        tools=sub_tools,
        provider_name=provider_name,
        model=model,
        max_steps=max_steps,
        **kwargs,
    )
    return result.get("content", "")


# ─── 主循环 ───────────────────────────────────────────────

async def tool_loop(
    messages: list[dict],
    tools: list[dict],
    provider_name: str,
    model: str,
    max_steps: int = 5,
    compress_threshold: int = 8000,
    **kwargs,
) -> dict:
    """Tool Loop 核心循环（非流式）

    增强：
      - 多 tool_calls 并行执行（asyncio.gather）
      - 上下文自动压缩（超过阈值时压缩旧消息）
      - 支持 delegate_task 子代理委托

    返回:
        {"content": str, "reasoning": str, "tool_steps": int}
    """
    tool_steps = 0
    duplicate_counter: dict[str, int] = {}

    for step in range(max_steps):
        # 上下文压缩：每轮开始前检查
        if _estimate_messages_tokens(messages) > compress_threshold:
            messages[:] = _compress_messages(messages, max_tokens=compress_threshold)

        raw = await llm_adapter.chat(
            messages=messages,
            tools=tools,
            provider_name=provider_name,
            model=model,
            return_raw=True,
            **kwargs,
        )

        if not isinstance(raw, dict):
            return {"content": str(raw), "reasoning": "", "tool_steps": tool_steps}

        tool_calls = raw.get("tool_calls", [])
        content = raw.get("content", "") or ""
        reasoning = raw.get("reasoning", "") or ""

        if not tool_calls:
            return {"content": content, "reasoning": reasoning, "tool_steps": tool_steps}

        messages.append({
            "role": "assistant",
            "content": content or None,
            "tool_calls": tool_calls,
        })

        # 并行执行所有 tool_calls
        results = await _execute_tool_calls_parallel(
            tool_calls, step, duplicate_counter,
            provider_name=provider_name, model=model,
        )
        tool_steps += len([r for r in results if not isinstance(r, Exception)])

        # 按原始 tool_call 顺序追加结果到 messages
        for tc_id, result_msg in results:
            messages.append(result_msg)

    messages.append({"role": "user", "content": "请根据已获取的信息总结回答用户的问题，不要再调用工具。"})
    final = await llm_adapter.chat(
        messages=messages,
        provider_name=provider_name,
        model=model,
        **kwargs,
    )
    final_content = final.get("content", "") if isinstance(final, dict) else str(final)
    final_reasoning = final.get("reasoning", "") if isinstance(final, dict) else ""
    return {"content": final_content, "reasoning": final_reasoning, "tool_steps": tool_steps}


async def tool_loop_stream(
    messages: list[dict],
    tools: list[dict],
    provider_name: str,
    model: str,
    max_steps: int = 5,
    compress_threshold: int = 8000,
    **kwargs,
):
    """Tool Loop 核心循环（流式）

    增强：
      - 多 tool_calls 并行执行（asyncio.gather）
      - 上下文自动压缩（超过阈值时压缩旧消息）
      - 支持 delegate_task 子代理委托

    每轮 yield:
      - {"type": "content", "content": str}     — LLM 文本输出
      - {"type": "reasoning", "content": str}   — 推理/状态提示
      - {"type": "done", "content": str, "reasoning": str} — 最终结果
    """
    tool_steps = 0
    duplicate_counter: dict[str, int] = {}
    collected_reasoning = ""

    for step in range(max_steps):
        # 上下文压缩：每轮开始前检查
        if _estimate_messages_tokens(messages) > compress_threshold:
            messages[:] = _compress_messages(messages, max_tokens=compress_threshold)

        collected_content = ""
        step_reasoning = ""
        collected_tool_calls: dict[int, dict] = {}

        async for chunk in llm_adapter.chat_stream(
            messages=messages,
            tools=tools,
            provider_name=provider_name,
            model=model,
            **kwargs,
        ):
            content = chunk.get("content", "")
            reasoning = chunk.get("reasoning", "")
            tc_complete = chunk.get("tool_calls_complete")

            if content:
                collected_content += content
                yield {"type": "content", "content": content}
            if reasoning:
                step_reasoning += reasoning
                yield {"type": "reasoning", "content": reasoning}

            if tc_complete:
                for tc in tc_complete:
                    idx = tc.get("index", len(collected_tool_calls))
                    collected_tool_calls[idx] = tc

        if not collected_tool_calls:
            collected_reasoning += step_reasoning
            yield {
                "type": "done",
                "content": collected_content,
                "reasoning": collected_reasoning,
            }
            return

        # 构造 assistant 消息（含 tool_calls），按模型原始 index 排序
        tool_calls_list = [
            {
                "id": v.get("id", f"call_{step}_{k}"),
                "type": "function",
                "function": v.get("function", {}),
            }
            for k, v in sorted(collected_tool_calls.items(), key=lambda kv: kv[1].get("index", 0))
        ]
        messages.append({
            "role": "assistant",
            "content": collected_content or None,
            "tool_calls": tool_calls_list,
        })

        # 并行执行所有 tool_calls
        results = await _execute_tool_calls_parallel(
            tool_calls_list, step, duplicate_counter,
            provider_name=provider_name, model=model,
        )
        tool_steps += len([r for r in results if not isinstance(r, Exception)])

        # 按原始顺序追加结果到 messages
        for tc_id, result_msg in results:
            messages.append(result_msg)

        collected_reasoning += step_reasoning

    # 最终汇总：不再调用工具，直接回答
    messages.append({"role": "user", "content": "请根据已获取的信息总结回答用户的问题，不要再调用工具。"})
    final_content = ""
    try:
        async for chunk in llm_adapter.chat_stream(
            messages=messages,
            tools=None,
            provider_name=provider_name,
            model=model,
            **kwargs,
        ):
            content = chunk.get("content", "")
            rc = chunk.get("reasoning", "")
            if content:
                final_content += content
                yield {"type": "content", "content": content}
            if rc:
                collected_reasoning += rc
    except Exception as e:
        logger.error(f"[ToolLoop] Final summary stream error: {e}")
        if not final_content and collected_content:
            final_content = collected_content

    yield {"type": "done", "content": final_content, "reasoning": collected_reasoning}
