"""EPUBの本文から、フォームの部品（<input>・<button> 等）を取り除く後処理。

Markdown のチェックリスト（- [ ] 項目）は、VFM で <input type="checkbox" disabled /> になる。
Kindle はフォームの部品を扱えず、KDPの変換が「HTMLファイルをKindleフォーマットに変換できません
でした」で止まった（epubcheck・Kindle Previewer は通っていた）。チェックボックスは文字の
「☐」（チェック済みは「☑」）に、その他のフォームの部品は取り除く。

使い方: python3 epub_strip_forms.py <EPUBファイル>
"""
import re
import sys
import zipfile
from pathlib import Path


def main():
    epub = Path(sys.argv[1])
    with zipfile.ZipFile(epub) as z:
        infos = z.infolist()
        data = {i.filename: z.read(i.filename) for i in infos}
    n = 0
    for name in list(data):
        if not name.endswith((".xhtml", ".html")):
            continue
        t = data[name].decode("utf-8")

        def box(m):
            nonlocal n
            n += 1
            mark = "☑" if re.search(r"\schecked\b", m.group(0)) else "☐"
            return f'<span class="task-box">{mark}</span> '
        t = re.sub(r'<input\b[^>]*type="checkbox"[^>]*/?>\s*', box, t)

        def other(m):
            nonlocal n
            n += 1
            return ""
        t = re.sub(r"<(?:input|select|textarea)\b[^>]*/>|<(button|select|textarea|form)\b[^>]*>.*?</\1>", other, t, flags=re.S)
        t = re.sub(r"</?form\b[^>]*>", "", t)
        data[name] = t.encode("utf-8")
    tmp = epub.with_suffix(".epub.tmp")
    with zipfile.ZipFile(tmp, "w") as zo:
        for i in infos:
            zo.writestr(i, data[i.filename], compress_type=zipfile.ZIP_STORED if i.filename == "mimetype" else zipfile.ZIP_DEFLATED)
    tmp.replace(epub)
    print(f"EPUBのフォームの部品を文字に置き換えました（チェックボックス等）: {n}件")


if __name__ == "__main__":
    main()
