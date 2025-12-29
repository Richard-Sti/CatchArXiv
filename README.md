# CatchArXiv

Daily arXiv paper recommendations with keyword and Claude AI ranking.

## How it works

CatchArXiv fetches papers from the arXiv API and ranks them by relevance to your research. It supports two ranking modes:

### Keyword ranking (`--rank`)

Fast, local ranking using TF-IDF (Term Frequency-Inverse Document Frequency):

1. **Build corpus**: Combines title + abstract of all fetched papers
2. **Compute IDF weights**: Uses scikit-learn's `TfidfVectorizer` to learn which terms are rare across the corpus. Rare keywords get higher weights.
3. **Match keywords**: For each paper, counts occurrences of your keywords using:
   - Word boundary matching via regex (`\bkeyword\b`) to avoid partial matches
   - Automatic expansion to plurals (`velocity` → `velocities`) and hyphenation variants (`Type Ia` ↔ `Type-Ia`)
4. **Score**: `score = Σ (1 + count) × IDF × weight` where title matches get 3× weight
5. **Normalize**: Scores scaled so top paper = 100%

### Claude ranking (`--claude`)

AI-powered ranking using Claude to understand research relevance:

1. **Pre-filter**: Runs keyword ranking first, takes top N candidates (default 100)
2. **Build prompt**: Sends your research description, keywords, and paper abstracts to Claude
3. **Score**: Claude rates each paper 1-100% based on semantic relevance to your research
4. **Extract metadata**: Claude returns matching keywords and one-sentence summaries for papers ≥75%
5. **Cache**: Results cached by arXiv ID; cache invalidates automatically if you change `keywords.txt` or `research_description.txt`

### Output

Papers displayed in browser with:
- Tabs by category (astro-ph.CO, GA, IM)
- Percentage relevance scores with absolute ranking
- Matching keywords shown as tags (Claude mode)
- One-sentence summaries for top papers (Claude mode)
- Direct PDF links

## Installation

```bash
cd /Users/rstiskalek/Projects/CatchArXiv
python -m venv venv_arxiv
source venv_arxiv/bin/activate
pip install -e .
```

## Configuration

Create `data/` directory with:

**`data/keywords.txt`** - Keywords to match (one per line):
```
Hubble constant
peculiar velocity
Tully-Fisher
BORG
constrained simulation
```

**`data/research_description.txt`** - Your research focus:
```
My research focuses on measuring the Hubble constant using the
distance ladder with careful treatment of selection effects...
```

**`scripts/.env`** - Required configuration:
```
ANTHROPIC_API_KEY=sk-ant-...                         # for --claude mode
CATCHARXIV_OUTPUT_DIR=~/Downloads                    # where to save HTML
CATCHARXIV_CATEGORIES=astro-ph.CO,astro-ph.GA,astro-ph.IM  # arXiv categories
```

## Usage

```bash
# Add to ~/.zshrc
alias catch_arxiv='/Users/rstiskalek/Projects/CatchArXiv/scripts/catcharxiv.sh'
```

```bash
catch_arxiv                    # latest arXiv announcement
catch_arxiv --rank             # rank by keywords
catch_arxiv --claude           # rank with Claude AI
catch_arxiv --claude --sonnet  # use Sonnet model (default: Haiku)
catch_arxiv --days 7           # last 7 days instead of latest
catch_arxiv --clear-cache      # clear Claude score cache
```

## Output

HTML saved to `$CATCHARXIV_OUTPUT_DIR/catcharxiv_<date>_<method>.html` and opened in browser.

## Author

Richard Stiskalek (richard.stiskalek@protonmail.com)
