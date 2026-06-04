import json
from datetime import datetime, timezone

with open('data/memory/memory.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

current_name = data['profile']['name']
print(f'当前 Profile name: {current_name}')
print()
print('=== 需要清理的高置信度旧名字事实 ===')

other_names = ['小红', '小洪', '小天', '胡天', '小一', '小黑', '黑子', '小明', '小白', '小米']
other_names = [n for n in other_names if n != current_name]

count = 0
for f in data['facts']:
    if f['confidence'] >= 0.9:
        content = f['content']
        for name in other_names:
            if name in content and ('名字' in content or '叫' in content or '名为' in content):
                print(f"  - {content} (confidence: {f['confidence']}) → 设为0.3")
                f['confidence'] = 0.3
                count += 1
                break

data['last_updated'] = datetime.now(timezone.utc).isoformat()

with open('data/memory/memory.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print()
print(f'已清理 {count} 条高置信度旧名字事实')