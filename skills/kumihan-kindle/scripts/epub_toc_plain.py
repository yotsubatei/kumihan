"""EPUBの目次（nav）から、見出しのルビの読み（<rt>）を外す。

見出しに振ったルビは、目次の文書にもそのまま写る。Kindle のナビゲーションの一覧では
読みが語の後ろに続いて表示される（例「組版くみはん」）為、目次では読みを外し、
親文字だけにする。紙の本の目次は CSS（nav#toc rt { display: none }）で隠す。

あわせて、ランドマーク（nav epub:type="landmarks"）の目次へのリンク「toc.xhtml#toc」を、
「toc.xhtml」にする。Kindleの変換は nav の要素を取り除く為、id="toc" が無くなり、
Kindle Previewer は「ハイパーリンクは解決されていません」（W14001）、KDPは「目次に壊れている
リンクがあります」となった。

使い方: python3 epub_toc_plain.py <EPUBファイル>
"""
import re
import sys
import zipfile
from pathlib import Path


def main():
    epub = Path(sys.argv[1])
    tmp = epub.with_suffix(".tmp")
    n = 0
    with zipfile.ZipFile(epub) as zin, zipfile.ZipFile(tmp, "w") as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            if item.filename.endswith(".xhtml") and b"<nav" in data:
                s = data.decode("utf-8")
                def strip(m):
                    return re.sub(r"<rt>.*?</rt>|<rp>.*?</rp>|</?ruby>", "", m.group(0))
                new = re.sub(r"<nav.*?</nav>", strip, s, flags=re.S)
                n += s.count("<rt>") - new.count("<rt>")
                # ランドマークの、nav の id への目次のリンクは、ファイルへのリンクにする
                def land(m):
                    return re.sub(r'href="([^"#]+)#[^"]*"', r'href="\1"', m.group(0))
                new = re.sub(r'<nav[^>]*epub:type="landmarks".*?</nav>', land, new, flags=re.S)
                data = new.encode("utf-8")
            # mimetype は圧縮しない（EPUBの決まり）
            comp = zipfile.ZIP_STORED if item.filename == "mimetype" else zipfile.ZIP_DEFLATED
            zout.writestr(item, data, compress_type=comp)
    tmp.replace(epub)
    print(f"EPUBの目次から、見出しのルビの読みを外しました: {n}箇所")


if __name__ == "__main__":
    main()
