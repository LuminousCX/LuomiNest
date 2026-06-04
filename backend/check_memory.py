import json
from pathlib import Path
from app.core.config import settings

agent_id = "f39f2452-0f2e-466b-9fce-cef688be55a3"
memory_path = Path(settings.DATA_DIR) / "memory" / "agents" / agent_id / "memory.json"

print(f"Memory file path: {memory_path}")
print(f"File exists: {memory_path.exists()}")

if memory_path.exists():
    # 尝试用不同编码读取
    for encoding in ['utf-8', 'gbk', 'utf-16']:
        try:
            content = memory_path.read_text(encoding=encoding)
            print(f"\n--- Encoding: {encoding} ---")
            print(f"Content preview (first 500 chars):")
            print(content[:500])
            # 尝试解析JSON
            data = json.loads(content)
            print(f"\nSuccessfully parsed JSON")
            print(f"Profile name: {data.get('profile', {}).get('name')}")
            print(f"Fact count: {len(data.get('facts', []))}")
            break
        except Exception as e:
            print(f"Failed with {encoding}: {e}")