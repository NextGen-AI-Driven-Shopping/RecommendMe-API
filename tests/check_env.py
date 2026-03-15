import os
from dotenv import load_dotenv

def mask_key(key: str) -> str:
    if not key:
        return "<Missing or Empty>"
    if len(key) <= 8:
        return "***"
    return f"{key[:4]}...{key[-4:]}"

def main():
    # Load environment variables from .env file into os.environ
    load_dotenv()
    
    print("--- Reading API Keys using python-dotenv ---")
    keys_to_check = [
        "OPENAI_API_KEY",
        "SERPAPI_KEY",
        "GEMINI_API_KEY",
        "GROQ_API_KEY",
        "GROK_API_KEY",
        "OTHER_API_KEY",
    ]
    
    for var in keys_to_check:
        val = os.getenv(var)
        print(f"{var}: {mask_key(val)}")

if __name__ == "__main__":
    main()
