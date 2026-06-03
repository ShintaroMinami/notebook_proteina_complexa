#!/usr/bin/env python3
"""Convert an executed notebook into a single offline-interactive HTML file.

py3Dmol normally loads the 3Dmol.js library from a CDN, so exported HTML viewers
do not rotate/zoom without internet. This script vendors the exact 3Dmol.js the
notebook references directly into the HTML, so the 3D viewers stay interactive
fully offline (e.g. on a conference laptop with no network).

Network is needed once, at conversion time, to fetch 3Dmol.js. The produced HTML
is self-contained afterwards.

Usage:
    uv run --with nbconvert --with nbformat \
        python scripts/convert_NoteBook_to_HTML_offline.py path/to/notebook.ipynb

    # optional explicit output path
    uv run --with nbconvert --with nbformat \
        python scripts/convert_NoteBook_to_HTML_offline.py in.ipynb -o out.html
"""

from __future__ import annotations

import argparse
import re
import sys
import urllib.request
from pathlib import Path

import nbformat
from nbconvert import HTMLExporter

# Matches the CDN URL py3Dmol injects, e.g.
# https://cdn.jsdelivr.net/npm/3dmol@2.5.5/build/3Dmol-min.js
_THREEDMOL_URL_RE = re.compile(r"https?://[^'\"]*3Dmol[^'\"]*\.js", re.IGNORECASE)


def _fetch(url: str, timeout: int = 120) -> str:
    """Download a text resource (the 3Dmol.js bundle)."""
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return resp.read().decode("utf-8")


def _embed_3dmol(html: str) -> str:
    """Inline 3Dmol.js into the HTML head and short-circuit the CDN loader.

    py3Dmol guards its loader with `if (typeof $3Dmolpromise === 'undefined')`,
    so pre-defining `$3Dmolpromise` as an already-resolved promise makes every
    viewer skip the CDN and use the embedded global `$3Dmol`. The AMD globals are
    temporarily disabled around the bundle so its UMD wrapper assigns the browser
    global even if a require.js loader is present in the template.
    """
    match = _THREEDMOL_URL_RE.search(html)
    if not match:
        print("warning: no 3Dmol.js URL found; "
              "the notebook may have no 3D viewers (nothing to embed).")
        return html

    url = match.group(0)
    print(f"fetching 3Dmol.js: {url}")
    js = _fetch(url)

    inject = (
        "<script>window.__amd_define=window.define;window.define=undefined;</script>\n"
        f"<script>{js}</script>\n"
        "<script>window.define=window.__amd_define;"
        "var $3Dmolpromise=Promise.resolve();</script>\n"
    )
    if "</head>" in html:
        return html.replace("</head>", inject + "</head>", 1)
    # Templates without a </head> (rare): prepend so it runs before viewers.
    return inject + html


def convert(nb_path: Path, out_path: Path | None) -> Path:
    """Render the notebook to a self-contained offline-interactive HTML file."""
    nb = nbformat.read(nb_path, as_version=4)
    html, _ = HTMLExporter(template_name="lab").from_notebook_node(nb)
    html = _embed_3dmol(html)

    out_path = out_path or nb_path.with_suffix(".offline.html")
    out_path.write_text(html, encoding="utf-8")
    return out_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("notebook", type=Path, help="executed .ipynb file")
    parser.add_argument("-o", "--output", type=Path, default=None,
                        help="output HTML path (default: <notebook>.offline.html)")
    args = parser.parse_args()

    if not args.notebook.exists():
        print(f"error: notebook not found: {args.notebook}", file=sys.stderr)
        return 1

    out = convert(args.notebook, args.output)
    size_mb = out.stat().st_size / (1024 * 1024)
    print(f"wrote {out}  ({size_mb:.1f} MB)")
    print("Tip: 機内モードで file:// から開き、3D構造が回転するか確認してください。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
