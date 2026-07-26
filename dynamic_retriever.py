"""
dynamic_retriever.py

Orchestrates Tavily Web Search and Gemini AI structured extraction to dynamically
retrieve government schemes matching a citizen's profile.
"""

import os
import json
import logging
from typing import List, Dict, Any, Optional

from search_api import query_tavily_search, _build_search_query
from api_utils import generate_content_with_cascade, get_cached_response, cache_response

logger = logging.getLogger(__name__)


def fetch_schemes_dynamically(
    profile: Dict[str, Any],
    user_text: str = "",
    max_results: int = 5
) -> List[Dict[str, Any]]:
    """
    1. Check cache to prevent duplicate queries.
    2. Formulates search query.
    3. Runs Tavily Search to gather government web pages.
    4. Feeds results to Gemini cascade (3.5-flash -> 3.5-flash-lite -> etc.)
       to extract structured scheme details.
    """
    # 1. Check cache first to avoid duplicate API calls
    cached = get_cached_response("fetch_schemes_dynamically", profile, user_text, max_results)
    if cached is not None:
        logger.info("Serving dynamic schemes retrieval from cache.")
        return cached

    logger.info("Initializing dynamic scheme fetch from Tavily and Gemini...")
    
    # 2. Run Tavily Search
    query = _build_search_query(profile)
    if user_text:
        # Augment query with user text keywords
        query = f"{query} {user_text[:50]}"
        
    logger.info(f"Querying Tavily search: '{query}'")
    
    web_results = []
    try:
        web_results = query_tavily_search(query, max_results=max_results, include_gov_only=True)
        if not web_results:
            logger.info("Gov-only Tavily search returned no schemes. Trying broader web search...")
            web_results = query_tavily_search(query, max_results=max_results, include_gov_only=False)
    except Exception as e:
        logger.error(f"Search retrieval step failed: {e}")
        return []
        
    if not web_results:
        logger.warning("No search results returned from Tavily. Dynamic extraction cannot proceed.")
        return []
        
    logger.info(f"Retrieved {len(web_results)} web search results. Passing to Gemini for extraction...")

    # 3. Prepare context for Gemini (limit to top 3 unique results, truncate snippets to 250 chars)
    context_entries = []
    seen_titles = set()
    for res in web_results:
        title = res.get('title', '').strip()
        if not title or title in seen_titles:
            continue
        seen_titles.add(title)
        
        snippet = res.get('snippet', '').strip()
        if len(snippet) > 250:
            snippet = snippet[:250] + "..."
            
        context_entries.append(
            f"Source {len(context_entries)+1}:\n"
            f"Title: {title}\n"
            f"URL: {res.get('link')}\n"
            f"Snippet: {snippet}\n"
        )
        if len(context_entries) >= 3:
            break
            
    web_context = "\n\n".join(context_entries)

    # Format user profile
    profile_lines = []
    for k, v in profile.items():
        if v is not None:
            profile_lines.append(f" - {k}: {v}")
    profile_str = "\n".join(profile_lines)

    # 4. Formulate optimized extraction prompt (concise to reduce token count)
    prompt = f"""Evaluate the citizen profile and web search results to extract real Indian government welfare schemes.

CITIZEN PROFILE:
{profile_str}

SEARCH RESULTS:
{web_context}

TASK:
Extract specific schemes discussed in the search results that match this citizen. 

Respond ONLY with a valid JSON array of objects. No explanations or markdown wraps.
Strict JSON schema:
- "scheme_name": (string) Official name.
- "category": (string) Lowercase category (e.g. "widow pension", "pension", "housing", "employment", "women", "student", "agriculture").
- "state": (list of strings) e.g., ["bihar"] or ["all"]. Must be lowercase.
- "eligibility_criteria": (string) Short summary of who can apply.
- "required_documents": (list of strings) Needed documents (e.g. ["Aadhaar Card", "Income Certificate"]).
- "benefit_summary": (string) Brief description of the benefits.
- "application_steps": (list of strings) Steps to apply.
- "official_apply_link": (string) URL from the search results, or the main government site.
- "match_keywords": (list of strings) e.g., ["widow", "pension"].
- "income_limit": (integer or null) Max annual income.
- "age_limit": {{"min": (int), "max": (int)}} default min 0, max 120.
- "gender": (list of strings) Genders eligible. e.g. ["female"] or ["male", "female"].
- "marital_status": (list of strings) Marital status. e.g. ["widow"], ["married"] or ["any"].
- "occupation": (list of strings) Occupations. e.g. ["farmer"], ["student"] or ["any"].
- "priority_score": (integer) Value 50 to 100. Set higher for perfect matches.

RULES:
- Do not hallucinate; only extract schemes present in search results.
- official_apply_link MUST be a real link from the search results.

JSON array response:"""

    # 5. Call Gemini via the model cascade helper
    try:
        response = generate_content_with_cascade(
            prompt,
            generation_config={
                "temperature": 0.1,
                "response_mime_type": "application/json"
            },
            api_name="Gemini Dynamic Extraction API"
        )
        
        response_text = response.text.strip()
        
        # Strip markdown wraps if present
        if response_text.startswith("```"):
            lines = response_text.split("\n")
            if lines[0].startswith("```json") or lines[0].startswith("```"):
                response_text = "\n".join(lines[1:-1])
                
        schemes = json.loads(response_text)
        
        if not isinstance(schemes, list):
            logger.error("Gemini response is not a JSON list.")
            return []
            
        logger.info(f"Successfully extracted {len(schemes)} schemes from Gemini analysis.")
        
        # Cache successful retrieval
        cache_response("fetch_schemes_dynamically", schemes, profile, user_text, max_results)
        return schemes
        
    except Exception as e:
        logger.error(f"Gemini dynamic scheme extraction failed: {e}")
        return []
