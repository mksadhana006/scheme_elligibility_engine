"""
Test script to verify the Nearest Application Center workflow:
1. Nominatim geocoding (free)
2. Google Places API (New) Text Search
3. Haversine distance calculation
4. Sorting by distance (nearest first)
"""
import sys
import os

# Add the project directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from centers_db import geocode_address_free, fetch_places_new, haversine_distance

def test_nominatim_geocoding():
    """Test 1: Nominatim resolves 'Anna Nagar, Madurai, Tamil Nadu' to lat/lng."""
    print("=" * 60)
    print("TEST 1: Nominatim Geocoding")
    print("=" * 60)
    
    address = "Anna Nagar, Madurai, Tamil Nadu"
    print(f"Input address: {address}")
    
    result = geocode_address_free(address)
    
    if result is None:
        print("FAIL: Nominatim returned None")
        return None, None
    
    lat, lng, display_name = result
    print(f"  Latitude:     {lat}")
    print(f"  Longitude:    {lng}")
    print(f"  Display Name: {display_name}")
    
    # Sanity check: Madurai is roughly around 9.9°N, 78.1°E
    assert 9.0 < lat < 11.0, f"Latitude {lat} out of expected range for Madurai"
    assert 77.0 < lng < 79.0, f"Longitude {lng} out of expected range for Madurai"
    print("PASS: Coordinates are in the expected range for Madurai\n")
    return lat, lng


def test_nominatim_chennai():
    """Test 2: Nominatim resolves 'Chennai, Tamil Nadu' to lat/lng."""
    print("=" * 60)
    print("TEST 2: Nominatim Geocoding (Chennai)")
    print("=" * 60)
    
    address = "Chennai, Tamil Nadu"
    print(f"Input address: {address}")
    
    result = geocode_address_free(address)
    
    if result is None:
        print("FAIL: Nominatim returned None")
        return None, None
    
    lat, lng, display_name = result
    print(f"  Latitude:     {lat}")
    print(f"  Longitude:    {lng}")
    print(f"  Display Name: {display_name}")
    
    assert 12.0 < lat < 14.0, f"Latitude {lat} out of expected range for Chennai"
    assert 79.0 < lng < 81.0, f"Longitude {lng} out of expected range for Chennai"
    print("PASS: Coordinates are in the expected range for Chennai\n")
    return lat, lng


def test_google_places_search(lat, lng, location_label):
    """Test 3: Google Places API (New) returns e-Sevai centers near coordinates."""
    print("=" * 60)
    print(f"TEST 3: Google Places API (New) Text Search near {location_label}")
    print("=" * 60)
    
    api_key = os.environ.get("GOOGLE_MAPS_API_KEY")
    if not api_key:
        print("SKIP: GOOGLE_MAPS_API_KEY not found in environment")
        return []
    
    print(f"  Using coordinates: lat={lat}, lng={lng}")
    print(f"  Search query: 'e-Sevai center'")
    print(f"  Radius: 3000m")
    
    try:
        centers = fetch_places_new(lat, lng, "e-Sevai center", api_key, radius_meters=3000.0)
    except Exception as e:
        print(f"ERROR: Google Places API call failed: {e}")
        return []
    
    print(f"  Results returned: {len(centers)}")
    
    if not centers:
        print("WARNING: No centers found (this may be expected for some locations)")
        return []
    
    # Verify sorting: distances should be non-decreasing
    distances = [c['distance'] for c in centers]
    is_sorted = all(distances[i] <= distances[i+1] for i in range(len(distances)-1))
    print(f"  Sorted by distance (nearest first): {'YES' if is_sorted else 'NO'}")
    
    print(f"\n  {'#':>3}  {'Name':<40}  {'Distance (km)':>13}  {'Lat':>10}  {'Lng':>10}")
    print(f"  {'---':>3}  {'----------------------------------------':<40}  {'-------------':>13}  {'----------':>10}  {'----------':>10}")
    for i, c in enumerate(centers):
        print(f"  {i+1:>3}  {c['name'][:40]:<40}  {c['distance']:>10.2f} km  {c['lat']:>10.6f}  {c['lng']:>10.6f}")
    
    if is_sorted:
        print(f"\nPASS: {len(centers)} centers returned, sorted nearest first\n")
    else:
        print(f"\nFAIL: Centers are NOT sorted by distance\n")
    
    return centers


