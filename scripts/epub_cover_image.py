"""EPUBの表紙を、PDFの表紙ページ（1ページ目）を画像化したものに差し替える後処理。

Vivliostyleの設定（cover.src）に実在する画像を指定しないと、EPUBには空の画像が入る。
また表紙がWebP等Kindleで使えない形式だと、Kindle Previewerで表紙が組み込まれないうえ、
新しい組版エンジン（Enhanced Typesetting）も使えず、書式全般が崩れる。
PDFの1ページ目をJPEG（高さ2560px）にして表紙画像とし、表紙ページ（cover.xhtml）も
HTMLの文字からこの画像に置き換える（cover.xhtmlにあるnav〈目次のナビゲーション〉は残す）。
表紙ページは linear="no" で本文の流れから外す（Kindleは表紙画像を自動で1ページ目に
表示する為、表紙が2回続かないようにする）。

前提: Vivliostyleの設定で cover.src を指定し（ファイルは実在しなくてよい）、
content.opf に properties="cover-image" の項目と cover.xhtml がある事。

使い方: python3 epub_cover_image.py <EPUBファイル> <PDFファイル> [--alt 代替テキスト]
       （代替テキストの既定: EPUBの書名 dc:title）
"""
import argparse
import re
import sys
import time
import zipfile
from pathlib import Path

import fitz

COVER_HEIGHT_PX = 2560  # Kindleが推奨する表紙画像の高さ
COVER_NAME = "cover-image.jpg"


def render_cover(pdf_path):
    doc = fitz.open(pdf_path)
    page = doc[0]
    zoom = COVER_HEIGHT_PX / page.rect.height
    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
    data = pix.tobytes("jpg", jpg_quality=90)
    doc.close()
    return data, pix.width, pix.height


def main():
    ap = argparse.ArgumentParser(description="EPUBの表紙をPDFの1ページ目の画像に差し替える")
    ap.add_argument("epub")
    ap.add_argument("pdf")
    ap.add_argument("--alt", help="表紙画像の代替テキスト（既定: EPUBの書名）")
    args = ap.parse_args()
    epub, pdf = Path(args.epub), Path(args.pdf)
    jpg, w, h = render_cover(pdf)

    with zipfile.ZipFile(epub) as z:
        infos = z.infolist()
        data = {i.filename: z.read(i.filename) for i in infos}

    opf_name = next(n for n in data if n.endswith(".opf"))
    opf = data[opf_name].decode("utf-8")
    title = re.search(r"<dc:title[^>]*>([^<]+)</dc:title>", opf)
    cover_alt = args.alt or (title.group(1) if title else "表紙")
    m = re.search(r'<item [^>]*properties="cover-image"[^>]*/?>(?:</item>)?', opf)
    if not m:
        sys.exit("エラー: content.opfに表紙画像（properties=\"cover-image\"）の項目がありません")
    item = m.group(0)
    old_href = re.search(r'href="([^"]+)"', item).group(1)
    base = opf_name.rsplit("/", 1)[0] + "/" if "/" in opf_name else ""
    old_id = re.search(r'id="([^"]+)"', item).group(1)
    new_item = re.sub(r'href="[^"]+"', f'href="{COVER_NAME}"', item)
    new_item = re.sub(r'media-type="[^"]+"', 'media-type="image/jpeg"', new_item)
    new_item = new_item.replace(f'id="{old_id}"', 'id="cover-image"')
    opf = opf.replace(item, new_item)
    opf = opf.replace(f'<meta name="cover" content="{old_id}"', '<meta name="cover" content="cover-image"')
    # Kindleは表紙画像を自動で1ページ目に表示する為、表紙ページ（cover.xhtml）を
    # 本文の流れから外し、同じ表紙が2回続かないようにする（目次のnavを兼ねる為、
    # ファイル自体は残す）
    cover_id = re.search(r'<item [^>]*id="([^"]+)"[^>]*href="cover\.xhtml"', opf).group(1)
    opf = re.sub(rf'<itemref idref="{cover_id}"(?: linear="[^"]*")?',
                 f'<itemref idref="{cover_id}" linear="no"', opf)
    data[opf_name] = opf.encode("utf-8")

    old_path = base + old_href
    data.pop(old_path, None)
    data[base + COVER_NAME] = jpg
    if old_path != base + COVER_NAME:
        infos = [i for i in infos if i.filename != old_path]
        infos.append(zipfile.ZipInfo(base + COVER_NAME, time.localtime()[:6]))

    cover_xhtml = base + "cover.xhtml"
    html = data[cover_xhtml].decode("utf-8")
    body_start = html.index(">", html.index("<body")) + 1
    nav_start = html.find("<nav", body_start)
    if nav_start < 0:
        nav_start = html.index("</body>")
    image = (f'\n    <div class="cover-image-page">'
             f'<img src="{COVER_NAME}" alt="{cover_alt}" /></div>\n')
    html = html[:body_start] + image + html[nav_start:]
    html = re.sub(r'\s*<link rel="stylesheet"[^>]*href="cover\.css"[^>]*/>', "", html)
    style = ("<style>html, body { margin: 0; padding: 0; height: 100%; } "
             ".cover-image-page { height: 100%; text-align: center; } "
             ".cover-image-page img { height: 100%; max-width: 100%; object-fit: contain; }</style>")
    if style not in html:
        html = html.replace("</head>", f"  {style}\n  </head>", 1)
    data[cover_xhtml] = html.encode("utf-8")

    tmp = epub.with_suffix(".epub.tmp")
    with zipfile.ZipFile(tmp, "w") as out:
        for info in infos:
            method = zipfile.ZIP_STORED if info.filename == "mimetype" else zipfile.ZIP_DEFLATED
            out.writestr(info, data[info.filename], compress_type=method)
    tmp.replace(epub)
    print(f"EPUBの表紙をPDFの表紙ページの画像に差し替えました（{w}×{h}px、{len(jpg) // 1024}KB）")


if __name__ == "__main__":
    main()
