#!/usr/bin/env python3
"""source/*.svg -> dist/{otf,ttf,woff2}/BunAfaka-Regular.*

model.py says what the signs are and how they are typed; this file turns
that into a FontSpec, and the svg-font-builder pipeline does the rest.

    .venv/bin/python scripts/build_font.py
"""

import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from svgfont import build, feature, measure, verify            # noqa: E402
from svgfont.spec import ContextRule, FontSpec, Glyph, Grid, Vertical  # noqa: E402
import model                                                   # noqa: E402

SOURCE = os.path.join(ROOT, "source")
DIST = os.path.join(ROOT, "dist")
BUILD = os.path.join(ROOT, "build")
FLAT = os.path.join(BUILD, "svg")        # strokes expanded to outlines

# --- the grid ---------------------------------------------------------------
# Drawn on a 100 square.  23 of the 53 drawings stand on y=91 and the plain
# ones (e, ke, ma) hang from y=10: those are the baseline and the top line.
# Descenders (lo-lu, di, po) reach y=99; po rises to y=5.
GRID = Grid(size=100, cap=10, baseline=91, upm=1000)
VERTICAL = Vertical(ascender=900, descender=-250,
                    typo_ascender=860, typo_descender=-200)

# Side bearing on each side, font units.  Afaka signs never join, so each one
# is fitted to its own ink: narrow ko stays narrow, wide me stays wide, and
# the room between any two signs is 2 * SIDE before kerning.
SIDE = 70

SPACE = 320
CLONE = ".on"       # an n or m that opens the next syllable, see context_rules


def flatten(stem):
    """Expand strokes into filled outlines.

    Nine of the hand-drawn letters are a single stroked line in Figma
    (fill="none", stroke-width="2").  A font has no strokes; read as-is, the
    path would be filled shut and the letter would turn into a blob.
    """
    src = os.path.join(SOURCE, stem + ".svg")
    dst = os.path.join(FLAT, stem + ".svg")
    if 'stroke-width' not in open(src, encoding="utf-8").read():
        return src
    out = subprocess.run([os.path.join(os.path.dirname(sys.executable),
                                       "picosvg"), src],
                         check=True, capture_output=True, text=True).stdout
    with open(dst, "w", encoding="utf-8") as fh:
        fh.write(out)
    return dst


def fitted(name, svg, inputs=()):
    x0, _y0, x1, _y1 = measure.ink_bounds(svg)
    s = GRID.scale
    return Glyph(name=name, svg=svg,
                 advance=round((x1 - x0) * s) + 2 * SIDE,
                 shift_x=SIDE - x0 * s,
                 inputs=[list(i) for i in inputs])


def main():
    os.makedirs(FLAT, exist_ok=True)
    stems = sorted(f[:-4] for f in os.listdir(SOURCE) if f.endswith(".svg"))
    signs = [model.parse_stem(s) for s in stems]

    # which glyph a typed character lands on before any ligature
    char_glyph = {}
    for s in signs:
        if s.kind == "letter":
            char_glyph[s.stem] = s.name
        elif s.kind == "vowel":
            char_glyph[s.readings[0]] = s.name
        elif s.kind == "punct":
            char_glyph[model.PUNCTUATION[s.stem]] = s.name

    taken = {r for s in signs for r in s.readings}
    glyphs = [Glyph("space", advance=SPACE)]
    skipped = []

    for s in signs:
        svg = flatten(s.stem)
        inputs = []
        for typed in s.spellings(taken):
            if len(typed) < 2:
                continue
            if not all(ch in char_glyph for ch in typed):
                skipped.append(typed)
                continue
            seq = [char_glyph[ch] for ch in typed]
            inputs.append(seq)
            if typed[0] in model.SILENT_CODA and typed[1] in model.VOWELS:
                inputs.append([seq[0] + CLONE] + seq[1:])
        glyphs.append(fitted(s.name, svg, inputs))
        if s.kind == "letter" and s.stem in model.SILENT_CODA:
            glyphs.append(fitted(s.name + CLONE, svg))

    cmap = {0x20: "space"}
    for ch, name in char_glyph.items():
        cmap[ord(ch)] = name
        cmap[ord(ch.upper())] = name

    spec = FontSpec(
        family="Bun Afaka",
        version="2.000",
        designer="Mitia Morovov-Sheiner",
        description="Afaka syllabary for Ndyuka. Type Ndyuka in Latin, "
                    "get Afaka.",
        grid=GRID,
        vertical=VERTICAL,
        glyphs=glyphs,
        cmap=cmap,
        context_rules=context_rules(char_glyph),
    )

    written, fea = build.build(spec, DIST)
    with open(os.path.join(BUILD, spec.ps_name + ".fea"), "w") as fh:
        fh.write(fea)

    print(f"{len(signs)} drawings, {feature.rule_count(spec)} substitutions")
    for kind, path in written.items():
        print(f"  -> {os.path.relpath(path, ROOT)}")
    print(verify.describe(written["otf"]))

    gone = model.missing(signs)
    print(f"\nAfaka letters with no drawing ({len(gone)} of "
          f"{len(model.AFAKA_LETTERS)}): {' '.join(gone)}")
    undrawn = [v for k, v in model.AFAKA_PUNCTUATION.items()
               if k not in {s.stem for s in signs}]
    if undrawn:
        print("Afaka punctuation with no drawing: " + "; ".join(undrawn))
    if skipped:
        print("spellings needing a letter that has no drawing: "
              + " ".join(sorted(set(skipped))))

    problems = verify.audit(written["otf"], must_have_ink=[
        g.name for g in glyphs if g.svg])
    if problems:
        print("\nAUDIT\n  " + "\n  ".join(problems))
        sys.exit(1)


def context_rules(char_glyph):
    """An n or m before a vowel opens the next syllable.

    Without this, greedy longest-match reads "kona" as KON + A, since a coda
    n is silent and KON is a ligature.  Swapping such an n for a clone that
    the coda ligatures do not list forces KO + NA.
    """
    heads = [char_glyph[c] for c in model.SILENT_CODA if c in char_glyph]
    vowels = [char_glyph[v] for v in model.VOWELS if v in char_glyph]
    return [ContextRule(
        input=[heads], lookahead=[vowels],
        replace={g: g + CLONE for g in heads},
        comment="n/m before a vowel is an onset, not a silent coda.")]


if __name__ == "__main__":
    main()
