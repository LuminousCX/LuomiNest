import json

with open('data/memory/memory.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

print('=== AI总结内容 ===')
summaries = data.get('summaries', {})
if summaries:
    for key, value in summaries.items():
        if isinstance(value, dict) and value.get('summary'):
            print(f"{key}:")
            print(value['summary'])
            print()
