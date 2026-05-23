import json
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


async def tool_loop(
    messages: list[dict],
    tools: list[dict],
    provider_name: str,
    model: str,
    max_steps: int = 5,
    **kwargs,
) -> dict:
    tool_steps = 0
    duplicate_counter: dict[str, int] = {}

    for step in range(max_steps):
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

        for tc in tool_calls:
            tc_id = tc.get("id", f"call_{step}")
            fn = tc.get("function", {})
            tool_name = fn.get("name", "")
            args_str = fn.get("arguments", "{}")

            logger.info(f"[ToolLoop] Step {step + 1}: calling {tool_name}({args_str[:100]})")

            duplicate_counter[tool_name] = duplicate_counter.get(tool_name, 0) + 1
            if duplicate_counter[tool_name] >= 3:
                logger.warning(f"[ToolLoop] {tool_name} called {duplicate_counter[tool_name]} times, injecting warning")
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc_id,
                    "content": f"[警告] 你已经连续调用 {tool_name} {duplicate_counter[tool_name]} 次了。如果信息仍然不足，请直接根据已有信息回答用户。",
                })
                continue

            try:
                args = json.loads(args_str) if args_str else {}
            except json.JSONDecodeError:
                args = {}

            result = await execute_tool_by_name(tool_name, args)

            if len(result) > 2000:
                result = result[:2000] + "...(结果已截断)"

            logger.info(f"[ToolLoop] {tool_name} → {len(result)} chars")
            tool_steps += 1

            messages.append({
                "role": "tool",
                "tool_call_id": tc_id,
                "content": result,
            })

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
    **kwargs,
):
    tool_steps = 0
    duplicate_counter: dict[str, int] = {}

    for step in range(max_steps):
        collected_content = ""
        collected_reasoning = ""
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
                collected_reasoning += reasoning
                yield {"type": "reasoning", "content": reasoning}

            if tc_complete:
                for tc in tc_complete:
                    idx = tc.get("index", len(collected_tool_calls))
                    collected_tool_calls[idx] = tc

        if not collected_tool_calls:
            yield {
                "type": "done",
                "content": collected_content,
                "reasoning": collected_reasoning,
            }
            return

        messages.append({
            "role": "assistant",
            "content": collected_content or None,
            "tool_calls": [
                {
                    "id": v.get("id", f"call_{step}_{k}"),
                    "type": "function",
                    "function": v.get("function", {}),
                }
                for k, v in collected_tool_calls.items()
            ],
        })

        for idx in sorted(collected_tool_calls.keys()):
            tc_data = collected_tool_calls[idx]
            fn = tc_data.get("function", {})
            tool_name = fn.get("name", "")
            args_str = fn.get("arguments", "{}")
            tc_id = tc_data.get("id", f"call_{step}_{idx}")

            logger.info(f"[ToolLoop] Step {step + 1} stream: calling {tool_name}({args_str[:100]})")

            duplicate_counter[tool_name] = duplicate_counter.get(tool_name, 0) + 1
            if duplicate_counter[tool_name] >= 3:
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc_id,
                    "content": f"[警告] 你已经连续调用 {tool_name} {duplicate_counter[tool_name]} 次了。如果信息仍然不足，请直接根据已有信息回答用户。",
                })
                continue

            try:
                args = json.loads(args_str) if args_str else {}
            except json.JSONDecodeError:
                args = {}

            result = await execute_tool_by_name(tool_name, args)

            if len(result) > 2000:
                result = result[:2000] + "...(结果已截断)"

            logger.info(f"[ToolLoop] {tool_name} → {len(result)} chars")
            tool_steps += 1

            messages.append({
                "role": "tool",
                "tool_call_id": tc_id,
                "content": result,
            })

    messages.append({"role": "user", "content": "请根据已获取的信息总结回答用户的问题，不要再调用工具。"})
    final_content = ""
    async for chunk in llm_adapter.chat_stream(
        messages=messages,
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

    yield {"type": "done", "content": final_content, "reasoning": collected_reasoning}
