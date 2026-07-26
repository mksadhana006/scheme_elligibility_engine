"""
logic.py

Hybrid AI Recommendation Engine for the Adhikaar Scheme Eligibility Platform.

This module has been re-architected to be purely Gemini-driven.
It relies exclusively on the Google Gemini API to analyze the user profile and return
relevant government schemes.
"""

import json
import logging

logger = logging.getLogger(__name__)

def normalize_profile(profile):
    """
    Normalize user profile data for matching logic.
    Handles string-to-number conversion, currency normalization, etc.
    """
    p = {}
    for k, v in profile.items():
        if v is None or str(v).strip() == "":
            p[k] = None
        else:
            if isinstance(v, str):
                p[k] = v.lower().strip()
            else:
                p[k] = v
                
    # Normalize state
    if 'state' in p and p['state']:
        state_str = str(p['state']).lower().strip()
        if state_str in ["tamil nadu", "tamilnadu", "tn"]:
            p['state'] = "tamil nadu"
        elif state_str in ["bihar"]:
            p['state'] = "bihar"
        elif state_str in ["maharashtra"]:
            p['state'] = "maharashtra"
        elif state_str in ["uttar pradesh", "up"]:
            p['state'] = "uttar pradesh"
        else:
            p['state'] = state_str
                
    # Normalize income
    if 'income' in p and p['income']:
        try:
            if isinstance(p['income'], str):
                val = p['income'].replace(',', '').replace('₹', '').replace('rs', '').strip()
                if 'lakh' in val:
                    num = float(val.replace('lakh', '').strip())
                    p['income'] = int(num * 100000)
                else:
                    p['income'] = float(val)
            else:
                p['income'] = float(p['income'])
        except ValueError:
            p['income'] = None

    # Normalize age
    if 'age' in p and p['age']:
        try:
            p['age'] = int(p['age'])
        except ValueError:
            p['age'] = None

    # Handle widow_status derived from marital_status
    if p.get('marital_status') == 'widow':
        p['widow_status'] = True
    elif p.get('widow_status') in ['true', 'yes', True, '1']:
        p['marital_status'] = 'widow'
        
    return p

