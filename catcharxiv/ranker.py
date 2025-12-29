# Copyright (C) 2025 Richard Stiskalek
# This program is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation; either version 3 of the License, or (at your
# option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
# Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
"""Rank papers by keyword relevance with TF-IDF weighting."""

import hashlib
import json
import math
import re
from pathlib import Path

import anthropic


DATA_DIR = Path(__file__).parent.parent / "data"
CACHE_FILE = DATA_DIR / "claude_cache.json"


def compute_config_hash():
    """Compute hash of keywords and research description files."""
    hasher = hashlib.md5()
    for filename in ["keywords.txt", "research_description.txt"]:
        path = DATA_DIR / filename
        if path.exists():
            hasher.update(path.read_bytes())
    return hasher.hexdigest()[:12]


def load_cache():
    """Load cached Claude scores, invalidating if config changed."""
    if not CACHE_FILE.exists():
        return {}

    with open(CACHE_FILE) as f:
        cache = json.load(f)

    # Check if config hash matches
    current_hash = compute_config_hash()
    if cache.get("_config_hash") != current_hash:
        print("  Config changed, invalidating cache")
        return {}

    return cache


def save_cache(cache):
    """Save Claude scores to cache with config hash."""
    cache["_config_hash"] = compute_config_hash()
    with open(CACHE_FILE, "w") as f:
        json.dump(cache, f, indent=2)


def load_keywords(path=None):
    """Load keywords from text file."""
    if path is None:
        path = DATA_DIR / "keywords.txt"
    if not path.exists():
        return []
    keywords = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                keywords.append(line.lower())
    return keywords


def compute_idf(papers, keywords):
    """
    Compute IDF weights for keywords based on paper corpus.

    IDF = log(N / (1 + df)) where df is number of papers containing keyword.
    """
    n_papers = len(papers)
    if n_papers == 0:
        return {kw: 1.0 for kw in keywords}

    idf = {}
    for kw in keywords:
        doc_freq = sum(
            1 for p in papers
            if kw in (p.title + " " + p.abstract).lower()
        )
        # Add 1 to avoid division by zero, use log for IDF
        idf[kw] = math.log(n_papers / (1 + doc_freq)) + 1

    return idf


def rank_by_similarity(papers, keywords=None, title_weight=3.0):
    """
    Rank papers by TF-IDF weighted keyword matches.

    Keywords appearing in fewer papers get higher weight.
    Title matches are upweighted.

    Parameters
    ----------
    papers : list of Paper
        Papers to rank.
    keywords : list of str, optional
        Keywords to match. If None, loads from default location.
    title_weight : float
        Multiplier for keywords found in title.

    Returns
    -------
    list of tuple
        (paper, score) sorted by score descending.
    """
    if keywords is None:
        keywords = load_keywords()

    if not papers or not keywords:
        return [(p, 0.0) for p in papers]

    # Compute IDF weights
    idf = compute_idf(papers, keywords)

    # Compute raw scores
    raw_scores = []
    for paper in papers:
        title = paper.title.lower()
        abstract = paper.abstract.lower()

        score = 0
        for kw in keywords:
            if kw in title:
                score += idf[kw] * title_weight
            elif kw in abstract:
                score += idf[kw]

        raw_scores.append((paper, score))

    # Normalize by max score so best paper ~ 100%
    max_score = max(s for _, s in raw_scores) if raw_scores else 1
    ranked = [
        (p, s / max_score if max_score > 0 else 0) for p, s in raw_scores
    ]

    ranked.sort(key=lambda x: x[1], reverse=True)
    return ranked


def load_research_description(path=None):
    """Load research description from text file."""
    if path is None:
        path = DATA_DIR / "research_description.txt"
    if not path.exists():
        return ""
    with open(path) as f:
        return f.read().strip()


