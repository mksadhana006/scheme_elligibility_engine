"""
End-to-end test: Nearest Application Center workflow
Tests the FULL pipeline that runs when a user clicks "Find Nearest Centers":
  1. Nominatim free geocoding (address -> lat/lng)
  2. Google Places API (New) Text Search (lat/lng -> nearby centers)
  3. Haversine distance calculation
  4. Sorting by distance (nearest first)
  5. Verifies API key is loaded from .env
"""
import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dotenv import load_dotenv
load_dotenv()

from centers_db import geocode_address_free, fetch_places_new, haversine_distance

PASS_COUNT = 0
FAIL_COUNT = 0

def log_pass(msg):
    global PASS_COUNT
    PASS_COUNT += 1
    print(f"  [PASS] {msg}")

def log_fail(msg):
    global FAIL_COUNT
    FAIL_COUNT += 1
    print(f"  [FAIL] {msg}")

def section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


# =====================================================================
#  TEST 1: Verify GOOGLE_MAPS_API_KEY is loaded from .env
# =====================================================================
section("TEST 1: Google Maps API Key Check")

api_key = os.environ.get("GOOGLE_MAPS_API_KEY")
if api_key:
    masked = api_key[:8] + "..." + api_key[-4:]
    log_pass(f"GOOGLE_MAPS_API_KEY is set: {masked}")
else:
    log_fail("GOOGLE_MAPS_API_KEY is NOT set in .env")
    print("\n  Cannot proceed without API key. Exiting.")
    sys.exit(1)


# =====================================================================
#  TEST 2: Nominatim geocoding — Anna Nagar, Madurai, Tamil Nadu
# =====================================================================
section("TEST 2: Nominatim Geocoding (Madurai)")

address1 = "Anna Nagar, Madurai, Tamil Nadu"
print(f"  Location: {address1}")

result1 = geocode_address_free(address1)
if result1:
    lat1, lng1, display1 = result1
    print(f"  Latitude:     {lat1}")
    print(f"  Longitude:    {lng1}")
    print(f"  Display Name: {display1}")
    if 9.0 < lat1 < 11.0 and 77.0 < lng1 < 79.0:
        log_pass("Coordinates are valid for Madurai region")
    else:
        log_fail(f"Coordinates ({lat1}, {lng1}) outside expected Madurai range")
else:
    log_fail("Nominatim returned None for Madurai address")
    lat1, lng1 = None, None


# =====================================================================
#  TEST 3: Google Places API — e-Sevai centers near Madurai
# =====================================================================
section("TEST 3: Google Places API (New) — Madurai e-Sevai Centers")

if lat1 and lng1:
    print(f"  Coordinates: ({lat1}, {lng1})")
    print(f"  Query:       'e-Sevai center'")
    print(f"  Radius:      3000m")
    
    try:
        centers1 = fetch_places_new(lat1, lng1, "e-Sevai center", api_key, radius_meters=3000.0)
        print(f"  Centers returned: {len(centers1)}")
        
        if len(centers1) > 0:
            log_pass(f"Google Places returned {len(centers1)} centers")
            
            # Check sorting
            distances = [c['distance'] for c in centers1]
            is_sorted = all(distances[i] <= distances[i+1] for i in range(len(distances)-1))
            if is_sorted:
                log_pass("Centers are sorted nearest-first by Haversine distance")
            else:
                log_fail("Centers are NOT sorted by distance")
            
            # Display results
            print(f"\n  Nearest Centers:")
            print(f"  {'#':>3}  {'Name':<42}  {'Distance':>10}  {'Lat':>10}  {'Lng':>10}")
            print(f"  {'---':>3}  {'------------------------------------------':<42}  {'----------':>10}  {'----------':>10}  {'----------':>10}")
            for i, c in enumerate(centers1):
                name = c['name'][:42]
                # Safely encode for Windows console
                try:
                    name.encode('cp1252')
                except UnicodeEncodeError:
                    name = name.encode('ascii', errors='replace').decode('ascii')
                print(f"  {i+1:>3}  {name:<42}  {c['distance']:>7.2f} km  {c['lat']:>10.6f}  {c['lng']:>10.6f}")
            
            # Verify first center has required fields
            first = centers1[0]
            required_fields = ['name', 'address', 'lat', 'lng', 'distance']
            all_present = all(k in first for k in required_fields)
            if all_present:
                log_pass("Each center has: name, address, lat, lng, distance")
            else:
                missing = [k for k in required_fields if k not in first]
                log_fail(f"Missing fields in center data: {missing}")
            
            # Verify nearest center appears first
            if centers1[0]['distance'] <= centers1[-1]['distance']:
                log_pass(f"Nearest center: '{centers1[0]['name'][:40]}' at {centers1[0]['distance']:.2f} km")
            else:
                log_fail("Nearest center is NOT first in the list")
        else:
            log_fail("Google Places returned 0 centers")
    except Exception as e:
        log_fail(f"Google Places API call failed: {e}")
