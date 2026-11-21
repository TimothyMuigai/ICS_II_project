"""Local in-process API smoke checks for the real evaluation collection."""
import config
config.OPENAI_API_KEY = ''

from fastapi.testclient import TestClient
from rag_service import app

client = TestClient(app)
health = client.get('/health')
assert health.status_code == 200
assert health.json()['status'] == 'ok'
assert health.json()['collections']['kenya_real'] == 13

query = client.post('/query', json={
    'question': 'What does the Central Depository System (CDS) enable shareholders to do?',
    'collection': 'kenya_real',
})
assert query.status_code == 200, query.text
body = query.json()
assert 'CMA-Beginners-guide' in {citation['source'] for citation in body['citations']}
assert 'electronic accounts' in body['answer'].lower()

empty = client.post('/query', json={'question': '   ', 'collection': 'kenya_real'})
long = client.post('/query', json={'question': 'x' * 4001, 'collection': 'kenya_real'})
assert empty.status_code == 400
assert long.status_code == 400

print('GET /health: PASS (200; 13 real-evaluation chunks)')
print(f'POST /query: PASS (200; elapsed_ms={body["elapsed_ms"]}; cited source=CMA-Beginners-guide)')
print('POST /query empty question: PASS (400)')
print('POST /query over 4000 characters: PASS (400)')
