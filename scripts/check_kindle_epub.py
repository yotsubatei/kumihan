"""出来上がったEPUBに、Kindleで崩れる原因になる書き方が残っていないかを検査する。

Kindle（Kindle Previewer・KDPの変換）は、ブラウザやVivliostyleが解釈できるCSSの
一部を解釈しない。解釈しない書き方は警告も無く無視される為、見た目が崩れても
原因が分かりにくい。postbuild の後処理を通したEPUBに対して実行し、
後処理で直しきれていない箇所を一覧にする。EPUBは書き換えない。

検査する事:
- CSS（@page・@font-face・@media print の中を除く）
  - var()（CSS変数）が残っている
  - 論理プロパティ（margin-block 等）の直前に、同じ向きの物理プロパティが無い
  - :is() :where() :has() を含むまとめ書きのセレクタ（ルール全体が捨てられる）
  - leader() calc() を、直前に固定の値を書かずに使っている
  - @font-face の unicode-range（Kindleは範囲を無視して全文字に使う）
  - 縦書きなのに -epub-writing-mode が無い
- 画像: WebP・AVIF（Kindleが新しい組版エンジンを使えなくなる）、表紙画像の有無と形式
- 書体: 可変フォント（fvar）、書体の合計サイズ

使い方: python3 check_kindle_epub.py <EPUBファイル>
終了コード: 要修正（エラー）があれば1、警告だけなら0
"""
import posixpath
import re
import sys
import zipfile
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from epub_resolve_css_vars import blank_comments, declarations, parse_blocks, skipped, split_list  # noqa: E402

LOGICAL = re.compile(r"^(margin|padding|border|inset)-(block|inline)(-start|-end)?(-(width|style|color))?$|^(min-|max-)?(block|inline)-size$")
PHYSICAL = re.compile(r"^(margin|padding|border)-(top|right|bottom|left)(-(width|style|color))?$|^(top|right|bottom|left)$|^(min-|max-)?(width|height)$")
UNSUPPORTED_SEL = re.compile(r":(?:is|where|has)\(")


class Report:
    def __init__(self):
        self.errors, self.warnings, self.infos = [], [], []

    def show(self):
        for label, items in (("要修正", self.errors), ("注意", self.warnings), ("情報", self.infos)):
            for item in items:
                print(f"[{label}] {item}")
        print(f"\n要修正 {len(self.errors)}件・注意 {len(self.warnings)}件")


def check_css(name, text, rep, vertical_seen):
    s = blank_comments(text)
    rules = []
    parse_blocks(s, 0, len(s), (), rules)
    leftover_vars = Counter()
    lonely_logical = Counter()
    no_fallback = Counter()
    for context, selector, b0, b1 in rules:
        if context and context[-1].startswith("@font-face") and "unicode-range" in s[b0:b1]:
            rep.warnings.append(f"{name}: @font-face に unicode-range があります。Kindleは範囲を無視し、"
                                "その書体を全ての文字に使います（約物だけ別の書体にする等の使い方は効きません）")
        if selector is None or skipped(context):
            continue
        parts = split_list(selector)
        if len(parts) > 1 and any(UNSUPPORTED_SEL.search(p) for p in parts):
            rep.errors.append(f"{name}: 「{selector[:80]}」は :is()/:where()/:has() を含むまとめ書きの為、"
                              "Kindleではルール全体が無視されます（epub_split_selectors.py で分けられます）")
        if all(UNSUPPORTED_SEL.search(p) for p in parts):
            continue  # Kindleはこのルールを使わない為、中身は問わない
        decls = declarations(s, b0, b1)
        names = [d[0].lower() for d in decls]
        for k, (prop, value, *_rest) in enumerate(decls):
            p = prop.lower()
            if p.startswith("--"):
                continue
            if "var(" in value:
                leftover_vars[p] += 1
            if LOGICAL.match(p) and not (k > 0 and PHYSICAL.match(names[k - 1])):
                lonely_logical[f"{selector[:40]} {{ {p} }}"] += 1
            for fn in ("leader(", "calc("):
                if fn in value and not (k > 0 and names[k - 1] == p):
                    no_fallback[f"{selector[:30]} {{ {p}: {fn[:-1]}() }}"] += 1
            if p in ("writing-mode", "-epub-writing-mode") and "vertical" in value:
                vertical_seen.append(p)
    if leftover_vars:
        top = "、".join(f"{p}×{n}" for p, n in leftover_vars.most_common(8))
        rep.warnings.append(f"{name}: var() が {sum(leftover_vars.values())}箇所残っています（{top}）。"
                            "Kindleではこれらの宣言は無視されます。見た目に関わるものか確かめてください")
    if no_fallback:
        top = "、".join(list(no_fallback)[:5])
        rep.warnings.append(f"{name}: calc()・leader() を、直前に固定の値を書かずに使っている宣言が {sum(no_fallback.values())}箇所"
                            f"（{top}…）。Kindleはこれらの宣言を無視します。見た目に関わるものは、直前に固定の値を書きます")
    if lonely_logical:
        top = "、".join(list(lonely_logical)[:6])
        rep.warnings.append(f"{name}: 物理プロパティの補いが無い論理プロパティが {sum(lonely_logical.values())}箇所（{top}…）。"
                            "Kindleで効かない事があります（epub_physical_props.py で補えます）")


