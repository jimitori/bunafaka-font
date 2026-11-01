"""SVG drawings -> font contours.

The one genuinely fiddly part is winding direction.  Fonts fill with the
nonzero rule, so overlapping strokes union correctly *only* if every outer
contour turns the same way and every counter turns the other way.  Exported
SVGs make no such promise -- they may use fill-rule="evenodd", and separate
<path> elements are separate filled shapes that happen to overlap.

So: work out nesting per <path> element (a counter can only live inside its
own shape), and set direction from the nesting depth.  Contours that merely
overlap end up at the same depth and therefore union instead of cancelling.
"""

import re
from typing import List

from svgpathtools import parse_path

_PATH_RE = re.compile(r'<path\b[^>]*\bd="([^"]+)"', re.S)
_VIEWBOX_RE = re.compile(r'viewBox="([\d.eE+\- ]+)"')

FLATTEN = 12          # samples per segment when testing containment


def viewbox(path: str):
    src = open(path, encoding="utf-8").read()
    m = _VIEWBOX_RE.search(src)
    return [float(v) for v in m.group(1).split()] if m else None


def _polygon(subpath):
    pts = []
    for seg in subpath:
        for i in range(FLATTEN):
            p = seg.point(i / FLATTEN)
            pts.append((p.real, p.imag))
    return pts


def _area(poly):
    total = 0.0
    for i in range(len(poly)):
        x0, y0 = poly[i]
        x1, y1 = poly[(i + 1) % len(poly)]
        total += x0 * y1 - x1 * y0
    return total / 2.0


def _bbox(poly):
    xs = [p[0] for p in poly]
    ys = [p[1] for p in poly]
    return min(xs), min(ys), max(xs), max(ys)


def _point_in(pt, poly):
    x, y = pt
    hit = False
    n = len(poly)
    for i in range(n):
        x0, y0 = poly[i]
        x1, y1 = poly[(i + 1) % n]
        if (y0 > y) != (y1 > y):
            if x < x0 + (y - y0) * (x1 - x0) / (y1 - y0):
                hit = not hit
    return hit


def _encloses(outer_poly, outer_bb, inner_poly, inner_bb):
    """True only for real nesting.  Requiring the bounding box to sit wholly
    inside keeps partly overlapping shapes from being mistaken for counters,
    which would punch a hole where the design wanted solid ink."""
    ox0, oy0, ox1, oy1 = outer_bb
    ix0, iy0, ix1, iy1 = inner_bb
    if not (ox0 <= ix0 and oy0 <= iy0 and ox1 >= ix1 and oy1 >= iy1):
        return False
    return _point_in(inner_poly[0], outer_poly)


def load(path: str) -> List:
    """Read one SVG into subpaths with corrected winding.

    svg y points down and font y points up, so an outer contour has to be
    clockwise here in order to come out counter-clockwise in the font, which
    is what CFF wants.  build.py reverses again for the TrueType flavour.
    """
    src = open(path, encoding="utf-8").read()
    out = []
    for d in _PATH_RE.findall(src):
        subs = [sp for sp in parse_path(d).continuous_subpaths() if len(sp)]
        polys = [_polygon(sp) for sp in subs]
        bbs = [_bbox(p) for p in polys]
        for i, sp in enumerate(subs):
            depth = sum(
                1 for j in range(len(subs))
                if j != i and _encloses(polys[j], bbs[j], polys[i], bbs[i]))
            want_positive = (depth % 2 == 1)
            if (_area(polys[i]) > 0) != want_positive:
                sp = sp.reversed()
            out.append(sp)
    return out


def draw(contours, pen, grid, dx: float = 0.0):
    """Replay contours through a pen, mapped into font space."""
    def P(z):
        return (grid.x(z.real) + dx, grid.y(z.imag))

    for sp in contours:
        pen.moveTo(P(sp[0].start))
        for seg in sp:
            kind = type(seg).__name__
            if kind == "Line":
                pen.lineTo(P(seg.end))
            elif kind == "CubicBezier":
                pen.curveTo(P(seg.control1), P(seg.control2), P(seg.end))
            elif kind == "QuadraticBezier":
                s, c, e = seg.start, seg.control, seg.end
                pen.curveTo(P(s + (c - s) * (2 / 3)),
                            P(e + (c - e) * (2 / 3)), P(e))
            elif kind == "Arc":
                # svgpathtools can hand back arcs; approximate them
                prev = seg.start
                for i in range(1, 17):
                    nxt = seg.point(i / 16)
                    pen.lineTo(P(nxt))
                    prev = nxt
            else:
                raise ValueError(f"unsupported segment type {kind}")
        pen.closePath()