def get_top_matches(user_profile, top_n=15, user_text=""):
    """
    Get the top matching schemes using ONLY the Google Gemini API.
    
    Args:
        user_profile: Dict with user's profile fields.
        top_n: Maximum number of results to return.
        user_text: Raw text the user typed/spoke.
        
    Returns:
        List of scored scheme dicts, sorted by match_score descending.
    """
    try:
        from scheme_elligibility_engine.api_utils import generate_content_with_cascade
    except ImportError:
        from api_utils import generate_content_with_cascade

    # 1. Clean and normalize profile
    normalized_profile = normalize_profile(user_profile)
    
    # Log User profile
    logger.info(f"[1] User profile received: {normalized_profile} | Context: {user_text}")
    print(f"[1] User profile received: {normalized_profile} | Context: {user_text}")
    
    # 2. Formulate User Profile details
    profile_items = []
    for k, v in normalized_profile.items():
        if v is not None and str(v).strip() != "":
            label = k.replace("_", " ").title()
            profile_items.append(f"{label}: {v}")
    if user_text:
        profile_items.append(f"Additional Profile Context (such as caste/category, land ownership, disability, student status, etc.): {user_text}")
    user_profile_str = "\n".join(profile_items)

    # 3. Formulate prompt for Gemini
    prompt = f"""You are an expert on Government of India welfare schemes.
Given the following user profile, identify the government schemes (State or Central) that the user is genuinely eligible for based on their demographics.

USER PROFILE:
{user_profile_str}

TASK:
Analyze the complete user profile against the eligibility criteria of real Indian government schemes.
Identify which schemes the user is eligible for and satisfies all criteria.

STRICT MATCHING RULES:
1. You must consider all relevant profile fields (Gender, Age, Income, State, Occupation, Marital Status).
2. If a scheme is restricted to specific categories (e.g. only for women, students, senior citizens, farmers, or disabled persons), the user profile MUST explicitly satisfy those requirements. Do not match a scheme merely because the user's category matches if other criteria (like gender, age, income, state) are violated.
3. Every returned scheme MUST be a real, factual government scheme currently active in India. Do not invent/hallucinate any scheme names or details. Do not fabricate application URLs.
4. If you are uncertain or if the user profile violates a requirement, do not include that scheme.
5. If there are NO schemes that fit this profile, you must return a status of "no_match".

OUTPUT FORMAT:
Respond ONLY with a valid JSON object matching the schema below. Do not wrap the response in markdown blocks like ```json or any other text.

If there are matching schemes:
{{
  "status": "success",
  "matched_schemes": [
    {{
      "scheme_name": "Scheme Name",
      "eligibility_status": "Eligible",
      "match_score": 100,
      "reason": "Why the user qualifies",
      "matched_criteria": [
        "..."
      ],
      "unmatched_criteria": [
        "..."
      ],
      "official_source": "https://...",
      "required_documents": ["Document 1", "Document 2"],
      "benefit_summary": "Summary of what the scheme provides",
      "application_steps": ["Step 1", "Step 2"],
      "category": "e.g. Agriculture, Education, Health"
    }}
  ]
}}

If there are no genuinely matching schemes:
{{
  "status": "no_match",
  "matched_schemes": [],
  "message": "No matching government schemes were found for your profile."
}}

Ensure valid JSON structure.
"""

    logger.info("[2] Gemini API request started")
    print("[2] Gemini API request started")

    # 4. Call Gemini API via the cascade helper
    try:
        response = generate_content_with_cascade(
            prompt,
            generation_config={
                "temperature": 0.1,
                "response_mime_type": "application/json"
            },
            api_name="Gemini Eligibility Engine API"
        )
        response_text = response.text.strip()
        
        logger.info("[3] Gemini API response received")
        print("[3] Gemini API response received")
        
        # Scrub markdown wrappers if any
        if response_text.startswith("```"):
            lines = response_text.split("\n")
            if lines[0].startswith("```json") or lines[0].startswith("```"):
                response_text = "\n".join(lines[1:-1])
                
        gemini_response = json.loads(response_text)
    except Exception as e:
        logger.error(f"[ERROR] Gemini API request failed: {e}")
        print(f"[ERROR] Gemini API request failed: {e}")
        raise RuntimeError(f"Gemini API request failed: {e}")

    status = gemini_response.get("status", "success")
    gemini_results = gemini_response.get("matched_schemes", [])

    logger.info(f"[4] Number of schemes returned by Gemini: {len(gemini_results)}")
    print(f"[4] Number of schemes returned by Gemini: {len(gemini_results)}")

    if status == "no_match" or not gemini_results:
        logger.info("[5] Gemini returned zero matches.")
        print("[5] Gemini returned zero matches.")
        return []

    matched_names = [s.get("scheme_name", "Unknown") for s in gemini_results]
    logger.info(f"[5] Gemini returned matching schemes: {matched_names}")
    print(f"[5] Gemini returned matching schemes: {matched_names}")

    # 5. Post-process matched results to match UI structure
    results = []
    for g_res in gemini_results:
        # Prevent hallucinated status
        if g_res.get("eligibility_status") != "Eligible":
            continue
            
        matched_criteria = g_res.get("matched_criteria", [])
        unmatched_criteria = g_res.get("unmatched_criteria", [])
        reason = g_res.get("reason", "")
        
        why_matched = []
        if reason:
            why_matched.append(f"AI Eligibility Check: {reason}")
        why_matched.extend(matched_criteria)
        
        why_not_matched = list(unmatched_criteria)
        
        score = g_res.get("match_score", 100)
        
        # Build UI-compatible structured item
        results.append({
            "scheme_name": g_res.get("scheme_name", "Unknown Scheme"),
            "match_status": "Full Match",
            "match_score": score,
            "why_matched": why_matched,
            "why_not_matched": why_not_matched,
            "missing_fields": [],
            "required_documents": g_res.get("required_documents", []),
            "official_apply_link": g_res.get("official_source", ""),
            "benefit_summary": g_res.get("benefit_summary", ""),
            "application_steps": g_res.get("application_steps", []),
            "category": g_res.get("category", ""),
            "has_hard_block": False,
            "xai_breakdown": {
                "ai_eligibility_matching": "Decision verified contextually by Gemini API"
            }
        })
        
    # Rank results by score descending
    results = sorted(results, key=lambda x: x['match_score'], reverse=True)
    return results[:top_n]
