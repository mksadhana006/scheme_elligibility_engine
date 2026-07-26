import os
import requests
import json
import urllib3
from dotenv import load_dotenv

# Suppress SSL/Insecure Request Warnings (useful for local development environments with SSL issues)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def run_workflow(location_name="Anna Nagar, Madurai, Tamil Nadu", search_query="e sevai center"):
    # 1. Load API Key
    load_dotenv()
    api_key = os.environ.get("GOOGLE_MAPS_API_KEY")
    if not api_key:
        print("Error: GOOGLE_MAPS_API_KEY missing from environment or .env file.")
        return None

    # 2. Step 1: Geocoding via Nominatim
    print(f"\n[Step 1] Resolving location string '{location_name}' using Nominatim...")
    nominatim_url = "https://nominatim.openstreetmap.org/search"
    headers = {"User-Agent": "location_app_flow"}
    params = {"q": location_name, "format": "json", "limit": 1}
    
    try:
        res = requests.get(nominatim_url, headers=headers, params=params, verify=False)
        data = res.json()
        if not data:
            print(f"❌ Could not geocode '{location_name}'")
            return None
        
        lat = float(data[0]["lat"])
        lng = float(data[0]["lon"])
        resolved_addr = data[0]["display_name"]
        print(f"✅ Resolved to: {resolved_addr} (Lat: {lat}, Lng: {lng})")
    except Exception as e:
        print(f"💥 Nominatim request failed: {e}")
        return None

    # 3. Step 2: Places API (New) Text Search with Location Bias
    print(f"\n[Step 2] Querying Google Places API (New) for '{search_query}' near coordinates...")
    places_url = "https://places.googleapis.com/v1/places:searchText"
    places_headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.location"
    }
    payload = {
        "textQuery": search_query,
        "maxResultCount": 10,
        "locationBias": {
            "circle": {
                "center": {
                    "latitude": lat,
                    "longitude": lng
                },
                "radius": 3000.0  # 3km bias radius
            }
        }
    }

    try:
        response = requests.post(places_url, headers=places_headers, json=payload, verify=False)
        if response.status_code != 200:
            print(f"❌ Google Places API returned status code {response.status_code}")
            print(json.dumps(response.json(), indent=2))
            return None
            
        places_data = response.json()
        places = places_data.get("places", [])
        print(f"✅ Success! Found {len(places)} results:")
        for idx, p in enumerate(places):
            name = p.get("displayName", {}).get("text", "Unknown Name")
            address = p.get("formattedAddress", "Unknown Address")
            loc = p.get("location", {})
            print(f"   {idx+1}. {name}")
            print(f"      Address: {address}")
            print(f"      Coordinates: ({loc.get('latitude')}, {loc.get('longitude')})")
            
        return places
    except Exception as e:
        print(f"💥 Google Places API call failed: {e}")
        return None

if __name__ == "__main__":
    run_workflow()
