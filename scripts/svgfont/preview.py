"""Render sheets you can actually look at.

You cannot fit a script you have not seen.  Two views earn their keep:

  contact_sheet()  -- the raw drawings, before any font exists, optionally
                      with measured features marked in colour.  This is how
                      you read the design: which sides are cut off, where the
                      reference lines sit, what leaves the box.

  specimen()       -- text set in the built font.  The only way to confirm
                      that joins close, that gaps look right, and that the
                      shaping decisions produce the shapes you intended.

Both write an HTML file and shoot it with headless Chrome, because that gets
you a real text engine applying real OpenType features.
"""

import os
import re
import shutil
import subprocess
from typing import Dict, List, Optional, Sequence, Tuple

CHROME_CANDIDATES = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "google-chrome", "chromium", "chromium-browser",
]

DARK = "#14140f"
INK = "#f5f1e6"
LABEL = "#8a8577"


def find_chrome() -> Optional[str]:
    for cand in CHROME_CANDIDATES:
        if os.path.sep in cand:
            if os.path.exists(cand):
                return cand
        else:
            found = shutil.which(cand)
            if found:
                return found
    return None


def screenshot(html_path: str, png_path: str,
               width: int = 1400, height: int = 1600) -> Optional[str]:
    chrome = find_chrome()
    if not chrome:
        return None
    subprocess.run(
        [chrome, "--headless", "--disable-gpu", "--no-sandbox",
         "--allow-file-access-from-files", "--hide-scrollbars",
         "--virtual-time-budget=4000",
         f"--screenshot={os.path.abspath(png_path)}",
         f"--window-size={width},{height}",
         "file://" + os.path.abspath(html_path)],
        check=False, capture_output=True)
    return png_path if os.path.exists(png_path) else None


def _inner(svg_path: str) -> str:
    t = open(svg_path, encoding="utf-8").read()
    return t[t.index(">", t.index("<svg")) + 1: t.rindex("</svg>")]


def contact_sheet(out_html: str, rows: Sequence[Tuple[str, Sequence[str]]],
                  folder: str, viewbox: str = "-2 0 134 145",
                  marks: Optional[Dict[str, List[Tuple]]] = None,
                  columns: int = 8) -> str:
    """rows: (label, [file stems]).  marks: stem -> [(x, y, w, h, colour)]
    drawn on top in svg units, for calling out a measured feature."""
    parts = [
        "<!doctype html><meta charset='utf-8'><style>",
        f"body{{background:{DARK};color:#ddd;font:12px ui-monospace,monospace;margin:16px}}",
        "td{padding:4px 6px;vertical-align:top}",
        f"th{{color:#7cf;text-align:left;font-weight:400;white-space:nowrap;padding-right:14px}}",
        f".n{{color:{LABEL};font-size:10px}}",
        "</style><table>",
    ]
    for label, stems in rows:
        parts.append(f"<tr><th>{label}</th>")
        for stem in stems:
            path = os.path.join(folder, stem + ".svg")
            if not os.path.exists(path):
                parts.append(f"<td><div class='n'>{stem} missing</div></td>")
                continue
            overlay = ""
            for x, y, w, h, colour in (marks or {}).get(stem, []):
                overlay += (f"<rect x='{x}' y='{y}' width='{w}' height='{h}'"
                            f" fill='{colour}' fill-opacity='.85'/>")
            parts.append(
                f"<td><svg viewBox='{viewbox}' width='120'>"
                f"{_inner(path)}{overlay}</svg>"
                f"<div class='n'>{stem}</div></td>")
        parts.append("</tr>")
    parts.append("</table>")
    open(out_html, "w", encoding="utf-8").write("".join(parts))
    return out_html


def specimen(out_html: str, font_path: str,
             rows: Sequence[Tuple[str, str]],
             grid: Sequence[str] = (),
             size: int = 72, family: str = "Preview") -> str:
    """rows: (label, text set in the font).  grid: extra strings shown small
    in a wrapping grid, handy for the full character set."""
    rel = os.path.relpath(os.path.abspath(font_path),
                          os.path.dirname(os.path.abspath(out_html)))
    fmt = ("opentype" if font_path.endswith(".otf")
           else "woff2" if font_path.endswith(".woff2") else "truetype")
    parts = [
        "<!doctype html><meta charset='utf-8'><style>",
        f"@font-face{{font-family:'{family}';src:url('{rel}') format('{fmt}');}}",
        f"body{{background:{DARK};color:#eae6dd;"
        "font:12px ui-monospace,monospace;margin:18px}",
        ".r{display:grid;grid-template-columns:13rem 1fr;gap:1rem;"
        "align-items:center;padding:5px 0;border-bottom:1px solid #23231c}",
        f".j{{font-family:'{family}';font-size:{size}px;color:{INK};"
        "line-height:1.3;word-break:break-word}",
        ".g{display:grid;grid-template-columns:repeat(auto-fill,minmax(5rem,1fr));"
        "gap:4px;margin-top:14px}",
        ".c{background:#1c1c15;border-radius:2px;text-align:center;padding:3px 0}",
        f".c .j{{font-size:{max(22, size // 3)}px}}",
        f".c code{{font-size:9px;color:{LABEL}}}",
        "</style>",
    ]
    for label, text in rows:
        parts.append(f"<div class='r'><code>{label}</code>"
                     f"<div class='j'>{text}</div></div>")
    if grid:
        parts.append("<div class='g'>")
        for text in grid:
            parts.append(f"<div class='c'><div class='j'>{text}</div>"
                         f"<code>{text}</code></div>")
        parts.append("</div>")
    open(out_html, "w", encoding="utf-8").write("".join(parts))
    return out_html
