import sys
sys.path.insert(0, '.')

import asyncio
from app.core.app_factory import create_app
from fastapi.testclient import TestClient

try:
    print('Creating app...')
    app = create_app()
    print('App created successfully')
    
    print('Creating test client...')
    client = TestClient(app)
    print('Test client created')
    
    print('Testing /health endpoint...')
    response = client.get('/health')
    print(f'Health endpoint: {response.status_code}')
    print(f'Health response: {response.json()}')
    
    print('Testing /api/v1/memory/ endpoint...')
    response = client.get('/api/v1/memory/')
    print(f'Memory endpoint: {response.status_code}')
    if response.status_code == 200:
        data = response.json()
        print(f'Memory response keys: {list(data.keys())}')
        print(f'Fact count: {len(data.get("facts", []))}')
    else:
        print(f'Error: {response.text}')
        
except Exception as e:
    print(f'Error: {type(e).__name__}: {e}')
    import traceback
    traceback.print_exc()