import json
import math
import os
import streamlit as st
import streamlit.components.v1 as components
import time
import re
import requests
import osm_api
import logging
logger = logging.getLogger(__name__)
from logic import get_top_matches, normalize_profile
from preprocess import build_profile
from centers_db import geocode_address_free, fetch_places_new

def transliterate_to_tamil(text):
    try:
        words = text.split()
        out = []
        for w in words:
            if re.search('[a-zA-Z]', w):
                url = f"https://inputtools.google.com/request?text={w}&itc=ta-t-i0-und&num=1&cp=0&cs=1&ie=utf-8&oe=utf-8&app=demopage"
                r = requests.get(url, timeout=3).json()
                if r[0] == "SUCCESS" and r[1]:
                    out.append(r[1][0][1][0])
                else:
                    out.append(w)
            else:
                out.append(w)
        return " ".join(out)
    except Exception:
        return text

@st.cache_data
def load_schemes_data():
    path = "schemes.json"
    try:
        if os.path.exists(path) and os.path.getsize(path) > 0:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        # Check nested backup schemes.json
        backup_path = os.path.join("scheme_elligibility_engine", "schemes.json")
        if os.path.exists(backup_path) and os.path.getsize(backup_path) > 0:
            with open(backup_path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"Error loading schemes database: {e}")
    return []
        
# --- Translation Dictionaries ---
TEXTS = {
    "en": {
        "app_title": "Adhikaar",
        "app_subtitle": "Find government schemes you may be eligible for",
        "app_trust": "Simple. Multilingual. Explainable.",
        "btn_english": "English",
        "btn_tamil": "தமிழ்",
        "btn_hindi": "Hindi",
        "btn_check_eligibility": "Check My Eligibility",
        "btn_browse_schemes": "Browse Schemes",
        "voice_enabled": "🎙️ Multilingual Voice Input Enabled",
        "how_it_works": "How it works",
        "step1_title": "Tell us about yoursel",
        "step1_desc": "Type naturally or use your voice in your preferred language about your current situation.",
        "step2_title": "We check matching schemes",
        "step2_desc": "Our smart engine transparently matches your details against government scheme rules.",
        "step3_title": "View eligible schemes & apply",
        "step3_desc": "Get a clear list of what you qualify for and exactly which documents you need to apply.",
        "btn_back": "← Back",
        "input_title": "Tell us about yoursel",
        "input_desc": "Type naturally in English, தமிழ், or Hindi. Or use voice input below.",
        "quick_tags": "Quick Select Tags:",
        "btn_continue": "Continue to Match",
        "warn_empty_input": "Please enter some details about yourself to continue.",
        "review_title": "Review Your Profile",
        "stepper_1": "✅ Understand input",
        "stepper_2": "✅ Extract details",
        "stepper_3": "⏳ Check schemes",
        "stepper_4": "Prepare results",
        "review_info": "We extracted the following details from your input. Please verify and correct them if needed. Accurate details ensure better scheme matching.",
        "lbl_gender": "Gender",
        "lbl_income": "Annual Income (₹)",
        "lbl_occupation": "Occupation",
        "lbl_marital": "Marital Status",
        "lbl_state": "State",
        "lbl_age": "Age",
        "meta_title": "System Detected Metadata:",
        "meta_lang": "Detected Language:",
        "meta_income": "Normalized Income:",
        "not_provided": "Not provided",
        "btn_edit_input": "← Edit Input",
        "analyzing": "Analyzing your profile and matching eligible government schemes...",
        "schemes_found": "schemes found",
        "based_on_profile": "Based on your verified profile",
        "btn_start_over": "Start Over",
        "filter_category": "Filter by Category:",
        "cat_women": "Women",
        "cat_pension": "Pension",
        "cat_housing": "Housing",
        "cat_employment": "Employment",
        "cat_state": "State-specific",
        "warn_no_schemes": "No eligible schemes found for your profile.",
        "match": "Match:",
        "category": "Category:",
        "why_matched": "Why matched:",
        "why_not_matched": "Why not matched:",
        "req_docs": "Required documents:",
        "btn_view_details": "View Details",
        "btn_save_later": "Save for Later",
        "btn_apply": "Apply on Official Site",
        "btn_back_results": "← Back to Results",
        "overview": "Overview",
        "who_can_apply": "Who can apply",
        "matched": "Matched:",
        "not_matched": "Not matched / notes:",
        "how_to_apply": "How to apply",
        "docs_required": "Documents required",
        "btn_find_center": "Find Nearest Application Center",
        "btn_back_details": "← Back to Scheme Details",
        "find_center_title": "Find Nearest Application Center",
        "find_center_desc": "Locate government service centers nearby where you can apply for {scheme_name}",
        "gps_detect": "📍 Detect My Current Location",
        "manual_select": "Or select your location manually:",
        "select_state": "Select State",
        "select_city": "Select City",
        "nearest_center": "Nearest Application Center",
        "distance_km": "{distance} km away",
        "directions": "📍 Get Directions in Google Maps",
        "no_centers_state": "⚠️ No application centers found in your state. Showing closest available centers from other regions.",
        "recommended_type": "Recommended Center Type for this scheme:",
        "loading_location": "Detecting location, please wait...",
        "location_success": "✅ GPS Location detected successfully!",
        "location_error": "❌ Unable to detect GPS location. Please select manually.",
        "no_match_title": "No exact schemes found",
        "no_match_desc": "We couldn't find a scheme that exactly matches all your details right now. But don't worry, there might still be options for you.",
        "suggestions_title": "Suggestions to improve matches",
        "sugg_1": "<strong>Check your details:</strong> Make sure your income and age are entered correctly.",
        "sugg_2": "<strong>Broaden your search:</strong> Browse all schemes in your state manually.",
        "btn_edit_details": "Edit My Details",
        "btn_browse_all": "Browse All Schemes",
        "status_full_match": "Full Match",
        "status_partial_match": "Partial Match",
        "status_low_match": "Low Match",
        "status_no_match": "No Match",
        "reason_no_pos": "No clear positive matches.",
        "reason_no_neg": "No major mismatches.",
        "lbl_chips": ["Woman", "Widow", "Senior Citizen", "Farmer", "Student", "Disability", "Low Income", "Unemployed"],
        "live_search_rate_limited": "Live search is temporarily unavailable. Showing recommendations from the local database.",
        "ai_rate_limited": "AI re-ranking is temporarily unavailable. Showing recommendations from the local database.",
        "browse_schemes_title": "Browse Schemes",
        "search_placeholder": "Search schemes by name...",
        "filter_category_short": "Category:",
        "filter_state": "State/Central:",
        "filter_beneficiary": "Beneficiary:",
        "all_categories": "All Categories",
        "all_states": "All / Central",
        "all_beneficiaries": "All Beneficiaries",
        "beneficiary_student": "Student",
        "beneficiary_farmer": "Farmer",
        "beneficiary_women": "Women",
        "beneficiary_senior": "Senior Citizen",
        "beneficiary_low_income": "Low Income / BPL",
        "eligibility": "Eligibility:",
        "page": "Page",
        "prev_page": "Previous",
        "next_page": "Next",
        "no_schemes_found": "No schemes matching your search criteria.",
        "browse_mode": "Browse Mode",
        "reason_browse_mode": "Use the Eligibility Checker on the home page to find your personal match status."
    },
    "ta": {
        "app_title": "அதிகார் (Adhikaar)",
        "app_subtitle": "நீங்கள் தகுதிபெறக்கூடிய அரசு திட்டங்களை கண்டறியுங்கள்",
        "app_trust": "எளிமையானது. பன்மொழி ஆதரவு. விளக்கமானது.",
        "btn_english": "English",
        "btn_tamil": "தமிழ்",
        "btn_hindi": "Hindi",
        "btn_check_eligibility": "எனது தகுதியை சரிபார்க்கவும்",
        "btn_browse_schemes": "திட்டங்களை உலாவுக",
        "voice_enabled": "🎙️ பன்மொழி குரல் பதிவு வசதி உள்ளது",
        "how_it_works": "இது எப்படி வேலை செய்கிறது",
        "step1_title": "உங்களைப் பற்றி சொல்லுங்கள்",
        "step1_desc": "உங்கள் தற்போதைய சூழ்நிலையைப் பற்றி உங்கள் விருப்பமான மொழியில் தட்டச்சு செய்யவும் அல்லது குரல் பதிவு செய்யவும்.",
        "step2_title": "பொருத்தமான திட்டங்களை சரிபார்க்கிறோம்",
        "step2_desc": "எங்கள் ஸ்மார்ட் எஞ்சின் உங்கள் விவரங்களை அரசு திட்ட விதிகளுடன் வெளிப்படையாகப் பொருத்துகிறது.",
        "step3_title": "தகுதியான திட்டங்களைப் பார்த்து விண்ணப்பிக்கவும்",
        "step3_desc": "நீங்கள் தகுதி பெற்றுள்ள திட்டங்கள் மற்றும் விண்ணப்பிக்கத் தேவையான ஆவணங்களின் தெளிவான பட்டியலைப் பெறுங்கள்.",
        "btn_back": "← பின்செல்",
        "input_title": "உங்களைப் பற்றி சொல்லுங்கள்",
        "input_desc": "ஆங்கிலம், தமிழ் அல்லது ஹிங்க்லிஷில் இயல்பாக தட்டச்சு செய்யவும். அல்லது கீழே உள்ள குரல் பதிவைப் பயன்படுத்தவும்.",
        "quick_tags": "விரைவான தேர்வுகள்:",
        "btn_continue": "பொருத்தத்தை தொடரவும்",
        "warn_empty_input": "தொடர உங்களைப் பற்றிய சில விவரங்களை உள்ளிடவும்.",
        "review_title": "உங்கள் சுயவிவரத்தை சரிபார்க்கவும்",
        "stepper_1": "✅ உள்ளீட்டை புரிந்துகொள்ளல்",
        "stepper_2": "✅ விவரங்களை பிரித்தெடுத்தல்",
        "stepper_3": "⏳ திட்டங்களை சரிபார்த்தல்",
        "stepper_4": "முடிவுகளை தயாரித்தல்",
        "review_info": "உங்கள் உள்ளீட்டிலிருந்து பின்வரும் விவரங்களை எடுத்துள்ளோம். தேவைப்பட்டால் சரிபார்த்து திருத்தவும். சரியான விவரங்கள் சிறந்த திட்ட பொருத்தத்தை உறுதி செய்யும்.",
        "lbl_gender": "பாலினம்",
        "lbl_income": "ஆண்டு வருமானம் (₹)",
        "lbl_occupation": "தொழில்",
        "lbl_marital": "திருமண நிலை",
        "lbl_state": "மாநிலம்",
        "lbl_age": "வயது",
        "meta_title": "கணினி கண்டறிந்த விவரங்கள்:",
        "meta_lang": "கண்டறியப்பட்ட மொழி:",
        "meta_income": "இயல்பாக்கப்பட்ட வருமானம்:",
        "not_provided": "வழங்கப்படவில்லை",
        "btn_edit_input": "← உள்ளீட்டை திருத்து",
        "analyzing": "உங்கள் சுயவிவரத்தை பகுப்பாய்வு செய்து தகுதியான அரசு திட்டங்களை பொருத்துகிறது...",
        "schemes_found": "திட்டங்கள் கிடைத்துள்ளன",
        "based_on_profile": "உங்கள் சரிபார்க்கப்பட்ட சுயவிவரத்தின் அடிப்படையில்",
        "btn_start_over": "மீண்டும் தொடங்கு",
        "filter_category": "வகை மூலம் வடிகட்டவும்:",
        "cat_women": "பெண்கள்",
        "cat_pension": "ஓய்வூதியம்",
        "cat_housing": "வீட்டு வசதி",
        "cat_employment": "வேலைவாய்ப்பு",
        "cat_state": "மாநிலம் சார்ந்தது",
        "warn_no_schemes": "உங்கள் சுயவிவரத்திற்கு தகுதியான திட்டங்கள் எதுவும் கிடைக்கவில்லை.",
        "match": "பொருத்தம்:",
        "category": "வகை:",
        "why_matched": "ஏன் பொருந்துகிறது:",
        "why_not_matched": "ஏன் பொருந்தவில்லை:",
        "req_docs": "தேவையான ஆவணங்கள்:",
        "btn_view_details": "விவரங்களை காண்க",
        "btn_save_later": "பின்னர் சேமிக்கவும்",
        "btn_apply": "அதிகாரப்பூர்வ தளத்தில் விண்ணப்பிக்கவும்",
        "btn_back_results": "← முடிவுகளுக்கு திரும்புக",
        "overview": "மேலோட்டம்",
        "who_can_apply": "யார் விண்ணப்பிக்கலாம்",
        "matched": "பொருந்தியது:",
        "not_matched": "பொருந்தவில்லை / குறிப்புகள்:",
        "how_to_apply": "எப்படி விண்ணப்பிப்பது",
        "docs_required": "தேவையான ஆவணங்கள்",
        "btn_find_center": "அருகிலுள்ள விண்ணப்ப மையத்தை கண்டறியவும்",
        "btn_back_details": "← திட்ட விவரங்களுக்குத் திரும்பு",
        "find_center_title": "அருகிலுள்ள விண்ணப்ப மையத்தைக் கண்டறியவும்",
        "find_center_desc": "{scheme_name} திட்டத்திற்கு விண்ணப்பிக்கக்கூடிய அருகிலுள்ள அரசு சேவை மையங்களைக் கண்டறியவும்",
        "gps_detect": "📍 எனது தற்போதைய இருப்பிடத்தைக் கண்டறி",
        "manual_select": "அல்லது உங்கள் இருப்பிடத்தை கைமுறையாகத் தேர்ந்தெடுக்கவும்:",
        "select_state": "மாநிலத்தைத் தேர்ந்தெடுக்கவும்",
        "select_city": "நகரத்தைத் தேர்ந்தெடுக்கவும்",
        "nearest_center": "மிக அருகில் உள்ள விண்ணப்ப மையம்",
        "distance_km": "{distance} கி.மீ தொலைவில்",
        "directions": "📍 கூகுள் மேப்ஸில் வழிசெலுத்தலைப் பெறுக",
        "no_centers_state": "⚠️ உங்கள் மாநிலத்தில் விண்ணப்ப மையங்கள் எதுவும் இல்லை. பிற பகுதிகளிலிருந்து மிக அருகில் உள்ள மையங்களைக் காட்டுகிறது.",
        "recommended_type": "இந்த திட்டத்திற்கு பரிந்துரைக்கப்படும் மைய வகை:",
        "loading_location": "இருப்பிடத்தைக் கண்டறிகிறது, தயவுசெய்து காத்திருக்கவும்...",
        "location_success": "✅ ஜிபிஎஸ் இருப்பிடம் வெற்றிகரமாகக் கண்டறியப்பட்டது!",
        "location_error": "❌ ஜிபிஎஸ் இருப்பிடத்தைக் கண்டறிய முடியவில்லை. தயவுசெய்து கைமுறையாகத் தேர்ந்தெடுக்கவும்.",
        "no_match_title": "சரியான திட்டங்கள் எதுவும் கிடைக்கவில்லை",
        "no_match_desc": "தற்போது உங்கள் எல்லா விவரங்களுக்கும் பொருந்தக்கூடிய ஒரு திட்டத்தை எங்களால் கண்டுபிடிக்க முடியவில்லை. ஆனால் கவலைப்பட வேண்டாம், உங்களுக்கான மாற்று திட்டங்கள் இருக்கலாம்.",
        "suggestions_title": "பொருத்தங்களை மேம்படுத்துவதற்கான ஆலோசனைகள்",
        "sugg_1": "<strong>உங்கள் விவரங்களை சரிபார்க்கவும்:</strong> உங்கள் வருமானம் மற்றும் வயது சரியாக உள்ளிடப்பட்டுள்ளதா என்பதை உறுதிப்படுத்தவும்.",
        "sugg_2": "<strong>உங்கள் தேடலை விரிவாக்கவும்:</strong> உங்கள் மாநிலத்தில் உள்ள அனைத்து திட்டங்களையும் நாமே தேடி பார்க்கவும்.",
        "btn_edit_details": "எனது விவரங்களை திருத்து",
        "btn_browse_all": "அனைத்து திட்டங்களையும் உலாவுக",
        "status_full_match": "முழுமையான பொருத்தம்",
        "status_partial_match": "பகுதி பொருத்தம்",
        "status_low_match": "குறைந்த பொருத்தம்",
        "status_no_match": "பொருத்தம் இல்லை",
        "reason_no_pos": "தெளிவான நேர்மறையான பொருத்தங்கள் இல்லை.",
        "reason_no_neg": "பெரிய பொருத்தமின்மைகள் இல்லை.",
        "lbl_chips": ["பெண்", "விதவை", "முதியவர்", "விவசாயி", "மாணவர்", "மாற்றுத்திறனாளி", "குறைந்த வருமானம்", "வேலையில்லாதவர்"],
        "live_search_rate_limited": "நேரடி தேடல் தற்காலிகமாக கிடைக்கவில்லை. உள்ளூர் தரவுத்தளத்திலிருந்து பரிந்துரைகள் காட்டப்படுகின்றன.",
        "ai_rate_limited": "AI மறுவரிசைப்படுத்தல் தற்காலிகமாக கிடைக்கவில்லை. உள்ளூர் தரவுத்தளத்திலிருந்து பரிந்துரைகள் காட்டப்படுகின்றன.",
        "browse_schemes_title": "திட்டங்களை உலாவுக",
        "search_placeholder": "திட்டத்தின் பெயரைத் தேடுங்கள்...",
        "filter_category_short": "வகை:",
        "filter_state": "மாநிலம்/மத்திய:",
        "filter_beneficiary": "பயனாளி:",
        "all_categories": "அனைத்து பிரிவுகளும்",
        "all_states": "அனைத்து / மத்திய",
        "all_beneficiaries": "அனைத்து பயனாளிகளும்",
        "beneficiary_student": "மாணவர்",
        "beneficiary_farmer": "விவசாயி",
        "beneficiary_women": "பெண்கள்",
        "beneficiary_senior": "முதியவர்",
        "beneficiary_low_income": "குறைந்த வருமானம் / BPL",
        "eligibility": "தகுதி:",
        "page": "பக்கம்",
        "prev_page": "முந்தைய",
        "next_page": "அடுத்தது",
        "no_schemes_found": "உங்கள் தேடல் அளவுகோலுக்கு பொருந்தும் திட்டங்கள் எதுவும் இல்லை.",
        "browse_mode": "உலாவல் முறை",
        "reason_browse_mode": "உங்கள் தனிப்பட்ட பொருத்தம் நிலையை அறிய முகப்பு பக்கத்தில் உள்ள தகுதி சரிபார்ப்பைப் பயன்படுத்தவும்."
    }
}

