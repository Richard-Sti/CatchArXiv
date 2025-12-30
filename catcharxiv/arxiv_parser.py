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
"""arXiv paper fetcher for recent submissions."""

import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import arxiv
import feedparser


@dataclass
class Paper:
    """Container for arXiv paper metadata."""
    arxiv_id: str
    title: str
    abstract: str
    authors: list[str]
    categories: list[str]
    published: datetime
    url: str

    def __str__(self):
        authors_str = ", ".join(self.authors[:3])
        if len(self.authors) > 3:
            authors_str += " et al."
        return (f"{self.title}\n  {authors_str}\n  "
                f"{self.arxiv_id} | {self.published.date()}")


def fetch_recent_papers(
    categories=("astro-ph.CO", "astro-ph.GA", "astro-ph.IM"),
    days=3,
):
    """
    Fetch recent arXiv papers from specified categories.

    Parameters
    ----------
    categories : tuple of str
        arXiv category identifiers to search.
    days : int
        Number of days to look back.

    Returns
    -------
    list of Paper
        Deduplicated papers sorted by publication date (newest first).
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    seen_ids = set()
    papers = []
    categories_set = set(categories)

    client = arxiv.Client()

    # Build OR query for all categories to catch cross-lists
    query = " OR ".join(f"cat:{cat}" for cat in categories)
    search = arxiv.Search(
        query=query,
        sort_by=arxiv.SortCriterion.SubmittedDate,
        sort_order=arxiv.SortOrder.Descending,
    )

    for result in client.results(search):
        if result.published < cutoff:
            break

        # Check if paper has any of our target categories
        if not categories_set.intersection(result.categories):
            continue

        arxiv_id = result.entry_id.split("/")[-1]
        if arxiv_id in seen_ids:
            continue
        seen_ids.add(arxiv_id)

        paper = Paper(
            arxiv_id=arxiv_id,
            title=result.title.replace("\n", " "),
            abstract=result.summary.replace("\n", " "),
            authors=[a.name for a in result.authors],
            categories=result.categories,
            published=result.published,
            url=result.entry_id,
        )
        papers.append(paper)

    # Sort by publication date, newest first
    papers.sort(key=lambda p: p.published, reverse=True)
    return papers


def fetch_new_papers(categories=("astro-ph.CO", "astro-ph.GA", "astro-ph.IM")):
    """
    Fetch today's new arXiv papers from RSS feeds.

    Uses RSS to get exact announcement list, then fetches full metadata via API.

    Parameters
    ----------
    categories : tuple of str
        arXiv category identifiers to fetch.

    Returns
    -------
    list of Paper
        Papers from today's announcement, deduplicated.
    """
    seen_ids = set()
    all_ids = []

    # Fetch RSS for each category
    for cat in categories:
        feed_url = f"https://rss.arxiv.org/rss/{cat}"
        feed = feedparser.parse(feed_url)

        for entry in feed.entries:
            # Include new submissions and cross-lists, but not replacements
            announce_type = getattr(entry, 'arxiv_announce_type', '')
            if announce_type not in ('new', 'cross'):
                continue

            # Extract arXiv ID from link
            # Link format: http://arxiv.org/abs/2512.22356v1
            match = re.search(r'(\d{4}\.\d{4,5})(v\d+)?', entry.link)
            if match:
                arxiv_id = match.group(1)
                if arxiv_id not in seen_ids:
                    seen_ids.add(arxiv_id)
                    all_ids.append(arxiv_id)

    if not all_ids:
        return []

    # Fetch full metadata via API
    client = arxiv.Client()
    search = arxiv.Search(id_list=all_ids)

    papers = []
    categories_set = set(categories)

    for result in client.results(search):
        # Check if paper has any of our target categories
        if not categories_set.intersection(result.categories):
            continue

        arxiv_id = result.entry_id.split("/")[-1]
        # Remove version suffix for consistency
        arxiv_id = re.sub(r'v\d+$', '', arxiv_id)

        paper = Paper(
            arxiv_id=arxiv_id,
            title=result.title.replace("\n", " "),
            abstract=result.summary.replace("\n", " "),
            authors=[a.name for a in result.authors],
            categories=result.categories,
            published=result.published,
            url=result.entry_id,
        )
        papers.append(paper)

    # Sort by arxiv_id (newer IDs first)
    papers.sort(key=lambda p: p.arxiv_id, reverse=True)
    return papers


if __name__ == "__main__":
    papers = fetch_new_papers()
    print(f"Found {len(papers)} papers from today's announcement:\n")
    for p in papers[:10]:
        print(p)
        print()
