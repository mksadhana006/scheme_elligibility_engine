import re

with open("app.py", "r", encoding="utf-8") as f:
    content = f.read()

# Replace the distance logic and UI at the bottom of render_nearest_centers
pattern = r"    for center in APPLICATION_CENTERS:.*?st\.write\(\"\"\)\n"
replacement = """    for center in APPLICATION_CENTERS:
        center["distance"] = haversine_distance(user_lat, user_lng, center["lat"], center["lng"])
        
    sorted_centers = sorted(APPLICATION_CENTERS, key=lambda x: x["distance"])
    
    # Restrict to centers within 100 km to prevent arbitrary long-distance fallback to New Delhi
    MAX_DISTANCE_KM = 100.0
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
        if st.button(t("btn_back_details"), type="secondary", use_container_width=True, key="back_nearest"):
            st.session_state.step = 5
            st.rerun()
    with col_dir:
        st.link_button(t("directions"), f"https://www.google.com/maps/dir/?api=1&destination={c['lat']},{c['lng']}", use_container_width=True)
    st.write("")
"""

new_content, count = re.subn(pattern, replacement, content, flags=re.DOTALL)

with open("app.py", "w", encoding="utf-8") as f:
    f.write(new_content)

print(f"Replaced {count} instances.")