DATA_DICT = {
    "Female": "பெண்",
    "Male": "ஆண்",
    "Other": "மற்றவை",
    "Unemployed": "வேலையில்லாதவர்",
    "Farmer": "விவசாயி",
    "Student": "மாணவர்",
    "Employed": "வேலை செய்பவர்",
    "Business": "வியாபாரம்",
    "Widow": "விதவை",
    "Single": "திருமணமாகாதவர்",
    "Married": "திருமணமானவர்",
    "Divorced": "விவாகரத்து பெற்றவர்",
    "Tamil Nadu": "தமிழ்நாடு",
    "Bihar": "பீகார்",
    "Maharashtra": "மகாராஷ்டிரா",
    "Uttar Pradesh": "உத்தர பிரதேசம்"
}

def detect_output_language(text):
    if re.search(r'[\u0B80-\u0BFF]', text):
        return "ta"
    return "en"

def t(key):
    lang = st.session_state.get("output_language", "en")
    return TEXTS.get(lang, TEXTS["en"]).get(key, key)

def t_data(val):
    lang = st.session_state.get("output_language", "en")
    if lang == "ta" and isinstance(val, str):
        return DATA_DICT.get(val, val)
    return val

def translate_explanation(text):
    lang = st.session_state.get("output_language", "en")
    if lang == "en":
        return text
        
    trans = {
        "Gender matches": "பாலினம் பொருந்துகிறது",
        "Female": "பெண்",
        "Male": "ஆண்",
        "Marital status matches": "திருமண நிலை பொருந்துகிறது",
        "Widow": "விதவை",
        "Resident of eligible state": "தகுதியான மாநிலத்தின் வசிப்பவர்",
        "Income": "வருமானம்",
        "is within limit": "வரம்பிற்குள் உள்ளது",
        "Age": "வயது",
        "is within eligible range": "தகுதியான வரம்பிற்குள் உள்ளது",
        "Requires gender": "தேவைப்படும் பாலினம்",
        "Requires marital status": "தேவைப்படும் திருமண நிலை",
        "Requires residence in": "வசிப்பிடம் தேவைப்படும் மாநிலம்",
        "Age must be between": "வயது இவற்றுக்குள் இருக்க வேண்டும்",
        "Income exceeds the maximum limit": "வருமானம் அதிகபட்ச வரம்பை மீறுகிறது",
        "Occupation": "தொழில்",
        "is eligible": "தகுதி உள்ளது",
        "Occupation must be one o": "தொழில் இவற்றில் ஒன்றாக இருக்க வேண்டும்",
        "Missing information: Please provide your": "விடுபட்ட தகவல்: தயவுசெய்து உங்கள் தகவலை வழங்கவும்",
        "Full Match": "முழுமையான பொருத்தம்",
        "Partial Match": "பகுதி பொருத்தம்",
        "Low Match": "குறைந்த பொருத்தம்",
        "No Match": "பொருத்தம் இல்லை",
        "AI Score Breakdown": "AI மதிப்பெண் முறிவு",
        "Rules": "விதிகள்",
        "Relevance": "பொருத்தம்",
        "Priority": "முன்னுரிமை"
    }
    
    for en_text, ta_text in trans.items():
        if en_text in text:
            text = text.replace(en_text, ta_text)
            
    return text

