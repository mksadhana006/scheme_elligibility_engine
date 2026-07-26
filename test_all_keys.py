import os
import requests
from dotenv import load_dotenv

def test_gemini_api(api_key):
    print("\n--- Testing Google Gemini API ---")
    if not api_key:
        print("[ERROR] GEMINI_API_KEY is not set.")
        return False
    
    masked_key = api_key[:6] + "..." + api_key[-4:] if len(api_key) > 10 else "***"
    print(f"Using Gemini Key: {masked_key}")
    
    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key, transport="rest")
        
        # Test models cascade (trying both legacy names and standard names)
        models_to_try = [
            "gemini-1.5-flash", 
            "gemini-2.5-flash", 
            "gemini-2.0-flash", 
            "gemini-1.5-flash-8b", 
            "gemini-3.5-flash",
            "gemini-3.1-flash-lite"
        ]
        success = False
        for model_name in models_to_try:
            try:
                print(f"Trying model '{model_name}'...")
                model = genai.GenerativeModel(model_name)
                response = model.generate_content("Hello! Say 'Gemini works!' in one sentence.", generation_config={"max_output_tokens": 20})
                print(f"[SUCCESS] Gemini model '{model_name}' output: {response.text.strip()}")
                success = True
                break
            except Exception as e:
                print(f"Model '{model_name}' failed: {e}")
        return success
    except ImportError:
        print("[ERROR] google-generativeai package not installed.")
        return False
    except Exception as e:
        print(f"[ERROR] Gemini API failed: {e}")
        return False

def test_google_maps_api(api_key):
    print("\n--- Testing Google Maps API ---")
    if not api_key:
        print("[ERROR] GOOGLE_MAPS_API_KEY is not set.")
        return False
    
    masked_key = api_key[:6] + "..." + api_key[-4:] if len(api_key) > 10 else "***"
    print(f"Using Google Maps Key: {masked_key}")
    
    # 1. Test Geocoding API
    geocode_url = "https://maps.googleapis.com/maps/api/geocode/json"
    params = {
        "address": "Delhi, India",
        "key": api_key
    }
    geocode_success = False
    lat, lng = None, None
    try:
        r = requests.get(geocode_url, params=params, timeout=10)
        if r.status_code == 200:
            data = r.json()
            status = data.get("status")
            if status == "OK" and data.get("results"):
                loc = data["results"][0]["geometry"]["location"]
                lat, lng = loc["lat"], loc["lng"]
                print(f"[SUCCESS] Geocoding API works perfectly! Coordinates: lat={lat}, lng={lng}")
                geocode_success = True
            else:
                print(f"[ERROR] Geocoding API returned status '{status}': {data.get('error_message', 'No detail')}")
                if status == "REQUEST_DENIED":
                    print("[TIP] You need to search for 'Geocoding API' in GCP Console and click 'Enable'.")
        else:
            print(f"[ERROR] Geocoding API HTTP Error: {r.status_code}")
    except Exception as e:
        print(f"[ERROR] Geocoding connection error: {e}")

    # 2. Test Places API (Nearby Search)
    places_url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
    if lat is not None and lng is not None:
        params_places = {
            "location": f"{lat},{lng}",
            "radius": 5000,
            "keyword": "e-sevai center CSC citizen service center government office",
            "key": api_key
        }
        try:
            r = requests.get(places_url, params=params_places, timeout=10)
            if r.status_code == 200:
                data = r.json()
                status = data.get("status")
                if status in ["OK", "ZERO_RESULTS"]:
                    print(f"[SUCCESS] Places API (Legacy) works perfectly! Status: {status}")
                else:
                    print(f"[ERROR] Places API returned status '{status}': {data.get('error_message', 'No detail')}")
                    if status == "REQUEST_DENIED":
                        print("[TIP] You need to search for the legacy 'Places API' (not just Places API New) in GCP Console and click 'Enable'.")
            else:
                print(f"[ERROR] Places API HTTP Error: {r.status_code}")
        except Exception as e:
            print(f"[ERROR] Places connection error: {e}")
    else:
        print("[INFO] Skipping Places API test because Geocoding coordinates were not obtained.")
    
    return geocode_success

def test_tavily_api(api_key):
    print("\n--- Testing Tavily Search API ---")
    if not api_key:
        print("[ERROR] TAVILY_API_KEY is not set.")
        return False
    
    masked_key = api_key[:8] + "..." + api_key[-4:] if len(api_key) > 12 else "***"
    print(f"Using Tavily Key: {masked_key}")
    
    url = "https://api.tavily.com/search"
    payload = {
        "api_key": api_key,
        "query": "Indian government scheme 2025",
        "search_depth": "basic",
        "max_results": 2
    }
    try:
        r = requests.post(url, json=payload, timeout=10)
        if r.status_code == 200:
            data = r.json()
            results = data.get("results", [])
            print(f"[SUCCESS] Tavily API works perfectly! Found {len(results)} search results.")
            return True
        else:
            print(f"[ERROR] Tavily API returned status {r.status_code}: {r.text}")
            return False
    except Exception as e:
        print(f"[ERROR] Tavily connection failed (expected if terminal sandbox has no outgoing internet): {e}")
        return False

def main():
    print("Loading env variables...")
    dotenv_path = os.path.join(os.path.dirname(__file__), ".env")
    if os.path.exists(dotenv_path):
        load_dotenv(dotenv_path)
        print(f"Loaded .env from {dotenv_path}")
    else:
        load_dotenv()
        print("Loaded .env from default location")
        
    gemini_key = os.environ.get("GEMINI_API_KEY", "").strip()
    maps_key = os.environ.get("GOOGLE_MAPS_API_KEY", "").strip()
    tavily_key = os.environ.get("TAVILY_API_KEY", "").strip()
    
    test_gemini_api(gemini_key)
    test_google_maps_api(maps_key)
    test_tavily_api(tavily_key)

if __name__ == "__main__":
    main()
