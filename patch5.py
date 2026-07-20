import re

with open("app.py", "r", encoding="utf-8") as f:
    content = f.read()

# Replace all occurrences of Hinglish with Hindi
content = content.replace("Hinglish", "Hindi")
content = content.replace("btn_hinglish", "btn_hindi")

# Ensure English is the default highlighted language (it should be, but let's make sure)
# If init_session isn't setting it, we ensure it's there.
if "st.session_state.language = \"English\"" not in content:
    content = content.replace(
        "if 'language' not in st.session_state:",
        "if 'language' not in st.session_state:\n        st.session_state.language = \"English\""
    )

with open("app.py", "w", encoding="utf-8") as f:
    f.write(content)

print("Replacement complete.")
