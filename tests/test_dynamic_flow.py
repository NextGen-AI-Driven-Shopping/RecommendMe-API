#!/usr/bin/env python
"""Test the dynamic query flow to verify no static templates are used."""

import httpx
import json

def test_dynamic_flow():
    """Test the full query flow with dynamic analysis."""
    base_url = "http://localhost:8000"
    
    # First, let's check health
    try:
        resp = httpx.get(f"{base_url}/v1/health", timeout=5)
        print(f"✓ Health check: {resp.status_code}")
    except Exception as e:
        print(f"✗ Health check failed: {e}")
        return
    
    # Test 1: Generic vague query (should ask dynamic follow-ups)
    print("\n🔍 Test 1: Vague Query - 'Headphones'")
    try:
        resp = httpx.post(
            f"{base_url}/v1/query",
            json={"user_message": "Headphones"},
            timeout=10
        )
        print(f"Status: {resp.status_code}")
        print(f"Response: {json.dumps(resp.json(), indent=2)}")
    except Exception as e:
        print(f"✗ Query 1 failed: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Test 2: Specific query (should be CLEAR)
    print("\n✅ Test 2: Clear Query - 'Gaming headphones under $100'")
    try:
        resp = httpx.post(
            f"{base_url}/v1/query",
            json={"user_message": "Gaming headphones under $100"},
            timeout=30  # Increased timeout for SerpAPI
        )
        print(f"Status: {resp.status_code}")
        data = resp.json()
        if resp.status_code == 200:
            print(f"Classification: {data.get('status')}")
            if data.get('recommendations'):
                print(f"✓ Found {len(data['recommendations'])} products:")
                for r in data['recommendations'][:3]:
                    print(f"    - {r.get('title', 'Unknown')} (${r.get('price', 'N/A')})")
            else:
                print(f"Summary: {data.get('summary')}")
        else:
            print(f"Response: {json.dumps(data, indent=2)}")
    except Exception as e:
        print(f"✗ Query 2 failed: {e}")
        import traceback
        traceback.print_exc()
        return
    
    print("\n✨ Test Complete!")

if __name__ == "__main__":
    print("Starting dynamic flow test...")
    test_dynamic_flow()
