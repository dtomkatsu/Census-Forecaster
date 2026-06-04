"""scripts/brief — modular poverty-impact brief generation.

Modules:
    data          — BriefData, constants, formatting utilities, data loading
    charts        — matplotlib figure generation (PNG)
    pdf_renderer  — fpdf2 PDF assembly
    html_renderer — self-contained HTML fallback

Typical usage::

    from brief.data import load_brief_data
    from brief.charts import make_figures
    from brief.pdf_renderer import build_pdf
    from brief.html_renderer import build_html
"""

from .data import BriefData, load_brief_data
from .charts import make_figures
from .pdf_renderer import build_pdf
from .html_renderer import build_html

__all__ = ["BriefData", "load_brief_data", "make_figures", "build_pdf", "build_html"]
