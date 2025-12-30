#!/bin/bash -l
# Critique an arXiv paper using Claude Code (with iterative versioning)
# Usage: ./critique_arxiv.sh <arxiv_url_or_id>

set -e

if [ -z "$1" ]; then
    echo "Usage: $0 <arxiv_url_or_id>"
    echo "Example: $0 2312.12345"
    echo "Example: $0 https://arxiv.org/abs/2312.12345"
    echo ""
    echo "First run: downloads paper, generates critique_v1.md, creates feedback_v1.md"
    echo "Add your feedback to feedback_v1.md, then run again for critique_v2.md, etc."
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
WORKDIR="$(pwd)/critique_$ARXIV_ID"
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

# Determine current version
VERSION=1
while [ -f "$WORKDIR/v${VERSION}_critique.md" ]; do
    VERSION=$((VERSION + 1))
done

OUTPUT="$WORKDIR/v${VERSION}_critique.md"
FEEDBACK="$WORKDIR/v${VERSION}_feedback.md"
NEXT_VERSION=$((VERSION + 1))
NEXT_OUTPUT="$WORKDIR/v${NEXT_VERSION}_critique.md"
NEXT_FEEDBACK="$WORKDIR/v${NEXT_VERSION}_feedback.md"

echo "Generating critique version $VERSION..."

# Build context from previous versions
PREV_CONTEXT=""
for ((v=1; v<VERSION; v++)); do
    PREV_CRITIQUE="$WORKDIR/v${v}_critique.md"
    PREV_FEEDBACK="$WORKDIR/v${v}_feedback.md"

    if [ -f "$PREV_CRITIQUE" ]; then
        PREV_CONTEXT="${PREV_CONTEXT}

## Previous Critique (v${v})

$(cat "$PREV_CRITIQUE")
"
    fi

    if [ -f "$PREV_FEEDBACK" ] && [ -s "$PREV_FEEDBACK" ]; then
        # Check if feedback file has content beyond the template
        if grep -qv "^#\|^$\|^\[" "$PREV_FEEDBACK" 2>/dev/null; then
            PREV_CONTEXT="${PREV_CONTEXT}

## Feedback on v${v} Review

$(cat "$PREV_FEEDBACK")
"
        fi
    fi
done

# Build the prompt
if [ "$VERSION" -eq 1 ]; then
    PROMPT="I'm giving you the LaTeX source of arXiv:$ARXIV_ID.

Act as a harsh but constructive referee for a top journal (MNRAS/ApJ level).

## Instructions

Perform a TWO-PASS review:

### PASS 1: Section-by-section analysis

Go through each major section (Abstract, Introduction, Methods, Results, Discussion, Conclusions) one by one. For each section, critique:
- Scientific accuracy and methodology
- Statistical rigour and uncertainty quantification
- Clarity of writing and logical flow
- Missing elements or gaps

### PASS 2: Holistic assessment

After analyzing all sections, step back and evaluate the paper as a whole:
- Does the narrative flow logically from introduction to conclusions?
- Are the conclusions actually supported by the results presented?
- Is there internal consistency (do different sections contradict each other)?
- Are there any overreaching claims given the evidence?
- What are the major vs minor issues?

Be specific. Quote problematic passages. Suggest concrete improvements.

IMPORTANT: Save your complete critique to: $OUTPUT

After completing the critique, wait for my input. If I say 'next iteration' or 'run again':
1. Read my feedback from $FEEDBACK - this contains my comments on your review (e.g. areas you missed, things to focus on more, corrections to your critique)
2. Re-read the paper with fresh eyes, incorporating my feedback
3. Produce a NEW and IMPROVED critique that:
   - Addresses the specific points I raised in my feedback
   - Fixes any errors or oversights I pointed out
   - Expands on areas I asked you to focus on
   - Maintains the same rigorous referee standard
4. Save the new critique to $NEXT_OUTPUT
5. Create a new empty feedback file at $NEXT_FEEDBACK

Here's the paper:

$(cat combined.tex)"
else
    PROMPT="I'm giving you the LaTeX source of arXiv:$ARXIV_ID along with previous review iterations.

Act as a harsh but constructive referee for a top journal (MNRAS/ApJ level).

## Previous Review History
${PREV_CONTEXT}

## Instructions for This Round (v${VERSION})

Review the paper again, incorporating the feedback on your previous review. The feedback tells you what to focus on, what you missed, or how to improve your critique.

Focus on:
- Address any gaps or issues pointed out in the feedback
- Look deeper at areas the feedback highlights
- Provide a more thorough or refined critique based on the guidance
- Any new issues you notice on this pass

Be specific. Quote problematic passages. Suggest concrete improvements.

IMPORTANT: Save your complete critique to: $OUTPUT

After completing the critique, wait for my input. If I say 'next iteration' or 'run again':
1. Read my feedback from $FEEDBACK - this contains my comments on your review (e.g. areas you missed, things to focus on more, corrections to your critique)
2. Re-read the paper with fresh eyes, incorporating my feedback
3. Produce a NEW and IMPROVED critique that:
   - Addresses the specific points I raised in my feedback
   - Fixes any errors or oversights I pointed out
   - Expands on areas I asked you to focus on
   - Maintains the same rigorous referee standard
4. Save the new critique to $NEXT_OUTPUT
5. Create a new empty feedback file at $NEXT_FEEDBACK

Here's the paper:

$(cat combined.tex)"
fi

# Create feedback file for this version (before running Claude)
cat > "$FEEDBACK" << 'EOF'
# Feedback for next review iteration

EOF

# Run Claude Code critique (use Max subscription, not API key)
echo ""
unset ANTHROPIC_API_KEY
claude  "$PROMPT"

echo ""
echo "==========================================="
echo "Critique saved to: $OUTPUT"
echo "Feedback file created: $FEEDBACK"
echo ""
echo "To generate the next version:"
echo "  1. Edit $FEEDBACK with your feedback"
echo "  2. Run: $0 $ARXIV_ID"
echo "==========================================="
