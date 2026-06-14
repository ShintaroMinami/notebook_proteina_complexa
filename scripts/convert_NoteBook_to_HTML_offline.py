#!/usr/bin/env python3
"""Convert an executed notebook into a single offline-interactive HTML file.

py3Dmol normally loads the 3Dmol.js library from a CDN, so exported HTML viewers
do not rotate/zoom without internet. This script vendors the exact 3Dmol.js the
notebook references directly into the HTML, so the 3D viewers stay interactive
fully offline (e.g. on a conference laptop with no network).

It also supports a chardin.js guided tour: cells may carry one or more
`#@chardin[:target] [position] text` directives (target = form | output | code,
default form; position = left | right | top | bottom, English or 左/右/上/下,
default left). Those become data-intro / data-position attributes, and jQuery +
chardin.js + a floating "説明を表示" toggle button are inlined so the tour works
offline. If no cell has a #@chardin directive, none of this is added.

Network is needed once, at conversion time, to fetch 3Dmol.js (and jQuery +
chardin.js when a tour is present). The produced HTML is self-contained afterwards.

Usage:
    uv run --with nbconvert --with nbformat \
        python scripts/convert_NoteBook_to_HTML_offline.py path/to/notebook.ipynb

    # optional explicit output path
    uv run --with nbconvert --with nbformat \
        python scripts/convert_NoteBook_to_HTML_offline.py in.ipynb -o out.html
"""

from __future__ import annotations

import argparse
import ast
import re
import sys
import urllib.request
from pathlib import Path

import nbformat
from nbconvert import HTMLExporter
from nbconvert.preprocessors import Preprocessor

# Matches the CDN URL py3Dmol injects, e.g.
# https://cdn.jsdelivr.net/npm/3dmol@2.5.5/build/3Dmol-min.js
_THREEDMOL_URL_RE = re.compile(r"https?://[^'\"]*3Dmol[^'\"]*\.js", re.IGNORECASE)

# ---- Colab form directive parsing (#@title / #@markdown / #@param) ----
_TITLE_RE = re.compile(r"^\s*#@title\s?(?P<text>.*?)\s*(?:\{[^}]*\})?\s*$")
_MARKDOWN_RE = re.compile(r"^\s*#@markdown ?(?P<text>.*)$")
_PARAM_RE = re.compile(
    r"^\s*(?P<name>\w+)\s*=\s*(?P<val>.*?)\s*#@param\b(?P<spec>.*)$"
)

# ---- chardin.js guided-tour directive: #@chardin[:target] [position] text ----
# target  : form (default) | output | code   -> which element gets the hint
# position: left (default) | right | top | bottom  (English or 左/右/上/下)
# text    : the hint, rendered as HTML by chardin (so <br> etc. are allowed)
_POS_EN = {"left", "right", "top", "bottom"}
_POS_JP = {"左": "left", "右": "right", "上": "top", "下": "bottom"}
_CHARDIN_TARGETS = {"form", "output", "code", "cell"}
_CHARDIN_RE = re.compile(r"^\s*#@chardin(?::(?P<target>\w+))?\s+(?P<rest>.+?)\s*$")


def _parse_chardin(target: str | None, rest: str) -> tuple[str, dict]:
    """Parse one `#@chardin[:target] [position] text` directive into (target, spec).

    The text may contain inline HTML such as <br>; the template autoescapes it into
    entities, which the browser decodes back so chardin (data-intro -> innerHTML)
    renders the tag.
    """
    target = (target or "form").lower()
    if target not in _CHARDIN_TARGETS:
        target = "form"
    rest = rest.strip()
    head, _, tail = rest.partition(" ")
    if head in _POS_EN:
        pos, text = head, tail.strip()
    elif head in _POS_JP:
        pos, text = _POS_JP[head], tail.strip()
    else:
        pos, text = "left", rest
    return target, {"position": pos, "text": text}


def _literal(text: str) -> str:
    """Best-effort unwrap of a Python literal to its display string."""
    try:
        return str(ast.literal_eval(text.strip()))
    except (ValueError, SyntaxError):
        return text.strip().strip("\"'")


def _parse_param(name: str, val_raw: str, spec: str) -> dict:
    """Turn one `name = value #@param ...` line into a widget field spec."""
    spec = spec.strip()
    if spec.startswith("["):  # dropdown: #@param ["a", "b", ...]
        try:
            options = [str(o) for o in ast.literal_eval(spec)]
        except (ValueError, SyntaxError):
            options = []
        return {"name": name, "kind": "enum", "options": options,
                "value": _literal(val_raw)}

    type_match = re.search(r'type:\s*"(\w+)"', spec)
    ptype = type_match.group(1) if type_match else "string"
    if ptype == "boolean":
        return {"name": name, "kind": "boolean", "checked": val_raw.strip() == "True"}
    if ptype == "slider":
        field = {"name": name, "kind": "slider", "value": val_raw.strip()}
        for key in ("min", "max", "step"):
            km = re.search(key + r":\s*([-\d.]+)", spec)
            field[key] = km.group(1) if km else ""
        return field
    # string / integer / number → text box (strings get their quotes stripped)
    value = _literal(val_raw) if ptype == "string" else val_raw.strip()
    return {"name": name, "kind": "text", "value": value}


