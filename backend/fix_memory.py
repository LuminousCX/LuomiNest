import json
from datetime import datetime, timezone

with open('data/memory/memory.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

print('当前 Profile name:', data['profile']['name'])
print('需要清理的旧名字事实:')

facts_to_deprecate = []
for i, fact in enumerate(data['facts']):
    content = fact['content']
    if '名字' in content and ('小洪' in content or '小黑' in content or '小红' in content or '小天' in content):
        print(f"  [{i}] {content} (confidence: {fact['confidence']})")
        facts_to_deprecate.append(i)

# 将所有包含名字的旧事实置信度设为0.3
for i in reversed(facts_to_deprecate):
    data['facts'][i]['confidence'] = 0.3

# 更新时间戳
data['last_updated'] = datetime.now(timezone.utc).isoformat()

with open('data/memory/memory.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print()
print('已将所有旧名字事实的置信度设为0.3')
print('现在 profile.name 是最高优先级')