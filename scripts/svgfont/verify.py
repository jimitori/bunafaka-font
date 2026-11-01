"""Check that the built font actually behaves.

Two kinds of check, and both are worth having:

  shape()  -- run text through HarfBuzz and compare the glyph names you get
              against the ones you meant.  This is the only way to catch a
              ligature that lost a race with a longer one, or a contextual
              rule that fires in the wrong place.  Cheap, exact, and it turns
              every ambiguity you reasoned about into a permanent assertion.

  audit()  -- structural sanity: nothing above the writing line, side
              bearings where the class says they should be, every glyph that
              is supposed to have ink actually has some.
"""

from typing import Callable, Dict, List, Optional, Sequence, Tuple

from fontTools.pens.boundsPen import BoundsPen
from fontTools.ttLib import TTFont


class Shaper:
    def __init__(self, path: str):
        import uharfbuzz as hb
        self._hb = hb
        blob = hb.Blob.from_file_path(path)
        face = hb.Face(blob)
        self.font = hb.Font(face)

    def shape(self, text: str) -> Tuple[List[str], List[int]]:
        buf = self._hb.Buffer()
        buf.add_str(text)
        buf.guess_segment_properties()
        self._hb.shape(self.font, buf)
        names = [self.font.glyph_to_string(i.codepoint)
                 for i in buf.glyph_infos]
        advances = [p.x_advance for p in buf.glyph_positions]
        return names, advances


def run_cases(path: str, cases: Sequence[Tuple[str, List[str]]],
              verbose: bool = True) -> int:
    """Return the number of failures.  Cases are (typed text, glyph names)."""
    shaper = Shaper(path)
    fails = 0
    for text, expect in cases:
        got, _ = shaper.shape(text)
        ok = got == expect
        if not ok:
            fails += 1
        if verbose or not ok:
            line = f"{'ok  ' if ok else 'FAIL'}  {text:<14} -> {' '.join(got)}"
            if not ok:
                line += f"   (expected {' '.join(expect)})"
            print(line)
    print(f"\n{len(cases) - fails}/{len(cases)} passed")
    return fails


def audit(path: str, expect_lsb: Optional[Dict[str, int]] = None,
          ceiling: Optional[int] = None,
          must_have_ink: Optional[Sequence[str]] = None) -> List[str]:
    """Structural problems, as a list of human-readable strings."""
    font = TTFont(path)
    gs = font.getGlyphSet()
    hmtx = font["hmtx"]
    problems = []

    for name in font.getGlyphOrder():
        bp = BoundsPen(gs)
        gs[name].draw(bp)
        if bp.bounds is None:
            if must_have_ink and name in must_have_ink:
                problems.append(f"{name}: no outline")
            continue
        x0, _y0, _x1, y1 = bp.bounds
        if ceiling is not None and y1 > ceiling + 0.5:
            problems.append(f"{name}: rises to {round(y1)}, above {ceiling}")
        if expect_lsb and name in expect_lsb:
            want = expect_lsb[name]
            if round(x0) != want:
                problems.append(
                    f"{name}: left bearing {round(x0)}, expected {want}")
        if hmtx[name][0] <= 0 and name != ".notdef":
            problems.append(f"{name}: zero advance")
    return problems


def describe(path: str) -> str:
    """One-paragraph summary of what ended up in the font."""
    font = TTFont(path)
    lines = [f"{path}",
             f"  glyphs {font['maxp'].numGlyphs}"
             f"  upm {font['head'].unitsPerEm}"
             f"  cmap {len(font.getBestCmap())}"]
    for tag in ("GSUB", "GPOS"):
        if tag not in font:
            continue
        t = font[tag].table
        feats = sorted({r.FeatureTag for r in t.FeatureList.FeatureRecord})
        lines.append(f"  {tag} features {feats}"
                     f"  lookups {len(t.LookupList.Lookup)}")
    return "\n".join(lines)
