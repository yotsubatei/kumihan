"""Windowsで作られたZIPを、日本語のファイル名が文字化けしないように展開する。

著者から届くZIP（エクスプローラーの「送る→圧縮フォルダー」等）は、ファイル名を
UTF-8で書いていながら、UTF-8である印（フラグ0x800）を付けていない事がある。
Pythonの zipfile や macOS の unzip はその場合 CP437 として読む為、
「図版.png」が「σ¢│τëê.png」のように化ける。印の無い名前を CP437 のバイト列に
戻し、UTF-8、だめならShift_JIS（CP932）として読み直して展開する。

使い方: python3 unzip_ja.py <ZIPファイル> <展開先>
"""
import sys
import zipfile
from pathlib import Path


def real_name(info):
    if info.flag_bits & 0x800:
        return info.filename
    raw = info.filename.encode("cp437")
    for enc in ("utf-8", "cp932"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return info.filename


def main():
    if len(sys.argv) != 3:
        sys.exit("使い方: python3 unzip_ja.py <ZIPファイル> <展開先>")
    dest = Path(sys.argv[2])
    with zipfile.ZipFile(sys.argv[1]) as z:
        for info in z.infolist():
            name = real_name(info)
            if name.startswith(("__MACOSX/",)) or Path(name).name == ".DS_Store":
                continue
            target = (dest / name).resolve()
            if dest.resolve() not in target.parents and target != dest.resolve():
                sys.exit(f"展開先の外を指すファイル名の為、中止しました: {name}")
            if info.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(z.read(info))
            print(name)


if __name__ == "__main__":
    main()
