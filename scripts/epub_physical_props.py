"""EPUB内のCSSの論理プロパティ（margin-block等）に、同じ値の物理プロパティ（上下左右）を補う後処理。

Kindleはmargin-block等の論理プロパティを一部解釈できない（試験用EPUBで、margin-blockで
間隔を付けた枠どうしがくっつく事を確認。padding-inline-startは効いた）。各論理プロパティの
直前に、同じ値の物理プロパティを書き足す。論理プロパティを解釈できるリーダーでは後ろの
論理プロパティが使われ（同じ値の為、見た目は変わらない）、解釈できないリーダーでは
物理プロパティが使われる。

縦書き（vertical-rl）は block-start→右、block-end→左、inline-start→上、inline-end→下。
横書き（horizontal-tb）は block-start→上、block-end→下、inline-start→左、inline-end→右。
縦書きの本の中で横書きにしている要素（例: テーマが横書きにしているfigure）は
--horizontal で指定すると、その要素と中身を横書きとして変換する。
@page・@font-face・@media printの中は、電子書籍リーダーが使わない為そのまま。
epub_resolve_css_vars.py の後に実行する（var()が解決済みの値を使う為）。

使い方: python3 epub_physical_props.py <EPUBファイル> [--writing-mode vertical-rl|horizontal-tb]
                                       [--horizontal 要素名 ...]
例（縦書きの本、図版は横書き）: --writing-mode vertical-rl --horizontal figure
例（横書きの本）: --writing-mode horizontal-tb
"""
import argparse
import re
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from epub_resolve_css_vars import blank_comments, declarations, parse_blocks, skipped  # noqa: E402

SIDES = {
    "vertical": {"block-start": "right", "block-end": "left",
                 "inline-start": "top", "inline-end": "bottom"},
    "horizontal": {"block-start": "top", "block-end": "bottom",
                   "inline-start": "left", "inline-end": "right"},
}
SIZES = {
    "vertical": {"inline": "height", "block": "width"},
    "horizontal": {"inline": "width", "block": "height"},
}
BOX_RE = re.compile(r"^(margin|padding|border|inset)-(block|inline)(?:-(start|end))?(?:-(width|style|color))?$")
SIZE_RE = re.compile(r"^(min-|max-)?(inline|block)-size$")


def split_values(value):
    """空白区切りの値を、括弧の中を分割しないように分ける。"""
    parts, depth, cur = [], 0, ""
    for c in value:
        depth += (c == "(") - (c == ")")
        if c.isspace() and depth == 0:
            if cur:
                parts.append(cur)
            cur = ""
        else:
            cur += c
    if cur:
        parts.append(cur)
    return parts


def physical(name, value, mode):
    """論理プロパティ1つを、物理プロパティの(名前, 値)のリストに変換する。"""
    important = ""
    if value.rstrip().endswith("!important"):
        value, important = value.rstrip()[:-len("!important")].rstrip(), " !important"
    m = SIZE_RE.match(name)
    if m:
        return [(f"{m.group(1) or ''}{SIZES[mode][m.group(2)]}", value + important)]
    m = BOX_RE.match(name)
    if not m:
        return []
    kind, axis, edge, sub = m.groups()
    sides = SIDES[mode]

    def prop(side):
        if kind == "inset":
            return side
        return f"{kind}-{side}" + (f"-{sub}" if sub else "")

    if edge:
        return [(prop(sides[f"{axis}-{edge}"]), value + important)]
    if kind == "border" and sub is None:
        # border-block: 1px solid #000 のような一括指定は、両側に同じ値
        return [(prop(sides[f"{axis}-start"]), value + important),
                (prop(sides[f"{axis}-end"]), value + important)]
    vals = split_values(value)
    if not vals or len(vals) > 2:
        return []
    start, end = vals[0], vals[-1]
    return [(prop(sides[f"{axis}-start"]), start + important),
            (prop(sides[f"{axis}-end"]), end + important)]


def mode_of(selector, base, horizontal_elements):
    """セレクタが横書きの要素（horizontal_elements）の中を指すなら横書き、それ以外は本の書字方向。"""
    if base == "horizontal":
        return "horizontal"
    plain = re.sub(r":(?:has|not|is|where)\([^()]*(?:\([^()]*\)[^()]*)*\)", "", selector)
    for el in horizontal_elements:
        if re.search(rf"(?<![\w-]){re.escape(el)}(?![\w-])", plain):
            return "horizontal"
    return "vertical"


def main():
    ap = argparse.ArgumentParser(description="EPUBの論理プロパティに物理プロパティを補う")
    ap.add_argument("epub")
    ap.add_argument("--writing-mode", choices=["vertical-rl", "horizontal-tb"], default="vertical-rl")
    ap.add_argument("--horizontal", nargs="*", default=[], help="縦書きの本の中で横書きにしている要素名")
    args = ap.parse_args()
    epub = Path(args.epub)
    base = "vertical" if args.writing_mode == "vertical-rl" else "horizontal"
    with zipfile.ZipFile(epub) as z:
        infos = z.infolist()
        data = {i.filename: z.read(i.filename) for i in infos}

    total = 0
    for name in [n for n in data if n.endswith(".css")]:
        text = data[name].decode("utf-8")
        s = blank_comments(text)
        rules = []
        parse_blocks(s, 0, len(s), (), rules)
        edits = []
        for context, selector, b0, b1 in rules:
            if selector is None or skipped(context):
                continue
            decls = declarations(s, b0, b1)
            existing = {n for n, *_ in decls}
            for dname, value, dstart, vstart, vend in decls:
                if "var(" in value:
                    continue
                selectors = [x.strip() for x in selector.split(",")]
                modes = {mode_of(x, base, args.horizontal) for x in selectors}
                if len(modes) != 1:
                    continue
                pairs = physical(dname, value, modes.pop())
                pairs = [(p, v) for p, v in pairs if p not in existing]
                if not pairs:
                    continue
                edits.append((dstart, "".join(f"{p}: {v}; " for p, v in pairs)))
                total += 1
        if not edits:
            continue
        for pos, ins in sorted(edits, reverse=True):
            text = text[:pos] + ins + text[pos:]
        data[name] = text.encode("utf-8")

    tmp = epub.with_suffix(".epub.tmp")
    with zipfile.ZipFile(tmp, "w") as out:
        for info in infos:
            method = zipfile.ZIP_STORED if info.filename == "mimetype" else zipfile.ZIP_DEFLATED
            out.writestr(info, data[info.filename], compress_type=method)
    tmp.replace(epub)
    print(f"EPUBの論理プロパティに物理プロパティを補いました: {total}箇所")


if __name__ == "__main__":
    main()