def main():
    if len(sys.argv) != 2:
        sys.exit("使い方: python3 check_kindle_epub.py <EPUBファイル>")
    epub = Path(sys.argv[1])
    rep = Report()
    with zipfile.ZipFile(epub) as z:
        names = z.namelist()
        container = z.read("META-INF/container.xml").decode("utf-8")
        opf_path = re.search(r'full-path="([^"]+)"', container).group(1)
        opf = z.read(opf_path).decode("utf-8")
        opf_dir = posixpath.dirname(opf_path)

        vertical_seen = []
        for n in names:
            if n.endswith(".css"):
                check_css(n, z.read(n).decode("utf-8", "replace"), rep, vertical_seen)
        if "writing-mode" in vertical_seen and "-epub-writing-mode" not in vertical_seen:
            rep.errors.append("縦書き（writing-mode: vertical-rl）の指定はありますが、-epub-writing-mode: vertical-rl がどこにもありません。"
                              "Kindleでは横書きになります（html の指定に両方を書きます）")
        if vertical_seen and 'page-progression-direction="rtl"' not in opf:
            rep.warnings.append("縦書きですが、OPFの spine に page-progression-direction=\"rtl\" がありません（右綴じになりません）")

        items = re.findall(r"<item\b[^>]*>", opf)
        cover = None
        font_bytes = 0
        for item in items:
            href = re.search(r'href="([^"]+)"', item).group(1)
            mtype = re.search(r'media-type="([^"]+)"', item).group(1)
            path = posixpath.normpath(posixpath.join(opf_dir, href))
            if mtype in ("image/webp", "image/avif"):
                rep.errors.append(f"{href}: {mtype} の画像はKindleの新しい組版エンジン（Enhanced Typesetting）を使えなくします。JPEGかPNGにします")
            if "cover-image" in item:
                cover = (href, mtype, z.getinfo(path).file_size if path in names else 0)
            if mtype.startswith(("font/", "application/font", "application/vnd.ms-opentype", "application/x-font")) and path in names:
                raw = z.read(path)
                font_bytes += len(raw)
                if b"fvar" in raw[:2048]:
                    rep.warnings.append(f"{href}: 可変フォントです。Kindleが対応していない可能性がある為、太さごとの静的な書体を使います")
        if cover is None:
            rep.errors.append("表紙画像（properties=\"cover-image\"）がありません。Kindleで表紙が出ません（epub_cover_image.py で作れます）")
        elif cover[1] not in ("image/jpeg", "image/png") or cover[2] == 0:
            rep.errors.append(f"表紙画像 {cover[0]} が {cover[1]}・{cover[2]}バイトです。JPEGかPNGの、中身のある画像にします")
        else:
            rep.infos.append(f"表紙画像: {cover[0]}（{cover[1]}、{cover[2] // 1024}KB）")
        if font_bytes:
            rep.infos.append(f"埋め込み書体の合計: {font_bytes / 1e6:.1f}MB"
                             + ("（大きい為、epub_subset_fonts.py で使う文字だけに絞り込めます）" if font_bytes > 5e6 else ""))
        rep.infos.append(f"EPUBのサイズ: {epub.stat().st_size / 1e6:.1f}MB")
    rep.show()
    sys.exit(1 if rep.errors else 0)


if __name__ == "__main__":
    main()
