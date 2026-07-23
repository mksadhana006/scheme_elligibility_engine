import time
import math
import logging
import threading
import requests
import streamlit as st
from collections import deque

# Configure logging
logger = logging.getLogger(__name__)

class RateLimiter:
    """Thread-safe rate limiter for API requests."""
    def __init__(self, max_per_second=1, max_per_minute=30):
        self.max_per_second = max_per_second
        self.max_per_minute = max_per_minute
        self.second_timestamps = deque()
        self.minute_timestamps = deque()
        self.lock = threading.Lock()

    def wait(self):
        """Wait until it is safe to make another request."""
        with self.lock:
            now = time.time()
            
            # Clean up old timestamps
            while self.second_timestamps and now - self.second_timestamps[0] >= 1.0:
                self.second_timestamps.popleft()
            while self.minute_timestamps and now - self.minute_timestamps[0] >= 60.0:
                self.minute_timestamps.popleft()
                
            # Wait if limits are exceeded
            if len(self.second_timestamps) >= self.max_per_second:
                wait_time = 1.0 - (now - self.second_timestamps[0])
                if wait_time > 0:
                    time.sleep(wait_time)
                now = time.time()
                
            if len(self.minute_timestamps) >= self.max_per_minute:
                wait_time = 60.0 - (now - self.minute_timestamps[0])
                if wait_time > 0:
                    time.sleep(wait_time)
                now = time.time()

            self.second_timestamps.append(now)
            self.minute_timestamps.append(now)

# Global rate limiter and session to reuse across requests
rate_limiter = RateLimiter(max_per_second=1, max_per_minute=30)
session = requests.Session()
session.headers.update({'User-Agent': 'AdhikaarSchemeEngine/1.0 (Contact: local-admin)'})

