"""Topic modeling and pronoun analysis for Identity Drift (PRD FR-6).

Extracts top topics from utterances (BERTopic or TF-IDF fallback)
and computes pronoun frequencies (Choi et al. §5.3).
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional
import pandas as pd

logger = logging.getLogger(__name__)

PRONOUN_CATEGORIES = {
    "first_singular": {"i", "me", "my", "mine", "myself", "i'm", "i've", "i'd", "i'll"},
    "first_plural": {"we", "us", "our", "ours", "ourselves", "we're", "we've", "we'd", "we'll"},
    "second_person": {"you", "your", "yours", "yourself", "yourselves", "you're", "you've", "you'd", "you'll"},
}


def count_pronouns(texts: List[str]) -> Dict[str, Any]:
    """Compute raw count and relative rate per 1000 words for pronouns."""
    total_words = 0
    cat_counts = {k: 0 for k in PRONOUN_CATEGORIES}

    for text in texts:
        words = re.findall(r"\b[a-z']+\b", text.lower())
        total_words += len(words)
        for w in words:
            for cat, vocab in PRONOUN_CATEGORIES.items():
                if w in vocab:
                    cat_counts[cat] += 1

    rates = {}
    for cat, cnt in cat_counts.items():
        rate = (cnt / total_words * 1000) if total_words > 0 else 0.0
        rates[cat] = {"count": cnt, "rate_per_1000_words": round(rate, 2)}

    return {
        "total_words": total_words,
        "pronouns": rates,
    }


def run_topic_modeling_tfidf_fallback(
    texts: List[str],
    top_n_topics: int = 10,
    top_k_words: int = 10,
) -> List[Dict[str, Any]]:
    """Heuristic / TF-IDF topic extractor when BERTopic is not installed."""
    if not texts:
        return []

    # Clean words and filter English stopwords
    stopwords = {
        "i", "me", "my", "myself", "we", "our", "ours", "ourselves", "you", "your",
        "yours", "yourself", "yourselves", "he", "him", "his", "himself", "she", "her",
        "hers", "herself", "it", "its", "itself", "they", "them", "their", "theirs",
        "what", "which", "who", "whom", "this", "that", "these", "those", "am", "is",
        "are", "was", "were", "be", "been", "being", "have", "has", "had", "having",
        "do", "does", "did", "doing", "a", "an", "the", "and", "but", "if", "or",
        "because", "as", "until", "while", "of", "at", "by", "for", "with", "about",
        "against", "between", "into", "through", "during", "before", "after", "above",
        "to", "from", "up", "down", "in", "out", "on", "off", "over", "under", "again",
        "further", "then", "once", "here", "there", "when", "where", "why", "how", "all",
        "any", "both", "each", "few", "more", "most", "other", "some", "such", "no", "nor",
        "not", "only", "own", "same", "so", "than", "too", "very", "s", "t", "can", "will",
        "just", "don", "should", "now"
    }

    word_freq: Dict[str, int] = {}
    doc_word_counts: List[Dict[str, int]] = []

    for doc in texts:
        tokens = re.findall(r"\b[a-z]{3,}\b", doc.lower())
        doc_counts: Dict[str, int] = {}
        for t in tokens:
            if t not in stopwords:
                doc_counts[t] = doc_counts.get(t, 0) + 1
                word_freq[t] = word_freq.get(t, 0) + 1
        doc_word_counts.append(doc_counts)

    sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
    top_vocab = [w for w, _ in sorted_words[:100]]

    if not top_vocab:
        return []

    # Partition documents across top clusters
    num_topics = min(top_n_topics, max(1, len(top_vocab) // 5))
    topics = []
    chunk_size = max(1, len(top_vocab) // num_topics)

    for i in range(num_topics):
        topic_words = top_vocab[i * chunk_size : (i + 1) * chunk_size][:top_k_words]
        # Find representative utterances containing these words
        matches = []
        for idx, doc in enumerate(texts):
            doc_lower = doc.lower()
            overlap = sum(1 for w in topic_words if w in doc_lower)
            if overlap > 0:
                matches.append((overlap, doc))
        matches.sort(key=lambda x: x[0], reverse=True)

        topics.append({
            "topic_id": i,
            "keywords": topic_words,
            "count": len(matches),
            "sample_utterances": [m[1] for m in matches[:3]],
        })

    return topics


def run_topic_modeling(
    utterances: List[Dict[str, Any]],
    top_n_topics: int = 10,
    min_topic_size: int = 10,
) -> Dict[str, Any]:
    """Execute topic modeling and pronoun analysis on agent utterances."""
    texts = [u.get("text", "") for u in utterances if u.get("text")]
    pronouns = count_pronouns(texts)

    try:
        from bertopic import BERTopic
        if len(texts) >= min_topic_size:
            topic_model = BERTopic(min_topic_size=min_topic_size, language="english")
            topics, probs = topic_model.fit_transform(texts)
            info = topic_model.get_topic_info()
            extracted_topics = []
            for _, row in info.head(top_n_topics + 1).iterrows():
                t_id = row["Topic"]
                if t_id == -1:
                    continue
                words = [w for w, _ in topic_model.get_topic(t_id)[:10]]
                extracted_topics.append({
                    "topic_id": int(t_id),
                    "keywords": words,
                    "count": int(row["Count"]),
                    "sample_utterances": topic_model.get_representative_docs(t_id)[:3],
                })
        else:
            extracted_topics = run_topic_modeling_tfidf_fallback(texts, top_n_topics=top_n_topics)
    except Exception as ex:
        logger.info("BERTopic not available (%s), using keyword fallback", ex)
        extracted_topics = run_topic_modeling_tfidf_fallback(texts, top_n_topics=top_n_topics)

    return {
        "num_utterances": len(texts),
        "pronouns": pronouns,
        "topics": extracted_topics,
    }
