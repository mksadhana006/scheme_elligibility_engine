"""
api_utils.py

Shared utilities for API rate-limiting, caching, and exponential backoff retries.
"""

import time
import random
import logging
import threading
import json
from typing import Callable, Any, Dict, Optional

logger = logging.getLogger(__name__)

# Thread-safe in-memory cache
_api_cache = {}
_cache_lock = threading.Lock()

def make_hashable(o: Any) -> Any:
    """Helper to convert unhashable types (dicts, lists) into hashable structures."""
    if isinstance(o, dict):
        return tuple(sorted((k, make_hashable(v)) for k, v in o.items()))
    elif isinstance(o, list):
        return tuple(make_hashable(x) for x in o)
    elif isinstance(o, set):
        return tuple(sorted(make_hashable(x) for x in o))
    return o

def get_cache_key(func_name: str, *args, **kwargs) -> str:
    """Generate a stable, unique cache key for function calls."""
    hashable_args = make_hashable(args)
    hashable_kwargs = make_hashable(kwargs)
    return json.dumps((func_name, hashable_args, hashable_kwargs), sort_keys=True)

def get_cached_response(func_name: str, *args, **kwargs) -> Any:
    """Retrieve a cached response if it exists."""
    key = get_cache_key(func_name, *args, **kwargs)
    with _cache_lock:
        if key in _api_cache:
            logger.info(f"Cache hit for API function '{func_name}'")
            return _api_cache[key]
    return None

def cache_response(func_name: str, response: Any, *args, **kwargs) -> None:
    """Save a response to the cache."""
    if response is not None:
        key = get_cache_key(func_name, *args, **kwargs)
        with _cache_lock:
            _api_cache[key] = response
            logger.info(f"Cached response for API function '{func_name}'")

def execute_with_retry_and_backoff(
    func: Callable,
    args: tuple,
    kwargs: dict,
    max_retries: int = 3,
    base_delay: float = 2.0,
    api_name: str = "API"
) -> Any:
    """
    Executes a function with exponential backoff and retries when a rate limit (HTTP 429) is detected.
    """
    import os
    import re
    
    # Helper to extract retry delay from Gemini / Google RPC exceptions or headers
    def extract_retry_after(exc: Exception) -> Optional[float]:
        # 1. Check HTTP response headers
        if hasattr(exc, 'response') and exc.response is not None:
            headers = getattr(exc.response, 'headers', {})
            retry_after = headers.get('Retry-After') or headers.get('retry-after')
            if retry_after:
                try:
                    return float(retry_after)
                except ValueError:
                    pass
        # 2. Parse from exception error message (custom RPC response formats)
        err_msg = str(exc)
        match = re.search(r"Please retry in\s+([\d\.]+)\s*s", err_msg, re.IGNORECASE)
        if match:
            try:
                return float(match.group(1))
            except ValueError:
                pass
        match2 = re.search(r"retryDelay:\s*'(\d+)\s*s'", err_msg, re.IGNORECASE)
        if match2:
            try:
                return float(match2.group(1))
            except ValueError:
                pass
        return None

    delay = base_delay
    for attempt in range(max_retries + 1):
        if attempt > 0:
            logger.info(f"[DEBUG] Retry attempt number {attempt}/{max_retries} for {api_name}...")
        else:
            logger.info(f"[DEBUG] {api_name} request started...")
            
        try:
            res = func(*args, **kwargs)
            logger.info(f"[DEBUG] {api_name} request succeeded.")
            return res
        except Exception as e:
            is_rate_limit = False
            error_msg = str(e)
            
            # Scrub API key if present in error details (Gemini key starts with AIzaSy)
            clean_error_msg = re.sub(r"AIzaSy[A-Za-z0-9_-]{33}", "AIzaSy[REDACTED]", error_msg)
            
            # Check for HTTP 429 status code
            if hasattr(e, 'response') and e.response is not None:
                if getattr(e.response, 'status_code', None) == 429:
                    is_rate_limit = True
            elif "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg:
                is_rate_limit = True
                
            # Check for Google API core exceptions (ResourceExhausted / TooManyRequests / QuotaExceeded)
            exc_type_name = type(e).__name__
            if any(term in exc_type_name for term in ["ResourceExhausted", "TooManyRequests", "QuotaExceeded"]):
                is_rate_limit = True
                
            if is_rate_limit:
                logger.warning(
                    f"[WARNING] Gemini rate limit detected (HTTP 429 / RESOURCE_EXHAUSTED) in {api_name}. "
                    f"Technical details: {clean_error_msg}"
                )
                
                # Set Streamlit session state flags only on final failure for search API
                if attempt == max_retries:
                    try:
                        import streamlit as st
                        if hasattr(st, "session_state"):
                            if "search" in api_name.lower():
                                st.session_state.search_rate_limited = True
                                st.session_state.search_rate_limited_until = time.time() + 30.0
                    except Exception:
                        pass

                if attempt < max_retries:
                    retry_after = extract_retry_after(e)
                    if retry_after is not None:
                        # Respect retry-after but cap to 10 seconds to keep app responsive
                        sleep_time = min(retry_after, 10.0)
                        logger.warning(
                            f"[DEBUG] Server requested retry delay: {retry_after:.2f}s. "
                            f"Sleeping for capped {sleep_time:.2f}s before retry..."
                        )
                    else:
                        sleep_time = delay + random.uniform(0.0, 1.0)
                        logger.warning(
                            f"[DEBUG] Sleeping for {sleep_time:.2f}s before retry..."
                        )
                        delay *= 2.0
                    time.sleep(sleep_time)
                else:
                    logger.error(
                        f"[ERROR] Final failure after maximum retries ({max_retries}) for {api_name}. "
                        f"Technical error: {clean_error_msg}"
                    )
                    raise e
            else:
                # Other exceptions (timeout, API error, parsing error) are logged and re-raised
                logger.error(f"[ERROR] {api_name} failed with technical error: {clean_error_msg}")
                raise e

def generate_content_with_cascade(
    prompt: str,
    generation_config: Optional[dict] = None,
    api_name: str = "Gemini API"
) -> Any:
    """
    Tries to generate content using a cascade of Gemini models (flash, flash-lite, 3.6-flash, etc.)
    to avoid running out of quota on a single free-tier model.
    """
    import os
    import google.generativeai as genai
    models = [
        "gemini-2.5-flash",
        "gemini-2.0-flash",
        "gemini-1.5-flash",
        "gemini-1.5-flash-8b",
        "gemini-3.1-flash-lite"
    ]
    last_err = None
    
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if api_key:
        genai.configure(api_key=api_key, transport="rest")
        
    for model_name in models:
        try:
            logger.info(f"Cascade: trying model '{model_name}'...")
            model = genai.GenerativeModel(model_name)
            
            def _call(m, p):
                return m.generate_content(p, generation_config=generation_config)
                
            response = execute_with_retry_and_backoff(
                _call,
                args=(model, prompt),
                kwargs={},
                api_name=f"{api_name} ({model_name})",
                max_retries=1,
                base_delay=1.0
            )
            logger.info(f"Cascade: successfully generated content using '{model_name}'")
            return response
        except Exception as e:
            last_err = e
            logger.warning(f"Cascade: model '{model_name}' failed: {e}. Trying next model...")
            continue
    # If all models in cascade fail, flag Streamlit
    try:
        import streamlit as st
        if hasattr(st, "session_state"):
            st.session_state.ai_rate_limited = True
            st.session_state.ai_rate_limited_until = time.time() + 30.0
    except Exception:
        pass
    logger.error("Cascade: all models in cascade failed.")
    raise last_err
