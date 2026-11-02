"""Afaka, as data: which drawing is typed how.

The only file that knows anything about the script.  build_font.py turns it
into a font; check_shaping.py holds it to its word.

------------------------------------------------------------------------
THE SCRIPT

Afaka is a syllabary for Ndyuka (an English creole of Suriname), devised by
Afaka Atumisi in 1908-1910.  Fifty-six syllable letters, no consonant-only
signs, no shaping -- every syllable is one sign, written left to right.
Source: M. Everson, "Proposal for encoding the Afaka script in the SMP of the
UCS", WG2 N4132R / L2/11-297R (2011).

What the script leaves unwritten, and what that means for typing:

  - o and u are seldom told apart: one sign serves bo/bu, fo/fu, lo/lu,
    go/gu, do/du, mo/mu, no/nu, so/su, dyo/dyu.
  - e and i merge after l, m, s, w: le/li, me/mi, se/si, we/wi.
  - BA was originally ba and pa; a separate PA was innovated later.
  - U is also ku ("uku", a pair of hooks).
  - Syllable-final n and m are not written: kon, kom -> KO.
  - Prenasalised stops share the plain sign: mba -> BA, nda -> DA, nga -> GA.
  - Long vowels repeat the vowel sign: koo -> KO O.  Falls out by itself.
  - Tone is not written.

So typing ordinary Ndyuka Latin orthography gives Afaka.

------------------------------------------------------------------------
THE FILES

source/<syllables>.svg, syllables joined by "-" when one drawing serves
several of them (bo-bu.svg is typed both bo and bu).  A single consonant
(b.svg, n.svg ...) is a small hand-drawn Latin capital -- not part of Afaka,
which has no consonant signs -- shown when a typed consonant does not form a
syllable.  Deliberate: half-typed input is never blank, yet the letter is
different enough that nobody reads it as an Afaka sign.
"""

VOWELS = "aeiou"
CONSONANTS = "bdfgklmnpstwy"

# Script-level aliases: one sign, several readings (Everson 2011, section 1
# and the character annotations).  Applied only when the file itself does not
# already name the reading -- a drawing called se.svg and another called
# si.svg stay two signs.  That one is deliberate: the manuscripts vary a lot,
# and separate se/si is the first step towards variant forms of signs.
ALIASES = {
    "bo": ["bu"], "fo": ["fu"], "lo": ["lu"], "go": ["gu"], "do": ["du"],
    "mo": ["mu"], "no": ["nu"], "so": ["su"], "dyo": ["dyu"],
    "le": ["li"], "me": ["mi"], "se": ["si"], "we": ["wi"],
    "ba": ["pa"],
}

# Punctuation: file name -> the characters typed for it.  Transcriptions
# write the Afaka full stop as . / \ or |, so all four give the bar.  A file cannot be
# called ".svg" (it would be hidden), so the names are words.  Afaka has three
# marks (Everson 2011, section 7); the full stop also does duty as a
# semicolon.
PUNCTUATION = {"period": [".", "/", "\\", "|"],
               "exclamation": ["!"],
               # a dingbat, no Latin counterpart: the asterisk is the nearest star
               "comet": ["*"],
               # not in the manuscripts: Mitia's own addition, version 2.1
               "question": ["?"]}

# Letters typed two ways.  Ndyuka texts write the glide either y (current
# orthography) or j (the older, Dutch-based one): ja, tja, djo, nja.  A typed
# j behaves exactly like y; with no j.svg drawn it also shows the y letter.
LETTER_ALIASES = {"j": "y"}

# Prenasalised onsets written with the plain sign.
PRENASAL = {"b": ["mb"], "d": ["nd"], "g": ["ng"]}

# Coda consonants Afaka leaves unwritten.
SILENT_CODA = ["n", "m"]


class Sign:
    """One drawing, resolved."""

    __slots__ = ("stem", "kind", "readings", "name")

    def __init__(self, stem, kind, readings):
        self.stem = stem          # file name without .svg
        self.kind = kind          # "syllable" | "vowel" | "letter"
        self.readings = readings  # syllables this drawing stands for
        self.name = ("lat_" + stem if kind == "letter"
                     else "af_" + stem.replace("-", "_"))
        if kind == "punct":
            self.name = "af_" + stem

    def spellings(self, taken=()):
        """Typed sequences that become this sign, as strings.

        `taken` is every reading some other file claims outright, so an
        alias never steals a sign that was drawn on purpose.
        """
        if self.kind == "letter":
            return [self.stem]
        if self.kind == "punct":
            return list(PUNCTUATION[self.stem])
        readings = list(self.readings)
        for r in self.readings:
            readings += [a for a in ALIASES.get(r, []) if a not in taken]
        for alt, letter in LETTER_ALIASES.items():
            readings += [r.replace(letter, alt) for r in readings
                         if letter in r]
        out = []
        for r in dict.fromkeys(readings):
            heads = [r] + [p + r[1:] for p in PRENASAL.get(r[0], [])]
            for h in heads:
                out.append(h)
                out += [h + c for c in SILENT_CODA]
        return list(dict.fromkeys(out))


def parse_stem(stem):
    """File name -> Sign, or raise.  An unparseable name is a typo or a class
    of sign nobody mentioned; both are worth stopping for."""
    if stem in PUNCTUATION:
        return Sign(stem, "punct", [])
    readings = stem.split("-")
    for r in readings:
        if not r or not set(r) <= set(VOWELS + CONSONANTS):
            raise ValueError(f"{stem}.svg: cannot read {r!r}")
    if len(readings) == 1 and len(stem) == 1 and stem in CONSONANTS:
        return Sign(stem, "letter", [])
    if len(readings) == 1 and stem in VOWELS:
        return Sign(stem, "vowel", readings)
    for r in readings:
        if r[-1] not in VOWELS:
            raise ValueError(f"{stem}.svg: {r!r} does not end in a vowel")
    kind = "vowel" if readings[0] in VOWELS else "syllable"
    return Sign(stem, kind, readings)


# The full repertoire, in Everson's traditional order, so the build can say
# which letters have no drawing yet.
AFAKA_LETTERS = (
    "we so pu fo tu le fe dyo no po pe da bi bo fa de ko kwa go gi i to lo "
    "ge la pi ne wa tya o di a ti ya fi e na nya mo ke u ta ki ni se yu me "
    "ma sa ga do te ba pa ka be ye"
).split()
AFAKA_PUNCTUATION = {"period": "full stop (long vertical bar)",
                     "exclamation": "exclamation (vertical row of rings)",
                     "comet": "Halley's comet"}


def missing(signs):
    """Afaka letters no drawing covers, by name or by alias."""
    covered = set()
    for s in signs:
        for r in s.readings:
            covered.add(r)
            covered.update(ALIASES.get(r, []))
    # a merged reading counts as covered from either side
    for head, alts in ALIASES.items():
        if any(a in covered for a in alts):
            covered.add(head)
    return [l for l in AFAKA_LETTERS if l not in covered]
