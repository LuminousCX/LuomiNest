"""消息截断工具（从原 __init__.py 拆出）。"""


class ContextTruncator:
    @staticmethod
    def _split_system_rest(messages: list[dict]) -> tuple[list[dict], list[dict]]:
        first_non_system = 0
        for i, msg in enumerate(messages):
            if msg.get("role") != "system":
                first_non_system = i
                break
        return messages[:first_non_system], messages[first_non_system:]

    @staticmethod
    def _ensure_user_message(
        system_messages: list[dict],
        truncated: list[dict],
        original_messages: list[dict],
    ) -> list[dict]:
        if truncated and truncated[0].get("role") == "user":
            return system_messages + truncated

        first_user = next((m for m in original_messages if m.get("role") == "user"), None)
        if first_user is None:
            return system_messages + truncated

        return system_messages + [first_user] + truncated

    def fix_messages(self, messages: list[dict]) -> list[dict]:
        if not messages:
            return messages

        fixed: list[dict] = []
        pending_assistant: dict | None = None
        pending_tools: list[dict] = []

        def flush_pending_if_valid():
            nonlocal pending_assistant, pending_tools
            if pending_assistant is not None and pending_tools:
                fixed.append(pending_assistant)
                fixed.extend(pending_tools)
            pending_assistant = None
            pending_tools = []

        for msg in messages:
            if msg.get("role") == "tool":
                if pending_assistant is not None:
                    pending_tools.append(msg)
                continue

            if msg.get("role") == "assistant" and msg.get("tool_calls"):
                flush_pending_if_valid()
                pending_assistant = msg
                continue

            flush_pending_if_valid()
            fixed.append(msg)

        flush_pending_if_valid()
        return fixed

    def truncate_by_dropping_oldest_turns(
        self,
        messages: list[dict],
        drop_turns: int = 1,
    ) -> list[dict]:
        if drop_turns <= 0:
            return messages

        system_messages, non_system_messages = self._split_system_rest(messages)

        if len(non_system_messages) // 2 <= drop_turns:
            truncated_non_system = []
        else:
            truncated_non_system = non_system_messages[drop_turns * 2:]

        index = next(
            (i for i, item in enumerate(truncated_non_system) if item.get("role") == "user"),
            None,
        )
        if index is not None:
            truncated_non_system = truncated_non_system[index:]

        result = self._ensure_user_message(system_messages, truncated_non_system, messages)
        return self.fix_messages(result)

    def truncate_by_halving(self, messages: list[dict]) -> list[dict]:
        if len(messages) <= 2:
            return messages

        system_messages, non_system_messages = self._split_system_rest(messages)

        messages_to_delete = len(non_system_messages) // 2
        if messages_to_delete == 0:
            return messages

        truncated_non_system = non_system_messages[messages_to_delete:]

        index = next(
            (i for i, item in enumerate(truncated_non_system) if item.get("role") == "user"),
            None,
        )
        if index is not None:
            truncated_non_system = truncated_non_system[index:]

        result = self._ensure_user_message(system_messages, truncated_non_system, messages)
        return self.fix_messages(result)
