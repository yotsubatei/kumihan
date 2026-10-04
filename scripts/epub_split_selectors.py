"""EPUB内のCSSで、まとめて書いたセレクタ（`a, b:is(c) { … }`）を1つずつのルールに分ける後処理。

CSSでは、まとめて書いたセレクタのうち1つでも解釈できないものがあると、ルール全体が
捨てられる。Kindleは :is() :where() :has() を解釈できない為、例えば
`ul, ul:not(:is(ul *, ol *)) { list-style-type: none; }` が丸ごと無視され、
箇条書きの点が消えずに、::before で付けた「・」と二重に表示されていた。
:is() :where() :has() を含むセレクタが混ざったまとめ書きを、セレクタ1つずつの
ルールに分ける（宣言は同じ、順番も保つ）。各セレクタの詳細度は変わらない為、
解釈できるリーダーでの見た目は変わらず、Kindleでは解釈できるセレクタの分だけ効く。
@page・@font-face・@media printの中は、電子書籍リーダーが使わない為そのまま。

使い方: python3 epub_split_selectors.py <EPUBファイル>
"""
import re
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from epub_resolve_css_vars import blank_comments, skip_string, skipped, split_list  # noqa: E402

UNSUPPORTED = re.compile(r":(?:is|where|has)\(")


def find_rules(s, start, end, context, out):
    """(文脈, セレクタ, セレクタの開始位置, 本文の終了位置〈閉じ括弧の次〉) を集める。"""
    i, prelude_start = start, start
    while i < end:
        c = s[i]
        if c in "\"'":
            i = skip_string(s, i)
            continue
        if c == ";":
            prelude_start = i + 1
        elif c == "{":
            prelude = " ".join(s[prelude_start:i].split())
            depth, j = 1, i + 1
            while j < end and depth:
                if s[j] in "\"'":
                    j = skip_string(s, j)
                    continue
                depth += {"{": 1, "}": -1}.get(s[j], 0)
                j += 1
            if prelude.startswith("@"):
                if prelude.startswith(("@media", "@supports")):
                    find_rules(s, i + 1, j - 1, context + (prelude,), out)
            else:
                lead = len(s[prelude_start:i]) - len(s[prelude_start:i].lstrip())
                out.append((context, prelude, prelude_start + lead, i, j))
            i, prelude_start = j, j
            continue
        elif c == "}":
            prelude_start = i + 1
        i += 1


def main():
    if len(sys.argv) != 2:
        sys.exit("使い方: python3 epub_split_selectors.py <EPUBファイル>")
    epub = Path(sys.argv[1])
    with zipfile.ZipFile(epub) as z:
        infos = z.infolist()
        data = {i.filename: z.read(i.filename) for i in infos}

    total = 0
    for name in [n for n in data if n.endswith(".css")]:
        text = data[name].decode("utf-8")
        s = blank_comments(text)
        rules = []
        find_rules(s, 0, len(s), (), rules)
        edits = []
        for context, selector, sel_start, brace, rule_end in rules:
            if skipped(context):
                continue
            parts = split_list(selector)
            if len(parts) < 2 or not any(UNSUPPORTED.search(p) for p in parts):
                continue
            body = text[brace:rule_end]  # 「{ … }」（コメントを含めて元のまま）
            edits.append((sel_start, rule_end, "\n".join(f"{p} {body}" for p in parts)))
            total += 1
        if not edits:
            continue
        for a, b, rep in sorted(edits, reverse=True):
            text = text[:a] + rep + text[b:]
        data[name] = text.encode("utf-8")

    tmp = epub.with_suffix(".epub.tmp")
    with zipfile.ZipFile(tmp, "w") as out:
        for info in infos:
            method = zipfile.ZIP_STORED if info.filename == "mimetype" else zipfile.ZIP_DEFLATED
            out.writestr(info, data[info.filename], compress_type=method)
    tmp.replace(epub)
    print(f"EPUBのCSSで、Kindleが解釈できないセレクタを含むまとめ書きを分けました: {total}箇所")


if __name__ == "__main__":
    main()
