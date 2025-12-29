#!/bin/bash
# CatchArXiv launcher script

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

source "$PROJECT_DIR/venv_arxiv/bin/activate"
python "$SCRIPT_DIR/fetch_papers.py" "$@"