def setup_page():
    st.set_page_config(
        page_title="Adhikaar: Multilingual Scheme Eligibility Engine",
        page_icon="🏛️",
        layout="centered",
        initial_sidebar_state="collapsed"
    )
    st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&display=swap');
        html, body, [class*="css"]  { font-family: 'Plus Jakarta Sans', sans-serif; }
        .stApp {
            background-color: #f8fafc;
            background-image: radial-gradient(at 0% 0%, hsla(183,40%,94%,1) 0, transparent 50%), radial-gradient(at 100% 0%, hsla(212,40%,94%,1) 0, transparent 50%);
            background-attachment: fixed;
        }
        .main-header {
            text-align: center;
            font-size: 3.8rem;
            font-weight: 800;
            background: linear-gradient(135deg, #0d9488, #0369a1);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 0.2rem;
            padding-top: 1rem;
            line-height: 1.2;
            letter-spacing: -0.02em;
        }
        .sub-header {
            text-align: center;
            font-size: 1.2rem;
            color: #64748b;
            font-weight: 500;
            margin-bottom: 1rem;
        }
        .stButton > button {
            border-radius: 14px !important;
            width: 100% !important;
            font-weight: 600 !important;
            border: 1px solid #e2e8f0 !important;
            background-color: #ffffff !important;
            color: #334155 !important;
            transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1) !important;
            box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.05), 0 1px 2px -1px rgba(0, 0, 0, 0.05) !important;
        }
        .stButton > button * { color: #334155 !important; font-weight: 600 !important; }
        .stButton > button:hover {
            border-color: #0d9488 !important;
            background-color: #f0fdfa !important;
            color: #0d9488 !important;
            transform: translateY(-2px) !important;
            box-shadow: 0 10px 15px -3px rgba(13, 148, 136, 0.1), 0 4px 6px -4px rgba(13, 148, 136, 0.05) !important;
        }
        .stButton > button:hover * { color: #0d9488 !important; }
        .stButton > button:focus {
            outline: none !important;
            border-color: #0d9488 !important;
            box-shadow: 0 0 0 4px rgba(13, 148, 136, 0.15) !important;
            color: #0d9488 !important;
        }
        .stButton > button:focus * { color: #0d9488 !important; }
        .stButton > button:active {
            transform: translateY(0) !important;
            background-color: #ccfbf1 !important;
            box-shadow: none !important;
            color: #0f766e !important;
        }
        .stButton > button:active * { color: #0f766e !important; }
        .stButton > button:disabled {
            background-color: #f8fafc !important;
            border-color: #e2e8f0 !important;
            color: #cbd5e1 !important;
            cursor: not-allowed !important;
            transform: none !important;
            box-shadow: none !important;
        }
        .stButton > button:disabled * { color: #cbd5e1 !important; }
        .stButton > button[data-testid="baseButton-primary"] {
            background: linear-gradient(135deg, #0d9488 0%, #0f766e 100%) !important;
            border: none !important;
            color: #ffffff !important;
            box-shadow: 0 4px 6px -1px rgba(13, 148, 136, 0.3), 0 2px 4px -2px rgba(13, 148, 136, 0.2) !important;
        }
        .stButton > button[data-testid="baseButton-primary"] * { color: #ffffff !important; }
        .stButton > button[data-testid="baseButton-primary"]:hover {
            background: linear-gradient(135deg, #0f766e 0%, #115e59 100%) !important;
            box-shadow: 0 10px 15px -3px rgba(13, 148, 136, 0.4), 0 4px 6px -4px rgba(13, 148, 136, 0.3) !important;
            transform: translateY(-2px) !important;
        }
        .premium-card {
            background: rgba(255, 255, 255, 0.8);
            backdrop-filter: blur(12px);
            -webkit-backdrop-filter: blur(12px);
            padding: 1.75rem 2rem;
            border-radius: 20px;
            border: 1px solid rgba(255, 255, 255, 0.5);
            box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.03), 0 8px 10px -6px rgba(0, 0, 0, 0.01);
            margin-bottom: 1.5rem;
            transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1), box-shadow 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        }
        .premium-card:hover { transform: translateY(-4px); box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.05), 0 8px 10px -6px rgba(0, 0, 0, 0.02); }
        .premium-card h4 {
            margin-top: 0;
            color: #0f172a;
            font-weight: 700;
            display: flex;
            align-items: center;
            font-size: 1.25rem;
        }
        .scheme-card {
            background: #ffffff;
            padding: 2rem;
            border-radius: 20px;
            border: 1px solid #e2e8f0;
            border-left: 8px solid #0d9488;
            margin-bottom: 1.5rem;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.03), 0 2px 4px -2px rgba(0, 0, 0, 0.03);
            transition: all 0.3s ease;
            position: relative;
            overflow: hidden;
        }
        .scheme-card::before {
            content: '';
            position: absolute;
            top: 0; left: 0; width: 100%; height: 100%;
            background: linear-gradient(135deg, rgba(13, 148, 136, 0.03) 0%, transparent 100%);
            pointer-events: none;
        }
        .scheme-card:hover {
            transform: translateY(-3px);
            box-shadow: 0 15px 25px -5px rgba(0, 0, 0, 0.06), 0 8px 10px -6px rgba(0, 0, 0, 0.02);
            border-color: #cbd5e1;
        }
        .badge-eligible {
            background: #ecfdf5;
            color: #059669;
            padding: 6px 16px;
            border-radius: 24px;
            font-size: 0.85rem;
            font-weight: 700;
            display: inline-block;
            margin-bottom: 16px;
            border: 1px solid #a7f3d0;
            box-shadow: 0 2px 4px rgba(5, 150, 105, 0.05);
        }
        .badge-partial {
            background: #fefce8;
            color: #ca8a04;
            padding: 6px 16px;
            border-radius: 24px;
            font-size: 0.85rem;
            font-weight: 700;
            display: inline-block;
            margin-bottom: 16px;
            border: 1px solid #fef08a;
            box-shadow: 0 2px 4px rgba(202, 138, 4, 0.05);
        }
        .trust-text {
            background: linear-gradient(90deg, #0d9488, #2563eb);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            font-weight: 700;
            font-size: 1.25rem;
            letter-spacing: 0.5px;
        }
        .stepper {
            display: flex;
            justify-content: space-between;
            color: #94a3b8;
            font-size: 0.95rem;
            margin-bottom: 2.5rem;
            border-bottom: 2px solid #f1f5f9;
            padding-bottom: 1.5rem;
            font-weight: 600;
        }
        .stepper span { display: flex; align-items: center; gap: 8px; }
        .stepper-active {
            color: #0d9488;
            font-weight: 700;
            position: relative;
        }
        .stepper-active::after {
            content: '';
            position: absolute;
            bottom: -1.6rem;
            left: 50%;
            transform: translateX(-50%);
            width: 40px;
            height: 3px;
            background-color: #0d9488;
            border-radius: 3px 3px 0 0;
        }
        @keyframes float {
            0% { transform: translateY(0px); }
            50% { transform: translateY(-12px); }
            100% { transform: translateY(0px); }
        }
        div[data-baseweb="input"] > div,
        div[data-baseweb="select"] > div,
        div[data-baseweb="textarea"] > div {
            border-radius: 14px !important;
            border: 1px solid #cbd5e1 !important;
            background-color: #ffffff !important;
            transition: all 0.2s ease !important;
            box-shadow: inset 0 1px 2px rgba(0, 0, 0, 0.02) !important;
        }
        div[data-baseweb="input"] > div:focus-within,
        div[data-baseweb="select"] > div:focus-within,
        div[data-baseweb="textarea"] > div:focus-within {
            border-color: #0d9488 !important;
            box-shadow: 0 0 0 3px rgba(13, 148, 136, 0.15), inset 0 1px 2px rgba(0, 0, 0, 0.02) !important;
        }
        .stMarkdown label, .stSelectbox label, .stTextInput label, .stTextArea label {
            font-weight: 600 !important;
            color: #334155 !important;
            font-size: 0.95rem !important;
            margin-bottom: 0.25rem !important;
        }
    </style>
    """, unsafe_allow_html=True)

def init_session():
    if 'step' not in st.session_state:
        st.session_state.step = 1
    if 'language' not in st.session_state:
        st.session_state.language = "English"
    if 'output_language' not in st.session_state:
        st.session_state.output_language = "en"
    if 'user_input' not in st.session_state:
        st.session_state.user_input = ""
    if 'profile' not in st.session_state:
        st.session_state.profile = {}
    if 'selected_scheme' not in st.session_state:
        st.session_state.selected_scheme = None
    if 'results' not in st.session_state:
        st.session_state.results = []
    if 'search_rate_limited_until' not in st.session_state:
        st.session_state.search_rate_limited_until = 0.0
    if 'search_rate_limited' not in st.session_state:
        st.session_state.search_rate_limited = False
    if 'ai_rate_limited_until' not in st.session_state:
        st.session_state.ai_rate_limited_until = 0.0
    if 'ai_rate_limited' not in st.session_state:
        st.session_state.ai_rate_limited = False
    if 'detail_search_query' not in st.session_state:
        st.session_state.detail_search_query = "e-Sevai center"
    if 'page_search_query' not in st.session_state:
        st.session_state.page_search_query = "e-Sevai center"
    if 'browse_search_query' not in st.session_state:
        st.session_state.browse_search_query = ""
    if 'find_centers_clicked' not in st.session_state:
        st.session_state.find_centers_clicked = False
    if 'nearby_centers' not in st.session_state:
        st.session_state.nearby_centers = []
    if 'geo_state' not in st.session_state:
        st.session_state.geo_state = "pending_input"
    if 'user_lat' not in st.session_state:
        st.session_state.user_lat = None
    if 'user_lng' not in st.session_state:
        st.session_state.user_lng = None
    if 'location_source' not in st.session_state:
        st.session_state.location_source = ""
    if 'detail_entered_address' not in st.session_state:
        st.session_state.detail_entered_address = ""

def build_backend_profile():
    return {
        "gender": st.session_state.profile.get("Gender"),
        "marital_status": st.session_state.profile.get("Marital Status"),
        "income": st.session_state.profile.get("Income"),
        "state": st.session_state.profile.get("State"),
        "occupation": st.session_state.profile.get("Occupation"),
        "age": st.session_state.profile.get("Age"),
    }

def render_home():
    st.markdown(f"<h1 class='main-header'>{t('app_title')}</h1>", unsafe_allow_html=True)
    st.markdown(f"<p class='sub-header'>{t('app_subtitle')}</p>", unsafe_allow_html=True)
    st.markdown(f"<p style='text-align: center;'><span class='trust-text'>{t('app_trust')}</span></p>", unsafe_allow_html=True)
    st.write("")
    st.write("")
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button(t("btn_english"), use_container_width=True, type="primary" if st.session_state.language == "English" else "secondary"):
            st.session_state.language = "English"
            st.session_state.output_language = "en"
            st.rerun()
    with col2:
        if st.button(t("btn_tamil"), use_container_width=True, type="primary" if st.session_state.language == "தமிழ்" else "secondary"):
            st.session_state.language = "தமிழ்"
            st.session_state.output_language = "ta"
            st.rerun()
    with col3:
        if st.button(t("btn_hindi"), use_container_width=True, type="primary" if st.session_state.language == "Hindi" else "secondary"):
            st.session_state.language = "Hindi"
            st.session_state.output_language = "en"
            st.rerun()
    st.write("")
    st.write("")
    col_main1, col_main2 = st.columns([1, 1])
    with col_main1:
        if st.button(t("btn_check_eligibility"), type="primary", use_container_width=True):
            st.session_state.step = 2
            st.rerun()
    with col_main2:
        if st.button(t("btn_browse_schemes"), use_container_width=True):
            st.session_state.step = 8
            st.rerun()
    st.write("")
    st.markdown(f"<p style='text-align: center; color: #0d9488; font-size: 1rem; font-weight: 600; background: #ccfbf1; padding: 8px 16px; border-radius: 20px; display: inline-block; margin: 0 auto 2rem auto;'>{t('voice_enabled')}</p>", unsafe_allow_html=True)
    st.markdown(f"<h3 style='text-align: center; color: #1e293b; margin-bottom: 2rem; font-weight: 700;'>{t('how_it_works')}</h3>", unsafe_allow_html=True)
    st.markdown(f"""
    <div class="premium-card">
        <h4><span style='font-size: 1.8rem; margin-right: 16px; background: #f1f5f9; border-radius: 12px; padding: 4px 8px;'>1️⃣</span> {t('step1_title')}</h4>
        <p style="color: #475569; margin-top: 12px; font-size: 1rem; line-height: 1.6; margin-left: 60px;">{t('step1_desc')}</p>
    </div>
    <div class="premium-card">
        <h4><span style='font-size: 1.8rem; margin-right: 16px; background: #f1f5f9; border-radius: 12px; padding: 4px 8px;'>2️⃣</span> {t('step2_title')}</h4>
        <p style="color: #475569; margin-top: 12px; font-size: 1rem; line-height: 1.6; margin-left: 60px;">{t('step2_desc')}</p>
    </div>
    <div class="premium-card">
        <h4><span style='font-size: 1.8rem; margin-right: 16px; background: #f1f5f9; border-radius: 12px; padding: 4px 8px;'>3️⃣</span> {t('step3_title')}</h4>
        <p style="color: #475569; margin-top: 12px; font-size: 1rem; line-height: 1.6; margin-left: 60px;">{t('step3_desc')}</p>
    </div>
    """, unsafe_allow_html=True)

def render_input():
    if st.button(t("btn_back")):
        st.session_state.step = 1
        st.rerun()
    st.markdown(f"<h2 style='color: #0f172a; font-weight: 800; margin-bottom: 0.5rem;'>{t('input_title')}</h2>", unsafe_allow_html=True)
    st.markdown(f"<p style='color: #475569; font-size: 1.1rem; margin-bottom: 1.5rem;'>{t('input_desc')}</p>", unsafe_allow_html=True)
    current_lang = "ta-IN" if st.session_state.language == "தமிழ்" else "hi-IN" if st.session_state.language == "Hindi" else "en-US"
    
    voice_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@500;600;700&display=swap" rel="stylesheet">
        <style>
            body {{ margin: 0; padding: 0; font-family: 'Plus Jakarta Sans', sans-serif; background: transparent; }}
            .voice-container {{
                display: flex; align-items: center; gap: 16px;
                background: white; padding: 16px 20px; border-radius: 16px;
                border: 1px solid #e2e8f0; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05);
            }}
            .mic-btn {{
                background: linear-gradient(135deg, #0d9488 0%, #0f766e 100%);
                color: white; border: none; border-radius: 12px;
                padding: 12px 24px; cursor: pointer; font-weight: 700;
                font-family: 'Plus Jakarta Sans', sans-serif; font-size: 15px;
                transition: all 0.25s ease; box-shadow: 0 4px 6px -1px rgba(13, 148, 136, 0.3);
            }}
            .mic-btn:hover {{ transform: translateY(-2px); box-shadow: 0 8px 12px -1px rgba(13, 148, 136, 0.4); }}
            select {{
                padding: 12px 16px; border-radius: 12px; border: 1px solid #cbd5e1;
                font-family: 'Plus Jakarta Sans', sans-serif; font-size: 15px; font-weight: 500; outline: none;
                transition: border-color 0.2s; background: white; color: #1e293b;
            }}
            select:focus {{ border-color: #0d9488; box-shadow: 0 0 0 3px rgba(13, 148, 136, 0.15); }}
            #status {{ font-size: 15px; color: #64748b; font-weight: 600; }}
            .pulse {{ animation: pulse-animation 1.5s infinite; background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%); box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.7); }}
            @keyframes pulse-animation {{
                0% {{ box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.7); }}
                70% {{ box-shadow: 0 0 0 10px rgba(239, 68, 68, 0); }}
                100% {{ box-shadow: 0 0 0 0 rgba(239, 68, 68, 0); }}
            }}
        </style>
    </head>
    <body>
        <div class="voice-container">
            <select id="lang">
                <option value="en-US" {'selected' if current_lang == 'en-US' else ''}>English (US)</option>
                <option value="ta-IN" {'selected' if current_lang == 'ta-IN' else ''}>தமிழ் (Tamil)</option>
                <option value="hi-IN" {'selected' if current_lang == 'hi-IN' else ''}>हिन्दी (Hindi)</option>
            </select>
            <button id="mic-btn" class="mic-btn">🎙️ Voice Input</button>
            <span id="status"></span>
        </div>
        <script>
            const btn = document.getElementById('mic-btn');
            const status = document.getElementById('status');
            const langSelect = document.getElementById('lang');
            if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {{
                const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
                const recognition = new SpeechRecognition();
                recognition.continuous = false;
                recognition.interimResults = false;
                btn.onclick = () => {{
                    recognition.lang = langSelect.value;
                    recognition.start();
                    status.innerText = "Listening...";
                    btn.innerText = "🛑 Stop";
                    btn.classList.add("pulse");
                }};
                recognition.onresult = (event) => {{
                    const transcript = event.results[0][0].transcript;
                    const lang = recognition.lang;
                    let langName = "English";
                    if(lang === "ta-IN") langName = "Tamil";
                    if(lang === "hi-IN") langName = "Hindi";
                    status.innerText = langName + " recognized! Updating...";
                    
                    try {{
                        const textAreas = window.parent.document.querySelectorAll('textarea');
                        if (textAreas.length > 0) {{
                            const textArea = textAreas[0];
                            const currentValue = textArea.value;
                            const newValue = currentValue ? currentValue + " " + transcript : transcript;
                            const nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, "value").set;
                            nativeInputValueSetter.call(textArea, newValue);
                            const inputEvent = new Event('input', {{ bubbles: true }});
                            textArea.dispatchEvent(inputEvent);
                            setTimeout(() => {{ status.innerText = "Done!"; }}, 1500);
                        }} else {{
                            status.innerText = "Error: Textbox not found.";
                        }}
                    }} catch (e) {{
                        status.innerText = "Error updating text.";
                    }}
                }};
                recognition.onerror = (event) => {{
                    if(event.error === 'not-allowed') {{
                        status.innerText = "Microphone permission denied.";
                    }} else {{
                        status.innerText = "Error: " + event.error;
                    }}
                    btn.innerText = "🎙️ Voice Input";
                    btn.classList.remove("pulse");
                }};
                recognition.onend = () => {{
                    if (status.innerText === "Listening...") {{
                        status.innerText = "";
                    }}
                    btn.innerText = "🎙️ Voice Input";
                    btn.classList.remove("pulse");
                }};
            }} else {{
                btn.disabled = true;
                status.innerText = "Voice input not supported in this browser.";
                status.style.color = "red";
            }}
        </script>
    </body>
    </html>
    """
    components.html(voice_html, height=90)
    st.write("")
    
    st.session_state.user_input = st.text_area(
        "Your details",
        value=st.session_state.user_input,
        height=180,
        placeholder='e.g. "I am a widow, income 1 lakh, living in Bihar"',
        label_visibility="collapsed"
    )
    
    if st.session_state.language == "தமிழ்":
        use_transliteration = st.checkbox("Type Tamil using English letters", value=False)
    else:
        use_transliteration = False
    
    # Auto-detect language
    if st.session_state.user_input:
        st.session_state.output_language = detect_output_language(st.session_state.user_input)
        
    st.markdown(f"<p style='font-size: 0.95rem; color: #64748b; font-weight: 600; margin-bottom: 0.5rem;'>{t('quick_tags')}</p>", unsafe_allow_html=True)
    chip_cols = st.columns(4)
    chips = t("lbl_chips")
    for i, chip in enumerate(chips):
        with chip_cols[i % 4]:
            if st.button(chip, key=f"chip_{chip}", use_container_width=True):
                st.session_state.user_input = (st.session_state.user_input + " " + chip).strip()
                st.rerun()
    st.write("")
    st.write("")
    if st.button(t("btn_continue"), type="primary", use_container_width=True):
        if st.session_state.user_input.strip() == "":
            st.warning(t("warn_empty_input"))
        else:
            if use_transliteration:
                st.session_state.user_input = transliterate_to_tamil(st.session_state.user_input)
                st.session_state.output_language = detect_output_language(st.session_state.user_input)

            raw_profile = build_profile(st.session_state.user_input, st.session_state.language)
            
            gender_map = {"female": "Female", "male": "Male"}
            st.session_state.profile["Gender"] = gender_map.get(raw_profile.get("gender"))
            
            occ_map = {"unemployed": "Unemployed", "farmer": "Farmer", "student": "Student", "employed": "Employed", "business": "Business"}
            st.session_state.profile["Occupation"] = occ_map.get(raw_profile.get("occupation"))
            
            mar_map = {"widowed": "Widow", "unmarried": "Single", "married": "Married", "divorced": "Divorced"}
            st.session_state.profile["Marital Status"] = mar_map.get(raw_profile.get("marital_status"))
            
            state_map = {"bihar": "Bihar", "maharashtra": "Maharashtra", "tamil nadu": "Tamil Nadu", "uttar pradesh": "Uttar Pradesh"}
            state_val = raw_profile.get("state")
            st.session_state.profile["State"] = state_map.get(state_val, "Other") if state_val else None
            
            st.session_state.profile["Income"] = str(raw_profile.get("income")) if raw_profile.get("income") is not None else ""
            st.session_state.profile["Age"] = str(raw_profile.get("age")) if raw_profile.get("age") is not None else ""
            
            st.session_state.step = 3
            st.rerun()

def render_processing():
    st.markdown(f"<h2 style='color: #0f172a; font-weight: 800; margin-bottom: 1.5rem;'>{t('review_title')}</h2>", unsafe_allow_html=True)
    st.markdown(f"""
    <div class="stepper">
        <span style="color: #10b981;">{t('stepper_1')}</span>
        <span style="color: #10b981;">{t('stepper_2')}</span>
        <span class="stepper-active">{t('stepper_3')}</span>
        <span>{t('stepper_4')}</span>
    </div>
    """, unsafe_allow_html=True)
    st.info(t('review_info'))
    with st.container():
        st.markdown("<div class='premium-card' style='padding-top: 1rem;'>", unsafe_allow_html=True)
        col1, col2 = st.columns(2)
        with col1:
            gender_opts = ["Female", "Male", "Other"]
            g_val = st.session_state.profile.get("Gender")
            g_idx = gender_opts.index(g_val) if g_val in gender_opts else None
            # Show translated options but map back to English keys internally
            disp_gender_opts = [t_data(g) for g in gender_opts]
            disp_g_val = t_data(g_val) if g_val else None
            disp_g_idx = disp_gender_opts.index(disp_g_val) if disp_g_val in disp_gender_opts else None
            selected_disp_g = st.selectbox(t('lbl_gender'), disp_gender_opts, index=disp_g_idx)
            if selected_disp_g:
                st.session_state.profile["Gender"] = gender_opts[disp_gender_opts.index(selected_disp_g)]
            
            st.session_state.profile["Income"] = st.text_input(t('lbl_income'), value=st.session_state.profile.get("Income", ""))
            
            occ_opts = ["Unemployed", "Farmer", "Student", "Employed", "Business"]
            o_val = st.session_state.profile.get("Occupation")
            disp_occ_opts = [t_data(o) for o in occ_opts]
            disp_o_val = t_data(o_val) if o_val else None
            disp_o_idx = disp_occ_opts.index(disp_o_val) if disp_o_val in disp_occ_opts else None
            selected_disp_o = st.selectbox(t('lbl_occupation'), disp_occ_opts, index=disp_o_idx)
            if selected_disp_o:
                st.session_state.profile["Occupation"] = occ_opts[disp_occ_opts.index(selected_disp_o)]
        with col2:
            mar_opts = ["Widow", "Single", "Married", "Divorced"]
            m_val = st.session_state.profile.get("Marital Status")
            disp_mar_opts = [t_data(m) for m in mar_opts]
            disp_m_val = t_data(m_val) if m_val else None
            disp_m_idx = disp_mar_opts.index(disp_m_val) if disp_m_val in disp_mar_opts else None
            selected_disp_m = st.selectbox(t('lbl_marital'), disp_mar_opts, index=disp_m_idx)
            if selected_disp_m:
                st.session_state.profile["Marital Status"] = mar_opts[disp_mar_opts.index(selected_disp_m)]
            
            state_opts = ["Bihar", "Maharashtra", "Tamil Nadu", "Uttar Pradesh", "Other"]
            s_val = st.session_state.profile.get("State")
            disp_state_opts = [t_data(s) for s in state_opts]
            disp_s_val = t_data(s_val) if s_val else None
            disp_s_idx = disp_state_opts.index(disp_s_val) if disp_s_val in disp_state_opts else None
            selected_disp_s = st.selectbox(t('lbl_state'), disp_state_opts, index=disp_s_idx)
            if selected_disp_s:
                st.session_state.profile["State"] = state_opts[disp_state_opts.index(selected_disp_s)]
            
            st.session_state.profile["Age"] = st.text_input(t('lbl_age'), value=st.session_state.profile.get("Age", ""))
        st.write("---")
        st.markdown(f"**{t('meta_title')}**")
        st.markdown(f"• {t('meta_lang')} **{st.session_state.language}**")
        inc_val = st.session_state.profile.get("Income", "")
        if inc_val:
            st.markdown(f"• {t('meta_income')} **₹{str(inc_val).replace(',', '')}**")
        else:
            st.markdown(f"• {t('meta_income')} **{t('not_provided')}**")
        st.markdown("</div>", unsafe_allow_html=True)
    st.write("")
    col1, col2 = st.columns([1, 1])
    with col1:
        if st.button(t("btn_edit_input"), use_container_width=True):
            st.session_state.step = 2
            st.rerun()
    with col2:
        if st.button(t("btn_check_eligibility"), type="primary", use_container_width=True):
            current_time = time.time()
            last_submit_time = st.session_state.get("last_submit_time", 0.0)
            
            # Cooldown guard: prevent accidental rapid repeated clicks
            if current_time - last_submit_time < 3.0:
                st.warning("Please wait a moment before resubmitting.")
                st.stop()
                
            backend_profile = build_backend_profile()
            normalized_profile = normalize_profile(backend_profile)
            user_input_text = st.session_state.get("user_input", "")
            
            # Formulate a unique profile key to check for changes
            current_profile_key = {
                "profile": normalized_profile,
                "user_text": user_input_text
            }
            
            last_profile_key = st.session_state.get("last_profile_key")
            last_results = st.session_state.get("last_results")
            
            # Check if profile is unchanged and we already have results
            if last_profile_key == current_profile_key and last_results is not None:
                logger.info("[DEBUG] User profile is unchanged. Reusing cached matching results.")
                print("[DEBUG] User profile is unchanged. Reusing cached matching results.")
                st.session_state.results = last_results
                st.session_state.selected_scheme = last_results[0] if last_results else None
                st.session_state.step = 4
                st.rerun()
                
            # If we reach here, it's a new or changed profile submission
            st.session_state.last_submit_time = current_time
            st.session_state.last_profile_key = current_profile_key
            
            with st.spinner(t("analyzing")):
                # Reset rate limit status flags for the new search
                st.session_state.search_rate_limited = False
                st.session_state.ai_rate_limited = False
                
                try:
                    results = get_top_matches(
                        normalized_profile,
                        top_n=15,
                        user_text=st.session_state.user_input
                    )
                    st.session_state.results = results
                    st.session_state.last_results = results  # cache results
                    st.session_state.selected_scheme = results[0] if results else None
                    st.session_state.step = 4
                    st.rerun()
                except Exception as e:
                    st.error(f"Error matching schemes: {e}")
                    logger.error(f"Error in matching: {e}")

def render_results():
    # Log 7: UI displays the Gemini-generated matching results
    logger.info(f"[DEBUG] UI rendering Gemini-generated matching results: {[r.get('scheme_name') for r in st.session_state.results]}")
    print(f"[DEBUG] UI rendering Gemini-generated matching results: {[r.get('scheme_name') for r in st.session_state.results]}")
    
    col1, col2 = st.columns([3, 1])
    with col1:
        total = len(st.session_state.results)
        st.markdown(f"<h2 style='color: #0f172a; font-weight: 800;'>{total} {t('schemes_found')}</h2>", unsafe_allow_html=True)
        st.markdown(f"<p style='color: #64748b; margin-top: -10px;'>{t('based_on_profile')}</p>", unsafe_allow_html=True)
    
    if st.session_state.get("ai_rate_limited"):
        st.warning(t("ai_rate_limited"))
    if st.session_state.get("search_rate_limited"):
        st.warning(t("live_search_rate_limited"))

    with col2:
        if st.button(t("btn_start_over"), use_container_width=True):
            st.session_state.step = 1
            st.session_state.user_input = ""
            st.session_state.results = []
            st.session_state.selected_scheme = None
            st.rerun()
    st.markdown(f"<p style='font-size: 0.95rem; color: #475569; font-weight: 600; margin-bottom: 0.5rem;'>{t('filter_category')}</p>", unsafe_allow_html=True)
    filt_col1, filt_col2, filt_col3, filt_col4, filt_col5 = st.columns(5)
    with filt_col1: st.button(t("cat_women"), use_container_width=True)
    with filt_col2: st.button(t("cat_pension"), use_container_width=True)
    with filt_col3: st.button(t("cat_housing"), use_container_width=True)
    with filt_col4: st.button(t("cat_employment"), use_container_width=True)
    with filt_col5: st.button(t("cat_state"), use_container_width=True)
    st.write("---")
    if not st.session_state.results:
        st.warning(t("warn_no_schemes"))
        return
    for i, scheme in enumerate(st.session_state.results):
        raw_status = scheme.get("match_status", "No Match")
        status_key = "status_" + raw_status.lower().replace(" ", "_")
        status = t(status_key)
        
        score = scheme.get("match_score", 0)
        badge_class = "badge-eligible" if raw_status == "Full Match" else "badge-partial"
        
        raw_why_matched = scheme.get("why_matched", [])
        raw_why_not_matched = scheme.get("why_not_matched", [])
        
        matched_list = [translate_explanation(x) for x in raw_why_matched]
        not_matched_list = [translate_explanation(x) for x in raw_why_not_matched]
        
        reasons_matched = "<br>".join([f"✓ {x}" for x in matched_list]) or t("reason_no_pos")
        reasons_not = "<br>".join([f"✗ {x}" for x in not_matched_list]) or t("reason_no_neg")
        
        req_docs_text = ", ".join([translate_explanation(x) for x in scheme.get('required_documents', [])])
        
        st.markdown(f"""
        <div class="scheme-card">
            <div style="display:flex; justify-content:space-between; align-items:start;">
                <span class="{badge_class}">{status}</span>
                <span style="color:#0f766e; font-weight:800; font-size:0.9rem; background:#ccfbf1; padding:6px 14px; border-radius:16px; border:1px solid #99f6e4;">{t('match')} {score}%</span>
            </div>
            <h3 style="margin-top:0.5rem; color:#0f172a; font-weight:800;">{scheme.get('scheme_name', '')}</h3>
            <p style="color:#475569; line-height:1.6; font-size:1.05rem;"><strong>{t('category')}</strong> {translate_explanation(scheme.get('category', ''))}</p>
            <p style="color:#475569; line-height:1.6; font-size:1.05rem;"><strong>{t('why_matched')}</strong><br>{reasons_matched}</p>
            <p style="color:#b45309; line-height:1.6; background:#fffbeb; padding:12px 16px; border-radius:12px; border-left:4px solid #f59e0b; font-weight:500;"><strong>{t('why_not_matched')}</strong><br>{reasons_not}</p>
            <div style="background:#f8fafc; padding:12px 16px; border-radius:12px; margin-top:1rem;">
                <p style="color:#334155; line-height:1.5; margin-bottom:0;"><strong>{t('req_docs')}</strong> {req_docs_text}</p>
            </div>
        </div>
        """, unsafe_allow_html=True)
        btn_col1, btn_col2, btn_col3 = st.columns(3)
        with btn_col1:
            if st.button(t("btn_view_details"), key=f"view_{i}", type="primary", use_container_width=True):
                st.session_state.selected_scheme = scheme
                st.session_state.prev_step = 4
                st.session_state.step = 5
                st.session_state.find_centers_clicked = False
                st.rerun()
        with btn_col2:
            st.button(t("btn_save_later"), key=f"save_{i}", use_container_width=True)
        with btn_col3:
            st.link_button(t("btn_apply"), scheme.get("official_apply_link", "#"), use_container_width=True)
        st.write("")

    # --- Web Search: Newly Announced Schemes ---
    try:
        from search_api import fetch_new_schemes, is_available as search_available
        if search_available():
            web_results = fetch_new_schemes(build_backend_profile(), max_results=3)
            if web_results:
                st.write("---")
                if st.session_state.get("search_rate_limited"):
                    st.warning(t("live_search_rate_limited"))
                st.markdown("""
                <div style="margin-top: 1rem; margin-bottom: 1rem;">
                    <h3 style="color: #0f172a; font-weight: 700;">🌐 Discover More Schemes</h3>
                    <p style="color: #64748b; font-size: 0.95rem;">Recently announced schemes that may be relevant to you:</p>
                </div>
                """, unsafe_allow_html=True)
                for wr in web_results:
                    st.markdown(f"""
                    <div class="premium-card" style="padding: 1.25rem 1.5rem;">
                        <h4 style="margin-top: 0; font-size: 1.05rem; color: #0f172a;">
                            🔗 {wr.get('title', '')}
                        </h4>
                        <p style="color: #475569; font-size: 0.95rem; line-height: 1.5; margin-bottom: 0.75rem;">
                            {wr.get('snippet', '')}
                        </p>
                        <p style="margin-bottom: 0;">
                            <a href="{wr.get('link', '#')}" target="_blank" 
                               style="color: #0d9488; font-weight: 600; text-decoration: none; font-size: 0.9rem;">
                                Visit {wr.get('source', 'source')} →
                            </a>
                        </p>
                    </div>
                    """, unsafe_allow_html=True)
    except Exception:
        pass  # Web search is optional — silently skip on any error

def render_browse_schemes():
    if st.button(t("btn_back")):
        st.session_state.step = 1
        st.rerun()

    st.markdown(f"<h1 class='main-header'>{t('browse_schemes_title')}</h1>", unsafe_allow_html=True)
    st.write("")

    search_query = st.text_input("Search current government schemes (e.g. 'farmer schemes', 'subsidies'):", value=st.session_state.get("browse_search_query", ""), placeholder="Type query and click search...")
    if st.button("Search Web-grounded Schemes", type="primary", use_container_width=True):
        if search_query.strip():
            st.session_state.browse_search_query = search_query
            st.rerun()
        else:
            st.warning("Please enter a search query.")
            
    active_query = st.session_state.get("browse_search_query", "")
    if active_query:
        st.markdown(f"### 🌐 Live AI Results for: *'{active_query}'*")
        with st.spinner("Analyzing with Gemini..."):
            try:
                # Use Gemini dynamically here
                from scheme_elligibility_engine.api_utils import generate_content_with_cascade
                prompt = f"""You are an AI expert on Government of India schemes.
                Provide a list of up to 5 government schemes matching the user's query: "{active_query}".
                Respond only with a JSON object:
                {{
                  "schemes": [
                    {{
                      "scheme_name": "...",
                      "description": "...",
                      "eligibility": "...",
                      "benefits": "...",
                      "application_process": "...",
                      "source_url": "..."
                    }}
                  ]
                }}
                """
                response = generate_content_with_cascade(prompt, generation_config={"response_mime_type": "application/json"}, api_name="Gemini Browse API")
                import json
                resp_text = response.text.strip()
                if resp_text.startswith("```"):
                    lines = resp_text.split("\n")
                    if lines[0].startswith("```json") or lines[0].startswith("```"):
                        resp_text = "\n".join(lines[1:-1])
                data = json.loads(resp_text)
                live_schemes = data.get("schemes", [])
                
                if not live_schemes:
                    st.warning("⚠️ No relevant schemes found.")
                else:
                    st.success(f"✓ Found {len(live_schemes)} schemes.")
                    for idx, s in enumerate(live_schemes):
                        st.markdown(f"""
                        <div class="premium-card" style="background: #ffffff; border: 1px solid #e2e8f0; padding: 1.5rem; margin-bottom: 1rem; border-radius: 12px; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);">
                            <h3 style="margin: 0 0 0.5rem 0; font-size: 1.35rem; color: #1e3a8a; font-weight: 800;">🏢 {s.get('scheme_name', 'Unknown Scheme')}</h3>
                            <p style="color: #475569; font-size: 1rem; line-height: 1.5; margin-bottom: 1rem;">{s.get('description', '')}</p>
                            <div style="background-color: #f8fafc; border-radius: 12px; padding: 1rem; border: 1px solid #f1f5f9; margin-bottom: 1rem; font-size: 0.95rem; line-height: 1.6; color: #1e293b;">
                                <b>🎯 Eligibility Criteria:</b> {s.get('eligibility', 'N/A')}<br>
                                <b>💰 Benefits & Subsidies:</b> {s.get('benefits', 'N/A')}<br>
                                <b>✍️ How to Apply:</b> {s.get('application_process', 'N/A')}<br>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
                        source_url = s.get('source_url', '#')
                        st.link_button("Open Official Website Source", source_url, use_container_width=True, key=f"browse_live_btn_{idx}")
                        st.write("")
            except Exception as e:
                st.error(f"❌ Search failed: AI synthesis is temporarily unavailable. Error details: {str(e)}")

def render_detail():
    scheme = st.session_state.get("selected_scheme")
    if not scheme:
        st.warning(t("warn_no_schemes"))
        return
    
    back_step = st.session_state.get("prev_step", 4)
    if st.button(t("btn_back_results")):
        st.session_state.step = back_step
        st.rerun()
        
    raw_status = scheme.get("match_status", "No Match")
    status_key = "status_" + raw_status.lower().replace(" ", "_")
    status = t(status_key)
        
    st.markdown(f"<h2 style='color:#0f172a; font-weight:800; margin-bottom:0.5rem;'>{scheme.get('scheme_name', '')}</h2>", unsafe_allow_html=True)
    if "match_score" in scheme:
        st.markdown(f"<span class='badge-eligible' style='margin-bottom:2rem;'>{status} - {scheme.get('match_score', 0)}% Match</span>", unsafe_allow_html=True)
    else:
        st.markdown(f"<span class='badge-eligible' style='margin-bottom:2rem;'>📁 {t('browse_mode')}</span>", unsafe_allow_html=True)
        
    col1, col2 = st.columns([2, 1.2])
    with col1:
        st.markdown(f"<h3 style='color:#1e293b; font-weight:700;'>{t('overview')}</h3>", unsafe_allow_html=True)
        st.markdown(f"<p style='color:#475569; font-size:1.1rem; line-height:1.6;'>{translate_explanation(scheme.get('benefit_summary', ''))}</p>", unsafe_allow_html=True)
        st.write("")
        st.markdown(f"<h3 style='color:#1e293b; font-weight:700;'>{t('who_can_apply')}</h3>", unsafe_allow_html=True)
        
        if "match_score" in scheme:
            matched_list = [translate_explanation(x) for x in scheme.get("why_matched", [])]
            not_matched_list = [translate_explanation(x) for x in scheme.get("why_not_matched", [])]
            
            matched = "<br>".join([f"• {x}" for x in matched_list]) or t("reason_no_pos")
            not_matched = "<br>".join([f"• {x}" for x in not_matched_list]) or t("reason_no_neg")
        else:
            matched = f"• {translate_explanation(scheme.get('eligibility_criteria', ''))}"
            not_matched = translate_explanation(t("reason_browse_mode"))
        
        st.markdown(f"<p style='color:#475569; line-height:1.7;'><strong>{t('matched')}</strong><br>{matched}</p>", unsafe_allow_html=True)
        st.markdown(f"<p style='color:#b45309; line-height:1.7;'><strong>{t('not_matched')}</strong><br>{not_matched}</p>", unsafe_allow_html=True)
        st.write("")
        st.markdown(f"<h3 style='color:#1e293b; font-weight:700;'>{t('how_to_apply')}</h3>", unsafe_allow_html=True)
        st.markdown("<ol style='color:#475569; font-size:1.05rem; line-height:1.8;'>" + "".join([f"<li>{translate_explanation(step)}</li>" for step in scheme.get("application_steps", [])]) + "</ol>", unsafe_allow_html=True)
    with col2:
        st.markdown(f"""
        <div class="premium-card" style="background: linear-gradient(180deg, #f0fdf4 0%, #ffffff 100%); border: 1px solid #bbf7d0; box-shadow: 0 10px 25px -5px rgba(22, 101, 52, 0.05);">
            <h4 style="color: #166534;"><span style="font-size: 1.4rem; margin-right: 12px;">📁</span> {t('docs_required')}</h4>
        </div>
        """, unsafe_allow_html=True)
        st.markdown("<ul style='color:#166534; font-size:1rem; line-height:1.8; margin-top:16px; font-weight:500;'>" + "".join([f"<li>{translate_explanation(doc)}</li>" for doc in scheme.get("required_documents", [])]) + "</ul>", unsafe_allow_html=True)
        st.link_button(t("btn_apply"), scheme.get("official_apply_link", "#"), use_container_width=True)
        st.write("")
        st.write("---")
        # Subtitle
        st.markdown(f"<h4 style='color:#0f172a; font-weight:700; margin-top:1rem;'>📍 {t('find_center_title')}</h4>", unsafe_allow_html=True)
        
        # Input field for location search
        user_address = st.text_input(
            "Enter your location (e.g. area, city, pincode, or address):",
            value=st.session_state.get("detail_entered_address", ""),
            key="detail_entered_address_input",
            placeholder="Type location..."
        )
        
        # Input field for search query
        user_query = st.text_input(
            "Enter type of center to find (e.g. e-Sevai center, CSC center):",
            value=st.session_state.get("detail_search_query", "e-Sevai center"),
            key="detail_search_query_input",
            placeholder="Type center type..."
        )
        
        col_search, col_gps = st.columns([1, 1])
        with col_search:
            if st.button("Find Nearest Centers", type="primary", use_container_width=True):
                st.session_state.find_centers_clicked = True
                st.session_state.detail_entered_address = user_address
                st.session_state.detail_search_query = user_query
                if user_address.strip():
                    with st.spinner("Finding location details..."):
                        try:
                            geocode_res = geocode_address_free(user_address)
                            if geocode_res:
                                lat, lng, formatted_addr = geocode_res
                                st.session_state.user_lat = lat
                                st.session_state.user_lng = lng
                                st.session_state.location_source = formatted_addr
                                st.session_state.geo_state = "granted"
                            else:
                                st.session_state.user_lat = None
                                st.session_state.user_lng = None
                                st.session_state.location_source = user_address
                                st.session_state.geo_state = "fallback_search"
                            st.rerun()
                        except Exception as e:
                            st.error(f"Could not find location: {str(e)}")
                else:
                    st.warning("Please enter a location.")
        with col_gps:
            if st.button("Use GPS Location", use_container_width=True):
                st.session_state.find_centers_clicked = True
                st.session_state.geo_state = "requesting"
                st.session_state.user_lat = None
                st.session_state.user_lng = None
                st.rerun()
        
        if st.session_state.find_centers_clicked:
            
            # Render Geolocation request HTML/JS if we are requesting via GPS
            if st.session_state.geo_state == "requesting":
                geo_html = """
                <!DOCTYPE html>
                <html>
                <head>
                    <style>
                        body {{ font-family: sans-serif; background: transparent; margin: 0; padding: 10px; }}
                        #debug-box {{ border: 1px solid #ccc; padding: 10px; border-radius: 8px; font-size: 13px; background: #f8fafc; display: none; }}
                    </style>
                </head>
                <body>
                    <div id="debug-box">
                        <span id="d-res">Waiting...</span>
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
                                console.error(e);
                            }}
                            return false;
                        }}

                        window.onload = function() {{
                            try {{
                                const parentHasGeo = window.parent && window.parent.navigator && window.parent.navigator.geolocation;
                                if (parentHasGeo) {{
                                    window.parent.eval(`
                                        navigator.geolocation.getCurrentPosition(
                                            (position) => {{
                                                const inputs = document.querySelectorAll('input');
                                                for (let input of inputs) {{
                                                    if (input.placeholder === 'geo_lat') {{
                                                        const nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                                                        nativeSetter.call(input, position.coords.latitude.toString());
                                                        input.dispatchEvent(new Event('input', {{ bubbles: true }}));
                                                        input.dispatchEvent(new Event('change', {{ bubbles: true }}));
                                                    }}
                                                    if (input.placeholder === 'geo_lng') {{
                                                        const nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                                                        nativeSetter.call(input, position.coords.longitude.toString());
                                                        input.dispatchEvent(new Event('input', {{ bubbles: true }}));
                                                        input.dispatchEvent(new Event('change', {{ bubbles: true }}));
                                                    }}
                                                }}
                                            }},
                                            (error) => {{
                                                let reason = "Unknown error";
                                                if (error.code === 1) reason = "Permission denied";
                                                if (error.code === 2) reason = "Location unavailable";
                                                if (error.code === 3) reason = "Timeout";
                                                const inputs = document.querySelectorAll('input');
                                                for (let input of inputs) {{
                                                    if (input.placeholder === 'geo_err') {{
                                                        const nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                                                        nativeSetter.call(input, reason);
                                                        input.dispatchEvent(new Event('input', {{ bubbles: true }}));
                                                        input.dispatchEvent(new Event('change', {{ bubbles: true }}));
                                                    }}
                                                }}
                                            }},
                                            {{ enableHighAccuracy: true, timeout: 10000, maximumAge: 0 }}
                                        );
                                    `);
                                }} else {{
                                    setInput("geo_err", "Unsupported");
                                }}
                            }} catch (err) {{
                                setInput("geo_err", err.message);
                            }}
                        }};
                    </script>
                </body>
                </html>
                """
                components.html(geo_html, height=0)
                
            # Render hidden Streamlit widgets
            st.markdown("""
            <style>
                div[data-testid="stTextInput"]:has(input[placeholder="geo_lat"]),
                div[data-testid="stTextInput"]:has(input[placeholder="geo_lng"]),
                div[data-testid="stTextInput"]:has(input[placeholder="geo_err"]) {
                    display: none !important;
                }
            </style>
            """, unsafe_allow_html=True)
            
            lat_val = st.text_input("Lat", value="", placeholder="geo_lat", key="detail_geo_lat", label_visibility="collapsed")
            lng_val = st.text_input("Lng", value="", placeholder="geo_lng", key="detail_geo_lng", label_visibility="collapsed")
            err_val = st.text_input("Err", value="", placeholder="geo_err", key="detail_geo_err", label_visibility="collapsed")
            
            import logging
            logger = logging.getLogger("geolocation_workflow")
            
            # Check inputs to update state
            if err_val and st.session_state.geo_state == "requesting":
                logger.warning(f"Geolocation error/permission response received from browser: {err_val}")
                st.session_state.geo_state = err_val
                st.rerun()
                
            if lat_val and lng_val and st.session_state.geo_state == "requesting":
                try:
                    st.session_state.user_lat = float(lat_val)
                    st.session_state.user_lng = float(lng_val)
                    st.session_state.location_source = "GPS Coordinates"
                    st.session_state.geo_state = "granted"
                    logger.info(f"Geolocation permission granted: lat={lat_val}, lng={lng_val}")
                    st.rerun()
                except ValueError as e:
                    logger.error(f"Error parsing geolocation coordinate values lat={lat_val}, lng={lng_val}: {str(e)}")
            
            # Render states
            if st.session_state.geo_state == "requesting":
                st.info("Detecting your location, please accept the browser permission request...")
            elif "denied" in str(st.session_state.geo_state).lower() or "permission" in str(st.session_state.geo_state).lower():
                logger.warning("User denied location permission.")
                st.warning("Location permission was denied. Please enter your location manually in the search box above.")
            elif st.session_state.geo_state == "granted":
                user_lat = st.session_state.user_lat
                user_lng = st.session_state.user_lng
                
                if user_lat is not None and user_lng is not None:
                    # Retrieve the custom query entered by the user
                    search_query_val = st.session_state.get("detail_search_query_input", "e-Sevai center")
                    if not search_query_val.strip():
                        search_query_val = "e-Sevai center"
                        
                    # Fetch and show centers using Google Places API (New)
                    try:
                        logger.info(f"Fetching live application centers for lat={user_lat}, lng={user_lng}, query='{search_query_val}'")
                        
                        # Load Maps API Key from environment
                        api_key = os.environ.get("GOOGLE_MAPS_API_KEY")
                        if not api_key:
                            st.error("❌ Google Maps API Key is missing from the environment. Please check your .env configuration.")
                            nearby_centers = []
                        else:
                            # Use 3km (3000m) default radius as requested
                            nearby_centers = fetch_places_new(user_lat, user_lng, search_query_val, api_key, radius_meters=3000.0)
                        
                        if not nearby_centers:
                            st.warning(f"⚠️ No '{search_query_val}' centers were found within 3 km of this location.")
                        else:
                            st.success(f"✓ Showing centers near: {st.session_state.get('location_source', 'your location')}")
                            
                            import urllib.parse
                            for idx, c in enumerate(nearby_centers):
                                if idx == 0:
                                    bg_style = "background: linear-gradient(135deg, #f0fdf4 0%, #ffffff 100%); border: 1.5px solid #059669; box-shadow: 0 4px 6px rgba(5,150,105,0.05);"
                                    badge = "<span style='color:#059669; font-weight:700; font-size:0.8rem; background:#d1fae5; padding:2px 6px; border-radius:4px;'>Nearest Center</span>"
                                    st.markdown("##### 🏢 Nearest Center Details")
                                else:
                                    if idx == 1:
                                        st.markdown("##### 📍 Other Nearby Centers (within 3 km)")
                                    bg_style = "background: #ffffff; border: 1px solid #e2e8f0;"
                                    badge = ""
                                    
                                st.markdown(f"""
                                <div class="premium-card" style="{bg_style} padding: 12px; margin-bottom: 10px; border-radius: 8px; font-size: 0.9rem;">
                                    <b style="color: #0f172a; font-size: 1rem;">{c['name']}</b> {badge}<br>
                                    <div style="margin-top: 6px; color: #475569; line-height: 1.4;">
                                        <b>Address:</b> {c['address']}<br>
                                        <b>Distance:</b> <span style="font-weight: 700; color: #0d9488;">{c['distance']:.2f} km</span> from your current location<br>
                                        <b>Latitude:</b> {c['lat']}<br>
                                        <b>Longitude:</b> {c['lng']}
                                    </div>
                                </div>
                                """, unsafe_allow_html=True)
                                
                                query_str = urllib.parse.quote(f"{c['name']}, {c['address']}")
                                st.link_button("Open in Google Maps", f"https://www.google.com/maps/search/?api=1&query={query_str}", use_container_width=True, key=f"detail_btn_map_{idx}")
                                
                    except Exception as e:
                        logger.exception(f"Exception raised in Places API lookup: {str(e)}")
                        st.error(f"⚠️ Could not search for nearby centers: {str(e)}")
            elif st.session_state.geo_state == "fallback_search":
                # When geocoding is unavailable or fails
                st.error("❌ Invalid location: We could not resolve coordinates for this address. Please try a different address (e.g. city or state).")
            else:
                logger.error(f"Invalid geo_state encountered: {st.session_state.geo_state}")
                st.error(f"❌ Location detection failed: {st.session_state.geo_state}")

def render_no_match():
    st.write("")
    st.write("")
    st.markdown("<div style='text-align: center; padding: 2rem 0; animation: float 4s ease-in-out infinite;'>", unsafe_allow_html=True)
    st.markdown("<span style='font-size: 6rem; display: inline-block; filter: drop-shadow(0 10px 8px rgb(0 0 0 / 0.04));'>🔍</span>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)
    st.markdown(f"<h2 style='text-align: center; color: #0f172a; margin-top: 0; font-weight: 800;'>{t('no_match_title')}</h2>", unsafe_allow_html=True)
    st.markdown(f"<p style='text-align: center; color: #64748b; font-size: 1.15rem; max-width: 600px; margin: 1rem auto 2rem auto; line-height: 1.6;'>{t('no_match_desc')}</p>", unsafe_allow_html=True)
    st.markdown(f"""
    <div class="premium-card" style="max-width: 700px; margin: 0 auto;">
        <h4 style="margin-bottom: 1rem;">{t('suggestions_title')}</h4>
        <ul style="color: #475569; font-size: 1.05rem; line-height: 1.8; margin-bottom: 0;">
            <li>{t('sugg_1')}</li>
            <li>{t('sugg_2')}</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)
    st.write("---")
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            if st.button(t("btn_edit_details"), type="primary", use_container_width=True):
                st.session_state.step = 3
                st.rerun()
        with col_btn2:
            if st.button(t("btn_browse_all"), use_container_width=True):
                st.toast("Browsing all schemes")

# --- Geolocation & Map Database / Logic ---

STATE_CITIES = {
    "Tamil Nadu": {
        "Chennai": (13.0827, 80.2707),
        "Coimbatore": (11.0168, 76.9558),
        "Madurai": (9.9252, 78.1198),
        "Trichy": (10.7905, 78.7047),
        "Salem": (11.6643, 78.1460)
    },
    "Bihar": {
        "Patna": (25.5941, 85.1376),
        "Gaya": (24.7955, 85.0002),
        "Muzaffarpur": (26.1209, 85.3647),
        "Bhagalpur": (25.2425, 87.0135)
    },
    "Maharashtra": {
        "Mumbai": (19.0760, 72.8777),
        "Pune": (18.5204, 73.8567),
        "Nagpur": (21.1458, 79.0882),
        "Nashik": (19.9975, 73.7898)
    },
    "Uttar Pradesh": {
        "Lucknow": (26.8467, 80.9462),
        "Kanpur": (26.4499, 80.3319),
        "Varanasi": (25.3176, 82.9739),
        "Agra": (27.1767, 78.0081),
        "Prayagraj": (25.4358, 81.8463)
    },
    "Other": {
        "New Delhi": (28.6139, 77.2090)
    }
}

APPLICATION_CENTERS = [
    # --- Tamil Nadu (e-Sevai Centers) ---
    {
        "name": "e-Sevai Center (TNESEV01)",
        "type": "e-Sevai Center",
        "address": "Fort St. George, Secretariat, Chennai, Tamil Nadu 600009",
        "state": "Tamil Nadu",
        "lat": 13.0827,
        "lng": 80.2707,
        "phone": "+91 44 2567 1876",
        "service_specialty": "All Tamil Nadu State Welfare Schemes, Pensions, and Certificates"
    },
    {
        "name": "e-Sevai Center (TNESEV02)",
        "type": "e-Sevai Center",
        "address": "District Collectorate Compound, Coimbatore, Tamil Nadu 641018",
        "state": "Tamil Nadu",
        "lat": 11.0168,
        "lng": 76.9558,
        "phone": "+91 422 230 0124",
        "service_specialty": "Agricultural & Widow Pensions, Income Certificates"
    },
    {
        "name": "e-Sevai Center (TNESEV03)",
        "type": "e-Sevai Center",
        "address": "Collectorate Compound, Madurai, Tamil Nadu 625020",
        "state": "Tamil Nadu",
        "lat": 9.9252,
        "lng": 78.1198,
        "phone": "+91 452 253 1156",
        "service_specialty": "Social Welfare Schemes, Housing and Pension Schemes"
    },
    {
        "name": "e-Sevai Center (TNESEV04)",
        "type": "e-Sevai Center",
        "address": "District Collector's Office, Tiruchirappalli, Tamil Nadu 620001",
        "state": "Tamil Nadu",
        "lat": 10.7905,
        "lng": 78.7047,
        "phone": "+91 431 241 5122",
        "service_specialty": "Unorganized Sector Schemes, Old Age Pension"
    },
    {
        "name": "e-Sevai Center (TNESEV05)",
        "type": "e-Sevai Center",
        "address": "District Collectorate, Salem, Tamil Nadu 636001",
        "state": "Tamil Nadu",
        "lat": 11.6643,
        "lng": 78.1460,
        "phone": "+91 427 241 1234",
        "service_specialty": "Widow Welfare, Family Benefit Schemes"
    },

    # --- Bihar (Vasudha Kendra - CSC) ---
    {
        "name": "Vasudha Kendra (CSC-BH01)",
        "type": "Common Service Centre (CSC)",
        "address": "Collectorate Road, Patna, Bihar 800001",
        "state": "Bihar",
        "lat": 25.5941,
        "lng": 85.1376,
        "phone": "+91 612 221 5432",
        "service_specialty": "Bihar State Social Security Pensions, PM-SYM, Aadhaar Services"
    },
    {
        "name": "Vasudha Kendra (CSC-BH02)",
        "type": "Common Service Centre (CSC)",
        "address": "District Collectorate, Gaya, Bihar 823001",
        "state": "Bihar",
        "lat": 24.7955,
        "lng": 85.0002,
        "phone": "+91 631 222 0045",
        "service_specialty": "PM-KISAN registration, Agricultural & Widow Pension"
    },
    {
        "name": "Vasudha Kendra (CSC-BH03)",
        "type": "Common Service Centre (CSC)",
        "address": "Collectorate Compound, Muzaffarpur, Bihar 842001",
        "state": "Bihar",
        "lat": 26.1209,
        "lng": 85.3647,
        "phone": "+91 621 224 3321",
        "service_specialty": "Social Welfare Department Pension Schemes, PMUY LPG Application"
    },
    {
        "name": "Vasudha Kendra (CSC-BH04)",
        "type": "Common Service Centre (CSC)",
        "address": "District Office, Bhagalpur, Bihar 812001",
        "state": "Bihar",
        "lat": 25.2425,
        "lng": 87.0135,
        "phone": "+91 641 240 1122",
        "service_specialty": "Jan Dhan Bank Account linkage, PM-SYM unorganized pension"
    },

    # --- Maharashtra (Maha e-Seva Kendra) ---
    {
        "name": "Maha e-Seva Kendra (MH-01)",
        "type": "Maha e-Seva Kendra",
        "address": "Old Secretariat Bldg, Fort, Mumbai, Maharashtra 400032",
        "state": "Maharashtra",
        "lat": 19.0760,
        "lng": 72.8777,
        "phone": "+91 22 2202 4321",
        "service_specialty": "Sanjay Gandhi Niradhar Pension, Shravanbal Seva State Schemes"
    },
    {
        "name": "Maha e-Seva Kendra (MH-02)",
        "type": "Maha e-Seva Kendra",
        "address": "District Collector Office, Pune, Maharashtra 411001",
        "state": "Maharashtra",
        "lat": 18.5204,
        "lng": 73.8567,
        "phone": "+91 20 2612 3456",
        "service_specialty": "Unorganized worker pensions, PM-SYM, Housing Schemes"
    },
    {
        "name": "Maha e-Seva Kendra (MH-03)",
        "type": "Maha e-Seva Kendra",
        "address": "Collectorate Compound, Civil Lines, Nagpur, Maharashtra 440001",
        "state": "Maharashtra",
        "lat": 21.1458,
        "lng": 79.0882,
        "phone": "+91 712 256 1234",
        "service_specialty": "Widow & Old Age pensions, PMUY LPG distributor support"
    },
    {
        "name": "Maha e-Seva Kendra (MH-04)",
        "type": "Maha e-Seva Kendra",
        "address": "District Collector Office, Nashik, Maharashtra 422002",
        "state": "Maharashtra",
        "lat": 19.9975,
        "lng": 73.7898,
        "phone": "+91 253 257 8899",
        "service_specialty": "Farmers Scheme registrations, Sanjay Gandhi Niradhar"
    },

    # --- Uttar Pradesh (Jan Seva Kendra - CSC) ---
    {
        "name": "Jan Seva Kendra (CSC-UP01)",
        "type": "Common Service Centre (CSC)",
        "address": "Collectorate Office, Hazratganj, Lucknow, Uttar Pradesh 226001",
        "state": "Uttar Pradesh",
        "lat": 26.8467,
        "lng": 80.9462,
        "phone": "+91 522 262 3045",
        "service_specialty": "UP Widow/Destitute Women Pension, PM-SYM, Jan Dhan services"
    },
    {
        "name": "Jan Seva Kendra (CSC-UP02)",
        "type": "Common Service Centre (CSC)",
        "address": "Collectorate Office, Civil Lines, Kanpur, Uttar Pradesh 208001",
        "state": "Uttar Pradesh",
        "lat": 26.4499,
        "lng": 80.3319,
        "phone": "+91 512 230 4055",
        "service_specialty": "Old Age & Destitute Pension, Labor registration"
    },
    {
        "name": "Jan Seva Kendra (CSC-UP03)",
        "type": "Common Service Centre (CSC)",
        "address": "District Collectorate, Kutchery, Varanasi, Uttar Pradesh 221002",
        "state": "Uttar Pradesh",
        "lat": 25.3176,
        "lng": 82.9739,
        "phone": "+91 542 250 8243",
        "service_specialty": "PMUY LPG gas connection, Widow Welfare Scheme registrations"
    },
    {
        "name": "Jan Seva Kendra (CSC-UP04)",
        "type": "Common Service Centre (CSC)",
        "address": "Collectorate Office, Agra, Uttar Pradesh 282001",
        "state": "Uttar Pradesh",
        "lat": 27.1767,
        "lng": 78.0081,
        "phone": "+91 562 226 5044",
        "service_specialty": "Destitute Pension, PM-KISAN, Aadhaar Updation"
    },
    {
        "name": "Jan Seva Kendra (CSC-UP05)",
        "type": "Common Service Centre (CSC)",
        "address": "Collectorate Office, Prayagraj, Uttar Pradesh 211002",
        "state": "Uttar Pradesh",
        "lat": 25.4358,
        "lng": 81.8463,
        "phone": "+91 532 264 1205",
        "service_specialty": "Unorganized Sector Schemes, Old Age Pension"
    },

    # --- National / New Delhi (Other) ---
    {
        "name": "Common Service Centre (CSC-DL01)",
        "type": "Common Service Centre (CSC)",
        "address": "Palika Kendra, Connaught Place, New Delhi 110001",
        "state": "Other",
        "lat": 28.6139,
        "lng": 77.2090,
        "phone": "+91 11 2336 2345",
        "service_specialty": "All Central Government Schemes, Aadhaar Seva Kendra, PM-SYM"
    },
    {
        "name": "Aadhaar Seva Kendra (DL02)",
        "type": "Aadhaar Seva Kendra",
        "address": "Akshardham Metro Station Premises, New Delhi 110092",
        "state": "Other",
        "lat": 28.6180,
        "lng": 77.2785,
        "phone": "+91 11 2201 1122",
        "service_specialty": "Aadhaar Card Enrollment & Update (Mandatory for most schemes)"
    }
]

def _unused_haversine_distance(lat1, lon1, lat2, lon2):
    R = 6371.0 # Radius of the earth in km
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def get_recommended_center_type(scheme, state):
    if not scheme:
        return "Government Service Centre (CSC)"
    
    steps_text = " ".join(scheme.get("application_steps", [])).lower()
    scheme_name = scheme.get("scheme_name", "").lower()
    
    if state == "Tamil Nadu":
        state_center = "e-Sevai Center"
    elif state == "Maharashtra":
        state_center = "Maha e-Seva Kendra"
    elif state == "Bihar":
        state_center = "Vasudha Kendra (CSC)"
    elif state == "Uttar Pradesh":
        state_center = "Jan Seva Kendra (CSC)"
    else:
        state_center = "Common Service Centre (CSC)"
        
    if "lpg" in scheme_name or "ujjwala" in scheme_name or "lpg" in steps_text:
        return "LPG Distributor / Agency"
    elif "csc" in steps_text or "common service" in steps_text:
        return state_center
    elif "panchayat" in steps_text or "block office" in steps_text or "social welfare" in steps_text:
        return f"{state_center} or Local Block/Panchayat Office"
    elif "post office" in steps_text or "bank" in steps_text or "financial" in steps_text:
        return "Post Office / Public Sector Bank"
    else:
        return state_center

def geocode_address(address):
    import os
    import logging
    from dotenv import load_dotenv
    load_dotenv()
    
    logger = logging.getLogger("geolocation_workflow")
    
    api_key = os.environ.get("GOOGLE_MAPS_API_KEY", "").strip()
    if not api_key or api_key == "your_google_maps_api_key_here":
        raise ValueError("Google Maps API key is not configured. Please set GOOGLE_MAPS_API_KEY in your environment variables/file.")
        
    url = "https://maps.googleapis.com/maps/api/geocode/json"
    params = {
        "address": address,
        "key": api_key
    }
    
    logger.info(f"Sending Google Geocoding API request for address: {address}")
    try:
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            status = data.get("status")
            if status == "OK" and data.get("results"):
                loc = data["results"][0]["geometry"]["location"]
                formatted_address = data["results"][0].get("formatted_address", address)
                logger.info(f"Geocoding successful: lat={loc['lat']}, lng={loc['lng']}, formatted_address={formatted_address}")
                return loc["lat"], loc["lng"], formatted_address
            else:
                error_message = data.get("error_message", "Geocoding failed.")
                raise Exception(f"Geocoding API returned status {status}: {error_message}")
        else:
            raise Exception(f"HTTP error {response.status_code}")
    except Exception as e:
        logger.exception("Error while geocoding address")
        raise Exception(f"Failed to geocode address: {str(e)}")

def fetch_nearby_places(lat, lng, radius=5000):
    import os
    import logging
    from dotenv import load_dotenv
    load_dotenv()
    
    logger = logging.getLogger("geolocation_workflow")
    
    api_key = os.environ.get("GOOGLE_MAPS_API_KEY", "").strip()
    if not api_key or api_key == "your_google_maps_api_key_here":
        raise ValueError("Google Maps API key is not configured. Please set GOOGLE_MAPS_API_KEY in your environment variables/file.")
        
    url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
    params = {
        "location": f"{lat},{lng}",
        "radius": radius,
        "keyword": "e-sevai center CSC citizen service center government office",
        "key": api_key
    }
    
    logger.info(f"Sending Google Places API request to {url} with parameters: location={lat},{lng}, radius={radius}")
    
    try:
        response = requests.get(url, params=params, timeout=10)
        logger.info(f"Google Places API HTTP Status Code: {response.status_code}")
        
        data = response.json()
        logger.info(f"Google Places API Full Response JSON: {data}")
        
        status = data.get("status")
        error_message = data.get("error_message", "No detailed error message provided by Google Places API.")
        
        if status == "OK":
            return data.get("results", [])
        elif status == "ZERO_RESULTS":
            return []
        elif status in ["REQUEST_DENIED", "INVALID_KEY", "API_NOT_ACTIVATED", "INVALID_REQUEST", "OVER_QUERY_LIMIT"]:
            raise Exception(f"Google Places API returned {status}: {error_message}")
        else:
            raise Exception(f"Google Places API returned status {status}: {error_message}")
            
    except requests.exceptions.RequestException as e:
        logger.exception("Network error while connecting to Google Places API")
        raise Exception(f"Network error while connecting to Google Places API: {str(e)}")

def render_nearest_centers():
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

    # Let the user type their location
    user_address = st.text_input(
        "Enter your location (e.g. area, city, pincode, or address):",
        value=st.session_state.get("page_entered_address", ""),
        key="page_entered_address_input",
        placeholder="Type location..."
    )
    
    # Input field for search query
    user_query = st.text_input(
        "Enter type of center to find (e.g. e-Sevai center, CSC center):",
        value=st.session_state.get("page_search_query", "e-Sevai center"),
        key="page_search_query_input",
        placeholder="Type center type..."
    )
    
    # Radius Selection
    radius_km = st.selectbox(
        "Select maximum search radius:",
        options=[1, 5, 10, 25, 50],
        index=1, # Default is 5 km
        format_func=lambda x: f"{x} km",
        key="page_search_radius_select"
    )
    
    col_search, col_gps, col_manual = st.columns([1.5, 1.5, 1.5])
    with col_search:
        if st.button("Search Centers", type="primary", use_container_width=True, key="page_search_btn"):
            st.session_state.page_entered_address = user_address
            st.session_state.page_search_query = user_query
            if user_address.strip():
                with st.spinner("Finding location details..."):
                    try:
                        geocode_res = geocode_address_free(user_address)
                        if geocode_res:
                            lat, lng, formatted_addr = geocode_res
                            st.session_state.user_lat = lat
                            st.session_state.user_lng = lng
                            st.session_state.location_source = formatted_addr
                            st.session_state.geo_state = "granted"
                        else:
                            st.session_state.user_lat = None
                            st.session_state.user_lng = None
                            st.session_state.location_source = user_address
                            st.session_state.geo_state = "fallback_search"
                        st.session_state.manual_location_mode = False
                        st.rerun()
                    except Exception as e:
                        st.error(f"Could not find location: {str(e)}")
            else:
                st.warning("Please enter a location.")
    with col_gps:
        if st.button("Use GPS Location", use_container_width=True, key="page_gps_btn"):
            st.session_state.geo_state = "requesting"
            st.session_state.user_lat = None
            st.session_state.user_lng = None
            st.session_state.manual_location_mode = False
            st.rerun()
    with col_manual:
        if st.button("Choose City Dropdown", use_container_width=True, key="page_manual_btn"):
            st.session_state.manual_location_mode = True
            st.session_state.geo_state = "manual"
            st.rerun()

    if st.session_state.geo_state == "requesting" and not st.session_state.manual_location_mode:
        geo_html = """
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: sans-serif; background: transparent; margin: 0; padding: 10px; }}
                #debug-box {{ border: 1px solid #ccc; padding: 10px; border-radius: 8px; font-size: 13px; background: #f8fafc; display: none; }}
            </style>
        </head>
        <body>
            <div id="debug-box">
                <span id="d-res">Waiting...</span>
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
                        console.error(e);
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
        """
        components.html(geo_html, height=0)
        
    st.markdown("""
    <style>
        div[data-testid="stHorizontalBlock"] > div:has(input[placeholder="geo_lat"]),
        div[data-testid="stHorizontalBlock"] > div:has(input[placeholder="geo_lng"]),
        div[data-testid="stHorizontalBlock"] > div:has(input[placeholder="geo_err"]) {
            display: none !important;
        }
    </style>
    """, unsafe_allow_html=True)

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
            st.session_state.location_source = "GPS Coordinates"
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
    elif st.session_state.geo_state != "granted" and st.session_state.geo_state != "fallback_search":
        st.write("")
        if st.session_state.geo_state != "requesting" and st.session_state.geo_state != "pending_input":
            if "denied" in str(st.session_state.geo_state).lower() or "permission" in str(st.session_state.geo_state).lower():
                st.warning("⚠️ Location permission was denied. Please enter your location in the search box above, or select manually.")
            else:
                st.markdown(f"<p style='color:#ef4444; font-weight:600;'>{st.session_state.geo_state if st.session_state.geo_state != 'manual' else 'Location undetected.'}</p>", unsafe_allow_html=True)
            col_retry, col_manual = st.columns([1, 1])
            with col_retry:
                if st.button("Retry Location", use_container_width=True, key="page_retry_btn"):
                    st.session_state.geo_state = "requesting"
                    st.rerun()
            with col_manual:
                if st.button("Choose Location Manually", use_container_width=True, key="page_choose_man_btn"):
                    st.session_state.manual_location_mode = True
                    st.session_state.geo_state = "manual"
                    st.rerun()

    if (st.session_state.geo_state == "requesting" or st.session_state.geo_state == "pending_input") and not st.session_state.manual_location_mode:
        col_back, _ = st.columns([1.5, 2.5])
        with col_back:
            if st.button(t("btn_back_details"), type="secondary", use_container_width=True, key="page_back_btn"):
                st.session_state.step = 5
                st.rerun()
        return

    # Handle direct database fallback query rendering
    if st.session_state.geo_state == "fallback_search":
        # Output a clear error message as geocoding failed
        st.error("❌ Invalid location: We could not resolve coordinates for this address. Please try a different address (e.g. city or state).")
        st.write("---")
        col_back, _ = st.columns([1.5, 2.5])
        with col_back:
            if st.button(t("btn_back_details"), type="secondary", use_container_width=True, key="back_fallback_centers"):
                st.session_state.step = 5
                st.rerun()
        return

    user_lat = st.session_state.get("user_lat")
    user_lng = st.session_state.get("user_lng")
    # noqa: F841 loc_source = st.session_state.get("location_source", "GPS")
    
    if user_lat is None or user_lng is None:
        return

    # Nominatim Reverse Geocoding
    if "address_dict" not in st.session_state or st.session_state.get("last_geo_lat") != user_lat:
        st.session_state.address_dict = osm_api.get_address_from_coords(user_lat, user_lng)
        st.session_state.last_geo_lat = user_lat

    addr = st.session_state.get("address_dict", {})
    # noqa: F841 area = addr.get("suburb", addr.get("neighbourhood", addr.get("road", "")))
    # noqa: F841 city = addr.get("city", addr.get("town", addr.get("village", "")))
    # noqa: F841 district = addr.get("state_district", addr.get("county", ""))
    state = addr.get("state", "")
    
    # Retrieve the custom query entered by the user
    search_query_val = st.session_state.get("page_search_query", "e-Sevai center")
    if not search_query_val.strip():
        search_query_val = "e-Sevai center"
        
    try:
        api_key = os.environ.get("GOOGLE_MAPS_API_KEY")
        if not api_key:
            st.error("❌ Google Maps API Key is missing from the environment. Please check your .env configuration.")
            nearby_centers = []
        else:
            radius_meters = float(radius_km) * 1000.0
            nearby_centers = fetch_places_new(user_lat, user_lng, search_query_val, api_key, radius_meters=radius_meters)
    except Exception as e:
        logger.exception(f"Error calling fetch_places_new: {str(e)}")
        st.error(f"⚠️ Error loading nearby application centers: {str(e)}")
        col_back, _ = st.columns([1.5, 2.5])
        with col_back:
            if st.button(t("btn_back_details"), type="secondary", use_container_width=True, key="back_err_centers"):
                st.session_state.step = 5
                st.rerun()
        return

    if not nearby_centers:
        st.write("")
        st.warning(f"⚠️ No '{search_query_val}' centers were found within {radius_km} km of this location. Try increasing the search radius or changing the search query.")
        col_back, _ = st.columns([1.5, 2.5])
        with col_back:
            if st.button(t("btn_back_details"), type="secondary", use_container_width=True, key="back_no_centers"):
                st.session_state.step = 5
                st.rerun()
        return

    rec_type = get_recommended_center_type(scheme, st.session_state.profile.get("State", "Other"))
    st.write("")
    st.markdown(f"<div class='premium-card' style='background: #f0fdf4; border: 1px solid #99f6e4; padding: 1rem; margin-bottom: 1.5rem;'><strong>💡 Recommended Service Point:</strong> <span style='color:#0d9488; font-weight:700;'>{rec_type}</span></div>", unsafe_allow_html=True)
    
    import urllib.parse
    for idx, c in enumerate(nearby_centers):
        if idx == 0:
            # Highlight nearest center
            bg_style = "background: linear-gradient(135deg, #f0fdf4 0%, #ffffff 100%); border: 2px solid #059669; box-shadow: 0 10px 15px -3px rgba(5, 150, 105, 0.1);"
            badge_html = "<span style='color:#059669; font-weight:700; font-size:0.9rem; background:#d1fae5; padding:4px 8px; border-radius:8px; display:inline-block; margin-bottom: 0.5rem;'>⭐ Nearest Center</span>"
            st.markdown("<h3 style='color:#0f172a; font-weight:800; margin-bottom:1rem;'>🏢 Nearest Application Center</h3>", unsafe_allow_html=True)
        else:
            if idx == 1:
                st.markdown(f"<h3 style='color:#1e293b; font-weight:800; margin-top:2rem; margin-bottom:1rem;'>📍 Other Nearby Centers (within {radius_km} km)</h3>", unsafe_allow_html=True)
            bg_style = "background: #ffffff; border: 1px solid #e2e8f0; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);"
            badge_html = ""
            
        st.markdown(f"""
        <div class="premium-card" style="{bg_style} padding: 1.25rem; margin-bottom: 1rem; border-radius: 12px;">
            <div style="display: flex; justify-content: space-between; align-items: start; flex-wrap: wrap; gap: 8px;">
                <div>
                    <h4 style="margin: 0 0 0.25rem 0; font-size: 1.15rem; color: #0f172a; font-weight: 700;">{c['name']}</h4>
                    {badge_html}
                </div>
                <div style="text-align: right;">
                    <span style="font-weight: 700; color: #0d9488; font-size: 0.95rem; background: #e6f4ea; padding: 6px 12px; border-radius: 8px; display: inline-block;">Distance: {c['distance']:.2f} km</span>
                </div>
            </div>
            <div style="color: #475569; font-size: 0.95rem; margin-top: 8px; line-height: 1.5;">
                <b>Address:</b> {c['address']}<br>
                <b>Latitude:</b> {c['lat']}<br>
                <b>Longitude:</b> {c['lng']}<br>
                <b>District:</b> {c['district']}<br>
                <b>State:</b> {c['state']}<br>
                <b>Available Services:</b> <span style="color: #0f766e;">{c['services']}</span>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        query_str = urllib.parse.quote(f"{c['name']}, {c['address']}")
        st.link_button("Open in Google Maps", f"https://www.google.com/maps/search/?api=1&query={query_str}", use_container_width=True, key=f"btn_map_{idx}")
        st.write("")

    st.write("---")
    col_back, _ = st.columns([1.5, 2.5])
    with col_back:
        if st.button(t("btn_back_details"), type="secondary", use_container_width=True, key="back_final_centers"):
            st.session_state.step = 5
            st.rerun()
    st.write("")

def main():
    setup_page()
    init_session()
    import time
    if st.session_state.get("search_rate_limited_until", 0.0) <= time.time():
        st.session_state.search_rate_limited = False
    if st.session_state.get("ai_rate_limited_until", 0.0) <= time.time():
        st.session_state.ai_rate_limited = False
    if st.session_state.step == 1:
        render_home()
    elif st.session_state.step == 2:
        render_input()
    elif st.session_state.step == 3:
        render_processing()
    elif st.session_state.step == 4:
        render_results()
    elif st.session_state.step == 5:
        render_detail()
    elif st.session_state.step == 6:
        render_no_match()
    elif st.session_state.step == 7:
        render_nearest_centers()
    elif st.session_state.step == 8:
        render_browse_schemes()

if __name__ == "__main__":
    main()