def haversine_distance(lat1, lon1, lat2, lon2):
    """Calculate the great circle distance in kilometers between two points on the earth."""
    R = 6371.0 # Earth radius in kilometers

    lat1_rad = math.radians(float(lat1))
    lon1_rad = math.radians(float(lon1))
    lat2_rad = math.radians(float(lat2))
    lon2_rad = math.radians(float(lon2))

    dlon = lon2_rad - lon1_rad
    dlat = lat2_rad - lat1_rad

    a = math.sin(dlat / 2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    distance = R * c
    return distance

def get_address_from_coords(lat, lng):
    """
    Get address dictionary from coordinates using Nominatim Reverse Geocoding.
    Includes rate limiting and 10-second timeout handling.
    """
    url = f"https://nominatim.openstreetmap.org/reverse?format=json&lat={lat}&lon={lng}"
    rate_limiter.wait()
    try:
        resp = session.get(url, timeout=10)
        if resp.status_code == 200:
            return resp.json().get("address", {})
        else:
            logger.warning(f"Nominatim returned status code {resp.status_code}")
            return {}
    except requests.exceptions.RequestException as e:
        logger.error(f"Error calling Nominatim API: {e}")
        return {}

@st.cache_data(ttl=86400)
def get_formatted_address_from_coords(lat, lng):
    """
    Reverse geocode coordinates using Nominatim to get a formatted readable address.
    Cached by coordinates.
    """
    addr_dict = get_address_from_coords(lat, lng)
    if not addr_dict:
        return "Address not available"
        
    parts = []
    for key in ['road', 'suburb', 'village', 'town', 'city', 'state', 'postcode', 'country']:
        if key in addr_dict:
            parts.append(addr_dict[key])
            
    if parts:
        return ", ".join(parts)
    return "Address not available"

@st.cache_data(ttl=600)
def find_nearby_centres(lat, lng, center_type=None, radius_km=10):
    """
    Find nearby application centres using the Overpass API.
    Cached in Streamlit for 10 minutes.
    Retries up to 3 times with exponential backoff on HTTP 429, 500, 502, 503, 504.
    """
    radius_meters = radius_km * 1000
    
    # Overpass QL query searching for various government offices and centres
    query = f"""
    [out:json][timeout:10];
    (
      node["amenity"="townhall"](around:{radius_meters},{lat},{lng});
      node["office"="government"](around:{radius_meters},{lat},{lng});
      node["office"="employment_agency"](around:{radius_meters},{lat},{lng});
      node["amenity"="community_centre"](around:{radius_meters},{lat},{lng});
      way["amenity"="townhall"](around:{radius_meters},{lat},{lng});
      way["office"="government"](around:{radius_meters},{lat},{lng});
      way["office"="employment_agency"](around:{radius_meters},{lat},{lng});
      way["amenity"="community_centre"](around:{radius_meters},{lat},{lng});
    );
    out center;
    """
    
    url = "https://overpass-api.de/api/interpreter"
    
    backoff_times = [1, 2, 4]
    
    for attempt in range(len(backoff_times) + 1):
        rate_limiter.wait()
        try:
            resp = session.post(url, data={'data': query}, timeout=10)
            
            if resp.status_code == 200:
                data = resp.json()
                elements = data.get("elements", [])
                
                centres = []
                for el in elements:
                    el_lat = el.get("lat") or el.get("center", {}).get("lat")
                    el_lon = el.get("lon") or el.get("center", {}).get("lon")
                    
                    if el_lat is None or el_lon is None:
                        continue
                        
                    tags = el.get("tags", {})
                    name = tags.get("name", "Government Centre")
                    
                    # Filter based on recommended center type
                    if center_type:
                        name_lower = name.lower()
                        c_type_lower = center_type.lower()
                        if "common service centre" in c_type_lower or "csc" in c_type_lower or "e-sevai" in c_type_lower or "meeseva" in c_type_lower:
                            valid_keywords = ["csc", "common service centre", "e-sevai", "meeseva", "e-governance", "eseva"]
                            if not any(k in name_lower for k in valid_keywords):
                                continue
                        elif "taluk" in c_type_lower or "tehsildar" in c_type_lower:
                            if "taluk" not in name_lower and "tehsildar" not in name_lower:
                                continue
                        elif "collector" in c_type_lower:
                            if "collector" not in name_lower:
                                continue
                    
                    # Ignore unrelated POIs that might sneak into the Overpass results
                    unrelated = ["restaurant", "railway", "hospital", "hotel", "bus", "atm", "shop", "clinic", "bank", "school", "college"]
                    if any(u in name.lower() for u in unrelated):
                        continue
                    
                    distance = haversine_distance(lat, lng, el_lat, el_lon)
                    
                    # Try to get address from OSM tags first
                    address = tags.get("addr:full") or tags.get("addr:street")
                    if not address:
                        # Fallback to Nominatim Reverse Geocoding for this specific center
                        address = get_formatted_address_from_coords(el_lat, el_lon)
                    
                    centres.append({
                        "name": name,
                        "type": name,  # Setting type to name for compatibility with existing UI
                        "lat": el_lat,
                        "lng": el_lon,
                        "distance": distance,
                        "address": address
                    })
                    
                # Sort by distance
                centres.sort(key=lambda x: x["distance"])
                return centres
                
            elif resp.status_code in [429, 500, 502, 503, 504]:
                if attempt < len(backoff_times):
                    sleep_time = backoff_times[attempt]
                    logger.warning(f"Overpass API error {resp.status_code}. Retrying in {sleep_time}s...")
                    time.sleep(sleep_time)
                else:
                    logger.error(f"Overpass API error {resp.status_code}. Max retries reached.")
                    return []
            else:
                logger.error(f"Overpass API returned status code {resp.status_code}")
                return []
                
        except requests.exceptions.RequestException as e:
            if attempt < len(backoff_times):
                sleep_time = backoff_times[attempt]
                logger.warning(f"Network error: {e}. Retrying in {sleep_time}s...")
                time.sleep(sleep_time)
            else:
                logger.error(f"Max retries reached after network error: {e}")
                return []
                
    return []
