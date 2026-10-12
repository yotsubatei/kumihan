"""EPUBの中の日本語（ASCII以外）のファイル名と、content.opf の項目のIDを、英数字に置き換える後処理。

図版のファイル名が日本語（images/図1.png 等）だと、Vivliostyle は日本語のID（images図1png）も作る。
EPUBの決まり（epubcheck）や Kindle Previewer の変換は通るが、KDPのサーバーの変換では、
アップロードはできてもプレビューで変換エラーになり、保存もできなかった事例がある為、英数字に揃える。

本文の見出し等のID（Vivliostyle は見出しの文字からIDを作る為、日本語の本では「はじめに」のような
日本語のIDになり、目次のリンクは %E3%81%AF… と%エンコードされる）も、h-（ハッシュ）のような英数字にし（CSSの #ID の指定も書き換える）、
目次などのリンクを書き換える。KDPは、%エンコードされたリンク先を解決できず「目次に壊れている
リンクがあります」で止まった（epubcheck・Kindle Previewer は通っていた）。

ASCII以外の文字を含むファイルを images/fig-01.png のような名前にし、content.opf・XHTML・CSS の
中の参照（そのままの表記と、%エンコードされた表記の両方）を書き換える。IDは、ASCII以外の文字を
含む物を item-01 のような名前にし、参照（idref、meta の content 等）も書き換える。

使い方: python3 epub_ascii_names.py <EPUBファイル>
"""
import posixpath
import re
import sys
import zipfile
from pathlib import Path
from urllib.parse import quote, unquote


def non_ascii(s):
    return bool(re.search(r"[^\x00-\x7f]", s))


def main():
    epub = Path(sys.argv[1])
    with zipfile.ZipFile(epub) as z:
        infos = z.infolist()
        data = {i.filename: z.read(i.filename) for i in infos}

    # ファイル名の置き換え表（ZIPの中のパス）
    renames = {}
    n = 0
    for name in sorted(data):
        if non_ascii(name):
            n += 1
            d, base = posixpath.split(name)
            ext = posixpath.splitext(base)[1].lower()
            renames[name] = posixpath.join(d, f"fig-{n:02d}{ext}")

    opf_name = next(k for k in data if k.endswith(".opf"))
    # IDの置き換え表
    opf = data[opf_name].decode("utf-8")
    ids = {}
    for i, old in enumerate(sorted({m for m in re.findall(r'\bid="([^"]+)"', opf) if non_ascii(m)}), 1):
        ids[old] = f"item-{i:02d}"

    # 本文の中のID（ASCII以外の文字を含む物）の置き換え表。文書ごと
    from urllib.parse import unquote as _unq
    # 新しいIDは、元のIDから決まる名前（h- と、元のIDのハッシュ）にする。同じ名前のIDは、どの文書でも
    # 同じ新しいIDになる為、CSSの #元のID という指定も、そのまま #新しいID に書き換えられる
    import hashlib
    new_id = lambda old: "h-" + hashlib.md5(old.encode("utf-8")).hexdigest()[:10]
    elem_ids = {}
    for name in sorted(data):
        if name.endswith((".xhtml", ".html")):
            for old in re.findall(r'\bid="([^"]+)"', data[name].decode("utf-8")):
                if non_ascii(old):
                    elem_ids[(name, old)] = new_id(old)
    css_ids = sorted({old for (_, old) in elem_ids}, key=len, reverse=True)

    def fix_links(name, text):
        """href="file#frag" と href="#frag" の、frag（%エンコードでも生でも）を新しいIDに"""
        base_dir = posixpath.dirname(name)
        def rep(m):
            href = m.group(2)
            f, sep, frag = href.partition("#")
            if not sep:
                return m.group(0)
            target = posixpath.normpath(posixpath.join(base_dir, _unq(f))) if f else name
            new = elem_ids.get((target, _unq(frag)))
            return f'{m.group(1)}{f}#{new}"' if new else m.group(0)
        text = re.sub(r'(\bhref=")([^"]*#[^"]*)"', rep, text)
        # 文書の中のIDそのもの
        for (doc, old), new in elem_ids.items():
            if doc == name:
                text = text.replace(f'id="{old}"', f'id="{new}"')
        return text

    def fix_text(name, text):
        base_dir = posixpath.dirname(name)
        for old, new in renames.items():
            # 参照は、そのファイルからの相対パス
            rel_old = posixpath.relpath(old, base_dir) if base_dir else old
            rel_new = posixpath.relpath(new, base_dir) if base_dir else new
            for form in {rel_old, quote(rel_old)}:
                text = text.replace(form, rel_new)
        if name.endswith(".css"):
            # CSSの #元のID を #新しいID に（IDの名前の続きの文字が後ろに無い所だけ）
            for old in css_ids:
                text = re.sub(re.escape("#" + old) + r"(?![\w-])", "#" + new_id(old), text)
        if name == opf_name:
            for old, new in ids.items():
                text = re.sub(rf'(\b(?:id|idref|content)=")({re.escape(old)})(")', rf"\g<1>{new}\3", text)
        return text

    out = {}
    for name, body in data.items():
        if name.endswith((".opf", ".xhtml", ".html", ".css", ".ncx")):
            text = body.decode("utf-8")
            if name.endswith((".xhtml", ".html", ".ncx")):
                text = fix_links(name, text)
            body = fix_text(name, text).encode("utf-8")
        out[renames.get(name, name)] = body

    tmp = epub.with_suffix(".epub.tmp")
    with zipfile.ZipFile(tmp, "w") as zo:
        for info in infos:
            new = renames.get(info.filename, info.filename)
            method = zipfile.ZIP_STORED if new == "mimetype" else zipfile.ZIP_DEFLATED
            zi = zipfile.ZipInfo(new, info.date_time)
            zo.writestr(zi, out[new], compress_type=method)
    tmp.replace(epub)
    left = [k for k in out if non_ascii(k)]
    print(f"EPUBの日本語のファイル名・IDを英数字にしました: ファイル{len(renames)}件、項目のID{len(ids)}件、本文のID{len(elem_ids)}件"
          + (f"（残り: {left}）" if left else ""))


if __name__ == "__main__":
    main()
