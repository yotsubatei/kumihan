"""EPUBの中のSVGの画像を、PNGの画像に置き換える後処理。

KDPの変換は、画像として使うSVG（<img src="x.svg"> や CSS の url(x.svg)）を扱えない事があり、
epubcheck・Kindle Previewer が通っても「Kindle 変換で内部エラー」になる原因の候補になる。
SVGを rsvg-convert でPNG（既定は幅800px程度まで。小さなアイコンは元の大きさの8倍）にし、
content.opf・XHTML・CSS の参照を書き換える。本文に直接書いた <svg> 要素はそのまま。

使い方: python3 epub_svg_to_png.py <EPUBファイル>
依存: rsvg-convert（Homebrew の librsvg）
"""
import posixpath
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path


def main():
    epub = Path(sys.argv[1])
    if not shutil.which("rsvg-convert"):
        sys.exit("rsvg-convert がありません（brew install librsvg）")
    with zipfile.ZipFile(epub) as z:
        infos = z.infolist()
        data = {i.filename: z.read(i.filename) for i in infos}
    svgs = [n for n in data if n.lower().endswith(".svg")]
    if not svgs:
        print("SVGの画像はありませんでした")
        return
    renames = {}
    with tempfile.TemporaryDirectory() as tmp:
        for n in svgs:
            src = Path(tmp) / "in.svg"
            src.write_bytes(data[n])
            m = re.search(rb'width="([\d.]+)', data[n])
            w = float(m.group(1)) if m else 100
            zoom = 8 if w < 100 else max(1, 800 / w)
            out = Path(tmp) / "out.png"
            subprocess.run(["rsvg-convert", "-z", f"{zoom:.3f}", "-o", str(out), str(src)], check=True)
            new = n[:-4] + ".png"
            renames[n] = new
            data[new] = out.read_bytes()
            del data[n]

    for name in list(data):
        if not name.endswith((".xhtml", ".html", ".css", ".opf")):
            continue
        text = data[name].decode("utf-8")
        base = posixpath.dirname(name)
        for old, new in renames.items():
            rel_old = posixpath.relpath(old, base)
            rel_new = posixpath.relpath(new, base)
            text = text.replace(rel_old, rel_new)
        if name.endswith(".opf"):
            text = re.sub(r'(href="[^"]+\.png"[^>]*?)media-type="image/svg\+xml"', r'\1media-type="image/png"', text)
            text = re.sub(r'media-type="image/svg\+xml"([^>]*?href="[^"]+\.png")', r'media-type="image/png"\1', text)
        data[name] = text.encode("utf-8")

    tmp = epub.with_suffix(".epub.tmp")
    with zipfile.ZipFile(tmp, "w") as zo:
        for info in infos:
            n = renames.get(info.filename, info.filename)
            method = zipfile.ZIP_STORED if n == "mimetype" else zipfile.ZIP_DEFLATED
            zo.writestr(zipfile.ZipInfo(n, info.date_time), data[n], compress_type=method)
    tmp.replace(epub)
    print(f"EPUBのSVGの画像をPNGにしました: {len(renames)}件")


if __name__ == "__main__":
    main()
