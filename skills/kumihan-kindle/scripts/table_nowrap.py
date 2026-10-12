"""原稿（draft/*.md）の表で、中身がすべて短い列（6文字以下。「第16章」「同じ」「番号」等）のセルを
<span class="nw"> で囲み、折り返さないようにする（custom.css の .nw）。

狭い列の中で、短い語が「第／16／章」のように縦に並ぶのを防ぐ。コードのセル（`…`）と空のセルは囲まない。
表を足したり直したりした後に、もう一度実行する（既に囲んだセルはそのまま）。
コードの囲み（```）の中の表は、原稿の書き方の例なので触らない。

使い方: python3 table_nowrap.py [原稿のフォルダ（既定: draft）] [--dry-run]
"""
import re
import sys
from pathlib import Path

LIMIT = 6


def plain(cell):
    return re.sub(r"<rt>.*?</rt>|<[^>]+>", "", cell).strip()


def process(text):
    lines = text.split("\n")
    out, i, n = [], 0, 0
    fence = False
    while i < len(lines):
        if lines[i].startswith("```"):
            fence = not fence
        if (not fence and lines[i].startswith("|") and i + 1 < len(lines)
                and re.match(r"^\|\s*:?-{3}", lines[i + 1])):
            j = i
            while j < len(lines) and lines[j].startswith("|"):
                j += 1
            rows = lines[i:j]
            cells = [[c.strip() for c in r.strip().strip("|").split("|")] for r in rows]
            ncol = len(cells[0])
            short = [all(k == 1 or len(c) <= col or len(plain(c[col])) <= LIMIT
                         for k, c in enumerate(cells)) for col in range(ncol)]
            for k, c in enumerate(cells):
                if k == 1:
                    out.append(rows[k])
                    continue
                for col in range(len(c)):
                    v = c[col]
                    if short[col] and v and "`" not in v and not v.startswith('<span class="nw">'):
                        c[col] = f'<span class="nw">{v}</span>'
                        n += 1
                out.append("| " + " | ".join(c) + " |")
            i = j
            continue
        out.append(lines[i])
        i += 1
    return "\n".join(out), n


def main():
    dry = "--dry-run" in sys.argv
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    for f in sorted(Path(args[0] if args else "draft").glob("*.md")):
        s = f.read_text()
        new, n = process(s)
        if n:
            print(f"{f.name}: {n}セル")
            if not dry:
                f.write_text(new)


if __name__ == "__main__":
    main()
