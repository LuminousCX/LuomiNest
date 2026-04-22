from dataclasses import dataclass, field
from typing import Any, Callable, Awaitable


@dataclass
class SkillParameter:
    name: str
    type: str = "string"
    description: str = ""
    required: bool = True
    default: Any = None


@dataclass
class SkillDefinition:
    name: str
    description: str = ""
    category: str = "general"
    parameters: dict[str, dict] = field(default_factory=dict)
    is_active: bool = True
    is_builtin: bool = False
    handler_name: str | None = None
    prompt_template: str | None = None
    tags: list[str] = field(default_factory=list)

    def to_openai_tool(self) -> dict:
        properties = {}
        required = []
        for pname, pinfo in self.parameters.items():
            properties[pname] = {
                "type": pinfo.get("type", "string"),
                "description": pinfo.get("description", ""),
            }
            if pinfo.get("required", True):
                required.append(pname)

        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            },
        }


@dataclass
class SkillResult:
    success: bool
    data: Any = None
    error: str | None = None
    metadata: dict = field(default_factory=dict)

    def to_text(self) -> str:
        if self.success:
            if isinstance(self.data, str):
                return self.data
            import json
            return json.dumps(self.data, ensure_ascii=False, indent=2)
        return f"Error: {self.error}"


SkillHandler = Callable[..., Awaitable[SkillResult]]
