"""EPUBに埋め込んだ書体を、本で実際に使っている文字だけに絞り込む（サブセット化）後処理。

日本語の書体は1書体で数MBあり、そのまま埋め込むとEPUBが大きくなる（Kindleは配信の料金が
ファイルサイズで変わる）。EPUB内の本文（ルビを含む）と、CSSの content で追加する記号
（見出しの記号・リーダー線等）に使われている文字を集め、各書体をその文字だけに絞る。
縦書き用の字形（vert/vrt2）等の組版機能（OpenTypeのレイアウト機能）はすべて残す。
念の為、英数字・基本的な約物は使っていなくても残す。

書体のライセンスが改変（サブセット化）を許しているかは、使う側で確認する事
（SIL Open Font License の書体は可）。

使い方: python3 epub_subset_fonts.py <EPUBファイル>
依存: fontTools
"""
import html
import io
import re
import sys
import zipfile
from pathlib import Path

from fontTools import subset
from fontTools.ttLib import TTFont

FONT_EXT = (".otf", ".ttf")
# 使っていなくても残す文字（英数字・基本的な記号、日本語の基本的な約物）
ALWAYS = set(chr(c) for c in range(0x20, 0x7F)) | set(
    "　、。，．・：；？！゛゜´｀¨＾￣＿ヽヾゝゞ〃仝々〆〇ー―‐／＼～∥｜…‥‘’“”（）〔〕［］｛｝〈〉《》「」『』【】"
    "＋－±×÷＝≠＜＞≦≧∞∴♂♀°′″℃￥＄￠￡％＃＆＊＠§☆★○●◎◇◆□■△▲▽▼※〒→←↑↓〓•◉"
    "０１２３４５６７８９"
)


def used_chars(data):
    chars = set(ALWAYS)
    for name, raw in data.items():
        if name.endswith((".xhtml", ".html", ".htm")):
            text = raw.decode("utf-8")
            text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
            text = re.sub(r"<[^>]+>", "", text)
            chars |= set(html.unescape(text))
        elif name.endswith(".css"):
            css = raw.decode("utf-8")
            for m in re.finditer(r"content\s*:\s*([^;}]+)", css):
                for q in re.findall(r"'([^']*)'|\"([^\"]*)\"", m.group(1)):
                    chars |= set(q[0] or q[1])
    return {c for c in chars if not c.isspace() or c in (" ", "　")}


def subset_font(raw, chars):
    font = TTFont(io.BytesIO(raw))
    options = subset.Options()
    options.layout_features = ["*"]
    options.name_IDs = ["*"]
    options.name_languages = ["*"]
    options.notdef_outline = True
    options.glyph_names = True
    options.legacy_kern = True
    sub = subset.Subsetter(options=options)
    sub.populate(text="".join(chars))
    sub.subset(font)
    out = io.BytesIO()
    font.save(out)
    return out.getvalue()


def main():
    if len(sys.argv) != 2:
        sys.exit("使い方: python3 epub_subset_fonts.py <EPUBファイル>")
    epub = Path(sys.argv[1])
    with zipfile.ZipFile(epub) as z:
        infos = z.infolist()
        data = {i.filename: z.read(i.filename) for i in infos}

    chars = used_chars(data)
    before = after = 0
    for name in [n for n in data if n.lower().endswith(FONT_EXT)]:
        raw = data[name]
        new = subset_font(raw, chars)
        before += len(raw)
        after += len(new)
        data[name] = new

    tmp = epub.with_suffix(".epub.tmp")
    with zipfile.ZipFile(tmp, "w") as out:
        for info in infos:
            method = zipfile.ZIP_STORED if info.filename == "mimetype" else zipfile.ZIP_DEFLATED
            out.writestr(info, data[info.filename], compress_type=method)
    tmp.replace(epub)
    print(f"EPUBの書体を、使っている文字（{len(chars)}字）だけに絞り込みました: "
          f"{before / 1e6:.1f}MB → {after / 1e6:.2f}MB")


if __name__ == "__main__":
    main()
