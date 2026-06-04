import json

with open('data/memory/memory.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

print('Profile name:', data['profile']['name'])
print('Profile updated at:', data['profile']['updated_at'])
print()
print('名字相关的事实:')
for f in data['facts']:
    if '名字' in f['content']:
        print(f"  - {f['content']} (confidence: {f['confidence']})")
