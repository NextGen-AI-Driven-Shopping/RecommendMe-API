import urllib.request, json, urllib.error

url = 'http://127.0.0.1:8000/v1/query'

# Test 1: Vague query
data1 = {
    'session_id': 'test-vague',
    'user_message': 'Laptop',
    'conversation_history': [{'role': 'user', 'content': 'Laptop'}]
}
req1 = urllib.request.Request(url, data=json.dumps(data1).encode('utf-8'), headers={'Content-Type': 'application/json'}, method='POST')
try:
    response = urllib.request.urlopen(req1, timeout=30)
    result = json.loads(response.read().decode('utf-8'))
    
    status = result.get('status', 'unknown')
    questions = result.get('questions', [])
    
    print(f"STATUS: {status}")
    print(f"QUESTION_COUNT: {len(questions)}")
    for i, q in enumerate(questions):
        print(f"Q{i+1}: {q}")
    
    if result.get('message'):
        print(f"MESSAGE: {result['message']}")
    if result.get('summary'):
        print(f"SUMMARY: {result['summary']}")
except urllib.error.HTTPError as e:
    err_body = e.read().decode('utf-8')
    print(f"HTTP_ERROR: {e.code}")
    print(f"DETAIL: {err_body[:500]}")
except Exception as e:
    print(f"EXCEPTION: {e}")
