"""Write module — article generation utilities.

- extract_figures: crop paper PDF figures and upload to WeChat CDN
- formula_render: render LaTeX formulas to WeChat CDN images
- generate_covers: generate WeChat article cover images
"""

from .extract_figures import process_paper, replace_figure_in_article
from .formula_render import process_article as render_formulas, render_formulas_in_article
from .generate_covers import generate_cover, generate_all_covers

__all__ = [
    "process_paper",
    "replace_figure_in_article",
    "render_formulas",
    "render_formulas_in_article",
    "generate_cover",
    "generate_all_covers",
]
