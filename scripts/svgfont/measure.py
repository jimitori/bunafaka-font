"""Measure drawings and built fonts.

Fitting decisions should come from the artwork, not from a guess.  These
helpers give you the numbers: where the reference lines are, how far ink pokes
out of the box, how much of each edge carries ink, and -- the one that
actually matters for spacing -- the true visual gap between two adjacent signs
at the heights where both of them have ink.

A bounding box is not enough for that last one.  A thin stroke projecting at
mid height only crowds the next sign if the next sign has ink at mid height
too.

Nothing here knows what any measurement means.  Producing the numbers and the
groupings is this module's job; interpreting them belongs to the design.
"""

import os
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

from fontTools.pens.recordingPen import RecordingPen

from . import outline


# --------------------------------------------------------------------------
# drawings
# --------------------------------------------------------------------------

def ink_bounds(svg_path: str) -> Tuple[float, float, float, float]:
    """xmin, ymin, xmax, ymax of a drawing, in svg units."""
    xs, ys = [], []
    for sp in outline.load(svg_path):
        for seg in sp:
            for i in range(9):
                p = seg.point(i / 8)
                xs.append(p.real)
                ys.append(p.imag)
    return min(xs), min(ys), max(xs), max(ys)


def reference_lines(svg_path: str) -> Tuple[float, float]:
    """Read the two vertical reference lines off one drawing: (cap, baseline).

    Pick a drawing that stays inside the intended box on every side -- nothing
    hanging below, nothing reaching past an edge.  Its ink top and bottom are
    the lines, and everything else in the set is fitted relative to it.  Doing
    it this way rather than from an average over the folder keeps signs with
    descenders or projections from dragging the baseline off.
    """
    _x0, y0, _x1, y1 = ink_bounds(svg_path)
    return y0, y1


def survey(folder: str) -> Dict[str, dict]:
    """Geometry of every drawing in a folder, keyed by file stem."""
    out = {}
    for fn in sorted(os.listdir(folder)):
        if not fn.endswith(".svg"):
            continue
        path = os.path.join(folder, fn)
        vb = outline.viewbox(path)
        x0, y0, x1, y1 = ink_bounds(path)
        out[fn[:-4]] = {
            "viewbox": vb,
            "ink": (round(x0, 2), round(y0, 2), round(x1, 2), round(y1, 2)),
        }
    return out


def _polys_svg(svg_path: str):
    out = []
    for sp in outline.load(svg_path):
        poly = []
        for seg in sp:
            for i in range(outline.FLATTEN):
                p = seg.point(i / outline.FLATTEN)
                poly.append((p.real, p.imag))
        out.append(poly)
    return out


def _crossings(polys, value: float, axis: int) -> List[Tuple[float, float]]:
    other = 1 - axis
    hits = []
    for poly in polys:
        n = len(poly)
        for i in range(n):
            a, b = poly[i], poly[(i + 1) % n]
            if (a[axis] > value) != (b[axis] > value):
                t = (value - a[axis]) / (b[axis] - a[axis])
                hits.append(a[other] + t * (b[other] - a[other]))
    hits.sort()
    return [(hits[i], hits[i + 1]) for i in range(0, len(hits) - 1, 2)]


def vertical_spans(svg_path: str, x: float) -> List[Tuple[float, float]]:
    """y-intervals where a vertical line at `x` crosses ink."""
    return _crossings(_polys_svg(svg_path), x, 0)


def horizontal_spans(svg_path: str, y: float) -> List[Tuple[float, float]]:
    """x-intervals where a horizontal line at `y` crosses ink."""
    return _crossings(_polys_svg(svg_path), y, 1)


def edge_ink(svg_path: str, box: Tuple[float, float, float, float],
             inset: float = 3.0) -> Dict[str, float]:
    """Fraction of each edge of `box` that carries ink, just inside the edge.

    box is (left, cap, right, baseline) in svg units.

    This is the measurement that tells you which drawings are cut off at an
    edge to meet a neighbour -- but only the measurement.  What a given value
    means is a property of the design, not of fonts: in one script the signs
    that join carry a thin connecting stroke at the edge while the rest carry
    none, and in another the signs that join are the ones missing a full-height
    edge the rest all have.  Both show up here as a clean split into groups.
    Report the groups, ask what they mean, do not assume.
    """
    left, cap, right, baseline = box
    polys = _polys_svg(svg_path)
    width, height = right - left, baseline - cap

    def covered(spans, lo, hi):
        return sum(min(b, hi) - max(a, lo) for a, b in spans
                   if b > lo and a < hi)

    return {
        "left": covered(_crossings(polys, left + inset, 0), cap, baseline) / height,
        "right": covered(_crossings(polys, right - inset, 0), cap, baseline) / height,
        "top": covered(_crossings(polys, cap + inset, 1), left, right) / width,
        "bottom": covered(_crossings(polys, baseline - inset, 1), left, right) / width,
    }