def rank_with_claude(papers, top_n=30, model="claude-sonnet-4-20250514"):
    """
    Rank papers using Claude API.

    First filters to top_n using keyword ranking, then refines with Claude.

    Parameters
    ----------
    papers : list of Paper
        Papers to rank.
    top_n : int
        Number of top keyword-ranked papers to send to Claude.
    model : str
        Claude model to use.

    Returns
    -------
    list of tuple
        (paper, score) sorted by score descending.
    """
    if not papers:
        return [], {}, {}

    # First pass: keyword ranking
    keywords = load_keywords()
    keyword_ranked = rank_by_similarity(papers, keywords=keywords)

    # Take top N for Claude ranking
    candidates = keyword_ranked[:top_n]
    remaining = keyword_ranked[top_n:]

    if not candidates or not keywords:
        return keyword_ranked, {}, {}

    # Load cache
    cache = load_cache()

    # Split candidates into cached and uncached
    cached_papers = []
    uncached_papers = []
    for paper, kw_score in candidates:
        if paper.arxiv_id in cache:
            cached = cache[paper.arxiv_id]
            # Handle old cache format (just score) and new format (dict)
            if isinstance(cached, dict):
                score = cached.get("score", 50) / 100.0
            else:
                score = cached / 100.0
            cached_papers.append((paper, score))
        else:
            uncached_papers.append((paper, kw_score))

    print(f"  Top {len(candidates)} candidates: {len(cached_papers)} cached, "
          f"{len(uncached_papers)} new to send to Claude")

    # If all cached, skip API call
    if not uncached_papers:
        claude_ranked = cached_papers
    else:
        # Format keywords and research description for prompt
        keywords_text = ", ".join(keywords)
        research_desc = load_research_description()

        # Build prompt for uncached papers only
        papers_text = ""
        for i, (paper, _) in enumerate(uncached_papers):
            papers_text += f"\n[{i+1}] {paper.title}\n{paper.abstract[:600]}\n"

        prompt = f"""You are helping a researcher filter daily arXiv papers.
Rate each paper's relevance from 1-100%, list matching keywords,
and for papers scoring 75%+, write a one-sentence summary.

RESEARCHER'S FOCUS AREAS:
{research_desc}

RELEVANT KEYWORDS:
{keywords_text}

SCORING RUBRIC:
90-100%: Directly addresses my research, must read
70-89%: Closely related, relevant methodology
50-69%: Tangentially related, useful background
30-49%: Same broad field but different focus
1-29%: Unrelated to my research

PAPERS:
{papers_text}

Return ONLY valid JSON. Include "summary" only if score >= 75:
{{"1": {{"score": 85, "keywords": ["H0"], "summary": "..."}}, "2": ...}}"""

        # Call Claude API
        client = anthropic.Anthropic()
        response = client.messages.create(
            model=model,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}]
        )

        # Parse response
        response_text = response.content[0].text
        try:
            # Find JSON object (may be nested)
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                results_dict = json.loads(json_match.group())
            else:
                raise ValueError("No JSON found in response")
        except (json.JSONDecodeError, ValueError) as e:
            print(f"Warning: Could not parse Claude response: {e}")
            return keyword_ranked, {}, {}

        # Apply Claude scores and update cache
        claude_ranked = list(cached_papers)
        for i, (paper, kw_score) in enumerate(uncached_papers):
            result = results_dict.get(str(i + 1), {})
            if isinstance(result, dict):
                score = result.get("score", 50)
                kws = result.get("keywords", [])
                summary = result.get("summary", "")
            else:
                score = result
                kws = []
                summary = ""
            cache[paper.arxiv_id] = {
                "score": score, "keywords": kws, "summary": summary
            }
            claude_ranked.append((paper, score / 100.0))

        save_cache(cache)
        print(f"  Scored {len(uncached_papers)} papers, saved to cache")

    # Sort by Claude score
    claude_ranked.sort(key=lambda x: x[1], reverse=True)

    # Append remaining papers with lower scores
    if remaining:
        min_claude = min(s for _, s in claude_ranked) if claude_ranked else 0
        remaining_scaled = [(p, s * min_claude * 0.9) for p, s in remaining]
        claude_ranked.extend(remaining_scaled)

    # Build keywords and summaries dicts from cache
    keywords_dict = {}
    summaries_dict = {}
    for paper, _ in claude_ranked:
        cached = cache.get(paper.arxiv_id, {})
        if isinstance(cached, dict):
            keywords_dict[paper.arxiv_id] = cached.get("keywords", [])
            if cached.get("summary"):
                summaries_dict[paper.arxiv_id] = cached.get("summary")

    return claude_ranked, keywords_dict, summaries_dict
