import os
import requests
from dotenv import load_dotenv

def test_tavily_api():
    print("Loading environment variables from .env...")
    dotenv_path = os.path.join(os.path.dirname(__file__), ".env")
    if os.path.exists(dotenv_path):
        load_dotenv(dotenv_path)
        print(f"Loaded .env from {dotenv_path}")
    else:
        load_dotenv()
        print("Loaded .env from default location")

    api_key = os.environ.get("TAVILY_API_KEY", "").strip()
    if not api_key:
        print("[ERROR] TAVILY_API_KEY is not set in the environment or .env file.")
        return False
    
    if api_key == "your_tavily_api_key_here":
        print("[ERROR] TAVILY_API_KEY is still set to the placeholder value.")
        return False

    masked_key = api_key[:8] + "..." + api_key[-4:] if len(api_key) > 12 else "***"
    print(f"Using Tavily API Key: {masked_key}")

    url = "https://api.tavily.com/search"
    payload = {
        "api_key": api_key,
        "query": "Indian government scheme widow bihar 2025",
        "search_depth": "basic",
        "max_results": 3,
        "include_domains": ["gov.in", "nic.in"]
    }
    
    print("Sending test search request to Tavily API...")
    try:
        response = requests.post(url, json=payload, timeout=10)
        status_code = response.status_code
        print(f"HTTP Status Code: {status_code}")
        
        if status_code == 200:
            data = response.json()
            results = data.get("results", [])
            print("[SUCCESS] Tavily API key works perfectly!")
            print(f"Found {len(results)} search results:")
            for idx, r in enumerate(results):
                title = r.get("title", "No Title")
                link = r.get("url", "No URL")
                print(f"  {idx+1}. {title}")
                print(f"     Link: {link}")
            return True
        elif status_code == 401:
            print("[ERROR] Tavily API returned status 401 (Unauthorized).")
            print("[TIP] Your Tavily API key appears to be invalid or deactivated. Please check your Tavily dashboard at https://tavily.com to verify your API key.")
            return False
        elif status_code == 429:
            print("[ERROR] Tavily API returned status 429 (Rate Limit Exceeded).")
            print("[TIP] You have hit your request rate limit or run out of search credits on your Tavily account.")
            return False
        else:
            print(f"[ERROR] Tavily API returned status code {status_code}.")
            try:
                print(f"Response: {response.text}")
            except Exception:
                pass
            return False
            
    except Exception as e:
        print(f"[ERROR] Network/Connection Error while connecting to Tavily: {e}")
        return False

if __name__ == "__main__":
    test_tavily_api()
