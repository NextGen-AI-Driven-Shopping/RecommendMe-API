import os
import requests
from dotenv import load_dotenv

def test_openai():
    key = os.getenv("OPENAI_API_KEY")
    if not key: return "Skipped (No key)"
    try:
        res = requests.get("https://api.openai.com/v1/models", headers={"Authorization": f"Bearer {key}"}, timeout=5)
        if res.status_code == 200:
            return "SUCCESS (Models fetched)"
        return f"FAILED ({res.status_code}): {res.text[:100]}"
    except Exception as e:
        return f"ERROR: {e}"

def test_serpapi():
    key = os.getenv("SERPAPI_KEY")
    if not key: return "Skipped (No key)"
    try:
        res = requests.get(f"https://serpapi.com/search?engine=google&q=test&api_key={key}", timeout=5)
        if res.status_code == 200:
            return "SUCCESS (Search result fetched)"
        return f"FAILED ({res.status_code}): {res.text[:100]}"
    except Exception as e:
        return f"ERROR: {e}"

def test_gemini():
    key = os.getenv("GEMINI_API_KEY")
    if not key: return "Skipped (No key)"
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models?key={key}"
        res = requests.get(url, timeout=5)
        if res.status_code == 200:
            return "SUCCESS (Models fetched)"
        return f"FAILED ({res.status_code}): {res.text[:100]}"
    except Exception as e:
        return f"ERROR: {e}"

def test_groq():
    key = os.getenv("GROQ_API_KEY")
    if not key: return "Skipped (No key)"
    try:
        res = requests.get("https://api.groq.com/openai/v1/models", headers={"Authorization": f"Bearer {key}"}, timeout=5)
        if res.status_code == 200:
            return "SUCCESS (Models fetched)"
        return f"FAILED ({res.status_code}): {res.text[:100]}"
    except Exception as e:
        return f"ERROR: {e}"

def test_grok():
    key = os.getenv("GROK_API_KEY")
    if not key: return "Skipped (No key)"
    try:
        res = requests.get("https://api.x.ai/v1/models", headers={"Authorization": f"Bearer {key}"}, timeout=5)
        if res.status_code == 200:
            return "SUCCESS (Models fetched)"
        return f"FAILED ({res.status_code}): {res.text[:100]}"
    except Exception as e:
        return f"ERROR: {e}"

if __name__ == "__main__":
    load_dotenv()
    print("Testing API Keys...")
    print(f"OpenAI:  {test_openai()}")
    print(f"SerpAPI: {test_serpapi()}")
    print(f"Gemini:  {test_gemini()}")
    print(f"Groq:    {test_groq()}")
    print(f"Grok:    {test_grok()}")
