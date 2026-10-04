"""新旧2つのPDFを1ページずつ画像にして比べ、見た目が変わったページを一覧にする。

修正を反映した後、意図した箇所だけが変わったか（他のページが動いていないか）を
確かめる為に使う。ページ番号は、PDFの何枚目か（通し番号）と、ページに印刷された
ノンブル（ページの上端・下端にある数字だけの文字列）の両方を出す。報告や
修正依頼で使うのはノンブルの方で、両者は表紙や目次の分だけずれる事が多い。

途中でページ数が増減すると、それ以降のページは全て「変わった」になる。その場合は
最初に変わったページの前後を見て、何行・何ページ送られたかを確かめる。

使い方: python3 pdf_diff_pages.py <旧.pdf> <新.pdf> [--out 画像の出力先] [--dpi 50]
  --out を付けると、変わったページを「旧｜新」の左右に並べたPNGを書き出す。
  新の側では、見た目の変わった範囲を枠で囲む。
依存: PyMuPDF（pip install pymupdf）
"""
import argparse
import re
import sys

try:
    import pymupdf
except ImportError:  # 古い版は fitz の名前
    import fitz as pymupdf

DIGITS = re.compile(r"^[0-9０-９]+$")


def printed_number(page):
    """ページの上端・下端の帯にある、数字だけの文字列（ノンブル）を返す。"""
    h = page.rect.height
    found = []
    for x0, y0, x1, y1, text, *_ in page.get_text("words"):
        if DIGITS.match(text) and (y1 < h * 0.12 or y0 > h * 0.88):
            found.append(text)
    return found[0] if found else "—"


def changed_boxes(a, b, cell=10, gap=2):
    """同じ大きさの2枚の画像で、違いのある範囲を、近いもの同士まとめた矩形の一覧で返す。"""
    w, h, n = a.width, a.height, a.n
    sa, sb = a.samples, b.samples
    hit = set()
    for y in range(h):
        row = y * w * n
        for x in range(0, w * n, n):
            if abs(sa[row + x] - sb[row + x]) > 40:
                hit.add((x // n // cell, y // cell))
    boxes, seen = [], set()
    for start in hit:
        if start in seen:
            continue
        stack, cells = [start], []
        seen.add(start)
        while stack:
            cx, cy = stack.pop()
            cells.append((cx, cy))
            for dx in range(-gap, gap + 1):
                for dy in range(-gap, gap + 1):
                    nb = (cx + dx, cy + dy)
                    if nb in hit and nb not in seen:
                        seen.add(nb)
                        stack.append(nb)
        xs, ys = [c[0] for c in cells], [c[1] for c in cells]
        boxes.append((max(0, min(xs) * cell - 4), max(0, min(ys) * cell - 4),
                      min(w, (max(xs) + 1) * cell + 4), min(h, (max(ys) + 1) * cell + 4)))
    return boxes


def outline(pix, box, t=3, color=(220, 40, 40)):
    x0, y0, x1, y1 = box
    for r in ((x0, y0, x1, y0 + t), (x0, y1 - t, x1, y1), (x0, y0, x0 + t, y1), (x1 - t, y0, x1, y1)):
        pix.set_rect(pymupdf.IRect(*r), color)


def render(page, dpi):
    pix = page.get_pixmap(dpi=dpi, colorspace=pymupdf.csGRAY)
    return pix


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("old")
    ap.add_argument("new")
    ap.add_argument("--out")
    ap.add_argument("--dpi", type=int, default=50)
    a = ap.parse_args()
    old, new = pymupdf.open(a.old), pymupdf.open(a.new)
    print(f"ページ数: 旧 {old.page_count} → 新 {new.page_count}"
          + ("" if old.page_count == new.page_count else f"（{new.page_count - old.page_count:+d}）"))
    changed = []
    for i in range(max(old.page_count, new.page_count)):
        if i >= old.page_count or i >= new.page_count:
            changed.append((i, None))
            continue
        po, pn = render(old[i], a.dpi), render(new[i], a.dpi)
        if po.samples != pn.samples:
            diff = sum(1 for x, y in zip(po.samples, pn.samples) if abs(x - y) > 32)
            changed.append((i, diff / max(1, len(po.samples))))
    if not changed:
        print("見た目の変わったページはありません")
        return
    print(f"変わったページ: {len(changed)}ページ")
    print("通し番号\tノンブル（新）\t変わった画素の割合")
    for i, ratio in changed:
        label = printed_number(new[i]) if i < new.page_count else "（新には無いページ）"
        print(f"{i + 1}\t{label}\t" + ("—" if ratio is None else f"{ratio:.2%}"))
    if a.out:
        from pathlib import Path
        out = Path(a.out)
        out.mkdir(parents=True, exist_ok=True)
        for i, _ in changed:
            if i >= old.page_count or i >= new.page_count:
                continue
            po, pn = old[i].get_pixmap(dpi=100), new[i].get_pixmap(dpi=100)
            if (po.width, po.height) == (pn.width, pn.height):
                for box in changed_boxes(po, pn):
                    outline(pn, box)
            sheet = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, po.width + pn.width + 20, max(po.height, pn.height)), False)
            sheet.set_rect(sheet.irect, (200, 200, 200))
            po.set_origin(0, 0)
            sheet.copy(po, po.irect)
            pn.set_origin(po.width + 20, 0)
            sheet.copy(pn, pn.irect)
            sheet.save(out / f"page{i + 1:04d}.png")
        print(f"旧｜新を並べた画像: {out}/")
    sys.exit(0)


if __name__ == "__main__":
    main()