# --------------------------------------------------------------------------
# built font
# --------------------------------------------------------------------------

def _bez(p0, p1, p2, p3, n=10):
    out = []
    for i in range(1, n + 1):
        t = i / n
        u = 1 - t
        out.append((u**3 * p0[0] + 3 * u * u * t * p1[0]
                    + 3 * u * t * t * p2[0] + t**3 * p3[0],
                    u**3 * p0[1] + 3 * u * u * t * p1[1]
                    + 3 * u * t * t * p2[1] + t**3 * p3[1]))
    return out


def _polygons(glyph):
    rec = RecordingPen()
    glyph.draw(rec)
    polys, cur = [], []
    for op, args in rec.value:
        if op == "moveTo":
            if len(cur) > 2:
                polys.append(cur)
            cur = [args[0]]
        elif op == "lineTo":
            cur.append(args[0])
        elif op == "curveTo":
            cur.extend(_bez(cur[-1], *args))
        elif op == "qCurveTo":
            for pt in args:
                if pt is not None:
                    cur.append(pt)
        elif op in ("closePath", "endPath"):
            if len(cur) > 2:
                polys.append(cur)
            cur = []
    if len(cur) > 2:
        polys.append(cur)
    return polys


def profile(glyph, rows) -> Dict[int, Tuple[float, float]]:
    """row -> (leftmost ink x, rightmost ink x), nonzero winding."""
    polys = _polygons(glyph)
    out = {}
    for y in rows:
        xs = []
        for poly in polys:
            n = len(poly)
            for i in range(n):
                x0, y0 = poly[i]
                x1, y1 = poly[(i + 1) % n]
                if (y0 > y) != (y1 > y):
                    xs.append((x0 + (y - y0) * (x1 - x0) / (y1 - y0),
                               1 if y1 > y0 else -1))
        if not xs:
            continue
        xs.sort()
        wind, spans, start = 0, [], None
        for x, d in xs:
            was = wind
            wind += d
            if was == 0 and wind != 0:
                start = x
            elif was != 0 and wind == 0:
                spans.append((start, x))
        if spans:
            out[y] = (spans[0][0], spans[-1][1])
    return out


def kern_reader(font):
    """Read class kerning back out of GPOS.

    Reading it from the font rather than re-deriving it from the spec means
    the measurement stays honest when the kerning changes.
    """
    pairs = []
    if "GPOS" not in font:
        return lambda a, b: 0
    gpos = font["GPOS"].table
    for record in gpos.FeatureList.FeatureRecord:
        if record.FeatureTag != "kern":
            continue
        for index in record.Feature.LookupListIndex:
            for sub in gpos.LookupList.Lookup[index].SubTable:
                if getattr(sub, "Format", None) != 2:
                    continue
                pairs.append((sub.ClassDef1.classDefs,
                              sub.ClassDef2.classDefs,
                              sub.Class1Record))

    def kern(a, b):
        total = 0
        for left, right, rows in pairs:
            rec = rows[left.get(a, 0)].Class2Record[right.get(b, 0)]
            if rec.Value1 is not None:
                total += getattr(rec.Value1, "XAdvance", 0) or 0
        return total

    return kern


def gaps(font, lefts: List[str], rights: List[str],
         rows: Optional[range] = None) -> Dict[str, Tuple[int, str]]:
    """Narrowest true gap each left glyph leaves against a set of followers.

    Pick `rights` as one representative per shape family -- a dozen is plenty,
    and it keeps this fast enough to run on every build.
    """
    gs = font.getGlyphSet()
    hmtx = font["hmtx"]
    kern = kern_reader(font)
    if rows is None:
        upm = font["head"].unitsPerEm
        rows = range(-round(upm / 4), round(upm * 0.86), 5)
    rows = list(rows)
    prof = {n: profile(gs[n], rows) for n in set(lefts) | set(rights)}

    out = {}
    for a in lefts:
        adv = hmtx[a][0]
        pa = prof[a]
        best, who = None, None
        for b in rights:
            pb = prof[b]
            k = kern(a, b)
            for y, (_l, ra) in pa.items():
                if y not in pb:
                    continue
                g = (adv + k + pb[y][0]) - ra
                if best is None or g < best:
                    best, who = g, b
        if best is not None:
            out[a] = (round(best), who)
    return out


def report_gaps(font, lefts, rights, group_of=None) -> str:
    """Human-readable gap table.  `group_of` maps a glyph name to a label
    (its class, its group, whatever the interesting axis is)."""
    result = gaps(font, lefts, rights)
    buckets = defaultdict(list)
    for name, (g, _b) in result.items():
        buckets[group_of(name) if group_of else "all"].append(g)
    lines = [f"{'group':<12}{'n':>5}{'min':>7}{'max':>7}"]
    for key in sorted(buckets, key=lambda k: min(buckets[k])):
        v = buckets[key]
        lines.append(f"{str(key):<12}{len(v):>5}{min(v):>7}{max(v):>7}")
    return "\n".join(lines)
