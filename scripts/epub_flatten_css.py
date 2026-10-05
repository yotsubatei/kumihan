"""EPUBのテーマのCSS（themes/node_modules/@vivliostyle/... の @import の連なり）を、1つのCSSにまとめて
EPUBの直下（theme.css）に置き直す後処理。あわせて、ZIPの中のフォルダの項目（名前が / で終わる物）を除く。

Vivliostyle は、テーマのCSSを node_modules のフォルダの形のまま（パスに「@」を含む）EPUBに入れ、
CSSどうしを @import で何段にもつなぐ。epubcheck・Kindle Previewer は通るが、KDPのサーバーの変換で
「Kindle 変換で内部エラーが発生しました」となった本が2冊続いた為、KDPが受け付けやすい単純な形
（CSSは1つのファイル、パスは英数字だけ）にする。

- 各XHTMLの <link> のうち themes/node_modules/ の物を、まとめたCSS（theme.css）への1本に替える
- @import を中身で置き換える（url() の相対パスは、まとめたCSSの場所からのパスに直す）
- まとめた元のCSSは、EPUB・content.opf から外す
- フォルダの項目を除く

使い方: python3 epub_flatten_css.py <EPUBファイル>
"""
import posixpath
import re
import sys
import zipfile
from pathlib import Path

PREFIX = "themes/node_modules/"
OUT_NAME = "theme.css"


def main():
    epub = Path(sys.argv[1])
    with zipfile.ZipFile(epub) as z:
        infos = [i for i in z.infolist() if not i.filename.endswith("/")]
        dropped_dirs = len(z.infolist()) - len(infos)
        data = {i.filename: z.read(i.filename) for i in infos}

    opf_name = next(k for k in data if k.endswith(".opf"))
    root = posixpath.dirname(opf_name)  # 例: EPUB
    out_path = posixpath.join(root, OUT_NAME)

    def inline(path, seen):
        """path のCSSの中身を、@import を展開して返す。url() は out_path からの相対に直す"""
        if path in seen or path not in data:
            return ""
        seen.add(path)
        css = data[path].decode("utf-8")
        base = posixpath.dirname(path)

        def fix_url(m):
            u = m.group(2).strip("'\"")
            if re.match(r"^(data:|https?:|#)", u):
                return m.group(0)
            absu = posixpath.normpath(posixpath.join(base, u))
            return f"url({m.group(1)}{posixpath.relpath(absu, root)}{m.group(1)})"

        def do_import(m):
            u = m.group(1) or m.group(2)
            target = posixpath.normpath(posixpath.join(base, u))
            return f"\n/* ---- {posixpath.relpath(target, root)} ---- */\n" + inline(target, seen) + "\n"

        # @import url(x); / @import "x";（先に展開してから、残りの url() を直す）
        css = re.sub(r"""@import\s+(?:url\(\s*['"]?([^)'"]+)['"]?\s*\)|['"]([^'"]+)['"])\s*;""", do_import, css)
        css = re.sub(r'url\(\s*([\'"]?)([^)\'"]+)\1\s*\)', fix_url, css)
        return css

    # 各XHTMLが読み込んでいるテーマのCSSを、読み込みの順にまとめる
    order, linked = [], set()
    for name in sorted(data):
        if not name.endswith(".xhtml"):
            continue
        for href in re.findall(r'<link[^>]+href="([^"]+\.css)"', data[name].decode("utf-8")):
            p = posixpath.normpath(posixpath.join(posixpath.dirname(name), href))
            if PREFIX in p and p not in linked:
                linked.add(p)
                order.append(p)
    if not order:
        print("テーマのCSS（node_modules）は見つかりませんでした。フォルダの項目だけを除きます"
              f"（{dropped_dirs}件）")
    seen = set()
    merged = "".join(inline(p, seen) for p in order)
    # @charset は先頭に1つだけ
    merged = re.sub(r'@charset\s+"[^"]+"\s*;', "", merged)
    merged = '@charset "UTF-8";\n' + merged

    removed = {p for p in data if PREFIX in p and p.endswith(".css")} if order else set()
    out = {k: v for k, v in data.items() if k not in removed}
    if order:
        out[out_path] = merged.encode("utf-8")
        for name in list(out):
            if not name.endswith(".xhtml"):
                continue
            t = out[name].decode("utf-8")
            rel_out = posixpath.relpath(out_path, posixpath.dirname(name))
            first = [True]

            def rep(m):
                href = m.group(1)
                p = posixpath.normpath(posixpath.join(posixpath.dirname(name), href))
                if PREFIX not in p:
                    return m.group(0)
                if first[0]:
                    first[0] = False
                    return m.group(0).replace(href, rel_out)
                return ""
            out[name] = re.sub(r'<link[^>]+href="([^"]+\.css)"[^>]*/?>', rep, t).encode("utf-8")
        # content.opf：元のCSSの項目を外し、まとめたCSSの項目を足す
        opf = out[opf_name].decode("utf-8")
        for p in removed:
            href = posixpath.relpath(p, root)
            opf = re.sub(r'\s*<item [^>]*href="' + re.escape(href) + r'"[^>]*/?>(?:</item>)?', "", opf)
        opf = opf.replace("</manifest>", f'  <item id="theme-css" href="{OUT_NAME}" media-type="text/css"/>\n  </manifest>', 1)
        out[opf_name] = opf.encode("utf-8")

    tmp = epub.with_suffix(".epub.tmp")
    names = [i.filename for i in infos if i.filename in out] + ([out_path] if order and out_path not in data else [])
    with zipfile.ZipFile(tmp, "w") as zo:
        zo.writestr(zipfile.ZipInfo("mimetype"), out["mimetype"], compress_type=zipfile.ZIP_STORED)
        for n in names:
            if n == "mimetype":
                continue
            zo.writestr(n, out[n], compress_type=zipfile.ZIP_DEFLATED)
    tmp.replace(epub)
    print(f"EPUBのテーマのCSSを1つ（{OUT_NAME}）にまとめました: {len(removed)}ファイル、"
          f"フォルダの項目を除きました: {dropped_dirs}件")


if __name__ == "__main__":
    main()
