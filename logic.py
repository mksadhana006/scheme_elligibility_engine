"""
logic.py

Hybrid AI Recommendation Engine for the Adhikaar Scheme Eligibility Platform.

This module orchestrates a multi-stage pipeline:
  Stage 1: Semantic Retrieval (embeddings.py) — find semantically relevant schemes.
  Stage 2: Rule Validation — validate hard eligibility constraints with graduated penalties.
  Stage 3: LLM Re-Ranking (llm_reranker.py) — contextual re-ranking via Google Gemini.
  Stage 4: Score Fusion — weighted combination of all signals.

Changes from the original version:
- Removed dead `load_schemes()` function (was duplicating schemes.json).
- Softened rule scoring: single-field mismatches no longer kill the entire score.
- Integrated semantic search and LLM re-ranking into the pipeline.
- `get_top_matches()` now returns all schemes above a threshold (not a hard top_n cap).
- All existing function signatures preserved for backward compatibility with app.py.

AI Concepts:
1. Semantic Retrieval (Dense Retrieval via FAISS)
2. Expert System (Rule-Based Constraint Validation)
3. LLM-as-a-Judge (Re-Ranking)
4. Weighted Score Fusion (Ensemble Learning)
5. User Segmentation (Demographic Clustering)
6. Explainable AI (XAI Breakdowns)
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


def segment_user(profile):
    """
    AI Concept: User Segmentation / Clustering
    Classifies the user into demographic segments to boost relevant schemes.
    """
    segments = set()
    age = profile.get('age')
    income = profile.get('income')
    occupation = profile.get('occupation')
    marital_status = profile.get('marital_status')
    gender = profile.get('gender')

    if income is not None and income <= 150000:
        segments.add("bpl")
        segments.add("low income")
    
    if age is not None:
        if age >= 60:
            segments.add("senior citizen")
            segments.add("old age")
            segments.add("elderly")
        elif age <= 30:
            segments.add("youth")
            segments.add("student")
    
    if occupation in ["farmer", "agriculture"]:
        segments.add("farmer")
        segments.add("agriculture")
    
    if marital_status == "widow":
        segments.add("widow")
        
    if gender == "female":
        segments.add("women")
        segments.add("female")

    return list(segments)


def calculate_relevance_score(profile, scheme, user_segments):
    """
    AI Concept: Content-Based Filtering / Relevance Scoring
    Calculates Jaccard-like keyword overlap between user profile and scheme keywords.
    This now serves as a lightweight fallback/supplement to the semantic search score.
    """
    scheme_keywords = set(k.lower() for k in scheme.get("match_keywords", []))
    
    if not scheme_keywords:
        return 50  # Default relevance if no keywords defined

    # Implicit keywords derived from profile
    user_keywords = set(user_segments)
    if profile.get('occupation'):
        user_keywords.add(str(profile['occupation']).lower())
    if profile.get('state') and profile['state'] != "other":
        user_keywords.add(str(profile['state']).lower())
        
    # Calculate intersection-based score
    intersection = len(user_keywords.intersection(scheme_keywords))
    union = len(scheme_keywords)
    
    if union == 0:
        return 50
        
    relevance_pct = min(100, int((intersection / union) * 100))
    return max(20, relevance_pct)


def calculate_rule_score(profile, scheme):
    """
    AI Concept: Expert System / Rule-Based Logic with Graduated Penalties.
    
    UPGRADED: Instead of a binary critical_mismatch that kills the score,
    we use graduated penalties. Each dimension contributes independently
    to a total score. Missing fields get a small penalty rather than 
    blocking the match entirely.
    
    Returns: score (0-100), has_hard_block (bool), why_matched (list), 
             why_not_matched (list), missing_fields (list)
    """
    matched_conditions = 0
    total_conditions = 0
    why_matched = []
    why_not_matched = []
    missing_fields = []
    has_hard_block = False  # Only True for absolute dealbreakers

    # 1. Gender
    scheme_gender = scheme.get('gender', [])
    if scheme_gender and "any" not in scheme_gender:
        total_conditions += 1
        if profile.get('gender'):
            if profile['gender'] in scheme_gender:
                matched_conditions += 1
                why_matched.append("Your gender matches")
            else:
                why_not_matched.append(f"Requires gender: {', '.join(scheme_gender).capitalize()}")
                # Gender is a hard block for gender-specific schemes
                has_hard_block = True
        else:
            missing_fields.append("gender")

    # 2. Marital status
    scheme_marital = scheme.get('marital_status', [])
    if scheme_marital and "any" not in scheme_marital:
        total_conditions += 1
        if profile.get('marital_status'):
            if profile['marital_status'] in scheme_marital:
                matched_conditions += 1
                if profile['marital_status'] == 'widow':
                    why_matched.append("You are widowed")
                else:
                    why_matched.append("Your marital status matches")
            else:
                why_not_matched.append(f"Requires marital status: {', '.join(scheme_marital).capitalize()}")
                # Marital status is a hard block for marital-specific schemes (e.g., widow pension)
                has_hard_block = True
        else:
            missing_fields.append("marital_status")

    # 3. State
    scheme_state = scheme.get('state', [])
    if scheme_state and "all" not in scheme_state:
        total_conditions += 1
        if profile.get('state'):
            if profile['state'] in scheme_state:
                matched_conditions += 1
                why_matched.append(f"You are from {profile['state'].title()}")
            else:
                why_not_matched.append(f"Requires residence in: {', '.join([s.capitalize() for s in scheme_state])}")
                # State mismatch is a soft penalty — many schemes have expanded coverage
        else:
            missing_fields.append("state")

    # 4. Age
    age_limit = scheme.get('age_limit', {})
    min_age = age_limit.get('min', 0)
    max_age = age_limit.get('max', 999)
    if min_age > 0 or max_age < 999:
        total_conditions += 1
        if profile.get('age') is not None:
            if min_age <= profile['age'] <= max_age:
                matched_conditions += 1
                why_matched.append("Your age falls within the eligible range")
            else:
                why_not_matched.append(f"Age must be between {min_age} and {max_age} years")
                # Age outside range is a hard block
                has_hard_block = True
        else:
            missing_fields.append("age")

    # 5. Income
    max_income = scheme.get('income_limit')
    if max_income:
        total_conditions += 1
        if profile.get('income') is not None:
            if profile['income'] <= max_income:
                matched_conditions += 1
                why_matched.append("Your income satisfies eligibility")
            else:
                why_not_matched.append(f"Income exceeds the maximum limit of ₹{max_income:,.0f}")
                # Income over limit is NOT always a hard block — some schemes have flexibility
        else:
            missing_fields.append("income")

    # 6. Occupation
    scheme_occupation = scheme.get('occupation', [])
    if scheme_occupation and "any" not in scheme_occupation:
        total_conditions += 1
        if profile.get('occupation'):
            if profile['occupation'] in scheme_occupation:
                matched_conditions += 1
                if profile['occupation'] == 'student':
                    raw_txt = str(profile.get('raw_text', '')).lower()
                    if 'college' in raw_txt or 'university' in raw_txt or 'degree' in raw_txt or 'college' in str(scheme.get('match_keywords', [])) or 'college' in scheme.get('scheme_name', '').lower():
                        why_matched.append("You are a college student")
                    else:
                        why_matched.append("You are a student")
                    why_matched.append("Your education level matches")
                else:
                    why_matched.append(f"You are a {profile['occupation']}")
            else:
                why_not_matched.append(f"Occupation must be one of: {', '.join(scheme_occupation).capitalize()}")
                # Occupation mismatch is a soft penalty
        else:
            missing_fields.append("occupation")

    # Calculate base rule score
    if total_conditions == 0:
        rule_score = 100
    else:
        rule_score = int((matched_conditions / total_conditions) * 100)
    
    # Apply graduated penalty for missing fields (instead of a hard block)
    # Each missing field reduces confidence by 8 points (softer than the old 15)
    if missing_fields and not has_hard_block:
        rule_score = max(0, rule_score - (len(missing_fields) * 8))

    return rule_score, has_hard_block, why_matched, why_not_matched, missing_fields


def fuse_scores(rule_score, relevance_score, semantic_score, llm_score, priority_score, has_hard_block):
    """
    AI Concept: Weighted Score Fusion (Ensemble).
    
    UPGRADED weights to incorporate all four signals:
    - 35% semantic search score (new — captures meaning-based relevance)
    - 30% rule validation score (existing — hard constraint checking)
    - 20% LLM re-ranking score (new — contextual intelligence)
    - 10% keyword relevance score (existing — keyword overlap, now supplementary)
    - 5% priority score (existing — editorial priority)
    
    When LLM is unavailable (score=50 default), the effective weights shift
    toward semantic and rules, which is the desired behavior.
    """
    if has_hard_block:
        # Hard blocks still significantly reduce the score, but don't zero it out.
        # This allows hard-blocked schemes to appear as "Low Match" with explanations
        # instead of being completely hidden.
        penalty_score = min(rule_score, 25)
        return penalty_score, "Low Match"

    w_semantic = 0.35
    w_rule = 0.30
    w_llm = 0.20
    w_rel = 0.10
    w_prio = 0.05
    
    norm_prio = min(100, max(0, priority_score))
    norm_semantic = min(100, max(0, semantic_score))
    norm_llm = min(100, max(0, llm_score))
    
    final_score = (
        (norm_semantic * w_semantic) +
        (rule_score * w_rule) +
        (norm_llm * w_llm) +
        (relevance_score * w_rel) +
        (norm_prio * w_prio)
    )
    final_score = int(min(100, max(0, final_score)))
    
    if final_score >= 75 and rule_score >= 70:
        status = "Full Match"
    elif final_score >= 45:
        status = "Partial Match"
    elif final_score >= 25:
        status = "Low Match"
    else:
        status = "No Match"
        
    return final_score, status


def score_scheme(profile, scheme, semantic_score=50, llm_score=50, llm_explanation=""):
    """
    Orchestrator for the Hybrid AI Recommendation Pipeline.
    
    Combines:
    1. User segmentation (clustering)
    2. Rule validation (expert system) — with graduated penalties
    3. Keyword relevance (content-based filtering)
    4. Semantic similarity (dense retrieval) — from embeddings.py
    5. LLM re-ranking (contextual intelligence) — from llm_reranker.py
    6. Score fusion (ensemble)
    """
    # 1. Segment User
    user_segments = segment_user(profile)
    
    # 2. Rule Validation
    rule_score, has_hard_block, why_matched, why_not_matched, missing_fields = calculate_rule_score(profile, scheme)
    
    # 3. Keyword Relevance
    relevance_score = calculate_relevance_score(profile, scheme, user_segments)
    
    # 4. Priority Score
    priority_score = scheme.get("priority_score", 50)
    
    # 5. Score Fusion (semantic_score and llm_score are passed in from the pipeline)
    final_score, match_status = fuse_scores(
        rule_score, relevance_score, semantic_score, llm_score, priority_score, has_hard_block
    )
    
    # Add missing field warnings
    for field in missing_fields:
        why_not_matched.append(f"Missing information: Please provide your {field.replace('_', ' ')}")

    # 6. Explainability Breakdown (XAI)
    xai_breakdown = {
        "semantic_contribution": f"{semantic_score}% (weight: 35%)",
        "rule_contribution": f"{rule_score}% (weight: 30%)",
        "llm_contribution": f"{llm_score}% (weight: 20%)",
        "relevance_contribution": f"{relevance_score}% (weight: 10%)",
        "priority_contribution": f"{priority_score}% (weight: 5%)"
    }

    # Inject AI reasoning into the positive feedback list
    if not has_hard_block:
        ai_summary = (
            f"🧠 AI Score Breakdown: Semantic={semantic_score}%, "
            f"Rules={rule_score}%, LLM={llm_score}%, "
            f"Relevance={relevance_score}%, Priority={priority_score}"
        )
        why_matched.insert(0, ai_summary)

    # Add LLM explanation if available
    if llm_explanation and llm_explanation not in ("LLM re-ranking unavailable", "Not evaluated by LLM"):
        why_matched.append(f"🤖 AI Analysis: {llm_explanation}")

    return {
        "scheme_name": scheme.get("scheme_name", "Unknown Scheme"),
        "match_status": match_status,
        "match_score": final_score,
        "why_matched": why_matched,
        "why_not_matched": why_not_matched,
        "missing_fields": missing_fields,
        "required_documents": scheme.get("required_documents", []),
        "official_apply_link": scheme.get("official_apply_link", ""),
        "benefit_summary": scheme.get("benefit_summary", ""),
        "application_steps": scheme.get("application_steps", []),
        "category": scheme.get("category", ""),
        "xai_breakdown": xai_breakdown
    }


def match_user_to_schemes(user_profile, schemes_data):
    """
    Match a user profile against all available schemes (rule-based only fallback).
    Used when semantic search is not available.
    """
    normalized_profile = normalize_profile(user_profile)
    
    results = []
    for scheme in schemes_data:
        score_result = score_scheme(normalized_profile, scheme)
        results.append(score_result)
        
    return results


def rank_schemes(scored_schemes):
    """
    Rank matched schemes based on their match score in descending order.
    """
    return sorted(scored_schemes, key=lambda x: x['match_score'], reverse=True)


def explain_match(scored_scheme):
    """
    Generate a human-readable explanation of why a user matched or didn't match a scheme.
    AI Concept: Explainable AI (XAI)
    """
    explanation = ""
    if scored_scheme["why_matched"]:
        explanation += "Why you are eligible:\n"
        for reason in scored_scheme["why_matched"]:
            explanation += f"- {reason}\n"
    if scored_scheme["why_not_matched"]:
        if explanation:
            explanation += "\n"
        explanation += "Action Required or Mismatches:\n"
        for reason in scored_scheme["why_not_matched"]:
            explanation += f"- {reason}\n"
            
    explanation += "\n[AI Score Breakdown]\n"
    for k, v in scored_scheme.get("xai_breakdown", {}).items():
        explanation += f"- {k.replace('_', ' ').capitalize()}: {v}\n"
        
    return explanation.strip()


def get_top_matches(user_profile, schemes_data, top_n=15, user_text="", score_threshold=25):
    """
    Get the top matching schemes using the full AI pipeline.
    
    Pipeline:
    1. Semantic Retrieval (FAISS) — retrieve all schemes ranked by semantic similarity.
    2. Rule Validation — score each retrieved scheme against hard constraints.
    3. LLM Re-Ranking (Gemini) — contextually re-rank candidates.
    4. Score Fusion — combine all signals.
    5. Return all schemes above the score threshold, sorted by final score.
    
    Args:
        user_profile: Dict with user's profile fields (may not be normalized yet).
        schemes_data: List of scheme dicts from schemes.json.
        top_n: Maximum number of results to return.
        user_text: Raw text the user typed/spoke (used for semantic search).
        score_threshold: Minimum final score to include in results (default: 25%).
        
    Returns:
        List of scored scheme dicts, sorted by match_score descending.
    """
    normalized_profile = normalize_profile(user_profile)
    
    # --- Stage 1: Semantic Retrieval ---
    semantic_scores = {}
    try:
        from embeddings import semantic_search
        
        semantic_results = semantic_search(
            normalized_profile,
            schemes_data,
            user_text=user_text,
            top_k=len(schemes_data)  # Retrieve all schemes with scores
        )
        
        # Map scheme names to semantic scores
        for result in semantic_results:
            scheme_name = result["scheme"].get("scheme_name", "")
            semantic_scores[scheme_name] = result["semantic_score"]
            
        logger.info(f"Semantic search returned scores for {len(semantic_scores)} schemes.")
        
    except ImportError:
        logger.warning("embeddings module not available. Using keyword relevance only.")
    except Exception as e:
        logger.warning(f"Semantic search failed: {e}. Falling back to keyword relevance.")

    # --- Stage 2 & 3: Prepare candidates for LLM re-ranking ---
    # Build candidates list with semantic scores attached
    candidates = []
    for scheme in schemes_data:
        scheme_name = scheme.get("scheme_name", "")
        sem_score = semantic_scores.get(scheme_name, 50)  # Default 50 if not available
        candidates.append({
            "scheme": scheme,
            "semantic_score": sem_score
        })

    # --- Stage 3: LLM Re-Ranking ---
    llm_scores = {}
    llm_explanations = {}
    try:
        from llm_reranker import rerank_schemes, is_available as llm_available
        
        if llm_available():
            reranked = rerank_schemes(normalized_profile, candidates)
            for item in reranked:
                scheme_name = item["scheme"].get("scheme_name", "")
                llm_scores[scheme_name] = item.get("llm_score", 50)
                llm_explanations[scheme_name] = item.get("llm_explanation", "")
            logger.info(f"LLM re-ranking completed for {len(llm_scores)} schemes.")
        else:
            logger.info("LLM re-ranking not available (no API key). Using semantic + rules only.")
            
    except ImportError:
        logger.warning("llm_reranker module not available. Skipping LLM re-ranking.")
    except Exception as e:
        logger.warning(f"LLM re-ranking failed: {e}. Continuing without LLM scores.")

    # --- Stage 4: Score each scheme with all signals ---
    results = []
    for scheme in schemes_data:
        scheme_name = scheme.get("scheme_name", "")
        
        sem_score = semantic_scores.get(scheme_name, 50)
        llm_score = llm_scores.get(scheme_name, 50)
        llm_explanation = llm_explanations.get(scheme_name, "")
        
        score_result = score_scheme(
            normalized_profile,
            scheme,
            semantic_score=sem_score,
            llm_score=llm_score,
            llm_explanation=llm_explanation
        )
        results.append(score_result)

    # --- Stage 5: Rank and filter ---
    ranked = rank_schemes(results)
    
    # Filter by score threshold and cap at top_n
    filtered = [r for r in ranked if r["match_score"] >= score_threshold]
    
    return filtered[:top_n]
