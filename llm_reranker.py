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
from typing import List, Dict, Any, Optional

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
        genai.configure(api_key=api_key)
        _model_instance = genai.GenerativeModel("gemini-2.0-flash")
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
                profile_lines.append(f"  - {label}: {str(val).capitalize()}")
        else:
            profile_lines.append(f"  - {label}: Not provided")

    profile_text = "\n".join(profile_lines)

    # Format candidate schemes
    scheme_entries = []
    for i, candidate in enumerate(candidates):
        scheme = candidate.get("scheme", candidate)
        entry = f"""  Scheme {i+1}: "{scheme.get('scheme_name', 'Unknown')}"
    - Category: {scheme.get('category', 'N/A')}
    - Eligibility: {scheme.get('eligibility_criteria', 'N/A')}
    - Benefit: {scheme.get('benefit_summary', 'N/A')}
    - Income Limit: ₹{scheme.get('income_limit', 'N/A')}
    - Age Range: {scheme.get('age_limit', {}).get('min', 'N/A')}-{scheme.get('age_limit', {}).get('max', 'N/A')} years
    - Target Gender: {', '.join(scheme.get('gender', ['any']))}
    - Target State: {', '.join(scheme.get('state', ['all']))}
    - Target Occupation: {', '.join(scheme.get('occupation', ['any']))}"""
        scheme_entries.append(entry)

    schemes_text = "\n\n".join(scheme_entries)

    prompt = f"""You are an expert on Indian government welfare schemes. Your task is to evaluate how relevant each candidate scheme is for a specific citizen's profile.

USER PROFILE:
{profile_text}

CANDIDATE SCHEMES:
{schemes_text}

TASK:
For each scheme, provide:
1. A relevance score from 0 to 100 (where 100 = perfect match for this user).
2. A brief 1-sentence explanation of why the scheme is or isn't relevant.

SCORING GUIDELINES:
- Score 80-100: User clearly meets all or most eligibility criteria and would benefit significantly.
- Score 50-79: User meets some criteria but may have partial mismatches or the benefit is moderately relevant.
- Score 20-49: User has significant mismatches but the scheme might still be tangentially relevant.
- Score 0-19: User clearly does not meet key eligibility requirements.

Consider:
- Whether the user's income, age, gender, state, and occupation match the scheme's requirements.
- How much the user would realistically benefit from this scheme.
- Partial matches where information is missing (be generous with missing fields).

RESPOND WITH ONLY a valid JSON array, no other text:
[
  {{"scheme_index": 0, "llm_score": <0-100>, "explanation": "<brief reason>"}},
  ...
]"""

    return prompt


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
    # Graceful fallback: if no model available, return candidates with default scores
    model = _get_model()
    if model is None:
        logger.info("LLM re-ranking skipped (no API key or model unavailable).")
        for candidate in candidates:
            candidate["llm_score"] = 50
            candidate["llm_explanation"] = "LLM re-ranking unavailable"
        return candidates

    try:
        prompt = _build_prompt(profile, candidates)

        # Call Gemini with safety settings relaxed for factual content
        response = model.generate_content(
            prompt,
            generation_config={
                "temperature": 0.1,  # Low temperature for consistent scoring
                "max_output_tokens": 2048,
                "response_mime_type": "application/json"
            }
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
        return candidates

    except json.JSONDecodeError as e:
        logger.warning(f"LLM response was not valid JSON: {e}")
    except Exception as e:
        logger.warning(f"LLM re-ranking failed: {e}")

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
