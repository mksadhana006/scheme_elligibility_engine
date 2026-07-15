"""
search_api.py

Web Search Integration for the Adhikaar Scheme Recommendation Engine.

This module uses the Google Custom Search JSON API to fetch newly announced
government schemes or verify scheme details from official sources. Results
supplement the core matching engine (they don't replace it).

The search focuses on official government domains:
- india.gov.in, myscheme.gov.in, pib.gov.in, pmindia.gov.in

AI Concepts:
1. Information Retrieval: Querying external knowledge bases.
2. Query Expansion: Building search queries from structured user profiles.
3. Result Filtering: Extracting relevant snippets from web results.
"""

import os
import logging
import json
from typing import List, Dict, Any, Optional

import requests
from api_utils import execute_with_retry_and_backoff, get_cached_response, cache_response

logger = logging.getLogger(__name__)


def _get_search_credentials() -> tuple:
    """Get Google Custom Search API key and CX from environment."""
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    api_key = os.environ.get("GOOGLE_SEARCH_API_KEY", "").strip()
    cx = os.environ.get("GOOGLE_SEARCH_CX", "").strip()

    if api_key and api_key != "your_google_search_api_key_here" and cx and cx != "your_custom_search_engine_id_here":
        return api_key, cx
    return None, None


def _build_search_query(profile: Dict[str, Any]) -> str:
    """
    Build a targeted search query from the user's profile.
    
    The query is designed to find government schemes relevant to the user's
    demographic. We include key attributes that are most likely to match
    scheme eligibility criteria.
    """
    parts = ["Indian government scheme 2024 2025"]

    if profile.get("gender"):
        parts.append(profile["gender"])

    if profile.get("marital_status") and profile["marital_status"] != "any":
        parts.append(profile["marital_status"])

    if profile.get("occupation") and profile["occupation"] != "any":
        parts.append(profile["occupation"])

    if profile.get("state") and profile["state"] not in ("other", "all"):
        parts.append(profile["state"])

    if profile.get("age"):
        try:
            age = int(profile["age"])
            if age >= 60:
                parts.append("senior citizen elderly")
            elif age <= 25:
                parts.append("youth student")
        except (ValueError, TypeError):
            pass

    if profile.get("income"):
        try:
            income = float(profile["income"])
            if income <= 150000:
                parts.append("BPL low income poor")
        except (ValueError, TypeError):
            pass

    return " ".join(parts)


def _make_search_request(url: str, params: Dict[str, Any], timeout: int) -> Dict[str, Any]:
    """Helper to perform HTTP search request and raise for errors."""
    response = requests.get(url, params=params, timeout=timeout)
    response.raise_for_status()
    return response.json()


def _get_local_fallback_recommendations(profile: Dict[str, Any], max_results: int) -> List[Dict[str, Any]]:
    """Retrieve recommendations from local schemes.json if search API is rate-limited."""
    try:
        from logic import get_top_matches
        
        # Load local schemes
        schemes_path = os.path.join(os.path.dirname(__file__), "schemes.json")
        with open(schemes_path, "r", encoding="utf-8") as f:
            schemes_data = json.load(f)
            
        # Get top matches using local rule-based + semantic pipeline
        # Pass empty user_text to skip any external API calls inside semantic retrieval
        results = get_top_matches(profile, schemes_data, top_n=max_results, user_text="")
        
        fallback_results = []
        for r in results:
            fallback_results.append({
                "title": r.get("scheme_name", ""),
                "snippet": r.get("benefit_summary", "") or r.get("category", ""),
                "link": r.get("official_apply_link", "#"),
                "source": "Local Database"
            })
        logger.info(f"Generated {len(fallback_results)} local fallback recommendations.")
        return fallback_results
    except Exception as e:
        logger.warning(f"Failed to generate local search fallback recommendations: {e}")
        return []


def fetch_new_schemes(
    profile: Dict[str, Any],
    max_results: int = 5,
    timeout: int = 8
) -> List[Dict[str, Any]]:
    """
    Search the web for newly announced government schemes matching the user's profile.
    
    Args:
        profile: Normalized user profile.
        max_results: Maximum number of results to return.
        timeout: HTTP request timeout in seconds.
        
    Returns:
        List of dicts with 'title', 'snippet', 'link' for each result.
        Returns empty list if the API is not configured or the call fails.
    """
    # 1. Check cache first to avoid duplicate requests
    cached = get_cached_response("fetch_new_schemes", profile, max_results)
    if cached is not None:
        logger.info("Serving search results from cache.")
        return cached

    # 2. Check if currently marked as rate-limited to avoid spamming the API
    try:
        import streamlit as st
        if hasattr(st, "session_state") and st.session_state.get("search_rate_limited", False):
            logger.info("Search API is currently rate-limited. Skipping API call and using local fallback.")
            return _get_local_fallback_recommendations(profile, max_results)
    except Exception:
        pass

    api_key, cx = _get_search_credentials()
    if not api_key or not cx:
        logger.info("Google Search API not configured. Skipping web search.")
        return []

    query = _build_search_query(profile)

    url = "https://www.googleapis.com/customsearch/v1"
    params = {
        "key": api_key,
        "cx": cx,
        "q": query,
        "num": min(max_results, 10),  # API max is 10 per request
        "dateRestrict": "y1",  # Results from last 1 year
        "lr": "lang_en",
        "safe": "active"
    }

    try:
        # 3. Call search API with retry and backoff wrapper
        data = execute_with_retry_and_backoff(
            _make_search_request,
            args=(url, params, timeout),
            kwargs={},
            api_name="Google Search API"
        )

        results = []
        for item in data.get("items", []):
            results.append({
                "title": item.get("title", ""),
                "snippet": item.get("snippet", ""),
                "link": item.get("link", ""),
                "source": item.get("displayLink", "")
            })

        logger.info(f"Web search returned {len(results)} results for query: {query[:80]}...")
        
        # 4. Cache successful responses
        cache_response("fetch_new_schemes", results, profile, max_results)
        return results

    except Exception as e:
        is_rate_limit = False
        error_msg = str(e)
        if hasattr(e, 'response') and e.response is not None:
            if getattr(e.response, 'status_code', None) == 429:
                is_rate_limit = True
        elif "429" in error_msg:
            is_rate_limit = True

        if is_rate_limit:
            logger.error("Google Search API rate limit exceeded. Falling back to local schemes.json database.")
            try:
                import streamlit as st
                if hasattr(st, "session_state"):
                    st.session_state.search_rate_limited = True
            except Exception:
                pass
            return _get_local_fallback_recommendations(profile, max_results)
        else:
            logger.warning(f"Google Search API call failed with error: {e}")
            return []


def is_available() -> bool:
    """Check if the Google Search API is configured."""
    api_key, cx = _get_search_credentials()
    return api_key is not None and cx is not None


if __name__ == "__main__":
    print(f"Search API available: {is_available()}")

    if is_available():
        test_profile = {
            "gender": "female",
            "marital_status": "widow",
            "income": 100000,
            "state": "bihar"
        }
        results = fetch_new_schemes(test_profile)
        print(f"\nFound {len(results)} web results:")
        for r in results:
            print(f"  - {r['title']}")
            print(f"    {r['snippet'][:100]}...")
            print(f"    {r['link']}")
    else:
        print("Set GOOGLE_SEARCH_API_KEY and GOOGLE_SEARCH_CX in .env to enable.")
