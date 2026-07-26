"""
search_api.py

Web Search Integration for the Adhikaar Scheme Recommendation Engine.

This module uses the Tavily Search API to fetch newly announced
government schemes or verify scheme details from official sources. Results
supplement the core matching engine.

The search focuses on official government domains:
- india.gov.in, myscheme.gov.in, pib.gov.in, pmindia.gov.in, nic.in, gov.in
"""

import os
import logging
import json
from typing import List, Dict, Any, Optional

import requests
from api_utils import execute_with_retry_and_backoff, get_cached_response, cache_response

logger = logging.getLogger(__name__)


def _get_search_credentials() -> Optional[str]:
    """Get Tavily API key from environment."""
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    api_key = os.environ.get("TAVILY_API_KEY", "").strip()
    if api_key and api_key != "your_tavily_api_key_here":
        return api_key
    return None


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


def _make_tavily_request(url: str, payload: Dict[str, Any], timeout: int) -> Dict[str, Any]:
    """Helper to perform HTTP search request to Tavily and raise for errors."""
    logger.info("[DEBUG] Tavily Search API request started...")
    try:
        response = requests.post(url, json=payload, timeout=timeout)
        if response.status_code == 200:
            logger.info("[DEBUG] Tavily request status: Success (HTTP 200)")
        else:
            logger.error(f"[DEBUG] Tavily request status: Failed (HTTP {response.status_code})")
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"[DEBUG] Tavily request status: Failed ({e})")
        raise e


def _get_local_fallback_recommendations(profile: Dict[str, Any], max_results: int) -> List[Dict[str, Any]]:
    """Retrieve recommendations from local schemes fallback if search API fails."""
    try:
        from logic import get_top_matches
        
        # Load local schemes from root schemes.json or from nested folder backup
        schemes_path = os.path.join(os.path.dirname(__file__), "schemes.json")
        if not os.path.exists(schemes_path) or os.path.getsize(schemes_path) == 0:
            # Fall back to the nested directory backup schemes.json if root is empty
            schemes_path = os.path.join(os.path.dirname(__file__), "scheme_elligibility_engine", "schemes.json")
            
        if not os.path.exists(schemes_path) or os.path.getsize(schemes_path) == 0:
            logger.warning("No fallback schemes.json file found or it is empty.")
            return []
            
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


def query_tavily_search(
    query: str,
    max_results: int = 5,
    include_gov_only: bool = True,
    timeout: int = 10
) -> List[Dict[str, Any]]:
    """
    Query the Tavily Search API directly.
    """
    api_key = _get_search_credentials()
    if not api_key:
        logger.warning("Tavily API key not configured.")
        return []

    url = "https://api.tavily.com/search"
    payload = {
        "api_key": api_key,
        "query": query,
        "search_depth": "basic",
        "max_results": max_results
    }
    
    if include_gov_only:
        payload["include_domains"] = ["gov.in", "nic.in"]

    try:
        data = execute_with_retry_and_backoff(
            _make_tavily_request,
            args=(url, payload, timeout),
            kwargs={},
            api_name="Tavily Search API"
        )
        
        results = []
        for item in data.get("results", []):
            url_str = item.get("url", "")
            source = "Tavily"
            if "//" in url_str:
                parts = url_str.split("/")
                if len(parts) > 2:
                    source = parts[2]
            results.append({
                "title": item.get("title", ""),
                "snippet": item.get("content", ""),
                "link": url_str,
                "source": source
            })
        return results
    except Exception as e:
        logger.error(f"Tavily search API request failed: {e}")
        raise e


def fetch_new_schemes(
    profile: Dict[str, Any],
    max_results: int = 5,
    timeout: int = 10
) -> List[Dict[str, Any]]:
    """
    Search the web via Tavily for newly announced government schemes matching the user's profile.
    """
    # 1. Check cache first to avoid duplicate requests
    cached = get_cached_response("fetch_new_schemes", profile, max_results)
    if cached is not None:
        logger.info("Serving Tavily search results from cache.")
        return cached

    # 2. Check if currently marked as rate-limited to avoid spamming the API
    try:
        import streamlit as st
        import time
        if hasattr(st, "session_state"):
            if st.session_state.get("search_rate_limited_until", 0.0) > time.time():
                logger.info("Tavily Search API is currently rate-limited. Skipping API call and using local fallback.")
                return _get_local_fallback_recommendations(profile, max_results)
            else:
                st.session_state.search_rate_limited = False
    except Exception:
        pass

    api_key = _get_search_credentials()
    if not api_key:
        logger.info("Tavily Search API key not configured. Skipping web search.")
        return []

    query = _build_search_query(profile)

    try:
        # First try searching official government domains
        results = query_tavily_search(query, max_results=max_results, include_gov_only=True, timeout=timeout)
        
        # If no results, try general web search
        if not results:
            logger.info("Gov-only Tavily search returned empty. Trying a broader web search...")
            results = query_tavily_search(query, max_results=max_results, include_gov_only=False, timeout=timeout)

        logger.info(f"Tavily web search returned {len(results)} results for query: {query[:80]}...")
        
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
            logger.error("Tavily Search API rate limit exceeded. Falling back to local schemes database.")
            try:
                import streamlit as st
                import time
                if hasattr(st, "session_state"):
                    st.session_state.search_rate_limited = True
                    st.session_state.search_rate_limited_until = time.time() + 30.0
            except Exception:
                pass
            return _get_local_fallback_recommendations(profile, max_results)
        else:
            logger.warning(f"Tavily Search API call failed with error: {e}. Using local fallback.")
            return _get_local_fallback_recommendations(profile, max_results)


