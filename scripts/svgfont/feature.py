"""FontSpec -> feature file.

Three stages, in this order, because HarfBuzz applies GSUB lookups by lookup
index rather than by feature order -- so whatever is defined first wins:

  1. the context rules, in `ccmp` (always on, cannot be switched off)
  2. the ligatures, in `rlig` and `liga`
  3. class kerning, in `kern`

Ligature matching inside one lookup is greedy and longest-first, which is
exactly what a transliteration font wants: "TAT" should beat "TA".  fontTools
sorts each ligature set by component count for us, so the only thing we have
to get right is stage 1 -- the cases where longest-first is the wrong answer.
"""

from typing import List

from .spec import FontSpec


def _cls(names: List[str]) -> str:
    return "[" + " ".join(names) + "]"


def build(spec: FontSpec) -> str:
    L: List[str] = []
    A = L.append

    A("# generated -- edit the spec, not this file")
    A("languagesystem DFLT dflt;")
    A("languagesystem latn dflt;")
    A("")

    lookup_names = []
    for i, rule in enumerate(spec.context_rules):
        sub_name = f"ctx_sub_{i}"
        lookup_names.append((rule, sub_name))
        A(f"lookup {sub_name} {{")
        for src, dst in rule.replace.items():
            A(f"    sub {src} by {dst};")
        A(f"}} {sub_name};")
        A("")

    if spec.context_rules:
        A("lookup ctx_rules {")
        for rule, sub_name in lookup_names:
            if rule.comment:
                for line in rule.comment.strip().splitlines():
                    A(f"    # {line.strip()}")
            parts = [_cls(c) for c in rule.backtrack]
            parts += [f"{_cls(c)}' lookup {sub_name}" for c in rule.input]
            parts += [_cls(c) for c in rule.lookahead]
            A("    sub " + " ".join(parts) + ";")
        A("} ctx_rules;")
        A("")

    A("lookup ligatures {")
    count = 0
    for glyph in spec.glyphs:
        for seq in glyph.inputs:
            if len(seq) < 2:
                # a one-glyph "ligature" is a single substitution; keeping it
                # out of the ligature lookup avoids a silent no-op
                continue
            A(f"    sub {' '.join(seq)} by {glyph.name};")
            count += 1
    A("} ligatures;")
    A("")

    if spec.context_rules:
        A("feature ccmp {")
        A("    lookup ctx_rules;")
        A("} ccmp;")
        A("")

    # rlig cannot be turned off by the application; liga is there so that
    # engines which only honour the standard ligature feature still work
    for tag in ("rlig", "liga"):
        A(f"feature {tag} {{")
        A("    lookup ligatures;")
        A(f"}} {tag};")
        A("")

    if spec.kern:
        for name, names in spec.kern_left.items():
            A(f"@KL_{name} = {_cls(names)};")
        for name, names in spec.kern_right.items():
            A(f"@KR_{name} = {_cls(names)};")
        A("")
        A("feature kern {")
        for left, right, value in spec.kern:
            A(f"    pos @KL_{left} @KR_{right} {value};")
        A("} kern;")
        A("")

    return "\n".join(L)


def rule_count(spec: FontSpec) -> int:
    return sum(1 for g in spec.glyphs for s in g.inputs if len(s) >= 2)
