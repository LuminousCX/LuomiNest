import json
from datetime import datetime, timezone

with open('data/memory/memory.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

print('当前 Profile name:', data['profile']['name'])
print()
print('需要清理的高置信度旧名字事实:')

for fact in data['facts']:
    content = fact['content']
    if '小洪' in content and fact['confidence'] >= 0.9:
        print(f"  - {content} (confidence: {fact['confidence']})")
        fact['confidence'] = 0.3

# 更新时间戳
data['last_updated'] = datetime.now(timezone.utc).isoformat()

with open('data/memory/memory.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print()
print('已将所有高置信度的"小洪"事实置信度设为0.3')