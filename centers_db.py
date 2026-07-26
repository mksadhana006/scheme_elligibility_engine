import os
import sqlite3
import math
import requests
import logging

logger = logging.getLogger("geolocation_workflow")

def haversine_distance(lat1, lon1, lat2, lon2):
    """
    Calculate the great circle distance between two points 
    on the earth (specified in decimal degrees) in kilometers.
    """
    # Radius of the Earth in km
    R = 6371.0
    
    lat1_rad = math.radians(lat1)
    lon1_rad = math.radians(lon1)
    lat2_rad = math.radians(lat2)
    lon2_rad = math.radians(lon2)
    
    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad
    
    a = math.sin(dlat / 2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    
    return R * c

import time
_last_nominatim_call = 0.0
_nominatim_cache = {}

def geocode_address_free(address):
    """
    Convert a text address / pincode / location into latitude and longitude
    using the free OpenStreetMap Nominatim geocoding API.
    """
    global _last_nominatim_call
    
    cleaned_address = address.strip().lower() if address else ""
    if not cleaned_address:
        return None
        
    if cleaned_address in _nominatim_cache:
        logger.info(f"OSM Nominatim cache hit for: '{address}'")
        return _nominatim_cache[cleaned_address]

    # Rate limit: ensure at least 1.0 second between Nominatim calls
    elapsed = time.time() - _last_nominatim_call
    if elapsed < 1.0:
        time.sleep(1.0 - elapsed)
    _last_nominatim_call = time.time()

    url = "https://nominatim.openstreetmap.org/search"
    headers = {
        "User-Agent": "AdhikaarSchemeEligibilityEngine/1.0 (contact: support@adhikaar.gov.in)"
    }
    params = {
        "q": address,
        "format": "json",
        "limit": 1
    }
    
    logger.info(f"Geocoding address '{address}' using OpenStreetMap Nominatim...")
    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data:
                lat = float(data[0]["lat"])
                lng = float(data[0]["lon"])
                formatted_address = data[0].get("display_name", address)
                logger.info(f"Nominatim Geocoding successful: lat={lat}, lng={lng}")
                res = (lat, lng, formatted_address)
                _nominatim_cache[cleaned_address] = res
                return res
            else:
                logger.warning(f"No Nominatim results found for address: '{address}'")
                return None
        else:
            logger.error(f"Nominatim request failed with HTTP Status: {response.status_code}")
            return None
    except Exception as e:
        logger.exception("Error while calling Nominatim Geocoding API")
        return None

def fetch_nearby_places_local(lat, lng, radius_km=5.0):
    """
    Retrieve application centers from the SQLite database that fall within the specified
    radius (in kilometers) from the given latitude and longitude.
    """
    db_path = os.path.join(os.path.dirname(__file__), "centers.db")
    if not os.path.exists(db_path):
        logger.error(f"Database centers.db not found at: {db_path}")
        return []
        
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT center_name, address, district, state, pincode, latitude, longitude, available_services 
        FROM application_centers
    """)
    rows = cursor.fetchall()
    conn.close()
    
    nearby_centers = []
    for row in rows:
        c_name, c_addr, c_dist, c_state, c_pin, c_lat, c_lng, c_services = row
        dist = haversine_distance(lat, lng, c_lat, c_lng)
        if dist <= radius_km:
            nearby_centers.append({
                "name": c_name,
                "address": c_addr,
                "district": c_dist,
                "state": c_state,
                "pincode": c_pin,
                "lat": c_lat,
                "lng": c_lng,
                "distance": dist,
                "services": c_services
            })
            
    # Sort results by distance (nearest first)
    nearby_centers.sort(key=lambda x: x["distance"])
    return nearby_centers

def fallback_text_search(query_text):
    """
    Filter application centers directly from the database matching the given query text 
    against district, state, pincode, or address. Used when geocoding is unavailable.
    """
    db_path = os.path.join(os.path.dirname(__file__), "centers.db")
    if not os.path.exists(db_path):
        logger.error(f"Database centers.db not found at: {db_path}")
        return []
        
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    search_pattern = f"%{query_text.strip()}%"
    cursor.execute("""
        SELECT center_name, address, district, state, pincode, latitude, longitude, available_services 
        FROM application_centers
        WHERE district LIKE ? OR state LIKE ? OR pincode LIKE ? OR address LIKE ?
        LIMIT 50
    """, (search_pattern, search_pattern, search_pattern, search_pattern))
    rows = cursor.fetchall()
    conn.close()
    
    results = []
    for row in rows:
        c_name, c_addr, c_dist, c_state, c_pin, c_lat, c_lng, c_services = row
        results.append({
            "name": c_name,
            "address": c_addr,
            "district": c_dist,
            "state": c_state,
            "pincode": c_pin,
            "lat": c_lat,
            "lng": c_lng,
            "distance": None, # Distance is not calculated because we don't have user coordinates
            "services": c_services
        })
    return results

_places_cache = {}

def fetch_places_new(lat, lng, query, api_key, radius_meters=3000.0):
    """
    Search for places near the given coordinates using the Google Places API (New) Text Search.
    Includes retry-with-backoff for HTTP 429 rate limits and a simple in-memory cache.
    """
    import requests
    import time as _time

    # Check cache first
    cache_key = f"{lat:.6f}_{lng:.6f}_{query}_{radius_meters}"
    if cache_key in _places_cache:
        logger.info(f"Google Places cache hit for query='{query}' near ({lat}, {lng})")
        return _places_cache[cache_key]

    url = "https://places.googleapis.com/v1/places:searchText"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.location"
    }
    payload = {
        "textQuery": query,
        "maxResultCount": 10,
        "locationBias": {
            "circle": {
                "center": {
                    "latitude": lat,
                    "longitude": lng
                },
                "radius": radius_meters
            }
        }
    }
    logger.info(f"Querying Google Places API (New) for '{query}' near ({lat}, {lng}) with radius {radius_meters}m...")

    max_retries = 2
    for attempt in range(max_retries + 1):
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=10)

            # Handle rate limiting (HTTP 429)
            if response.status_code == 429:
                if attempt < max_retries:
                    wait_time = (attempt + 1) * 3.0  # 3s, 6s
                    logger.warning(f"Google Places API rate limited (429). Retrying in {wait_time:.0f}s... (attempt {attempt+1}/{max_retries})")
                    _time.sleep(wait_time)
                    continue
                else:
                    logger.error("Google Places API rate limit exceeded after all retries.")
                    raise Exception("Google Places API rate limit exceeded. Please try again in a minute.")

            if response.status_code != 200:
                try:
                    error_data = response.json()
                except Exception:
                    error_data = {}
                error_message = error_data.get("error", {}).get("message", f"HTTP status code {response.status_code}")
                logger.error(f"Google Places API returned error: {error_message}")
                raise Exception(f"Google Places API Error: {error_message}")

            data = response.json()
            places_raw = data.get("places", [])

            results = []
            for p in places_raw:
                name = p.get("displayName", {}).get("text", "Unknown Center")
                address = p.get("formattedAddress", "No Address Available")
                loc = p.get("location", {})
                item_lat = loc.get("latitude")
                item_lng = loc.get("longitude")

                if item_lat is None or item_lng is None:
                    continue

                dist = haversine_distance(lat, lng, item_lat, item_lng)
                results.append({
                    "name": name,
                    "address": address,
                    "lat": item_lat,
                    "lng": item_lng,
                    "distance": dist,
                    "district": "Google Places",
                    "state": "Google Places",
                    "pincode": "",
                    "services": "Dynamic Services (Google Places)"
                })

            # Sort results by distance (nearest first)
            results.sort(key=lambda x: x["distance"])

            # Cache the results
            _places_cache[cache_key] = results
            return results

        except requests.exceptions.RequestException as e:
            if attempt < max_retries:
                wait_time = (attempt + 1) * 2.0
                logger.warning(f"Network error in Google Places API. Retrying in {wait_time:.0f}s... (attempt {attempt+1}/{max_retries}): {e}")
                _time.sleep(wait_time)
                continue
            logger.exception("Network error while connecting to Google Places API (New)")
            raise Exception(f"Network error while connecting to Google Places API (New): {str(e)}")
