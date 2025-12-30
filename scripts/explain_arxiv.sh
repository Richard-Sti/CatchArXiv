#!/bin/bash -l
# Explain an arXiv paper using Claude Code
# Usage: ./explain_arxiv.sh <arxiv_url_or_id>

set -e

if [ -z "$1" ]; then
    echo "Usage: $0 <arxiv_url_or_id>"
    echo "Example: $0 2312.12345"
    echo "Example: $0 https://arxiv.org/abs/2312.12345"
    exit 1
fi

# Extract arXiv ID from URL or use directly
ARXIV_ID=$(echo "$1" | grep -oE '[0-9]{4}\.[0-9]{4,5}(v[0-9]+)?' | head -1)

if [ -z "$ARXIV_ID" ]; then
    echo "Error: Could not parse arXiv ID from: $1"
    exit 1
fi

echo "arXiv ID: $ARXIV_ID"

# Create directory named after arXiv ID in current working directory
WORKDIR="$(pwd)/explain_$ARXIV_ID"
mkdir -p "$WORKDIR"
cd "$WORKDIR"

# Download source if not already present
if [ ! -f combined.tex ]; then
    echo "Downloading source..."
    curl -sL "https://arxiv.org/e-print/$ARXIV_ID" -o source.tar.gz

    # Check if it's a tarball or single file
    if file source.tar.gz | grep -q "gzip"; then
        tar -xzf source.tar.gz 2>/dev/null || gunzip -c source.tar.gz > main.tex
    elif file source.tar.gz | grep -q "tar"; then
        tar -xf source.tar.gz
    else
        mv source.tar.gz main.tex
    fi

    # Find main tex file (look for \documentclass)
    MAIN_TEX=$(grep -l '\\documentclass' *.tex 2>/dev/null | head -1)

    if [ -z "$MAIN_TEX" ]; then
        MAIN_TEX=$(ls *.tex 2>/dev/null | head -1)
    fi

    if [ -z "$MAIN_TEX" ]; then
        echo "Error: No .tex file found"
        exit 1
    fi

    echo "Main TeX file: $MAIN_TEX"

    # Combine all tex files for context
    echo "Preparing paper content..."
    cat *.tex > combined.tex 2>/dev/null || cat "$MAIN_TEX" > combined.tex
else
    echo "Using existing downloaded source."
fi

OUTPUT="$WORKDIR/explanation.md"

echo "Generating explanation..."

PROMPT="I'm giving you the LaTeX source of arXiv:$ARXIV_ID.

I want to understand this paper BEFORE reading it in detail. Act as an expert colleague explaining the paper to me.

## Instructions

Provide a structured explanation covering:

### 1. Authors
List up to 10 authors (first name, last name). If more than 10, list the first 10 and note how many more.

### 2. One-paragraph summary
What is this paper about? What problem does it solve? What's the main result?

### 3. Background & Motivation
- What's the scientific context?
- What gap in knowledge does this address?
- Why should I care about this?

### 4. Key Methods
- What techniques/data do they use?
- What's novel about their approach?
- Any important assumptions or limitations?

### 5. Main Results
- What are the key findings? (Be specific with numbers if available)
- What figures/tables are most important?

### 6. Takeaways
- What should I remember from this paper?
- How does it fit into the broader field?
- Any caveats or controversies?

### 7. Terms to know
List any jargon, acronyms, or technical terms I should understand before reading.

Be concise but thorough. Use bullet points. Assume I'm a scientist but maybe not in this exact subfield.

IMPORTANT: Save your explanation to: $OUTPUT

After completing the explanation, wait for my questions. I may ask follow-up questions about specific sections, methods, or concepts. Answer them based on the paper content.

Here's the paper:

$(cat combined.tex)"

# Run Claude Code (use Max subscription, not API key)
echo ""
unset ANTHROPIC_API_KEY
claude "$PROMPT"

echo ""
echo "==========================================="
echo "Explanation saved to: $OUTPUT"
echo "==========================================="
