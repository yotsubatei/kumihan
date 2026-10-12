"""EPUBのCSSから、KDPの変換を「Kindle 変換で内部エラー」で止める指定を取り除く後処理。

2026-10-05、Vivliostyle のテーマ（theme-base の basic.css）で作った本が、KDPで内部エラーになり続けた。
試験用の下書きで1つずつ外して確かめた結果、書字方向と段組の指定（writing-mode・columns 等）を
テーマの書式から外すと通った（改ページの指定・:is()・var()・書体・本の独自の書式は原因ではなかった）。
テーマは、引用・図・コード・表のそれぞれに `writing-mode: unset` を、本全体（html）に
`columns: 1; column-fill: balance; column-gap: …` を指定している。

取り除く物：
- `writing-mode`（-epub- 付きも）の値が unset・initial・inherit・revert の宣言（書字方向を「親から外す」指定）と、
  値に解決できない var() が残った宣言

CSS変数を解決した後（epub_resolve_css_vars.py の後）に実行する（テーマは書字方向を変数で指定している為）。
- `columns`・`column-count`・`column-width`・`column-fill`・`column-gap`・`column-rule*`・`column-span` の宣言
  （段組。Kindle の本文は段組しない）

本全体の書字方向（`html { writing-mode: vertical-rl }` 等、値が具体的な物）は残す。
EPUBの書式だけを書き換え、紙のPDFには触れない。

使い方: python3 epub_kindle_safe_css.py <EPUBファイル>
"""
import re
import sys
import zipfile
from pathlib import Path

WM = re.compile(r"(?<![-\w])(?:-epub-|-webkit-)?writing-mode\s*:\s*(?:unset|initial|inherit|revert(?:-layer)?|var\([^;{}]*\))\s*(?:!important\s*)?(;|(?=\}))", re.I)
COL = re.compile(r"(?<![-\w])(?:-webkit-|-moz-)?(?:columns|column-(?:count|width|fill|gap|rule(?:-[a-z]+)?|span))\s*:[^;{}]*(;|(?=\}))", re.I)


def main():
    epub = Path(sys.argv[1])
    with zipfile.ZipFile(epub) as z:
        infos = z.infolist()
        data = {i.filename: z.read(i.filename) for i in infos}
    n_wm = n_col = 0
    for name in list(data):
        if not name.endswith(".css"):
            continue
        t = data[name].decode("utf-8")
        t, a = WM.subn("", t)
        t, b = COL.subn("", t)
        n_wm += a
        n_col += b
        data[name] = t.encode("utf-8")
    tmp = epub.with_suffix(".epub.tmp")
    with zipfile.ZipFile(tmp, "w") as zo:
        for i in infos:
            zo.writestr(i, data[i.filename], compress_type=zipfile.ZIP_STORED if i.filename == "mimetype" else zipfile.ZIP_DEFLATED)
    tmp.replace(epub)
    print(f"EPUBのCSSから、KDPの変換を止める指定を外しました: 書字方向の解除{n_wm}件、段組{n_col}件")


if __name__ == "__main__":
    main()