else:
    log_fail("Skipped — no coordinates from Nominatim")


# =====================================================================
#  TEST 4: Dynamic location test — Chennai
# =====================================================================
section("TEST 4: Dynamic Location Test (Chennai)")

address2 = "T. Nagar, Chennai, Tamil Nadu"
print(f"  Location: {address2}")

# Brief pause to respect Nominatim rate limits
time.sleep(1.5)

result2 = geocode_address_free(address2)
if result2:
    lat2, lng2, display2 = result2
    print(f"  Latitude:     {lat2}")
    print(f"  Longitude:    {lng2}")
    print(f"  Display Name: {display2}")
    
    if 12.0 < lat2 < 14.0 and 79.0 < lng2 < 81.0:
        log_pass("Chennai coordinates are valid")
    else:
        log_fail(f"Chennai coordinates ({lat2}, {lng2}) out of range")
    
    # Verify different from Madurai
    if lat1 and abs(lat2 - lat1) > 1.0:
        log_pass("Different coordinates returned for different cities (dynamic)")
    else:
        log_fail("Same coordinates returned for different cities")
    
    # Google Places for Chennai
    try:
        centers2 = fetch_places_new(lat2, lng2, "e-Sevai center", api_key, radius_meters=3000.0)
        print(f"  Centers returned: {len(centers2)}")
        
        if len(centers2) > 0:
            log_pass(f"Google Places returned {len(centers2)} centers for Chennai")
            
            # Verify different results from Madurai
            madurai_names = set(c['name'] for c in centers1) if lat1 else set()
            chennai_names = set(c['name'] for c in centers2)
            if madurai_names != chennai_names:
                log_pass("Different centers returned for Chennai vs Madurai (dynamic)")
            else:
                log_fail("Same centers returned for both cities")
            
            # Print nearest for Chennai
            nearest_c = centers2[0]
            try:
                cname = nearest_c['name'].encode('ascii', errors='replace').decode('ascii')
            except Exception:
                cname = nearest_c['name']
            print(f"  Nearest: '{cname}' at {nearest_c['distance']:.2f} km")
            log_pass(f"Nearest Chennai center identified")
        else:
            log_fail("Google Places returned 0 centers for Chennai")
    except Exception as e:
        log_fail(f"Google Places API call failed for Chennai: {e}")
else:
    log_fail("Nominatim returned None for Chennai address")


# =====================================================================
#  TEST 5: Haversine distance verification
# =====================================================================
section("TEST 5: Haversine Distance Sanity Check")

if lat1 and lat2:
    dist = haversine_distance(lat1, lng1, lat2, lng2)
    print(f"  Madurai -> Chennai: {dist:.2f} km")
    if 350 < dist < 500:
        log_pass(f"Haversine distance {dist:.2f} km is reasonable for Madurai-Chennai")
    else:
        log_fail(f"Haversine distance {dist:.2f} km seems wrong")


# =====================================================================
#  TEST 6: Error handling — empty location
# =====================================================================
section("TEST 6: Error Handling — Empty Location")

result_empty = geocode_address_free("")
if result_empty is None:
    log_pass("Empty string returns None (handled gracefully)")
else:
    log_fail("Empty string should return None")

result_space = geocode_address_free("   ")
if result_space is None:
    log_pass("Whitespace-only string returns None (handled gracefully)")
else:
    log_fail("Whitespace string should return None")


# =====================================================================
#  TEST 7: Session state initialization check
# =====================================================================
section("TEST 7: Session State Initialization in app.py")

with open("app.py", "r", encoding="utf-8") as f:
    content = f.read()

variables = {
    "find_centers_clicked": False,
    "nearby_centers": [],
    "geo_state": "pending_input",
    "user_lat": None,
    "user_lng": None,
    "location_source": "",
    "detail_entered_address": "",
}

for var in variables:
    if f"'{var}' not in st.session_state" in content:
        log_pass(f"'{var}' safely initialized in init_session()")
    else:
        log_fail(f"'{var}' NOT initialized in init_session()")

# Check the AttributeError line is now safe
if "if st.session_state.find_centers_clicked:" in content:
    init_pos = content.find("def init_session():")
    access_pos = content.find("if st.session_state.find_centers_clicked:")
    if init_pos < access_pos:
        log_pass("find_centers_clicked initialized BEFORE first access")
    else:
        log_fail("find_centers_clicked accessed BEFORE initialization")


# =====================================================================
#  SUMMARY
# =====================================================================
section("TEST SUMMARY")
total = PASS_COUNT + FAIL_COUNT
print(f"\n  Total:  {total}")
print(f"  Passed: {PASS_COUNT}")
print(f"  Failed: {FAIL_COUNT}")

if FAIL_COUNT == 0:
    print(f"\n  ** ALL {PASS_COUNT} TESTS PASSED **")
else:
    print(f"\n  ** {FAIL_COUNT} TEST(S) FAILED **")

print(f"\n{'='*60}\n")
