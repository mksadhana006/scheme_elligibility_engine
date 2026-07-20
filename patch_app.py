import re

with open("app.py", "r", encoding="utf-8") as f:
    content = f.read()

# 1. Update setInput to catch exceptions
set_input_old = """    function setInput(placeholder, value) {
      const pdoc   = window.parent.document;
      const inputs = pdoc.querySelectorAll('input');
      for (let inp of inputs) {
        if (inp.placeholder === placeholder) {
          const setter = Object.getOwnPropertyDescriptor(
            window.HTMLInputElement.prototype, "value"
          ).set;
          setter.call(inp, value);
          inp.dispatchEvent(new Event('input', { bubbles: true }));
          inp.dispatchEvent(new Event('change', { bubbles: true }));
          return true;
        }
      }
      return false;
    }"""
set_input_new = """    function setInput(placeholder, value) {
      try {
        const pdoc   = window.parent.document;
        const inputs = pdoc.querySelectorAll('input');
        for (let inp of inputs) {
          if (inp.placeholder === placeholder) {
            const setter = Object.getOwnPropertyDescriptor(
              window.HTMLInputElement.prototype, "value"
            ).set;
            setter.call(inp, value);
            inp.dispatchEvent(new Event('input', { bubbles: true }));
            inp.dispatchEvent(new Event('change', { bubbles: true }));
            return true;
          }
        }
        return false;
      } catch(e) { return false; }
    }"""
content = content.replace(set_input_old, set_input_new)


# 2. Add hard timeout to doGeo and change timeout to 8000
dogeo_old = """      navigator.geolocation.getCurrentPosition(
        function(pos) {
          clearTimeout(promptTimeout);
          isRequesting = false;"""
dogeo_new = """      const hardTimeout = setTimeout(() => {
        if(isRequesting) {
           isRequesting = false;
           msgEl.innerText = "Request Timed Out";
           subEl.innerText = "Browser did not respond. Use manual selection below.";
           setInput(GEO_ERR_PH, "timeout");
        }
      }, 10000);

      try {
      navigator.geolocation.getCurrentPosition(
        function(pos) {
          clearTimeout(promptTimeout);
          clearTimeout(hardTimeout);
          if(!isRequesting) return;
          isRequesting = false;"""
content = content.replace(dogeo_old, dogeo_new)

err_code_old = """        function(err) {
          clearTimeout(promptTimeout);
          isRequesting = false;"""
err_code_new = """        function(err) {
          clearTimeout(promptTimeout);
          clearTimeout(hardTimeout);
          if(!isRequesting) return;
          isRequesting = false;"""
content = content.replace(err_code_old, err_code_new)

timeout_old = """{ enableHighAccuracy: true, timeout: 15000, maximumAge: 0 }
      );
    }
  </script>"""
timeout_new = """{ enableHighAccuracy: true, timeout: 8000, maximumAge: 0 }
      );
      } catch (e) {
          clearTimeout(hardTimeout);
          isRequesting = false;
          setInput(GEO_ERR_PH, "error");
      }
    }
  </script>"""
content = content.replace(timeout_old, timeout_new)

# 3. Change the Python rendering logic
python_logic_old = """    if current_state == "requesting":
        # Waiting for user to interact with the iframe button
        return  # Nothing else to show yet

    elif current_state in ("denied", "unavailable", "timeout", "error", "unsupported"):
        # ── Permission denied / error state ─────────────────────────────────"""

python_logic_new = """    if current_state in ("denied", "unavailable", "timeout", "error", "unsupported"):
        # ── Permission denied / error state ─────────────────────────────────"""
content = content.replace(python_logic_old, python_logic_new)

python_fallback_old = """        # ── Graceful fallback: manual city selection ─────────────────────────
        st.markdown(
            "<p style='color:#374151; font-weight:600; margin-top:1.2rem;'>"
            "📍 Or choose your city manually to find nearest centers:</p>",
            unsafe_allow_html=True,
        )
        col_state, col_city = st.columns(2)
        with col_state:
            selected_state = st.selectbox(
                "State",
                list(STATE_CITIES.keys()),
                index=list(STATE_CITIES.keys()).index(profile_state)
                if profile_state in STATE_CITIES else 0,
                key="fallback_state_select",
            )
        with col_city:
            cities_fb = STATE_CITIES[selected_state]
            city_keys_fb = list(cities_fb.keys())
            selected_city = st.selectbox("City", city_keys_fb, key="fallback_city_select")

        coords_fb = cities_fb[selected_city]
        user_lat, user_lng = coords_fb[0], coords_fb[1]
        location_label = f"{selected_city}, {selected_state}"
        location_source = "manual"

    elif current_state == "granted":"""

python_fallback_new = """
    if current_state != "granted":
        # ── Graceful fallback: manual city selection ─────────────────────────
        st.markdown(
            "<p style='color:#374151; font-weight:600; margin-top:1.2rem;'>"
            "📍 Or choose your city manually to find nearest centers:</p>",
            unsafe_allow_html=True,
        )
        col_state, col_city = st.columns(2)
        with col_state:
            selected_state = st.selectbox(
                "State",
                list(STATE_CITIES.keys()),
                index=list(STATE_CITIES.keys()).index(profile_state)
                if profile_state in STATE_CITIES else 0,
                key="fallback_state_select",
            )
        with col_city:
            cities_fb = STATE_CITIES[selected_state]
            city_keys_fb = list(cities_fb.keys())
            selected_city = st.selectbox("City", city_keys_fb, key="fallback_city_select")

        coords_fb = cities_fb[selected_city]
        user_lat, user_lng = coords_fb[0], coords_fb[1]
        location_label = f"{selected_city}, {selected_state}"
        location_source = "manual"

    elif current_state == "granted":"""
content = content.replace(python_fallback_old, python_fallback_new)

with open("app.py", "w", encoding="utf-8") as f:
    f.write(content)
print("Patched app.py")
