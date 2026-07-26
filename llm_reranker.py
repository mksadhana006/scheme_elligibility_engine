"""
llm_reranker.py

LLM-Powered Re-Ranking Module for the Adhikaar Scheme Recommendation Engine.

This module uses Google Gemini to intelligently re-rank candidate schemes
based on the user's specific profile and situation. The LLM evaluates 
contextual fit that neither keyword matching nor rule engines can capture.

AI Concepts:
1. LLM-as-a-Judge: Using an LLM to evaluate relevance of retrieved candidates.
2. Prompt Engineering: Carefully structured prompts that produce parseable JSON.
3. Re-Ranking: A second-pass ranking that refines initial retrieval results.
4. Graceful Degradation: Falls back silently if the API is unavailable.
"""

import os
import json
import logging
import copy
from typing import List, Dict, Any, Optional
from api_utils import execute_with_retry_and_backoff, get_cached_response, cache_response

logger = logging.getLogger(__name__)

# Lazy import for google.generativeai
_genai = None
_model_instance = None


def _get_genai():
    """Lazy-load google.generativeai."""
    global _genai
    if _genai is None:
        try:
            import google.generativeai as genai
            _genai = genai
        except ImportError:
            logger.warning("google-generativeai not installed. LLM re-ranking disabled.")
            _genai = False  # Sentinel to avoid retrying
    return _genai if _genai is not False else None


def _get_api_key() -> Optional[str]:
    """Get Gemini API key from environment."""
    # Try .env file first
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if key and key != "your_gemini_api_key_here":
        return key
    return None


def _get_model():
    """Get or create the Gemini model instance."""
    global _model_instance
    if _model_instance is not None:
        return _model_instance

    genai = _get_genai()
    if genai is None:
        return None

    api_key = _get_api_key()
    if not api_key:
        logger.info("No GEMINI_API_KEY found. LLM re-ranking will be skipped.")
        return None

    try:
        genai.configure(api_key=api_key, transport="rest")
        _model_instance = genai.GenerativeModel("gemini-3.5-flash")
        return _model_instance
    except Exception as e:
        logger.error(f"Failed to initialize Gemini model: {e}")
        return None


def _build_prompt(profile: Dict[str, Any], candidates: List[Dict[str, Any]]) -> str:
    """
    Build a carefully structured prompt for the LLM re-ranker.
    
    The prompt includes:
    1. Clear role and task description.
    2. The user's profile in a readable format.
    3. Each candidate scheme with its details.
    4. Explicit output format instructions (JSON).
    """
    # Format the user profile
    profile_lines = []
    field_labels = {
        "gender": "Gender",
        "age": "Age",
        "income": "Annual Income (₹)",
        "state": "State",
        "occupation": "Occupation",
        "marital_status": "Marital Status"
    }
    for key, label in field_labels.items():
        val = profile.get(key)
        if val is not None:
            if key == "income":
                try:
                    profile_lines.append(f"  - {label}: ₹{float(val):,.0f}")
                except (ValueError, TypeError):
                    profile_lines.append(f"  - {label}: {val}")
            else:
                profile_lines.append(f"  - {label}: {str(val).title()}")
        else:
            profile_lines.append(f"  - {label}: Not specified")

    profile_text = "\n".join(profile_lines)

    # Format candidate schemes with system rules calculation comments
    scheme_entries = []
    for i, candidate in enumerate(candidates):
        scheme = candidate.get("scheme", candidate)
        
        # Calculate rules to pass to Gemini
        from logic import calculate_rule_score
        rule_score, has_hard_block, why_matched, why_not_matched, missing_fields = calculate_rule_score(profile, scheme)
        
        eligibility_notes = []
        if why_matched:
            eligibility_notes.append("Satisfied requirements: " + ", ".join(why_matched))
        if why_not_matched:
            eligibility_notes.append("Mismatches/Violations: " + ", ".join(why_not_matched))
        if missing_fields:
            eligibility_notes.append("Missing fields: " + ", ".join(missing_fields))
        eligibility_info = "; ".join(eligibility_notes)
        
        entry = f"""  Scheme {i+1}: "{scheme.get('scheme_name', 'Unknown')}"
    - Category: {scheme.get('category', 'N/A')}
    - Eligibility Criteria: {scheme.get('eligibility_criteria', 'N/A')}
    - Benefit Summary: {scheme.get('benefit_summary', 'N/A')}
    - Income Limit: ₹{scheme.get('income_limit', 'N/A')}
    - Age Range: {scheme.get('age_limit', {}).get('min', 'N/A')}-{scheme.get('age_limit', {}).get('max', 'N/A')} years
    - Target Gender: {', '.join(scheme.get('gender', ['any']))}
    - Target State: {', '.join(scheme.get('state', ['all']))}
    - Target Occupation: {', '.join(scheme.get('occupation', ['any']))}
    - System Eligibility Rules: Score {rule_score}%, Hard Blocked? {'Yes' if has_hard_block else 'No'}. {eligibility_info}"""
        scheme_entries.append(entry)

    schemes_text = "\n\n".join(scheme_entries)

    prompt = f"""You are an expert on Indian government welfare schemes. Your task is to evaluate and re-rank candidate schemes for a specific citizen's profile.

USER PROFILE:
{profile_text}

CANDIDATE SCHEMES:
{schemes_text}

TASK:
Re-rank and score each candidate scheme on a scale of 0 to 100 based on actual relevance and eligibility.

STRICT INSTRUCTIONS:
1. Return only schemes that are relevant to the user's profile and for which the user satisfies the mandatory eligibility requirements.
2. Do not recommend unrelated schemes. Do not infer eligibility when mandatory information is missing.
3. Prioritize schemes matching the user's occupation, category, needs, and location.
4. If a scheme is hard blocked or has critical mismatches, score it extremely low (0-10).
5. Output ONLY a valid JSON array, no conversational text or markdown wrappers:
[
  {{"scheme_index": 0, "llm_score": <0-100>, "explanation": "<1-sentence reason matching profile>"}},
  ...
]"""

    return prompt