def parse_colab_form(source: str) -> dict:
    """Extract Colab form metadata (title, markdown, param fields) from a cell."""
    title = ""
    markdown_lines: list[str] = []
    fields: list[dict] = []
    chardin: dict[str, dict] = {}
    for line in source.splitlines():
        tm = _TITLE_RE.match(line)
        if tm and line.lstrip().startswith("#@title"):
            title = tm.group("text").strip()
            continue
        cm = _CHARDIN_RE.match(line)
        if cm and line.lstrip().startswith("#@chardin"):
            target, spec = _parse_chardin(cm.group("target"), cm.group("rest"))
            chardin[target] = spec
            continue
        mm = _MARKDOWN_RE.match(line)
        if mm and line.lstrip().startswith("#@markdown"):
            markdown_lines.append(mm.group("text"))
            continue
        pm = _PARAM_RE.match(line)
        if pm:
            fields.append(_parse_param(pm.group("name"), pm.group("val"),
                                       pm.group("spec")))
    return {"title": title, "markdown": "\n".join(markdown_lines),
            "fields": fields, "chardin": chardin}


class ColabFormPreprocessor(Preprocessor):
    """Attach parsed Colab form metadata to each code cell for the template."""

    def preprocess_cell(self, cell, resources, index):
        if cell.cell_type == "code":
            cell.metadata["colab_form"] = parse_colab_form(cell.source)
        return cell, resources


def _fetch(url: str, timeout: int = 120) -> str:
    """Download a text resource. Decodes with utf-8-sig so a leading BOM is stripped
    — a BOM left in inlined CSS would corrupt the first selector (e.g. it broke the
    .chardinjs-overlay rule, leaving the overlay position:static)."""
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return resp.read().decode("utf-8-sig")


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


# chardin.js (guided-tour overlay): jQuery comes from a CDN; chardin.js + its CSS are
# vendored under scripts/vendor/ because the CDN builds behave differently (the newer
# one spotlights one element at a time with a 4-mask overlay). The vendored copy is
# the single-overlay "show all hints at once" version that matches the reference.
_JQUERY_URL = "https://code.jquery.com/jquery-1.9.1.min.js"
_VENDOR_DIR = Path(__file__).resolve().parent / "vendor"

# Floating "show guide" button + tooltip styling layered on top of chardin's own CSS.
_CHARDIN_EXTRA_CSS = (
    "#cc-guide-btn{position:fixed;right:20px;top:20px;z-index:2147483000;"
    "display:flex;align-items:center;gap:6px;padding:10px 16px;border:0;border-radius:24px;"
    "background:#1a73e8;color:#fff;font-family:'Roboto','Zen Kaku Gothic New',sans-serif;"
    "font-size:14px;font-weight:500;box-shadow:0 2px 8px rgba(0,0,0,.3);cursor:pointer;}"
    "#cc-guide-btn:hover{background:#1666c9;}"
    ".chardinjs-tooltiptext{font-family:'Roboto','Zen Kaku Gothic New',sans-serif;"
    "font-size:13px;line-height:1.6;}"
    ".chardinjs-tooltip.chardinjs-left{max-width:250px;}"
)

# Injects a fixed "説明を表示" button that toggles the chardin overlay over the
# elements that carry data-intro.
_CHARDIN_BTN_JS = (
    "(function(){function init(){var $=window.jQuery;if(!$){return;}"
    "var b=document.createElement('button');b.id='cc-guide-btn';b.type='button';"
    "b.textContent='説明を表示';"
    "b.addEventListener('click',function(){$('body').chardinJs('toggle');});"
    "document.body.appendChild(b);}"
    "if(document.readyState!=='loading'){init();}"
    "else{document.addEventListener('DOMContentLoaded',init);}})();"
)


def _embed_chardin(html: str) -> str:
    """Inline jQuery + chardin.js and a guide button so the data-intro hints work
    offline. No-op when the notebook has no #@chardin directives (no data-intro)."""
    if "data-intro=" not in html:
        return html

    print(f"fetching jQuery: {_JQUERY_URL}; vendoring chardin.js from {_VENDOR_DIR}")
    jquery_js = _fetch(_JQUERY_URL)
    chardin_js = (_VENDOR_DIR / "chardinjs.js").read_text(encoding="utf-8")
    chardin_css = (_VENDOR_DIR / "chardinjs.css").read_text(encoding="utf-8")

    head = (
        "<!-- chardin.js injected -->\n"
        f"<style type=\"text/css\">{chardin_css}\n{_CHARDIN_EXTRA_CSS}</style>\n"
    )
    if "</head>" in html:
        html = html.replace("</head>", head + "</head>", 1)
    else:
        html = head + html

    # jQuery checks define.amd; the lab template ships require.js, so temporarily
    # disable the AMD global so jQuery assigns window.jQuery (chardin needs it).
    body = (
        "<script>window.__cc_prev_define=window.define;window.define=undefined;</script>\n"
        f"<script>{jquery_js}</script>\n"
        f"<script>{chardin_js}</script>\n"
        "<script>window.define=window.__cc_prev_define;</script>\n"
        f"<script>{_CHARDIN_BTN_JS}</script>\n"
    )
    if "</body>" in html:
        return html.replace("</body>", body + "</body>", 1)
    return html + body


def convert(nb_path: Path, out_path: Path | None) -> Path:
    """Render the notebook to a self-contained offline-interactive HTML file."""
    nb = nbformat.read(nb_path, as_version=4)
    exporter = HTMLExporter(
        template_name="colab_template",
        extra_template_basedirs=[str(Path(__file__).resolve().parent)],
    )
    exporter.register_preprocessor(ColabFormPreprocessor, enabled=True)
    html, _ = exporter.from_notebook_node(nb)
    html = _embed_3dmol(html)
    html = _embed_chardin(html)

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
