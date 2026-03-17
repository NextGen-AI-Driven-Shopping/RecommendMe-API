#!/usr/bin/env python3
"""
Test the RecommendMe conversational flow:
Headphones -> What type? -> wired -> What budget? -> under 500 -> For gaming? -> yes
"""

import requests
import json
import time

BASE_URL = "http://127.0.0.1:8000/v1/query"

def print_section(title):
    print("\n" + "=" * 70)
    print(f" {title}")
    print("=" * 70)

print_section("RecommendMe Conversational Flow Test")

# STEP 1: Vague query
print_section("Step 1: Query 'Headphones' (Should be VAGUE)")

payload = {
    'user_message': 'Headphones',
    'conversation_history': []
}

response = requests.post(BASE_URL, json=payload)
result1 = response.json()
print(json.dumps(result1, indent=2))

session_id = result1.get('session_id')
questions = result1.get('questions')

print(f"\n✓ Session ID: {session_id}")
print(f"✓ Status: {result1['status']}")
if questions:
    print(f"✓ Follow-up Questions:")
    for i, q in enumerate(questions, 1):
        print(f"   {i}. {q}")


# STEP 2: Answer first clarification - type
print_section("Step 2: Clarify - 'wired headphones'")

payload = {
    'user_message': 'wired headphones',
    'session_id': session_id,
    'conversation_history': [
        {'role': 'user', 'content': 'Headphones'},
        {'role': 'assistant', 'content': f'I can help! To find the best headphones, I need to know:\n' + '\n'.join([f'• {q}' for q in questions])}
    ]
}

response = requests.post(BASE_URL, json=payload)
result2 = response.json()
print(json.dumps(result2, indent=2))

print(f"\n✓ Status: {result2['status']}")
if result2['status'] == 'clarification_needed':
    new_questions = result2.get('questions')
    print(f"✓ More Questions:")
    for i, q in enumerate(new_questions, 1):
        print(f"   {i}. {q}")


# STEP 3: Answer budget
print_section("Step 3: Clarify - 'under 500'")

payload = {
    'user_message': 'under 500',
    'session_id': session_id,
    'conversation_history': [
        {'role': 'user', 'content': 'Headphones'},
        {'role': 'user', 'content': 'wired headphones'},
    ]
}

response = requests.post(BASE_URL, json=payload)
result3 = response.json()
print(json.dumps(result3, indent=2))

print(f"\n✓ Status: {result3['status']}")
if result3['status'] == 'clarification_needed':
    new_questions = result3.get('questions')
    print(f"✓ More Questions:")
    for i, q in enumerate(new_questions, 1):
        print(f"   {i}. {q}")


# STEP 4: Answer use case
print_section("Step 4: Clarify - 'yes, for gaming'")

payload = {
    'user_message': 'yes, for gaming',
    'session_id': session_id,
    'conversation_history': [
        {'role': 'user', 'content': 'Headphones'},
        {'role': 'user', 'content': 'wired headphones'},
        {'role': 'user', 'content': 'under 500'},
    ]
}

response = requests.post(BASE_URL, json=payload)
result4 = response.json()
print(json.dumps(result4, indent=2))

print(f"\n✓ Status: {result4['status']}")
if result4['status'] == 'recommendations':
    categories = result4.get('categories', [])
    print(f"✓ Recommendations Found: {len(categories)} categories")
    if categories:
        for cat in categories:
            print(f"   • {cat.get('category')}: {len(cat.get('products', []))} products")
            for prod in cat.get('products', [])[:2]:  # Show first 2 products
                print(f"     - {prod.get('title')} ({prod.get('price')})")


print_section("✅ Conversational Flow Test Complete")
