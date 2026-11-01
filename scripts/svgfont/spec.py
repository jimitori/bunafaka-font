"""The declarative description of a font.

Everything project-specific lives in a FontSpec.  The rest of this package
turns a FontSpec into an OTF/TTF/WOFF2 and measures the result.  Keeping the
description declarative is what makes the pipeline reusable: a new script only
has to say what its signs are and how they are typed, not how OpenType works.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple


@dataclass
class Grid:
    """How the drawings' coordinate system maps onto the font's.

    Three independent facts, all read off the artwork rather than assumed:

      size      how many svg units make one em.  Usually the viewBox side,
                but only because that is how most sets are drawn.
      baseline  the svg y that becomes font y=0.
      cap       the svg y of the top reference line.  `body` is the distance
                between the two, and serves as cap height.

    `bearing` is deliberately NOT derived from any of these.  A drawing whose
    side margin happens to equal its top margin is a common layout, not a
    rule, and a font fitted on that assumption is wrong in a way that is hard
    to see.  Measure the side margin separately and set it here, or leave it
    at 0 and give each glyph its bearing explicitly.
    """
    size: float = 1000.0      # svg units per em
    baseline: float = 1000.0  # svg y that becomes y=0
    cap: float = 0.0          # svg y of the top reference line
    upm: int = 1000
    bearing: int = 0          # default side bearing, in font units

    @property
    def scale(self) -> float:
        return self.upm / self.size

    @property
    def body(self) -> int:
        """Distance between the reference lines, in font units."""
        return round((self.baseline - self.cap) * self.scale)

    def x(self, svg_x: float) -> float:
        return svg_x * self.scale

    def y(self, svg_y: float) -> float:
        return (self.baseline - svg_y) * self.scale


@dataclass
class Vertical:
    ascender: int = 1000          # hhea
    descender: int = -250
    typo_ascender: Optional[int] = None    # defaults to Grid.body
    typo_descender: Optional[int] = None
    typo_line_gap: int = 150
    win_ascent: Optional[int] = None
    win_descent: Optional[int] = None


@dataclass
class Glyph:
    """One glyph.  `inputs` are the typed glyph-name sequences that collapse
    into it; the builder sorts them longest-first so the greedy match works."""
    name: str
    svg: Optional[str] = None            # path to the drawing; None = blank
    advance: int = 0
    shift_x: float = 0.0                 # move the ink before fitting
    inputs: List[List[str]] = field(default_factory=list)


@dataclass
class ContextRule:
    """A chaining contextual substitution, run before the ligatures.

    This is how you stop a greedy longest match from making the wrong choice.
    The classic case: a unit that can both end one sign and begin the next.
    Swap it for a clone that the closing ligatures do not list, and the
    ligature pass is forced into the other reading.  See references/features.md.
    """
    backtrack: List[List[str]] = field(default_factory=list)
    input: List[List[str]] = field(default_factory=list)
    lookahead: List[List[str]] = field(default_factory=list)
    replace: Dict[str, str] = field(default_factory=dict)
    comment: str = ""


@dataclass
class FontSpec:
    family: str
    style: str = "Regular"
    version: str = "1.000"
    designer: str = ""
    description: str = ""
    vendor: str = "NONE"

    grid: Grid = field(default_factory=Grid)
    vertical: Vertical = field(default_factory=Vertical)

    glyphs: List[Glyph] = field(default_factory=list)
    cmap: Dict[int, str] = field(default_factory=dict)

    # substitutions that run before the ligature pass
    context_rules: List[ContextRule] = field(default_factory=list)

    # class kerning.  The classes on each side must not overlap, or the pair
    # table is ambiguous; validate() checks this for you.
    kern_left: Dict[str, List[str]] = field(default_factory=dict)
    kern_right: Dict[str, List[str]] = field(default_factory=dict)
    kern: List[Tuple[str, str, int]] = field(default_factory=list)

    # a plain text face to lift Latin letterforms from, so that input
    # characters the ligatures did not consume still show something
    latin_fallback: Optional[str] = None
    latin_chars: Dict[str, str] = field(default_factory=dict)   # char -> glyph
    latin_extra: Dict[str, int] = field(default_factory=dict)   # glyph -> codepoint

    notdef_advance: int = 600

    @property
    def ps_name(self) -> str:
        return f"{self.family}-{self.style}".replace(" ", "")

    def by_name(self) -> Dict[str, Glyph]:
        return {g.name: g for g in self.glyphs}

    def validate(self) -> List[str]:
        """Return a list of problems.  Cheap to run, and catches the mistakes
        that otherwise show up as a silently wrong font."""
        problems = []
        seen = set()
        for g in self.glyphs:
            if g.name in seen:
                problems.append(f"duplicate glyph name {g.name!r}")
            seen.add(g.name)
            if not _valid_ps_name(g.name):
                problems.append(f"{g.name!r} is not a legal PostScript name")
        for cp, name in self.cmap.items():
            if name not in seen:
                problems.append(f"cmap U+{cp:04X} points at missing glyph {name!r}")
        for side, classes in (("left", self.kern_left), ("right", self.kern_right)):
            members = {}
            for cname, names in classes.items():
                for n in names:
                    if n in members:
                        problems.append(
                            f"{n!r} is in two {side} kern classes: "
                            f"{members[n]} and {cname}")
                    members[n] = cname
                    if n not in seen:
                        problems.append(f"kern class {cname} lists missing glyph {n!r}")
        for left, right, _v in self.kern:
            if left not in self.kern_left:
                problems.append(f"kern rule uses undefined left class {left!r}")
            if right not in self.kern_right:
                problems.append(f"kern rule uses undefined right class {right!r}")
        for g in self.glyphs:
            for seq in g.inputs:
                for part in seq:
                    if part not in seen:
                        problems.append(
                            f"{g.name}: input sequence uses missing glyph {part!r}")
        return problems


_ALLOWED = set("ABCDEFGHIJKLMNOPQRSTUVWXYZ"
               "abcdefghijklmnopqrstuvwxyz0123456789._")


def _valid_ps_name(name: str) -> bool:
    if not name or len(name) > 63:
        return False
    if name[0].isdigit() or name[0] == ".":
        return name in (".notdef", ".null")
    return set(name) <= _ALLOWED


def ascii_name(text: str, translit: Optional[Dict[str, str]] = None) -> str:
    """Turn a source file name into a legal PostScript glyph name.

    Non-ASCII letters have to go somewhere; pass a transliteration map so the
    result stays readable (Č -> Ch beats uni010C when you open FontForge).
    """
    table = dict(translit or {})
    out = []
    for ch in text:
        if ch in table:
            out.append(table[ch])
        elif ch in _ALLOWED:
            out.append(ch)
        elif ch == "-":
            out.append("_")
        else:
            out.append("uni%04X" % ord(ch))
    name = "".join(out)
    if name and (name[0].isdigit() or name[0] == "."):
        name = "_" + name
    return name


def sequence(text: str, char_glyph: Dict[str, str]) -> List[str]:
    """Map a typed string to the glyph names its characters produce."""
    return [char_glyph[ch] for ch in text]
