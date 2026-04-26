import json
import re
from loguru import logger
from app.runtime.plugin.skill.base import SkillDefinition


class SkillParser:
    @staticmethod
    def parse_markdown(content: str, filename: str = "") -> SkillDefinition | None:
        try:
            frontmatter = SkillParser._extract_frontmatter(content)
            if not frontmatter:
                logger.warning(f"[SkillParser] No frontmatter found in {filename}")
                return None

            name = frontmatter.get("name", filename.replace(".md", ""))
            description = frontmatter.get("description", "")
            category = frontmatter.get("category", "custom")
            parameters = frontmatter.get("parameters", {})
            tags = frontmatter.get("tags", [])
            is_active = frontmatter.get("active", True)

            prompt_template = SkillParser._extract_body(content)

            return SkillDefinition(
                name=name,
                description=description,
                category=category,
                parameters=parameters,
                is_active=is_active,
                is_builtin=False,
                prompt_template=prompt_template,
                tags=tags,
            )
        except Exception as e:
            logger.error(f"[SkillParser] Failed to parse {filename}: {e}")
            return None

    @staticmethod
    def parse_json(data: dict) -> SkillDefinition | None:
        try:
            return SkillDefinition(
                name=data["name"],
                description=data.get("description", ""),
                category=data.get("category", "custom"),
                parameters=data.get("parameters", {}),
                is_active=data.get("is_active", True),
                is_builtin=data.get("is_builtin", False),
                handler_name=data.get("handler_name"),
                prompt_template=data.get("prompt_template"),
                tags=data.get("tags", []),
            )
        except Exception as e:
            logger.error(f"[SkillParser] Failed to parse JSON skill: {e}")
            return None

    @staticmethod
    def parse_tool_call_xml(content: str) -> list[dict]:
        pattern = r'<tool_call\s+name="([^"]+)">\s*(.*?)\s*</tool_call'
        matches = re.findall(pattern, content, re.DOTALL)
        results = []
        for name, args_str in matches:
            try:
                args = json.loads(args_str) if args_str.strip() else {}
            except json.JSONDecodeError:
                args = {"raw_input": args_str}
            results.append({"name": name, "arguments": args})
        return results

    @staticmethod
    def parse_tool_call_json(content: str) -> list[dict]:
        try:
            data = json.loads(content)
            if isinstance(data, dict) and "name" in data:
                return [{"name": data["name"], "arguments": data.get("arguments", {})}]
            if isinstance(data, list):
                return [{"name": item["name"], "arguments": item.get("arguments", {})} for item in data if "name" in item]
        except json.JSONDecodeError:
            pass
        return []

    @staticmethod
    def _extract_frontmatter(content: str) -> dict | None:
        match = re.match(r'^---\s*\n(.*?)\n---\s*\n', content, re.DOTALL)
        if not match:
            return None
        try:
            import yaml
            return yaml.safe_load(match.group(1))
        except ImportError:
            return SkillParser._parse_simple_frontmatter(match.group(1))
        except Exception:
            return None

    @staticmethod
    def _parse_simple_frontmatter(text: str) -> dict:
        result = {}
        for line in text.strip().split("\n"):
            if ":" in line:
                key, _, value = line.partition(":")
                key = key.strip()
                value = value.strip()
                if value.startswith("[") and value.endswith("]"):
                    result[key] = [v.strip().strip('"').strip("'") for v in value[1:-1].split(",")]
                elif value.startswith("{") and value.endswith("}"):
                    try:
                        result[key] = json.loads(value)
                    except json.JSONDecodeError:
                        result[key] = value
                elif value.lower() in ("true", "false"):
                    result[key] = value.lower() == "true"
                else:
                    result[key] = value.strip('"').strip("'")
        return result

    @staticmethod
    def _extract_body(content: str) -> str:
        match = re.match(r'^---\s*\n.*?\n---\s*\n(.*)', content, re.DOTALL)
        return match.group(1).strip() if match else content.strip()
