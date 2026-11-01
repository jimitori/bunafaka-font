"""svgfont -- turn a folder of SVG drawings into an OpenType font.

The pipeline is: describe the writing system as a FontSpec, hand it to
build.build(), then measure and shape-test the result.  Nothing here knows
anything about any particular script; all of that lives in the spec you write
for the project.

    from svgfont import build, feature, measure, outline, preview, verify
    from svgfont.spec import FontSpec, Glyph, Grid, ContextRule
"""

from . import build, feature, measure, outline, preview, spec, verify   # noqa: F401
from .spec import ContextRule, FontSpec, Glyph, Grid, Vertical, ascii_name  # noqa: F401

__all__ = ["build", "feature", "measure", "outline", "preview", "spec",
           "verify", "FontSpec", "Glyph", "Grid", "Vertical", "ContextRule",
           "ascii_name"]
