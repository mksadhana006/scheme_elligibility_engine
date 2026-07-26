"""
embeddings.py

Semantic Search Layer for the Adhikaar Scheme Recommendation Engine.

This module converts scheme descriptions and user queries into dense vector 
embeddings using sentence-transformers, stores them in a FAISS index, and 
retrieves the most semantically similar schemes for a given user query.

AI Concepts:
1. Dense Retrieval: Using learned embeddings instead of keyword matching.
2. Semantic Similarity: Cosine similarity in embedding space captures meaning.
3. Vector Database: FAISS provides efficient approximate nearest neighbor search.
4. Query Construction: Combining structured profile fields with natural language
   to create rich query representations.
"""

import json
import os
import numpy as np
from typing import List, Dict, Any, Optional

# Lazy imports to avoid slow startup when not needed
_model = None
_faiss = None


def _get_model():
    """Lazy-load the sentence-transformers model (downloaded once, cached locally)."""
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        # all-MiniLM-L6-v2: 384-dim, ~80MB, fast on CPU, strong English performance
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model


def _get_faiss():
    """Lazy-load FAISS."""
    global _faiss
    if _faiss is None:
        import faiss as faiss_lib
        _faiss = faiss_lib
    return _faiss


def _scheme_to_text(scheme: Dict[str, Any]) -> str:
    """
    Convert a scheme's structured data into a rich text representation
    suitable for embedding. Combines multiple fields to capture the full
    semantic meaning of what the scheme offers and who it targets.
    """
    parts = []

    # Scheme name is the most informative signal
    if scheme.get("scheme_name"):
        parts.append(scheme["scheme_name"])

    # Category provides broad topic
    if scheme.get("category"):
        parts.append(f"Category: {scheme['category']}")

    # Eligibility criteria is critical for matching
    if scheme.get("eligibility_criteria"):
        parts.append(scheme["eligibility_criteria"])

    # Benefit summary describes what the user gets
    if scheme.get("benefit_summary"):
        parts.append(scheme["benefit_summary"])

    # Match keywords add extra semantic coverage
    if scheme.get("match_keywords"):
        parts.append("Keywords: " + ", ".join(scheme["match_keywords"]))

    # Target demographics
    demographics = []
    if scheme.get("gender") and "any" not in [g.lower() for g in scheme["gender"]]:
        demographics.append(f"For {', '.join(scheme['gender'])}")
    if scheme.get("marital_status") and "any" not in [m.lower() for m in scheme["marital_status"]]:
        demographics.append(f"Marital status: {', '.join(scheme['marital_status'])}")
    if scheme.get("occupation") and "any" not in [o.lower() for o in scheme["occupation"]]:
        demographics.append(f"Occupation: {', '.join(scheme['occupation'])}")
    if scheme.get("state") and "all" not in [s.lower() for s in scheme["state"]]:
        demographics.append(f"State: {', '.join(scheme['state'])}")
    if scheme.get("income_limit"):
        demographics.append(f"Income limit: Rs {scheme['income_limit']}")
    if scheme.get("age_limit"):
        age = scheme["age_limit"]
        if age.get("min", 0) > 0 or age.get("max", 120) < 120:
            demographics.append(f"Age: {age.get('min', 0)}-{age.get('max', 120)} years")

    if demographics:
        parts.append("Target: " + ". ".join(demographics))

    return ". ".join(parts)


def _profile_to_query(profile: Dict[str, Any], user_text: str = "") -> str:
    """
    Convert the user's structured profile and raw text into a query string
    suitable for embedding. The query captures both the natural language
    description and the structured attributes.
    """
    parts = []

    # Include the raw user text first (most natural representation)
    if user_text and user_text.strip():
        parts.append(user_text.strip())

    # Add structured fields to ensure they're represented in the embedding
    structured_parts = []
    if profile.get("gender"):
        structured_parts.append(f"{profile['gender']}")
    if profile.get("age"):
        structured_parts.append(f"{profile['age']} years old")
    if profile.get("marital_status"):
        structured_parts.append(f"marital status {profile['marital_status']}")
    if profile.get("occupation"):
        structured_parts.append(f"occupation {profile['occupation']}")
    if profile.get("state"):
        structured_parts.append(f"living in {profile['state']}")
    if profile.get("income") is not None:
        try:
            inc = float(profile["income"])
            if inc >= 100000:
                structured_parts.append(f"income {inc/100000:.1f} lakh rupees")
            else:
                structured_parts.append(f"income {inc:.0f} rupees")
        except (ValueError, TypeError):
            pass

    if structured_parts:
        parts.append("Profile: " + ", ".join(structured_parts))

    # Add segment-based context for better semantic matching
    context_parts = []
    if profile.get("income") is not None:
        try:
            inc = float(profile["income"])
            if inc <= 150000:
                context_parts.append("below poverty line low income BPL")
        except (ValueError, TypeError):
            pass
    if profile.get("age") is not None:
        try:
            age = int(profile["age"])
            if age >= 60:
                context_parts.append("senior citizen elderly old age pension")
            elif age <= 30:
                context_parts.append("youth young person")
        except (ValueError, TypeError):
            pass
    if profile.get("marital_status") == "widow":
        context_parts.append("widow pension welfare women")

    if context_parts:
        parts.append("Context: " + " ".join(context_parts))

    return ". ".join(parts) if parts else "government scheme eligibility"