def is_available() -> bool:
    """Check if the Tavily Search API is configured."""
    return _get_search_credentials() is not None


if __name__ == "__main__":
    print(f"Tavily Search API available: {is_available()}")

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
        print("Set TAVILY_API_KEY in .env to enable.")

def browse_schemes_via_gemini(search_query: str) -> List[Dict[str, Any]]:
    """
    Search Tavily for relevant government schemes on official portals
    and parse the results with Gemini to present formatted details.
    """
    logger.info(f"Browse Schemes: Searching Tavily for query '{search_query}'")
    search_results = query_tavily_search(search_query, max_results=8, include_gov_only=True)
    
    if not search_results:
        # Try a broader search without strict domain filter if empty
        logger.info("Gov-only Tavily search returned empty. Trying a broader web search for schemes...")
        search_results = query_tavily_search(search_query, max_results=8, include_gov_only=False)
        
    if not search_results:
        logger.warning("No search results found from Tavily.")
        return []
        
    # Format search results context for Gemini
    context_parts = []
    for idx, r in enumerate(search_results):
        context_parts.append(f"Result [{idx+1}]:\nTitle: {r['title']}\nURL: {r['link']}\nSnippet: {r['snippet']}\nSource: {r['source']}\n")
    context_text = "\n".join(context_parts)
    
    prompt = f"""You are a helpful government schemes assistant. 
Your task is to analyze the web search results provided below and extract/synthesize real, verifiable government schemes matching the user's search query.

User Search Query: "{search_query}"

Web Search Results:
{context_text}

Instructions:
1. ONLY return real government schemes that are mentioned or supported by the search results. DO NOT fabricate or hallucinate any schemes.
2. If the search results do not contain enough details or are completely irrelevant to the user's query, return an empty JSON array []. Do not make up schemes.
3. For each relevant scheme identified, extract the following fields:
   - scheme_name (Name of the scheme)
   - description (Short description of what the scheme is)
   - eligibility (Eligibility criteria/who is eligible)
   - benefits (Benefits provided under the scheme)
   - application_process (Steps/how to apply)
   - source_name (Official source portal, e.g. "myScheme", "Ministry of Agriculture", state website)
   - source_url (The exact URL from the search results that verifies this scheme)

4. Return the results strictly as a JSON array of objects. Do not include any markdown formatting wrappers (like ```json) or explanation text outside the JSON.

Expected Output Format:
[
  {{
    "scheme_name": "Scheme Name",
    "description": "Short Description",
    "eligibility": "Eligibility criteria details...",
    "benefits": "Benefits details...",
    "application_process": "Application process details...",
    "source_name": "Official Source Portal",
    "source_url": "https://example.gov.in/scheme"
  }}
]
"""
    try:
        from api_utils import generate_content_with_cascade
        
        # We set generation_config to ensure JSON output
        response = generate_content_with_cascade(
            prompt,
            generation_config={
                "temperature": 0.2,
                "response_mime_type": "application/json"
            },
            api_name="Gemini Browse Schemes API"
        )
        
        raw_text = response.text.strip()
        if raw_text.startswith("```"):
            lines = raw_text.splitlines()
            if lines[0].startswith("```json"):
                raw_text = "\n".join(lines[1:-1])
            else:
                raw_text = "\n".join(lines[1:-1])
        
        schemes_list = json.loads(raw_text)
        if isinstance(schemes_list, list):
            logger.info(f"Gemini Browse Schemes: successfully parsed {len(schemes_list)} schemes.")
            return schemes_list
        else:
            logger.error("Gemini output was not a JSON list.")
            return []
            
    except Exception as e:
        logger.exception("Error during Gemini Browse Schemes synthesis.")
        raise e
