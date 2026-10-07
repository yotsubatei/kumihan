"""縦書き用の字の位置の情報（vhea・vmtx）が無い書体に、それを足した複製を作る。

外字の書体（Windowsの外字エディタで作った EUDC 等）には、縦書きの時に字をどこに置くかの情報が
入っていない事が多い。Chrome（Vivliostyle の PDF）は無くても横書きの位置を元に置くが、Kindle は
字の上端を枠の上端に寄せて置く為、外字だけが行の中で上の方に寄って見える（小さな記号ほど目立つ）。
横書きの時と同じ位置になるよう、各字の縦の送りを1em、上の余白を「ascent − 字の上端」にする。
PDF の見た目はほぼ変わらない（0.1pt程度）。

使い方: python3 font_add_vertical_metrics.py <書体.ttf> <出力.ttf>
依存: fontTools（TrueType〈glyf〉の書体。CFF の書体は対象外）
"""
import sys

from fontTools.ttLib import TTFont, newTable


def main():
    src, dst = sys.argv[1], sys.argv[2]
    f = TTFont(src)
    if "glyf" not in f:
        sys.exit("TrueType（glyf）の書体ではありません")
    if "vmtx" in f:
        print("この書体には既に縦書きの情報（vmtx）があります。そのまま複製します")
        f.save(dst)
        return
    upm = f["head"].unitsPerEm
    asc = f["hhea"].ascent
    glyf = f["glyf"]
    vmtx = {}
    for g in f.getGlyphOrder():
        gl = glyf[g]
        ymax = gl.yMax if getattr(gl, "numberOfContours", 0) else asc
        vmtx[g] = (upm, int(round(asc - ymax)))
    vhea = newTable("vhea")
    vhea.tableVersion = 0x00011000
    vhea.ascent, vhea.descent, vhea.lineGap = upm // 2, -(upm // 2), 0
    vhea.advanceHeightMax = upm
    vhea.minTopSideBearing = min(t for _, t in vmtx.values())
    vhea.minBottomSideBearing = 0
    vhea.yMaxExtent = upm
    vhea.caretSlopeRise, vhea.caretSlopeRun, vhea.caretOffset = 0, 1, 0
    for i in range(5):
        setattr(vhea, f"reserved{i}", 0)
    vhea.metricDataFormat = 0
    vhea.numberOfVMetrics = len(vmtx)
    f["vhea"] = vhea
    vt = newTable("vmtx")
    vt.metrics = vmtx
    f["vmtx"] = vt
    f.save(dst)
    print(f"縦書きの情報を足しました: {dst}（{len(vmtx)}字）")


if __name__ == "__main__":
    main()
