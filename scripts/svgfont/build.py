"""FontSpec -> OTF, TTF, WOFF2."""

import os
from typing import Dict, Optional, Tuple

from fontTools.fontBuilder import FontBuilder
from fontTools.misc.transform import Transform
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.cu2quPen import Cu2QuPen
from fontTools.pens.recordingPen import RecordingPen, DecomposingRecordingPen
from fontTools.pens.t2CharStringPen import T2CharStringPen
from fontTools.pens.transformPen import TransformPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont

from . import feature, outline
from .spec import FontSpec


def latin_fallback(spec: FontSpec) -> Dict[str, Tuple[RecordingPen, int]]:
    """Lift plain letterforms out of a text face.

    Why bother: the characters you type have to be in the cmap or the
    ligatures can never fire, and a cmapped glyph with no outline renders as
    a blank.  A half-typed sequence showing "T" is far better feedback than
    showing nothing.  Characters the script never uses are simply left out of
    the cmap, so the system falls back to its own font for those.

    Licence: whatever face you lift from, its terms follow into your font.
    """
    path = spec.latin_fallback
    if not path or not os.path.exists(path):
        return {}

    font = TTFont(path)
    if "fvar" in font:
        from fontTools.varLib.instancer import instantiateVariableFont
        axes = {a.axisTag: a.defaultValue for a in font["fvar"].axes}
        axes.update({k: v for k, v in (("wght", 400), ("wdth", 100))
                     if k in axes})
        font = instantiateVariableFont(font, axes, inplace=True,
                                       updateFontNames=False)
    upm = font["head"].unitsPerEm
    cmap = font.getBestCmap()
    gs = font.getGlyphSet()

    wanted = {name: ord(ch) for ch, name in spec.latin_chars.items()}
    wanted.update(spec.latin_extra)

    recordings = {}
    for name, cp in wanted.items():
        src = cmap.get(cp)
        if src is None:
            continue
        rec = DecomposingRecordingPen(gs)     # accented letters are composites
        gs[src].draw(rec)
        recordings[name] = (rec, gs[src].width)

    top = 0.0
    for rec, _w in recordings.values():
        for _op, args in rec.value:
            for pt in args:
                if isinstance(pt, tuple):
                    top = max(top, pt[1])

    # keep the fallback inside the writing band; nothing should rise above it
    limit = spec.grid.body - 20
    scale = spec.grid.upm / upm
    if top and top * scale > limit:
        scale = limit / top

    out = {}
    for name, (rec, width) in recordings.items():
        cubic = RecordingPen()
        _quad_to_cubic(rec, cubic)
        moved = RecordingPen()
        cubic.replay(TransformPen(moved, Transform(scale, 0, 0, scale, 0, 0)))
        out[name] = (moved, round(width * scale))
    return out


def _quad_to_cubic(rec, out):
    """Quadratic curves convert to cubics exactly, so no error to manage."""
    cur = start = None
    for op, args in rec.value:
        if op == "moveTo":
            cur = start = args[0]
            out.moveTo(*args)
        elif op == "lineTo":
            cur = args[0]
            out.lineTo(*args)
        elif op == "curveTo":
            cur = args[-1]
            out.curveTo(*args)
        elif op == "qCurveTo":
            pts = list(args)
            if pts[-1] is None:
                pts[-1] = start
            for k in range(len(pts) - 1):
                off, nxt = pts[k], pts[k + 1]
                end = nxt if k == len(pts) - 2 else (
                    (off[0] + nxt[0]) / 2, (off[1] + nxt[1]) / 2)
                out.curveTo(
                    (cur[0] + 2 / 3 * (off[0] - cur[0]),
                     cur[1] + 2 / 3 * (off[1] - cur[1])),
                    (end[0] + 2 / 3 * (off[0] - end[0]),
                     end[1] + 2 / 3 * (off[1] - end[1])),
                    end)
                cur = end
        elif op == "closePath":
            out.closePath()
            cur = start
        elif op == "endPath":
            out.endPath()


def _notdef(advance: int, height: int) -> RecordingPen:
    pen = RecordingPen()
    w = round(advance * 0.72)
    for box, reverse in (((round(advance * 0.14), 0, w, height), False),
                         ((round(advance * 0.24), round(height * 0.09),
                           round(w * 0.86), round(height * 0.91)), True)):
        x0, y0, x1, y1 = box
        pts = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
        if reverse:
            pts.reverse()
        pen.moveTo(pts[0])
        for p in pts[1:]:
            pen.lineTo(p)
        pen.closePath()
    return pen


