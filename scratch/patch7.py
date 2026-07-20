import re

with open('app.py', 'r', encoding='utf-8') as f:
    content = f.read()

start_idx = content.find('def render_nearest_centers():')
if start_idx == -1:
    print("Could not find render_nearest_centers")
    exit(1)

end_idx = content.find('def main():', start_idx)
if end_idx == -1:
    print("Could not find def main():")
    exit(1)

new_func = """def render_nearest_centers():
    import requests
    scheme = st.session_state.get("selected_scheme")
    profile_state = st.session_state.profile.get("State")
    if not profile_state or profile_state not in STATE_CITIES:
        profile_state = "Other"

    # Reset manual mode if we already have GPS granted
    if "geo_state" not in st.session_state:
        st.session_state.geo_state = "requesting"
    if st.session_state.geo_state == "granted" and st.session_state.get("location_source") == "gps":
        st.session_state.manual_location_mode = False
    elif "manual_location_mode" not in st.session_state:
        st.session_state.manual_location_mode = False

    if "location_retry_failed" not in st.session_state:
        st.session_state.location_retry_failed = False
        
    st.markdown(f"<h2 style='color:#0f172a; font-weight:800; margin-bottom:0.5rem;'>{t('find_center_title')}</h2>", unsafe_allow_html=True)
    if scheme:
        st.markdown(f"<p style='color:#64748b; font-size:1.15rem; margin-bottom:1.5rem;'>{t('find_center_desc').replace('{scheme_name}', scheme.get('scheme_name', ''))}</p>", unsafe_allow_html=True)

    if st.session_state.geo_state == "requesting" and not st.session_state.manual_location_mode:
        geo_html = f\"\"\"
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: sans-serif; background: transparent; margin: 0; padding: 0; }}
            </style>
        </head>
        <body>
            <script>
                function setInput(placeholder, value) {{
                    try {{
                        const inputs = window.parent.document.querySelectorAll('input');
                        for (let input of inputs) {{
                            if (input.placeholder === placeholder) {{
                                const nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set;
                                nativeSetter.call(input, value);
                                input.dispatchEvent(new Event('input', {{ bubbles: true }}));
                                input.dispatchEvent(new Event('change', {{ bubbles: true }}));
                                return true;
                            }}
                        }}
                    }} catch(e) {{
                    }}
                    return false;
                }}

                window.onload = function() {{
                    const nav = window.parent.navigator.geolocation ? window.parent.navigator : navigator;
                    
                    if (nav && nav.geolocation) {{
                        const hardTimeout = setTimeout(() => {{
                            setInput("geo_err", "Timeout");
                        }}, 15000);

                        nav.geolocation.getCurrentPosition(
                            (position) => {{
                                clearTimeout(hardTimeout);
                                const okLat = setInput("geo_lat", position.coords.latitude.toString());
                                const okLng = setInput("geo_lng", position.coords.longitude.toString());
                                if (!okLat || !okLng) {{
                                    setInput("geo_err", "Inputs not found");
                                }}
                            }},
                            (error) => {{
                                clearTimeout(hardTimeout);
                                let reason = "Unknown error";
                                if (error.code === 1) reason = "Permission denied";
                                if (error.code === 2) reason = "Location unavailable";
                                if (error.code === 3) reason = "Timeout";
                                setInput("geo_err", reason);
                            }},
                            {{ enableHighAccuracy: true, timeout: 10000, maximumAge: 0 }}
                        );
                    }} else {{
                        setInput("geo_err", "Unsupported");
                    }}
                }};
            </script>
        </body>
        </html>
        \"\"\"
        components.html(geo_html, height=0)
        
    st.markdown(\"\"\"
    <style>
        div[data-testid="stHorizontalBlock"] > div:has(input[placeholder="geo_lat"]),
        div[data-testid="stHorizontalBlock"] > div:has(input[placeholder="geo_lng"]),
        div[data-testid="stHorizontalBlock"] > div:has(input[placeholder="geo_err"]) {
            display: none !important;
        }
    </style>
    \"\"\", unsafe_allow_html=True)

    col_h1, col_h2, col_h3 = st.columns(3)
    with col_h1:
        lat_val = st.text_input("Lat", value="", placeholder="geo_lat", key="geo_lat_widget", label_visibility="collapsed")
    with col_h2:
        lng_val = st.text_input("Lng", value="", placeholder="geo_lng", key="geo_lng_widget", label_visibility="collapsed")
    with col_h3:
        err_val = st.text_input("Err", value="", placeholder="geo_err", key="geo_err_widget", label_visibility="collapsed")

    if err_val and st.session_state.geo_state == "requesting":
        st.session_state.geo_state = err_val
        st.rerun()

    if lat_val and lng_val and st.session_state.geo_state == "requesting":
        try:
            st.session_state.user_lat = float(lat_val)
            st.session_state.user_lng = float(lng_val)
            st.session_state.geo_state = "granted"
            st.session_state.location_detected = True
            st.session_state.location_source = "gps"
            st.rerun()
        except ValueError:
            pass

    if st.session_state.manual_location_mode:
        st.write("")
        st.markdown(f"**{t('manual_select')}**")
        
        col_state, col_city = st.columns(2)
        with col_state:
            selected_state = st.selectbox(t("select_state"), list(STATE_CITIES.keys()), index=list(STATE_CITIES.keys()).index(profile_state) if profile_state in STATE_CITIES else 0, key="man_state")
        with col_city:
            cities = STATE_CITIES[selected_state]
            city_keys = list(cities.keys())
            default_city_idx = 0
            if "prev_selected_city" in st.session_state and st.session_state.prev_selected_city in city_keys:
                default_city_idx = city_keys.index(st.session_state.prev_selected_city)
            selected_city = st.selectbox(t("select_city"), city_keys, index=default_city_idx, key="man_city")
            
        if "prev_selected_city" not in st.session_state or st.session_state.prev_selected_city != selected_city or st.session_state.get("prev_selected_state") != selected_state:
            st.session_state.prev_selected_city = selected_city
            st.session_state.prev_selected_state = selected_state
            coords = cities[selected_city]
            st.session_state.user_lat = coords[0]
            st.session_state.user_lng = coords[1]
            st.session_state.geo_state = "granted"
            st.session_state.location_detected = True
            st.session_state.location_source = f"{selected_city}, {selected_state}"
            st.rerun()
    elif st.session_state.geo_state != "granted":
        st.write("")
        if st.session_state.geo_state != "requesting":
            st.markdown(f"<p style='color:#ef4444; font-weight:600;'>{st.session_state.geo_state if st.session_state.geo_state != 'manual' else 'Location undetected.'}</p>", unsafe_allow_html=True)
            col_retry, col_manual = st.columns([1, 1])
            if not st.session_state.location_retry_failed:
                with col_retry:
                    if st.button("Retry Location", use_container_width=True):
                        st.session_state.location_retry_failed = True
                        st.session_state.geo_state = "requesting"
                        st.rerun()
            else:
                with col_manual:
                    if st.button("Choose Location Manually", use_container_width=True):
                        st.session_state.manual_location_mode = True
                        st.session_state.geo_state = "manual"
                        st.rerun()
        else:
            if st.button("Choose Location Manually"):
                st.session_state.manual_location_mode = True
                st.session_state.geo_state = "manual"
                st.rerun()

    if st.session_state.geo_state == "requesting" and not st.session_state.manual_location_mode:
        col_back, _ = st.columns([1.5, 2.5])
        with col_back:
            if st.button(t("btn_back_details"), type="secondary", use_container_width=True):
                st.session_state.step = 5
                st.rerun()
        return

    user_lat = st.session_state.get("user_lat")
    user_lng = st.session_state.get("user_lng")
    loc_source = st.session_state.get("location_source", "GPS")
    
    if user_lat is None or user_lng is None:
        return

    # Nominatim Reverse Geocoding
    if "address_dict" not in st.session_state or st.session_state.get("last_geo_lat") != user_lat:
        try:
            headers = {'User-Agent': 'AdhikaarSchemeEngine/1.0'}
            resp = requests.get(f"https://nominatim.openstreetmap.org/reverse?format=json&lat={user_lat}&lon={user_lng}", headers=headers, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                st.session_state.address_dict = data.get("address", {})
            else:
                st.session_state.address_dict = {}
        except Exception:
            st.session_state.address_dict = {}
        st.session_state.last_geo_lat = user_lat

    addr = st.session_state.get("address_dict", {})
    area = addr.get("suburb", addr.get("neighbourhood", addr.get("road", "")))
    city = addr.get("city", addr.get("town", addr.get("village", "")))
    district = addr.get("state_district", addr.get("county", ""))
    state = addr.get("state", "")
    
    parts = []
    if area: parts.append(area)
    if city: parts.append(city)
    
    parts2 = []
    if district: parts2.append(district)
    if state: parts2.append(state)
    
    if parts and parts2:
        loc_display = f"{', '.join(parts)}<br>{', '.join(parts2)}"
    elif parts or parts2:
        loc_display = f"{', '.join(parts) if parts else ', '.join(parts2)}"
    else:
        loc_display = "Location detected<br>Unable to determine city/state"

    if loc_source != "gps" and loc_source != "GPS":
        loc_display = f"{loc_source}"

    for center in APPLICATION_CENTERS:
        center["distance"] = haversine_distance(user_lat, user_lng, center["lat"], center["lng"])
        
    sorted_centers = sorted(APPLICATION_CENTERS, key=lambda x: x["distance"])
    
    MAX_DISTANCE_KM = 500.0
    nearby_centers = [c for c in sorted_centers if c["distance"] <= MAX_DISTANCE_KM]
    
    if not nearby_centers:
        st.write("")
        st.warning("No nearby application center found.")
        col_back, _ = st.columns([1, 1])
        with col_back:
            if st.button(t("btn_back_details"), type="secondary", use_container_width=True, key="back_no_centers"):
                st.session_state.step = 5
                st.rerun()
        return
        
    nearest = nearby_centers[0]
    rec_type = get_recommended_center_type(scheme, nearest.get("state", "Other"))
    dist_val = nearest['distance']
    if dist_val < 0.1:
        dist_val = 0.1 # Minimum display distance if exactly the same coordinates
    
    st.markdown(f\"\"\"
    <div style="position: fixed; top: 60px; right: 20px; background: white; padding: 16px; border-radius: 16px; box-shadow: 0 10px 25px rgba(0,0,0,0.1); border: 1px solid #e2e8f0; z-index: 999999; min-width: 240px; font-family: sans-serif;">
        <div style="margin-bottom: 12px;">
            <div style="color: #0f172a; font-weight: 700; font-size: 0.95rem; margin-bottom: 4px; display: flex; align-items: center; gap: 6px;">📍 Current Location</div>
            <div style="color: #475569; font-size: 0.85rem; margin-bottom: 4px;">{loc_display}</div>
            <div style="color: #059669; font-size: 0.75rem; font-weight: 600;">✓ Location Detected</div>
        </div>
        <hr style="border: 0; height: 1px; background: #e2e8f0; margin: 8px 0;">
        <div style="margin-bottom: 12px;">
            <div style="color: #0f172a; font-weight: 700; font-size: 0.95rem; margin-bottom: 4px; display: flex; align-items: center; gap: 6px;">🏢 Nearest Center</div>
            <div style="color: #475569; font-size: 0.85rem;">{nearest['type']}</div>
        </div>
        <div style="background: #f8fafc; padding: 8px; border-radius: 8px; border: 1px solid #f1f5f9;">
            <div style="color: #0f172a; font-weight: 700; font-size: 0.9rem; display: flex; align-items: center; gap: 6px;">📏 Distance</div>
            <div style="color: #0d9488; font-weight: 700; font-size: 1.1rem;">{dist_val:.1f} km</div>
        </div>
    </div>
    \"\"\", unsafe_allow_html=True)
    
    # Leaflet Map
    map_html = f\"\"\"
    <!DOCTYPE html>
    <html>
    <head>
        <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" integrity="sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY=" crossorigin=""/>
        <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js" integrity="sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo=" crossorigin=""></script>
        <style>
            #map {{ height: 400px; width: 100%; border-radius: 12px; margin-bottom: 1rem; border: 1.5px solid #0d9488; }}
        </style>
    </head>
    <body>
        <div id="map"></div>
        <script>
            var userLat = {user_lat};
            var userLng = {user_lng};
            var centerLat = {nearest['lat']};
            var centerLng = {nearest['lng']};

            var map = L.map('map');
            L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
                attribution: '&copy; OpenStreetMap contributors'
            }}).addTo(map);

            var userIcon = L.divIcon({{className: 'custom-icon', html: '<div style="font-size:24px;">🔵</div>', iconSize: [24,24], iconAnchor: [12,12]}});
            var centerIcon = L.divIcon({{className: 'custom-icon', html: '<div style="font-size:24px;">🟢</div>', iconSize: [24,24], iconAnchor: [12,12]}});

            L.marker([userLat, userLng], {{icon: userIcon}}).addTo(map).bindPopup("<b>User Location</b>");
            L.marker([centerLat, centerLng], {{icon: centerIcon}}).addTo(map).bindPopup("<b>Nearest Center:</b><br>{nearest['name']}");

            var latlngs = [[userLat, userLng], [centerLat, centerLng]];
            var polyline = L.polyline(latlngs, {{color: '#0d9488', weight: 4, dashArray: '5, 5'}}).addTo(map);

            map.fitBounds(polyline.getBounds(), {{padding: [50, 50]}});
        </script>
    </body>
    </html>
    \"\"\"
    components.html(map_html, height=420)

    st.write("")
    st.markdown(f"<div class='premium-card' style='background: #f0fdf4; border: 1px solid #99f6e4; padding: 1rem; margin-bottom: 1rem;'><strong>💡 {t('recommended_type')}</strong> <span style='color:#0d9488; font-weight:700;'>{rec_type}</span></div>", unsafe_allow_html=True)
    
    c = nearest
    bg_style = "background: linear-gradient(135deg, #f0fdf4 0%, #ffffff 100%); border: 1.5px solid #0d9488; box-shadow: 0 10px 15px -3px rgba(13, 148, 136, 0.1);"
    
    st.markdown(f\"\"\"
    <div class="premium-card" style="{bg_style} padding: 1.25rem; margin-bottom: 1rem; border-radius: 12px;">
        <div style="display: flex; justify-content: space-between; align-items: start; flex-wrap: wrap; gap: 8px;">
            <div>
                <h4 style="margin: 0 0 0.25rem 0; font-size: 1.1rem; color: #0f172a; font-weight: 700;">🏢 Nearest Application Center</h4>
                <span style="color:#0d9488; font-weight:600; font-size:0.9rem; display: block; margin-bottom: 0.5rem;">{c['type']}</span>
            </div>
            <div style="text-align: right;">
                <span style="font-weight: 700; color: #1e293b; font-size: 0.95rem; background: #f1f5f9; padding: 6px 12px; border-radius: 8px; display: inline-block;">📏 Distance: {dist_val:.1f} km</span>
            </div>
        </div>
        <div style="color: #475569; font-size: 0.9rem; margin: 0.5rem 0 0.5rem 0; line-height: 1.4;">
            <b>{c['name']}</b><br>
            <b>Address:</b><br>{c['address']}
        </div>
        <div style="color: #64748b; font-size: 0.85rem; margin: 0.25rem 0 1rem 0;">
            📞 <b>Phone:</b> {c.get('phone', 'N/A')}
        </div>
    </div>
    \"\"\", unsafe_allow_html=True)
    
    col_back, col_dir = st.columns([1, 1])
    with col_back:
        if st.button(t("btn_back_details"), type="secondary", use_container_width=True, key="back_nearest"):
            st.session_state.step = 5
            st.rerun()
    with col_dir:
        st.link_button("🗺️ Navigate", f"https://www.google.com/maps/dir/?api=1&destination={c['lat']},{c['lng']}", use_container_width=True)
    st.write("")
"""

new_content = content[:start_idx] + new_func + '\n' + content[end_idx:]

with open('app.py', 'w', encoding='utf-8') as f:
    f.write(new_content)
    
print("Successfully patched app.py")
