"""出来上がったPDFから、レイアウトの「泣き別れ」の候補を探す。

本来一緒にあるべき物が、ページや行で分かれてしまった所を、PDFの文字の位置から
推測して一覧にする。あくまで候補なので、最後は人がページを見て判断する。

探す物:
- 見出しの泣き別れ: 見出しがページの最後にあり、本文が次のページから始まる
- 段落の泣き別れ（ページの頭）: 前のページから続く段落の最後の1行だけが、ページの頭にある
- 段落の泣き別れ（ページの終わり）: 段落の最初の1行だけが、ページの終わりにある
- 段落の終わりの短い行: 段落の最後の行が、1〜2文字だけ

本文の文字の大きさ（--body）より大きい文字の行を見出しとみなす。縦書き・横書きの
両方に対応する（PDFの行の向きで判断する）。柱とノンブル（ページの上下の端の行）は
対象から外す。

使い方: python3 check_layout.py <PDF> [--body 10] [--from ページ] [--to ページ]
  ページは通し番号。結果は、通し番号とノンブル（あれば）で出す。
依存: PyMuPDF
"""
import argparse
import re

try:
    import pymupdf
except ImportError:
    import fitz as pymupdf

DIGITS = re.compile(r"^[0-9０-９]+$")
PUNCT = set("、。，．・：；？！」』）】〕〉》”’ー…―")


def page_lines(page, edge=0.09):
    """ページの行を、読む順に返す。縦書きでは、行の始まり・終わりを天地の位置で表す。"""
    w, h = page.rect.width, page.rect.height
    out = []
    for block in page.get_text("dict")["blocks"]:
        for line in block.get("lines", []):
            text = "".join(s["text"] for s in line["spans"]).strip()
            if not text:
                continue
            x0, y0, x1, y1 = line["bbox"]
            if y1 < h * edge or y0 > h * (1 - edge):   # 柱・ノンブル
                continue
            vertical = abs(line["dir"][1]) > abs(line["dir"][0])
            out.append({"text": text, "size": max(sp["size"] for sp in line["spans"]),
                        "start": y0 if vertical else x0, "end": y1 if vertical else x1})
    return out


def column_left(all_pages, body):
    """本文の欄の左端（縦書きでは天）の位置を、本全体で最も多い行の始まりから求める。
    左右のページで余白が違う事がある為、奇数・偶数のページで別に求める。"""
    lefts = {}
    for parity in (0, 1):
        starts = [round(ln["start"]) for i, lines in all_pages.items() if i % 2 == parity
                  for ln in lines if abs(ln["size"] - body) < 0.6]
        ends = [round(ln["end"]) for i, lines in all_pages.items() if i % 2 == parity
                for ln in lines if abs(ln["size"] - body) < 0.6]
        # 行末まで埋まった行の終わりの位置（最も多い行の終わり）
        lefts[parity] = ((max(set(starts), key=starts.count), max(set(ends), key=ends.count))
                         if starts else None)
    return lefts


def main_column(lines, body, left):
    """本文の行（本文の大きさで、本文の欄の左端から始まる行）と見出しを残す。
    箇条書き・囲み・表・コードなど、字下げの位置が違う行は外す。"""
    em = body
    if left is None:
        return []
    left, right = left
    keep = []
    for ln in lines:
        if ln["size"] > body * 1.1 and abs(ln["start"] - left) < em * 3:
            keep.append(dict(ln, kind="heading"))
        elif abs(ln["size"] - body) < 0.6:
            off = ln["start"] - left
            if abs(off) < 1.5:
                keep.append(dict(ln, kind="cont"))      # 段落の続きの行
            elif abs(off - em) < 1.5:
                keep.append(dict(ln, kind="first"))     # 段落の最初の行（1字下げ）
    for ln in keep:
        ln["full"] = ln["end"] > right - em * 1.5        # 行末まで埋まっている
    return keep


def printed_number(page):
    h = page.rect.height
    for x0, y0, x1, y1, text, *_ in page.get_text("words"):
        if DIGITS.match(text) and (y1 < h * 0.12 or y0 > h * 0.88):
            return text
    return "—"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf")
    ap.add_argument("--body", type=float, default=10.0, help="本文の文字の大きさ（pt）")
    ap.add_argument("--from", dest="first", type=int, default=1)
    ap.add_argument("--to", dest="last", type=int, default=0)
    ap.add_argument("--edge", type=float, default=0.09, help="柱・ノンブルとみなすページの上下の端の割合")
    a = ap.parse_args()
    doc = pymupdf.open(a.pdf)
    last = a.last or doc.page_count
    raw = {i: page_lines(doc[i], a.edge) for i in range(a.first - 1, last)}
    lefts = column_left(raw, a.body)
    pages = {i: main_column(lines, a.body, lefts[i % 2]) for i, lines in raw.items()}
    found = []

    for i, lines in pages.items():
        if not lines:
            continue
        label = f"{i + 1}（ノンブル {printed_number(doc[i])}）"
        nxt = pages.get(i + 1)
        tail, head = lines[-1], lines[0]
        # 見出しがページの最後にあり、次のページに本文がある
        # （囲み・箇条書き・表などを含め、見出しの後にそのページの行が無い時だけ）
        if (tail["kind"] == "heading" and nxt and any(ln["kind"] != "heading" for ln in lines)
                and raw[i] and raw[i][-1]["text"] == tail["text"]):
            found.append((label, "見出しの泣き別れ", f"ページの最後が見出し「{tail['text'][:20]}」で、本文は次のページから"))
        # ページの頭が、前のページから続く段落の最後の1行（続きの行で、行末まで埋まっていない）
        prev = pages.get(i - 1) or []
        prev_tail = prev[-1] if prev else None
        if (head["kind"] == "cont" and not head["full"]
                and (len(lines) == 1 or lines[1]["kind"] in ("first", "heading"))
                and prev_tail and prev_tail["kind"] != "heading" and prev_tail["full"]):
            found.append((label, "段落の泣き別れ（ページの頭）", f"前のページから続く段落の最後の1行「{head['text'][:20]}」だけがページの頭にある"))
        # ページの終わりが、段落の最初の1行（字下げで始まり、行末まで埋まっていて次へ続く）
        if tail["kind"] == "first" and tail["full"] and nxt:
            found.append((label, "段落の泣き別れ（ページの終わり）", f"段落の最初の1行「{tail['text'][:20]}」だけがページの終わりにある"))
        # 段落の最後の行が1〜2文字（前の行が行末まで埋まった続きの行）
        for k in range(1, len(lines)):
            ln, prev = lines[k], lines[k - 1]
            if ln["kind"] != "cont" or ln["full"] or not prev["full"] or prev["kind"] == "heading":
                continue
            chars = [c for c in ln["text"] if c not in PUNCT and not c.isspace()]
            if 1 <= len(chars) <= 2:
                found.append((label, "段落の終わりの短い行", f"段落の最後の行が「{ln['text']}」だけ"))

    if not found:
        print("泣き別れの候補は見つかりませんでした")
        return
    print(f"泣き別れの候補: {len(found)}件（最後は人がページを見て判断してください）")
    for label, kind, detail in found:
        print(f"{label}\t{kind}\t{detail}")


if __name__ == "__main__":
    main()
