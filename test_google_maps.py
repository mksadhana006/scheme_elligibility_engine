import os
import requests
from dotenv import load_dotenv

def geocode_address(address, api_key):
    url = "https://maps.googleapis.com/maps/api/geocode/json"
    params = {
        "address": address,
        "key": api_key
    }
    print(f"Testing Geocoding API for address: '{address}'...")
    response = requests.get(url, params=params, timeout=10)
    if response.status_code == 200:
        data = response.json()
        status = data.get("status")
        if status == "OK" and data.get("results"):
            loc = data["results"][0]["geometry"]["location"]
            formatted_address = data["results"][0].get("formatted_address", address)
            print(f"[SUCCESS] Geocoded successfully! coordinates: lat={loc['lat']}, lng={loc['lng']}")
            print(f"Formatted Address: {formatted_address}")
            return loc["lat"], loc["lng"]
        else:
            print(f"[ERROR] Geocoding API returned status {status}: {data.get('error_message', 'No detail')}")
            return None
    else:
        print(f"[ERROR] Geocoding HTTP status {response.status_code}")
        return None

def fetch_nearby_places(lat, lng, api_key, radius=5000):
    url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
    params = {
        "location": f"{lat},{lng}",
        "radius": radius,
        "keyword": "e-sevai center CSC citizen service center government office",
        "key": api_key
    }
    
    print(f"Testing Places API (Nearby Search) for lat={lat}, lng={lng} with radius={radius}m...")
    response = requests.get(url, params=params, timeout=10)
    if response.status_code == 200:
        data = response.json()
        status = data.get("status")
        print(f"Places API status: {status}")
        if status == "OK":
            results = data.get("results", [])
            print(f"[SUCCESS] Found {len(results)} centers within {radius/1000} km.")
            for idx, c in enumerate(results[:3]):
                print(f"  {idx+1}. {c.get('name')} - {c.get('vicinity')} (Lat: {c.get('geometry', {}).get('location', {}).get('lat')}, Lng: {c.get('geometry', {}).get('location', {}).get('lng')})")
            return True
        elif status == "ZERO_RESULTS":
            print(f"[SUCCESS] Places API worked, but found zero e-Sevai/CSC centers within {radius/1000} km of this location.")
            return True
        else:
            print(f"[ERROR] Places API returned error: {status} - {data.get('error_message', 'No detail')}")
            return False
    else:
        print(f"[ERROR] Places HTTP status {response.status_code}")
        return False

def test_google_maps_workflow():
    print("Loading environment variables from .env...")
    dotenv_path = os.path.join(os.path.dirname(__file__), ".env")
    if os.path.exists(dotenv_path):
        load_dotenv(dotenv_path)
        print(f"Loaded .env from {dotenv_path}")
    else:
        load_dotenv()
        print("Loaded .env from default location")

    api_key = os.environ.get("GOOGLE_MAPS_API_KEY", "").strip()
    if not api_key:
        print("[ERROR] GOOGLE_MAPS_API_KEY is not set.")
        return
    
    masked_key = api_key[:6] + "..." + api_key[-4:] if len(api_key) > 10 else "***"
    print(f"Using API Key: {masked_key}")

    # 1. Geocode location (e.g., Chennai, Tamil Nadu)
    address = "Chennai, Tamil Nadu"
    coords = geocode_address(address, api_key)
    if not coords:
        print("\n[TIP] Troubleshooting Geocoding API:")
        print("- Make sure the 'Geocoding API' is enabled on your Google Cloud Console project.")
        print("- Verify billing is active.")
        return

    # 2. Nearby search within 5 km
    lat, lng = coords
    success = fetch_nearby_places(lat, lng, api_key, radius=5000)
    if not success:
        print("\n[TIP] Troubleshooting Places API:")
        print("- Make sure the legacy 'Places API' (not just Places API New) is enabled on your project.")
        print("- Verify billing is active.")

if __name__ == "__main__":
    test_google_maps_workflow()
