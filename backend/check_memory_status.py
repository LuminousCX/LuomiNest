import json

with open('data/memory/memory.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

print('=== 当前记忆状态 ===')
print('Profile name:', data['profile']['name'])
print('Profile updated at:', data['profile']['updated_at'])
print()
print('=== 高置信度(>=0.9)的名字相关事实 ===')
for f in data['facts']:
    if '名字' in f['content'] and f['confidence'] >= 0.9:
        print(f"  - {f['content']} (confidence: {f['confidence']})")
print()
print('=== 高置信度(>=0.9)的其他名字事实 ===')
other_names = ['小红', '小洪', '小天', '胡天', '小一', '小黑', '黑子', '小明']
for f in data['facts']:
    content = f['content']
    if f['confidence'] >= 0.9:
        for name in other_names:
            if name in content and name != data['profile']['name']:
                print(f"  - {content} (confidence: {f['confidence']})")
                break