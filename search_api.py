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
from typing import List, Dict, Any, Optional

import requests

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
    api_key, cx = _get_search_credentials()
    if not api_key or not cx:
        logger.info("Google Search API not configured. Skipping web search.")
        return []

    query = _build_search_query(profile)

    try:
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

        response = requests.get(url, params=params, timeout=timeout)
        response.raise_for_status()
        data = response.json()

        results = []
        for item in data.get("items", []):
            results.append({
                "title": item.get("title", ""),
                "snippet": item.get("snippet", ""),
                "link": item.get("link", ""),
                "source": item.get("displayLink", "")
            })

        logger.info(f"Web search returned {len(results)} results for query: {query[:80]}...")
        return results

    except requests.exceptions.Timeout:
        logger.warning("Google Search API timed out.")
    except requests.exceptions.HTTPError as e:
        logger.warning(f"Google Search API HTTP error: {e}")
    except requests.exceptions.ConnectionError:
        logger.warning("Google Search API connection failed (no internet?).")
    except Exception as e:
        logger.warning(f"Google Search API unexpected error: {e}")

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
