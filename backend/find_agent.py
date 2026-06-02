from app.infrastructure.database.json_store import agents_store

agents = agents_store.all()
print('All agents:')
for a in agents:
    agent_id = a.get('id')
    agent_name = a.get('name')
    print(f"ID: {agent_id}, Name: {agent_name}")
    if agent_name == '大未发放':
        print(f"  -> Found target agent! ID: {agent_id}")