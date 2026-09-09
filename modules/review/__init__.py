"""Review module — fact-check articles against their source papers.

- review_article: review a single article against its source paper PDF
- review_all: review all articles in the data/articles/ directory
"""

from .reviewer import review_article, review_all

__all__ = ["review_article", "review_all"]
