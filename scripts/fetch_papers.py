#!/usr/bin/env python
"""Fetch recent arXiv papers and display in browser."""
import argparse
import os
import tempfile
import webbrowser
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from catcharxiv import (
    fetch_recent_papers, rank_by_similarity, rank_with_claude
)


def load_env():
    """Load environment variables from .env file."""
    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ[key.strip()] = value.strip()


def main():
    load_env()
    parser = argparse.ArgumentParser(description="Fetch recent arXiv papers")
    parser.add_argument("--days", type=int, default=10,
                        help="Days to look back")
    parser.add_argument("--rank", action="store_true",
                        help="Rank by keyword similarity")
    parser.add_argument("--claude", action="store_true",
                        help="Rank using Claude API")
    parser.add_argument("--model", default="haiku",
                        choices=["haiku", "sonnet", "opus"],
                        help="Claude model to use (default: haiku)")
    parser.add_argument("--top-n", type=int, default=50,
                        help="Number of top papers to send to Claude")
    parser.add_argument("--clear-cache", action="store_true",
                        help="Clear Claude score cache")
    args = parser.parse_args()

    if args.clear_cache:
        data_dir = Path(__file__).parent.parent / "data"
        cache_file = data_dir / "claude_cache.json"
        if cache_file.exists():
            cache_file.unlink()
            print("Cache cleared")
        else:
            print("No cache to clear")
        return

    model_map = {
        "haiku": "claude-3-5-haiku-latest",
        "sonnet": "claude-sonnet-4-20250514",
        # "opus": "claude-opus-4-20250514",
    }

    categories = ("astro-ph.CO", "astro-ph.GA", "astro-ph.IM")

    print(f"Fetching papers from the last {args.days} days...")
    papers = fetch_recent_papers(categories=categories, days=args.days)
    print(f"Found {len(papers)} papers")

    templates_dir = Path(__file__).parent.parent / "catcharxiv" / "templates"
    env = Environment(
        loader=FileSystemLoader(templates_dir),
        autoescape=select_autoescape(["html"]),
    )

    # Group papers by primary matching category
    papers_by_cat = {cat: [] for cat in categories}
    for paper in papers:
        for cat in categories:
            if cat in paper.categories:
                papers_by_cat[cat].append(paper)
                break

    if args.claude:
        print(f"Ranking with Claude API ({args.model})...")
        ranked = rank_with_claude(
            papers, top_n=args.top_n, model=model_map[args.model]
        )
        scores = {p.arxiv_id: s for p, s in ranked}

        for cat in categories:
            papers_by_cat[cat].sort(
                key=lambda p: scores.get(p.arxiv_id, 0), reverse=True
            )

        template = env.get_template("ranked.html")
        html = template.render(
            papers=papers,
            papers_by_cat=papers_by_cat,
            categories=categories,
            scores=scores,
            days=args.days,
            rank_method="Claude",
        )
    elif args.rank:
        print("Ranking by keywords...")
        ranked = rank_by_similarity(papers)
        scores = {p.arxiv_id: s for p, s in ranked}

        for cat in categories:
            papers_by_cat[cat].sort(
                key=lambda p: scores.get(p.arxiv_id, 0), reverse=True
            )

        template = env.get_template("ranked.html")
        html = template.render(
            papers=papers,
            papers_by_cat=papers_by_cat,
            categories=categories,
            scores=scores,
            days=args.days,
            rank_method="Keywords",
        )
    else:
        template = env.get_template("index.html")
        html = template.render(
            papers=papers,
            papers_by_cat=papers_by_cat,
            categories=categories,
            days=args.days,
        )

    # Write to temp file and open in browser
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".html", delete=False
    ) as f:
        f.write(html)
        webbrowser.open(f"file://{f.name}")


if __name__ == "__main__":
    main()
