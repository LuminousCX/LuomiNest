import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
MEMORY_DIR = DATA_DIR / "memory"
OLD_MEMORY_MD = MEMORY_DIR / "MEMORY.md"
OLD_SUMMARY_MD = MEMORY_DIR / "summary.md"
NEW_MEMORY_JSON = MEMORY_DIR / "memory.json"
OLD_USER_SPACE = DATA_DIR / "memory" / "user_space.json"


def migrate_md_to_json():
    if NEW_MEMORY_JSON.exists():
        print("memory.json already exists, skipping migration")
        return

    data = {
        "version": "2.0",
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "profile": {"name": "", "updated_at": ""},
        "facts": [],
        "summaries": {
            "user_profile": {"summary": "", "updated_at": ""},
            "preferences": {"summary": "", "updated_at": ""},
            "recent_state": {"summary": "", "updated_at": ""},
            "timeline": {"summary": "", "updated_at": ""},
        },
    }

    migrated = False

    if OLD_MEMORY_MD.exists():
        print(f"Reading {OLD_MEMORY_MD}...")
        content = OLD_MEMORY_MD.read_text(encoding="utf-8")
        name_match = re.search(r"(?:姓名|name|Name)[：:]\s*(.+)", content, re.IGNORECASE)
        if name_match:
            data["profile"]["name"] = name_match.group(1).strip()
            data["profile"]["updated_at"] = datetime.now(timezone.utc).isoformat()

        fact_lines = []
        for line in content.split("\n"):
            stripped = line.strip()
            if stripped.startswith("- ") and not stripped.lower().startswith("- name") and not stripped.lower().startswith("- nickname"):
                fact_text = stripped[2:].strip()
                if fact_text:
                    fact_lines.append(fact_text)

        for i, fact_text in enumerate(fact_lines[:100]):
            data["facts"].append({
                "id": f"fact_migrate_{i:03d}",
                "content": fact_text,
                "category": "context",
                "confidence": 0.7,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "source": "migration",
                "source_error": "",
            })

        migrated = True

    if OLD_SUMMARY_MD.exists():
        print(f"Reading {OLD_SUMMARY_MD}...")
        content = OLD_SUMMARY_MD.read_text(encoding="utf-8")
        now = datetime.now(timezone.utc).isoformat()
        section_map = {
            "用户画像": "user_profile",
            "兴趣偏好": "preferences",
            "近期状态": "recent_state",
            "事件时间线": "timeline",
        }
        for cn_name, attr_name in section_map.items():
            pattern = rf"##\s*{re.escape(cn_name)}\s*\n(.*?)(?=\n##\s|\Z)"
            match = re.search(pattern, content, re.DOTALL)
            if match:
                text = match.group(1).strip()
                if text:
                    data["summaries"][attr_name]["summary"] = text
                    data["summaries"][attr_name]["updated_at"] = now
        migrated = True

    if OLD_USER_SPACE.exists():
        print(f"Reading {OLD_USER_SPACE}...")
        try:
            with open(OLD_USER_SPACE, "r", encoding="utf-8") as f:
                old_data = json.load(f)

            profile = old_data.get("profile", {})
            if profile.get("name") and not data["profile"]["name"]:
                data["profile"]["name"] = profile["name"]
                data["profile"]["updated_at"] = datetime.now(timezone.utc).isoformat()

            old_facts = old_data.get("facts", [])
            existing_contents = {f["content"].casefold() for f in data["facts"]}
            for fact in old_facts[-50:]:
                content = fact.get("content", "")
                if content and content.casefold() not in existing_contents:
                    data["facts"].append({
                        "id": f"fact_us_{len(data['facts']):03d}",
                        "content": content,
                        "category": "context",
                        "confidence": 0.7,
                        "created_at": datetime.now(timezone.utc).isoformat(),
                        "source": "migration_user_space",
                        "source_error": "",
                    })
                    existing_contents.add(content.casefold())

            migrated = True
        except Exception as e:
            print(f"Warning: Failed to read user_space.json: {e}")

    if not migrated:
        print("No old memory files found, creating empty memory.json")
        MEMORY_DIR.mkdir(parents=True, exist_ok=True)
        NEW_MEMORY_JSON.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"Created: {NEW_MEMORY_JSON}")
        return

    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    NEW_MEMORY_JSON.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Created: {NEW_MEMORY_JSON}")

    if OLD_MEMORY_MD.exists():
        backup = OLD_MEMORY_MD.with_suffix(".md.bak")
        shutil.copy2(OLD_MEMORY_MD, backup)
        print(f"Backup: {backup}")
        OLD_MEMORY_MD.unlink()
        print(f"Deleted: {OLD_MEMORY_MD}")

    if OLD_SUMMARY_MD.exists():
        backup = OLD_SUMMARY_MD.with_suffix(".md.bak")
        shutil.copy2(OLD_SUMMARY_MD, backup)
        print(f"Backup: {backup}")
        OLD_SUMMARY_MD.unlink()
        print(f"Deleted: {OLD_SUMMARY_MD}")

    if OLD_USER_SPACE.exists():
        OLD_USER_SPACE.rename(OLD_USER_SPACE.with_suffix(".json.migrated"))
        print(f"Renamed: {OLD_USER_SPACE} -> .migrated")

    print(f"Migration complete! {len(data['facts'])} facts migrated.")


if __name__ == "__main__":
    migrate_md_to_json()