def test_haversine():
    """Test 4: Haversine distance calculation."""
    print("=" * 60)
    print("TEST 4: Haversine Distance Calculation")
    print("=" * 60)
    
    # Known distance: Madurai (9.9252, 78.1198) to Chennai (13.0827, 80.2707) ≈ 461 km
    madurai_lat, madurai_lng = 9.9252, 78.1198
    chennai_lat, chennai_lng = 13.0827, 80.2707
    
    dist = haversine_distance(madurai_lat, madurai_lng, chennai_lat, chennai_lng)
    print(f"  Madurai ({madurai_lat}, {madurai_lng}) -> Chennai ({chennai_lat}, {chennai_lng})")
    print(f"  Calculated distance: {dist:.2f} km")
    print(f"  Expected: ~420 km")
    
    assert 400 < dist < 480, f"Distance {dist} km not in expected range 400-480"
    print("PASS: Haversine distance is within expected range\n")


def test_session_state_check():
    """Test 5: Verify that init_session initializes find_centers_clicked."""
    print("=" * 60)
    print("TEST 5: Session State Initialization Check (code analysis)")
    print("=" * 60)
    
    with open("app.py", "r", encoding="utf-8") as f:
        content = f.read()
    
    checks = [
        ("find_centers_clicked", "'find_centers_clicked' not in st.session_state"),
        ("nearby_centers", "'nearby_centers' not in st.session_state"),
        ("geo_state", "'geo_state' not in st.session_state"),
        ("user_lat", "'user_lat' not in st.session_state"),
        ("user_lng", "'user_lng' not in st.session_state"),
        ("location_source", "'location_source' not in st.session_state"),
        ("detail_entered_address", "'detail_entered_address' not in st.session_state"),
    ]
    
    all_pass = True
    for var_name, expected_line in checks:
        found = expected_line in content
        status = "PASS" if found else "FAIL"
        if not found:
            all_pass = False
        print(f"  {status}: {var_name} initialized in init_session()")
    
    # Verify find_centers_clicked is NOT accessed before init
    # Check that 'if st.session_state.find_centers_clicked:' appears AFTER init_session()
    init_pos = content.find("def init_session():")
    access_pos = content.find("if st.session_state.find_centers_clicked:")
    if init_pos < access_pos:
        print("  PASS: find_centers_clicked accessed after init_session() definition")
    else:
        print("  FAIL: find_centers_clicked accessed BEFORE init_session() definition")
        all_pass = False
    
    if all_pass:
        print("\nPASS: All session state variables are properly initialized\n")
    else:
        print("\nFAIL: Some session state variables are missing initialization\n")


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("  NEAREST APPLICATION CENTER - VERIFICATION TESTS")
    print("=" * 60 + "\n")
    
    # Test 1: Nominatim geocoding for Madurai
    madurai_lat, madurai_lng = test_nominatim_geocoding()
    
    # Test 2: Nominatim geocoding for Chennai
    chennai_lat, chennai_lng = test_nominatim_chennai()
    
    # Test 3: Google Places search near Madurai
    if madurai_lat and madurai_lng:
        test_google_places_search(madurai_lat, madurai_lng, "Anna Nagar, Madurai")
    
    # Test 3b: Google Places search near Chennai (dynamic location test)
    if chennai_lat and chennai_lng:
        test_google_places_search(chennai_lat, chennai_lng, "Chennai")
    
    # Test 4: Haversine distance
    test_haversine()
    
    # Test 5: Session state code analysis
    test_session_state_check()
    
    print("=" * 60)
    print("  ALL TESTS COMPLETED")
    print("=" * 60)
