import json, os, sys
sys.stdout.reconfigure(encoding='utf-8')

agents = ['0f2fca0e-fc6c-464a-bcbc-8bae0cf5a9e3', '2071f8ec-7e0e-4ebd-8fe7-9113eb7c62b0', 'dc738fcf-ec47-4f24-b431-f47727627a55']
base = r'D:\Python学习\luominest\backend\data\memory\agents'

for aid in agents:
    path = os.path.join(base, aid, 'memory.json')
    with open(path, encoding='utf-8') as f:
        d = json.load(f)
    s = d.get('summaries', {})
    name = d.get('profile', {}).get('name', '?')
    fc = len(d.get('facts', []))
    print(f'=== {aid[:8]}... | profile={name} | facts={fc} ===')
    for k in ['user_profile','preferences','recent_state','timeline']:
        v = (s.get(k, {}) or {}).get('summary', '')
        has = 'YES' if v else '---'
        print(f'  {k}: [{has}] {v[:80]}')
    print()