class SchemeEmbeddingEngine:
    """
    Vector search engine for government schemes.
    
    Builds a FAISS index from scheme descriptions and supports
    cosine-similarity retrieval for user queries.
    """

    INDEX_FILE = "scheme_embeddings.index"
    METADATA_FILE = "scheme_embeddings_meta.json"

    def __init__(self, schemes_path: str = "schemes.json"):
        self.schemes_path = schemes_path
        self.schemes: List[Dict[str, Any]] = []
        self.scheme_texts: List[str] = []
        self.index = None
        self._dimension = 384  # all-MiniLM-L6-v2 output dimension

    def _load_schemes(self) -> List[Dict[str, Any]]:
        """Load schemes from JSON file."""
        with open(self.schemes_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _get_index_dir(self) -> str:
        """Get the directory where the FAISS index is stored (same as schemes.json)."""
        return os.path.dirname(os.path.abspath(self.schemes_path))

    def _index_path(self) -> str:
        return os.path.join(self._get_index_dir(), self.INDEX_FILE)

    def _meta_path(self) -> str:
        return os.path.join(self._get_index_dir(), self.METADATA_FILE)

    def _is_index_stale(self) -> bool:
        """Check if the cached index is older than schemes.json."""
        idx_path = self._index_path()
        if not os.path.exists(idx_path):
            return True
        if not os.path.exists(self._meta_path()):
            return True

        schemes_mtime = os.path.getmtime(self.schemes_path)
        index_mtime = os.path.getmtime(idx_path)
        return schemes_mtime > index_mtime

    def build_index(self, force: bool = False) -> None:
        """
        Build (or rebuild) the FAISS index from schemes.json.
        
        Steps:
        1. Load all schemes from JSON.
        2. Convert each scheme into a rich text representation.
        3. Encode all texts into embeddings using sentence-transformers.
        4. L2-normalize embeddings (so inner product = cosine similarity).
        5. Add to a FAISS IndexFlatIP index.
        6. Save index and metadata to disk for caching.
        """
        faiss = _get_faiss()
        model = _get_model()

        # Check if we can use cached index
        if not force and not self._is_index_stale():
            self._load_cached_index()
            return

        # Load and process schemes
        self.schemes = self._load_schemes()
        self.scheme_texts = [_scheme_to_text(s) for s in self.schemes]

        # Generate embeddings
        embeddings = model.encode(
            self.scheme_texts,
            normalize_embeddings=True,  # L2 normalize for cosine similarity
            show_progress_bar=False,
            batch_size=32
        )
        embeddings = np.array(embeddings, dtype=np.float32)

        # Build FAISS index (Inner Product on L2-normalized = cosine similarity)
        self._dimension = embeddings.shape[1]
        self.index = faiss.IndexFlatIP(self._dimension)
        self.index.add(embeddings)

        # Cache to disk
        self._save_index()

    def _save_index(self) -> None:
        """Save FAISS index and metadata to disk."""
        faiss = _get_faiss()
        faiss.write_index(self.index, self._index_path())

        meta = {
            "num_schemes": len(self.schemes),
            "dimension": self._dimension,
            "scheme_texts": self.scheme_texts,
            "scheme_names": [s.get("scheme_name", "") for s in self.schemes]
        }
        with open(self._meta_path(), "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)

    def _load_cached_index(self) -> None:
        """Load FAISS index and metadata from disk cache."""
        faiss = _get_faiss()
        self.index = faiss.read_index(self._index_path())
        self.schemes = self._load_schemes()

        with open(self._meta_path(), "r", encoding="utf-8") as f:
            meta = json.load(f)
        self.scheme_texts = meta.get("scheme_texts", [])
        self._dimension = meta.get("dimension", 384)

    def search(
        self,
        profile: Dict[str, Any],
        user_text: str = "",
        top_k: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Search for the most semantically similar schemes to the user's query.
        
        Args:
            profile: Normalized user profile dict.
            user_text: Raw text the user typed/spoke.
            top_k: Number of top results to retrieve.
            
        Returns:
            List of dicts with 'scheme_index', 'scheme', 'semantic_score' (0-100).
        """
        if self.index is None:
            self.build_index()

        model = _get_model()

        # Build query from profile + raw text
        query_text = _profile_to_query(profile, user_text)

        # Encode query
        query_embedding = model.encode(
            [query_text],
            normalize_embeddings=True,
            show_progress_bar=False
        )
        query_embedding = np.array(query_embedding, dtype=np.float32)

        # Search FAISS index
        # Clamp top_k to the number of schemes we have
        actual_k = min(top_k, len(self.schemes))
        scores, indices = self.index.search(query_embedding, actual_k)

        # Build results
        results = []
        for i in range(actual_k):
            idx = int(indices[0][i])
            if idx < 0 or idx >= len(self.schemes):
                continue

            # Convert cosine similarity [-1, 1] to percentage [0, 100]
            raw_score = float(scores[0][i])
            semantic_score = int(max(0, min(100, (raw_score + 1) * 50)))

            results.append({
                "scheme_index": idx,
                "scheme": self.schemes[idx],
                "semantic_score": semantic_score,
                "query_text": query_text
            })

        return results


# Module-level singleton for reuse across Streamlit reruns
_engine_instance: Optional[SchemeEmbeddingEngine] = None


def get_engine(schemes_path: str = "schemes.json") -> SchemeEmbeddingEngine:
    """Get or create the singleton embedding engine."""
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = SchemeEmbeddingEngine(schemes_path)
        _engine_instance.build_index()
    return _engine_instance


def semantic_search(
    profile: Dict[str, Any],
    schemes_data: List[Dict[str, Any]],
    user_text: str = "",
    top_k: int = 20
) -> List[Dict[str, Any]]:
    """
    High-level API for semantic search over schemes.
    
    If schemes_data is provided and not empty, it computes embeddings on the fly.
    Otherwise, it falls back to the static disk index.
    
    Args:
        profile: Normalized user profile.
        schemes_data: The schemes list.
        user_text: Raw user input text.
        top_k: Max results to return.
        
    Returns:
        List of dicts with 'scheme_index', 'scheme', 'semantic_score'.
    """
    if schemes_data:
        try:
            model = _get_model()
            
            # 1. Convert schemes to texts
            scheme_texts = [_scheme_to_text(s) for s in schemes_data]
            
            # 2. Convert query to text
            query_text = _profile_to_query(profile, user_text)
            
            # 3. Generate embeddings (L2 normalized)
            scheme_embeddings = model.encode(
                scheme_texts,
                normalize_embeddings=True,
                show_progress_bar=False
            )
            query_embedding = model.encode(
                [query_text],
                normalize_embeddings=True,
                show_progress_bar=False
            )
            
            # 4. Compute cosine similarity (dot product on normalized)
            scores = np.dot(scheme_embeddings, query_embedding[0])
            
            # 5. Build results
            results = []
            for idx, raw_score in enumerate(scores):
                semantic_score = int(max(0, min(100, (float(raw_score) + 1) * 50)))
                results.append({
                    "scheme_index": idx,
                    "scheme": schemes_data[idx],
                    "semantic_score": semantic_score,
                    "query_text": query_text
                })
                
            # Sort by score descending and limit to top_k
            results = sorted(results, key=lambda x: x["semantic_score"], reverse=True)
            return results[:top_k]
            
        except Exception as e:
            logger.warning(f"On-the-fly semantic search failed: {e}. Falling back to default scores.")
            results = []
            for idx, s in enumerate(schemes_data):
                results.append({
                    "scheme_index": idx,
                    "scheme": s,
                    "semantic_score": 50,
                    "query_text": ""
                })
            return results

    try:
        engine = get_engine()
        return engine.search(profile, user_text, top_k)
    except Exception as e:
        logger.warning(f"Static semantic search failed: {e}")
        return []


if __name__ == "__main__":
    # Quick test
    print("Building embedding index...")
    engine = SchemeEmbeddingEngine()
    engine.build_index(force=True)
    print(f"Indexed {len(engine.schemes)} schemes")

    test_profile = {
        "gender": "female",
        "marital_status": "widow",
        "income": 100000,
        "age": 45,
        "state": "bihar",
        "occupation": "unemployed"
    }
    test_text = "I am a 45 year old widow from Bihar with income 1 lakh"

    results = engine.search(test_profile, test_text, top_k=8)
    print(f"\nQuery: {test_text}")
    print(f"Results ({len(results)} schemes):")
    for r in results:
        print(f"  {r['semantic_score']}% - {r['scheme']['scheme_name']}")
