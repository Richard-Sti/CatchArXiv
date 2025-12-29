#!/usr/bin/env python
"""Fetch recent arXiv papers and display in browser."""
import argparse
import os
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
    parser.add_argument("--days", type=int, default=None,
                        help="Days to look back (overrides --new)")
    parser.add_argument("--rank", action="store_true",
                        help="Rank by keyword similarity")
    parser.add_argument("--claude", action="store_true",
                        help="Rank using Claude API")
    parser.add_argument("--model", default="haiku",
                        choices=["haiku", "sonnet"],
                        help="Claude model to use (default: haiku)")
    parser.add_argument("--top-n", type=int, default=100,
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
    }

    categories = ("astro-ph.CO", "astro-ph.GA", "astro-ph.IM")

    # Default: fetch latest announcement (like arXiv/new)
    # --days N overrides to fetch N days instead
    use_new = args.days is None
    fetch_days = 5 if use_new else args.days

    if use_new:
        print("Fetching latest arXiv announcement...")
    else:
        print(f"Fetching papers from the last {fetch_days} day(s)...")

    papers = fetch_recent_papers(categories=categories, days=fetch_days)

    # Filter to only the most recent announcement date
    if use_new and papers:
        latest_date = max(p.published.date() for p in papers)
        papers = [p for p in papers if p.published.date() == latest_date]
        print(f"Found {len(papers)} papers from {latest_date}")
    else:
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

    # Get date for title
    if papers:
        paper_date = max(p.published.date() for p in papers)
    else:
        paper_date = None

    if args.claude:
        print(f"Ranking with Claude API ({args.model})...")
        ranked, keywords_dict, summaries_dict = rank_with_claude(
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
            keywords=keywords_dict,
            summaries=summaries_dict,
            days=fetch_days,
            rank_method="Claude",
            paper_date=paper_date,
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
            days=fetch_days,
            rank_method="Keywords",
            paper_date=paper_date,
        )
    else:
        template = env.get_template("index.html")
        html = template.render(
            papers=papers,
            papers_by_cat=papers_by_cat,
            categories=categories,
            days=fetch_days,
        )

    # Build filename based on options
    if use_new and paper_date:
        date_str = paper_date.strftime("%Y-%m-%d")
    else:
        date_str = f"last_{fetch_days}d"

    if args.claude:
        method = "claude"
    elif args.rank:
        method = "keywords"
    else:
        method = "unranked"

    filename = f"catcharxiv_{date_str}_{method}.html"
    output_file = Path.home() / "Downloads" / filename
    output_file.write_text(html)
    print(f"Saved to {output_file}")
    webbrowser.open(f"file://{output_file}")


if __name__ == "__main__":
    main()