def _call_gemini_api(model, prompt) -> Any:
    """Helper to perform the Gemini content generation call."""
    return model.generate_content(
        prompt,
        generation_config={
            "temperature": 0.1,  # Low temperature for consistent scoring
            "max_output_tokens": 2048,
            "response_mime_type": "application/json"
        }
    )


def rerank_schemes(
    profile: Dict[str, Any],
    candidates: List[Dict[str, Any]],
    timeout: int = 15
) -> List[Dict[str, Any]]:
    """
    Re-rank candidate schemes using Google Gemini LLM.
    
    Args:
        profile: Normalized user profile.
        candidates: List of candidate scheme dicts (from semantic search + rule scoring).
        timeout: Request timeout in seconds.
        
    Returns:
        The same candidates list, enriched with 'llm_score' and 'llm_explanation' fields.
        If the LLM call fails, returns candidates with default llm_score of 50.
    """
    # 1. Check cache first
    cached = get_cached_response("rerank_schemes", profile, candidates)
    if cached is not None:
        logger.info("Serving LLM re-ranking from cache.")
        return copy.deepcopy(cached)

    # 2. Check if currently marked as rate-limited to avoid API spam
    try:
        import streamlit as st
        import time
        if hasattr(st, "session_state"):
            if st.session_state.get("ai_rate_limited_until", 0.0) > time.time():
                logger.info("Gemini AI API is currently rate-limited. Skipping API call and using local fallback (default scores).")
                for candidate in candidates:
                    candidate["llm_score"] = 50
                    candidate["llm_explanation"] = "LLM re-ranking unavailable"
                return candidates
            else:
                st.session_state.ai_rate_limited = False
    except Exception:
        pass

    # 3. Check if key is available
    if not _get_api_key():
        logger.info("LLM re-ranking skipped (no API key or model unavailable).")
        for candidate in candidates:
            candidate["llm_score"] = 50
            candidate["llm_explanation"] = "LLM re-ranking unavailable"
        return candidates

    try:
        prompt = _build_prompt(profile, candidates)

        # 4. Call Gemini via the model cascade helper
        from api_utils import generate_content_with_cascade
        response = generate_content_with_cascade(
            prompt,
            generation_config={
                "temperature": 0.1,
                "max_output_tokens": 2048,
                "response_mime_type": "application/json"
            },
            api_name="Gemini AI API"
        )

        # Parse the JSON response
        response_text = response.text.strip()

        # Handle potential markdown code blocks in response
        if response_text.startswith("```"):
            lines = response_text.split("\n")
            response_text = "\n".join(lines[1:-1])

        llm_results = json.loads(response_text)

        # Merge LLM scores back into candidates
        score_map = {}
        for result in llm_results:
            idx = result.get("scheme_index", -1)
            score_map[idx] = {
                "llm_score": max(0, min(100, int(result.get("llm_score", 50)))),
                "llm_explanation": result.get("explanation", "")
            }

        for i, candidate in enumerate(candidates):
            if i in score_map:
                candidate["llm_score"] = score_map[i]["llm_score"]
                candidate["llm_explanation"] = score_map[i]["llm_explanation"]
            else:
                candidate["llm_score"] = 50
                candidate["llm_explanation"] = "Not evaluated by LLM"

        logger.info(f"LLM re-ranking completed for {len(candidates)} candidates.")
        
        # 5. Cache successful responses
        cache_response("rerank_schemes", candidates, profile, candidates)
        return candidates

    except Exception as e:
        is_rate_limit = False
        error_msg = str(e)
        exc_type_name = type(e).__name__
        if any(term in exc_type_name for term in ["ResourceExhausted", "TooManyRequests", "QuotaExceeded"]) or "429" in error_msg:
            is_rate_limit = True

        if is_rate_limit:
            logger.error("Gemini AI API rate limit exceeded. Falling back to local default scores.")
            try:
                import streamlit as st
                import time
                if hasattr(st, "session_state"):
                    st.session_state.ai_rate_limited = True
                    st.session_state.ai_rate_limited_until = time.time() + 30.0
            except Exception:
                pass
        else:
            logger.warning(f"LLM re-ranking failed with error: {e}")

    # Fallback: set default scores
    for candidate in candidates:
        candidate["llm_score"] = 50
        candidate["llm_explanation"] = "LLM re-ranking unavailable"
    return candidates


def is_available() -> bool:
    """Check if LLM re-ranking is available (API key configured)."""
    return _get_api_key() is not None and _get_genai() is not None


if __name__ == "__main__":
    # Quick availability check
    print(f"Gemini API available: {is_available()}")

    if is_available():
        test_profile = {
            "gender": "female",
            "marital_status": "widow",
            "income": 100000,
            "age": 45,
            "state": "bihar",
            "occupation": "unemployed"
        }

        with open("schemes.json", "r", encoding="utf-8") as f:
            schemes = json.load(f)

        test_candidates = [{"scheme": s, "scheme_index": i} for i, s in enumerate(schemes[:3])]

        results = rerank_schemes(test_profile, test_candidates)
        for r in results:
            print(f"  LLM Score: {r['llm_score']}% - {r['scheme']['scheme_name']}")
            print(f"    Reason: {r.get('llm_explanation', 'N/A')}")
