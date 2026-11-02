#!/usr/bin/env python3
"""Typing X gives sign Y.  Every reading rule in model.py has a case here."""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from svgfont import verify  # noqa: E402

OTF = os.path.join(ROOT, "dist", "otf", "BunAfaka-Regular.otf")

CASES = [
    # one drawing, two readings
    ("bo", ["af_bo_bu"]), ("bu", ["af_bo_bu"]),
    ("ba", ["af_ba_pa"]), ("pa", ["af_ba_pa"]),
    ("u", ["af_u_ku"]), ("ku", ["af_u_ku"]),
    # o/u and e/i merges from the script itself
    ("gu", ["af_go"]), ("du", ["af_do"]), ("mu", ["af_mo"]),
    ("nu", ["af_no"]), ("li", ["af_le"]), ("mi", ["af_me"]),
    # se and si are drawn separately, so they stay separate
    ("se", ["af_se"]), ("si", ["af_si"]),
    # case does not matter
    ("BA", ["af_ba_pa"]), ("Ko", ["af_ko"]),
    # silent coda n/m
    ("bon", ["af_bo_bu"]), ("kom", ["af_ko"]), ("an", ["af_a"]),
    # ...unless it opens the next syllable
    ("kona", ["af_ko", "af_na"]), ("bona", ["af_bo_bu", "af_na"]),
    ("ama", ["af_a", "af_ma"]),
    # prenasalised onsets share the plain sign
    ("mba", ["af_ba_pa"]), ("nda", ["af_da"]), ("konda", ["af_ko", "af_da"]),
    ("anga", ["af_a", "af_ga"]),          # Everson fig. 3: a(n)ga
    # long vowels repeat the vowel
    ("koo", ["af_ko", "af_o"]),
    # drawn 1 Nov 2026
    ("wa", ["af_wa"]), ("we", ["af_we"]), ("wi", ["af_we"]),
    ("so", ["af_so"]), ("su", ["af_so"]), ("pu", ["af_pu"]),
    ("tu", ["af_tu"]), ("ya", ["af_ya"]), ("be", ["af_be"]),
    ("fa", ["af_fa"]), ("fe", ["af_fe"]), ("fi", ["af_fi"]),
    ("w", ["lat_w"]),
    # drawn later on 1 Nov 2026
    ("dyo", ["af_dyo"]), ("dyu", ["af_dyo"]), ("kwa", ["af_kwa"]),
    ("to", ["af_to"]), ("ti", ["af_ti"]), ("nya", ["af_nya"]),
    ("ni", ["af_ni"]), ("ye", ["af_ye"]), ("ani", ["af_a", "af_ni"]),
    ("koti.", ["af_ko", "af_ti", "af_period"]),
    # j is typed like y (older Dutch-based Ndyuka spelling)
    ("ja", ["af_ya"]), ("ju", ["af_yu"]), ("je", ["af_ye"]),
    ("JA", ["af_ya"]), ("tja", ["af_tya"]), ("djo", ["af_dyo"]),
    ("dju", ["af_dyo"]), ("nja", ["af_nya"]), ("j", ["lat_y"]),
    # n before ya opens NYA rather than falling silent
    ("anya", ["af_a", "af_nya"]), ("konya", ["af_ko", "af_nya"]),
    ("anja", ["af_a", "af_nya"]), ("konyu", ["af_ko", "af_yu"]),
    # three-letter syllable
    ("tya", ["af_tya"]),
    # a consonant with no syllable falls back to the hand-drawn letter
    ("t", ["lat_t"]), ("b", ["lat_b"]),
    # phrases from the proposal
    ("masa gado te baka be ye",
     ["af_ma", "af_sa", "space", "af_ga", "af_do", "space", "af_te",
      "space", "af_ba_pa", "af_ka", "space", "af_be", "space", "af_ye"]),
    ("a moke un taki",
     ["af_a", "space", "af_mo", "af_ke", "space", "af_u_ku", "space",
      "af_ta", "af_ki"]),
]

if __name__ == "__main__":
    sys.exit(1 if verify.run_cases(OTF, CASES, verbose=False) else 0)
