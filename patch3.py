import re

with open("app.py", "r", encoding="utf-8") as f:
    content = f.read()

new_logic = """def render_nearest_centers():
    scheme = st.session_state.get("selected_scheme")
    profile_state = st.session_state.profile.get("State")
    if not profile_state or profile_state not in STATE_CITIES:
        profile_state = "Other"

    if "manual_location_mode" not in st.session_state:
        st.session_state.manual_location_mode = False
    if "geo_state" not in st.session_state:
        st.session_state.geo_state = "requesting"
        
    st.markdown(f"<h2 style='color:#0f172a; font-weight:800; margin-bottom:0.5rem;'>{t('find_center_title')}</h2>", unsafe_allow_html=True)
    if scheme:
        st.markdown(f"<p style='color:#64748b; font-size:1.15rem; margin-bottom:1.5rem;'>{t('find_center_desc').replace('{scheme_name}', scheme.get('scheme_name', ''))}</p>", unsafe_allow_html=True)

    if st.session_state.geo_state == "requesting" and not st.session_state.manual_location_mode:
        geo_html = f\"\"\"
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: sans-serif; background: transparent; margin: 0; padding: 10px; }}
                #debug-box {{ border: 1px solid #ccc; padding: 10px; border-radius: 8px; font-size: 13px; background: #f8fafc; }}
                .row {{ display: flex; justify-content: space-between; margin-bottom: 4px; border-bottom: 1px solid #eee; padding-bottom: 2px; }}
                .val {{ font-weight: bold; color: #0d9488; }}
                .err {{ color: #ef4444; }}
            </style>
        </head>
        <body>
            <div id="debug-box">
                <div class="row"><span>Browser geolocation supported:</span><span id="d-supported" class="val">Checking...</span></div>
                <div class="row"><span>Browser permission requested:</span><span id="d-req" class="val">No</span></div>
                <div class="row"><span>Permission result:</span><span id="d-res" class="val">Waiting...</span></div>
                <div class="row"><span>Latitude:</span><span id="d-lat" class="val">-</span></div>
                <div class="row"><span>Longitude:</span><span id="d-lng" class="val">-</span></div>
                <div class="row"><span>Success callback executed:</span><span id="d-succ" class="val">No</span></div>
                <div class="row"><span>Error callback executed:</span><span id="d-err" class="val">No</span></div>
                <div class="row"><span>Coordinates to Streamlit:</span><span id="d-sent" class="val">No</span></div>
            </div>
            
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
                        document.getElementById('d-sent').innerText = "Failed: " + e.message;
                        document.getElementById('d-sent').className = "val err";
                    }}
                    return false;
                }}

                window.onload = function() {{
                    // Fallback to parent navigator to bypass iframe sandbox restrictions on geolocation
                    const nav = window.parent.navigator.geolocation ? window.parent.navigator : navigator;
                    
                    if (nav && nav.geolocation) {{
                        document.getElementById('d-supported').innerText = "Yes (" + (nav === window.parent.navigator ? "Parent" : "Iframe") + ")";
                        document.getElementById('d-req').innerText = "Yes";
                        
                        const hardTimeout = setTimeout(() => {{
                            if(document.getElementById('d-succ').innerText !== "Yes" && document.getElementById('d-err').innerText !== "Yes") {{
                                document.getElementById('d-res').innerText = "Timeout (No response)";
                                document.getElementById('d-res').className = "val err";
                                setInput("geo_err", "Timeout");
                            }}
                        }}, 15000);

                        nav.geolocation.getCurrentPosition(
                            (position) => {{
                                document.getElementById('d-res').innerText = "Granted";
                                document.getElementById('d-succ').innerText = "Yes";
                                document.getElementById('d-lat').innerText = position.coords.latitude;
                                document.getElementById('d-lng').innerText = position.coords.longitude;
                                
                                const okLat = setInput("geo_lat", position.coords.latitude.toString());
                                const okLng = setInput("geo_lng", position.coords.longitude.toString());
                                
                                if(okLat && okLng) {{
                                    document.getElementById('d-sent').innerText = "Yes";
                                }} else {{
                                    document.getElementById('d-sent').innerText = "No (inputs not found)";
                                    document.getElementById('d-sent').className = "val err";
                                    setInput("geo_err", "Inputs not found");
                                }}
                            }},
                            (error) => {{
                                document.getElementById('d-err').innerText = "Yes";
                                let reason = "Unknown error";
                                if (error.code === 1) reason = "Permission denied";
                                if (error.code === 2) reason = "Location unavailable";
                                if (error.code === 3) reason = "Timeout";
                                document.getElementById('d-res').innerText = "Denied/Error: " + reason;
                                document.getElementById('d-res').className = "val err";
                                setInput("geo_err", reason);
                            }},
                            {{ enableHighAccuracy: true, timeout: 10000, maximumAge: 0 }}
                        );
                    }} else {{
                        document.getElementById('d-supported').innerText = "No";
                        document.getElementById('d-supported').className = "val err";
                        document.getElementById('d-res').innerText = "Unsupported";
                        setInput("geo_err", "Unsupported");
                    }}
                }};
            </script>
        </body>
        </html>
        \"\"\"
        components.html(geo_html, height=220)
        
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
        st.session_state.manual_location_mode = True 
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
            with col_retry:
                if st.button("Retry Location", use_container_width=True):
                    st.session_state.geo_state = "requesting"
                    st.rerun()
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

    loc_display = f"{loc_source}" if loc_source != 'gps' else f"Latitude: {user_lat:.4f}<br>Longitude: {user_lng:.4f}"
    st.markdown(f\"\"\"
    <div style="position: fixed; top: 60px; right: 20px; background: white; padding: 12px 16px; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.1); border: 1px solid #e2e8f0; z-index: 999999; min-width: 200px;">
        <div style="color: #0f172a; font-weight: 700; font-size: 0.9rem; margin-bottom: 4px;">📍 Current Location</div>
        <div style="color: #64748b; font-size: 0.8rem; margin-bottom: 6px;">{loc_display}</div>
        <div style="color: #059669; font-size: 0.75rem; font-weight: 600;">✓ Location Detected</div>
    </div>
    \"\"\", unsafe_allow_html=True)
    
    for center in APPLICATION_CENTERS:
        center["distance"] = haversine_distance(user_lat, user_lng, center["lat"], center["lng"])
        
    sorted_centers = sorted(APPLICATION_CENTERS, key=lambda x: x["distance"])
    if not sorted_centers:
        return
        
    nearest = sorted_centers[0]
    rec_type = get_recommended_center_type(scheme, st.session_state.get("prev_selected_state", "Other"))
    
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
                <span style="font-weight: 700; color: #1e293b; font-size: 0.95rem; background: #f1f5f9; padding: 6px 12px; border-radius: 8px; display: inline-block;">Distance: {c['distance']:.1f} km</span>
            </div>
        </div>
        <div style="color: #475569; font-size: 0.9rem; margin: 0.5rem 0 0.5rem 0; line-height: 1.4;">
            <b>Address:</b><br>{c['address']}
        </div>
        <div style="color: #64748b; font-size: 0.85rem; margin: 0.25rem 0 1rem 0;">
            📞 <b>Phone:</b> {c.get('phone', 'N/A')}
        </div>
    </div>
    \"\"\", unsafe_allow_html=True)
    
    col_back, col_dir = st.columns([1, 1])
    with col_back:
        if st.button(t("btn_back_details"), type="secondary", use_container_width=True):
            st.session_state.step = 5
            st.rerun()
    with col_dir:
        st.link_button(t("directions"), f"https://www.google.com/maps/dir/?api=1&destination={c['lat']},{c['lng']}", use_container_width=True)
    st.write("")
"""

pattern = r"def render_nearest_centers\(\):.*?def main\(\):"
replacement = new_logic + "\ndef main():"

new_content, count = re.subn(pattern, replacement, content, flags=re.DOTALL)

with open("app.py", "w", encoding="utf-8") as f:
    f.write(new_content)

print(f"Replaced render_nearest_centers, substitutions made: {count}")