def collect(spec: FontSpec):
    """Draw everything once; both flavours reuse the result."""
    problems = spec.validate()
    if problems:
        raise ValueError("spec problems:\n  " + "\n  ".join(problems))

    latin = latin_fallback(spec)
    pens, metrics = {}, {}
    order = [".notdef"]

    pens[".notdef"] = _notdef(spec.notdef_advance, spec.grid.body)
    metrics[".notdef"] = (spec.notdef_advance, 0)

    for glyph in spec.glyphs:
        order.append(glyph.name)
        if glyph.svg:
            rec = RecordingPen()
            outline.draw(outline.load(glyph.svg), rec, spec.grid, dx=glyph.shift_x)
            pens[glyph.name] = rec
            metrics[glyph.name] = (glyph.advance, 0)
        elif glyph.name in latin:
            rec, width = latin[glyph.name]
            pens[glyph.name] = rec
            metrics[glyph.name] = (glyph.advance or width, 0)
        else:
            pens[glyph.name] = RecordingPen()
            metrics[glyph.name] = (glyph.advance, 0)

    # left side bearings have to agree with the outlines
    for name in order:
        bp = BoundsPen(None)
        pens[name].replay(bp)
        adv = metrics[name][0]
        metrics[name] = (adv, round(bp.bounds[0]) if bp.bounds else 0)

    return order, pens, metrics


def compile_font(spec: FontSpec, kind: str, order, pens, metrics, fea: str):
    is_ttf = kind == "ttf"
    grid, vert = spec.grid, spec.vertical
    fb = FontBuilder(grid.upm, isTTF=is_ttf)
    fb.updateHead(fontRevision=float(spec.version))
    fb.setupGlyphOrder(order)
    fb.setupCharacterMap(spec.cmap)

    if is_ttf:
        glyf = {}
        for name in order:
            tt = TTGlyphPen(None)
            # TrueType wants the opposite winding from CFF
            pens[name].replay(Cu2QuPen(tt, 0.6, reverse_direction=True))
            glyf[name] = tt.glyph()
        fb.setupGlyf(glyf)
    else:
        cs = {}
        for name in order:
            p = T2CharStringPen(metrics[name][0], None)
            pens[name].replay(p)
            cs[name] = p.getCharString()
        fb.setupCFF(spec.ps_name,
                    {"FullName": f"{spec.family} {spec.style}",
                     "FamilyName": spec.family,
                     "Weight": spec.style}, cs, {})

    fb.setupHorizontalMetrics(metrics)
    fb.setupHorizontalHeader(ascent=vert.ascender, descent=vert.descender,
                             lineGap=0)
    fb.setupNameTable({
        "familyName": spec.family,
        "styleName": spec.style,
        "uniqueFontIdentifier": f"{spec.family};{spec.version};{spec.ps_name}",
        "fullName": f"{spec.family} {spec.style}",
        "version": f"Version {spec.version}",
        "psName": spec.ps_name,
        "designer": spec.designer,
        "description": spec.description,
    })
    typo_asc = vert.typo_ascender if vert.typo_ascender is not None else grid.body
    typo_desc = (vert.typo_descender if vert.typo_descender is not None
                 else vert.descender)
    fb.setupOS2(
        version=4,           # bit 7 (use typo metrics) needs v4 or later
        sTypoAscender=typo_asc, sTypoDescender=typo_desc,
        sTypoLineGap=vert.typo_line_gap,
        usWinAscent=vert.win_ascent or max(typo_asc + 50, 0),
        usWinDescent=vert.win_descent or abs(typo_desc),
        sCapHeight=typo_asc, sxHeight=typo_asc,
        achVendID=spec.vendor[:4].ljust(4), fsType=0, usWeightClass=400,
        fsSelection=(1 << 6) | (1 << 7))     # regular + use typo metrics
    fb.setupPost(isFixedPitch=0)
    fb.addOpenTypeFeatures(fea)
    return fb


def build(spec: FontSpec, dist: str, formats=("otf", "ttf", "woff2")):
    """Build and write every requested flavour.  Returns {format: path}."""
    order, pens, metrics = collect(spec)
    fea = feature.build(spec)

    written = {}
    for kind in ("otf", "ttf"):
        if kind not in formats and not (kind == "ttf" and "woff2" in formats):
            continue
        fb = compile_font(spec, kind, order, pens, metrics, fea)
        path = os.path.join(dist, kind, f"{spec.ps_name}.{kind}")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        fb.save(path)
        if kind in formats:
            written[kind] = path
        if kind == "ttf" and "woff2" in formats:
            try:
                w = os.path.join(dist, "woff2", f"{spec.ps_name}.woff2")
                os.makedirs(os.path.dirname(w), exist_ok=True)
                f = TTFont(path)
                f.flavor = "woff2"
                f.save(w)
                written["woff2"] = w
            except ImportError:
                pass          # brotli not installed
        if kind == "ttf" and "ttf" not in formats:
            os.remove(path)
    return written, fea
