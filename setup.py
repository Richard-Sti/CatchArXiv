from setuptools import setup, find_packages

setup(
    name="catcharxiv",
    version="0.1.0",
    description="Daily arXiv paper recommendations using Claude API",
    author="Richard Stiskalek",
    author_email="richard.stiskalek@physics.ox.ac.uk",
    url="https://github.com/rstiskalek/catcharxiv",
    packages=find_packages(exclude=["venv_arxiv"]),
    python_requires=">=3.10",
    install_requires=[
        "arxiv",
        "anthropic",
        "jinja2",
    ],
)
