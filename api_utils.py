"""
api_utils.py

Shared utilities for API rate-limiting, caching, and exponential backoff retries.
"""

import time
import random
import logging
import threading
import json
from typing import Callable, Any, Dict

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
    delay = base_delay
    for attempt in range(max_retries + 1):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            is_rate_limit = False
            error_msg = str(e)
            
            # Check for HTTP 429 status code
            if hasattr(e, 'response') and e.response is not None:
                if getattr(e.response, 'status_code', None) == 429:
                    is_rate_limit = True
            elif "429" in error_msg:
                is_rate_limit = True
                
            # Check for Google API core exceptions (ResourceExhausted / TooManyRequests / QuotaExceeded)
            exc_type_name = type(e).__name__
            if any(term in exc_type_name for term in ["ResourceExhausted", "TooManyRequests", "QuotaExceeded"]):
                is_rate_limit = True
                
            if is_rate_limit:
                logger.warning(
                    f"[Rate Limit Event] {api_name} rate limit (429) detected. "
                    f"Attempt {attempt + 1}/{max_retries + 1}. Error: {error_msg}. "
                    f"Retrying in {delay:.2f} seconds..."
                )
                
                # Try to set Streamlit session state flags
                try:
                    import streamlit as st
                    if hasattr(st, "session_state"):
                        if "search" in api_name.lower():
                            st.session_state.search_rate_limited = True
                        if "gemini" in api_name.lower() or "ai" in api_name.lower():
                            st.session_state.ai_rate_limited = True
                except Exception:
                    pass

                if attempt < max_retries:
                    # Exponential backoff with jitter
                    time.sleep(delay + random.uniform(0.0, 1.0))
                    delay *= 2.0
                else:
                    logger.error(f"[Rate Limit Event] Max retries reached for {api_name}. Raising exception.")
                    raise e
            else:
                # Other exceptions are re-raised immediately
                raise e
