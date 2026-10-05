# Kindleで崩れる原因と直し方

Kindleの変換エンジン（KDP・Kindle Previewer）が解釈しないCSSは、警告なく無視される。ここに、実際の本の制作（300ページを超える縦書きの書籍）で見つけた物をまとめる。

## 症状から引く

| 症状 | 原因 | 直し方 |
| --- | --- | --- |
| 縦書きの本が横書きになる | テーマが `writing-mode: var(--vs-writing-mode)` と変数で指定している。`-epub-writing-mode` も無い | `html { -epub-writing-mode: vertical-rl; writing-mode: vertical-rl; }` を直接書く。OPFの `primary-writing-mode` だけでは縦書きにならなかった |
| 文字サイズ・行間・字下げ・見出しの書式がテーマ既定と違う | テーマの書式は大半が `var()` 経由 | `epub_resolve_css_vars.py` |
| 段落の頭の字下げが消える | 同上（`text-indent: var(--vs--p-text-indent)`） | 同上 |
| 見出しや囲みの上下・左右の余白が無い、隣の囲みとくっつく | `margin-block`・`padding-block` 等の論理プロパティを解釈しない（`padding-inline-start` は効いた） | `epub_physical_props.py`（縦書きは block-start→右、block-end→左、inline-start→上、inline-end→下） |
| 箇条書きの点が二重に出る（`::before` の「・」と、リストの点） | `ul, ul:not(:is(ul *, ol *)) { list-style-type: none }` のように、まとめ書きのセレクタに `:is()` が混ざると、ルール全体が捨てられる | `epub_split_selectors.py`（セレクタ1つずつのルールに分ける） |
| 約物（「、」「。」「」」）の位置が縦書きでおかしい | 約物だけ別の書体にする `@font-face` の `unicode-range` を解釈せず、縦書き用の字形を持たない書体が全文字に使われる | 範囲の書体を使わず、約物を `<span>` で囲んで縦書きに対応した書体を直接指定する後処理を作る（本ごとのクラス名に依存する為、本の側に置く） |
| 目次の点線（リーダー）が消える | `leader()` はVivliostyle専用 | 直前に固定の値を書く：`content: '……'; content: leader('…');` 。電子書籍ではページ番号ごと取り除く方がよい |
| 大きさ・位置がおかしい | `calc()` を解釈しない事がある | 直前に固定の値を書く：`text-indent: 3em; text-indent: calc(2rem + 1em);` |
| 書式が全体に崩れる、Previewerで Enhanced Typesetting が Not Supported | 表紙画像が WebP・空・無効 | `epub_cover_image.py`（PDFの1ページ目をJPEGにする） |
| 表紙が2回続けて出る | 表紙ページが本文の流れ（spine）に入っている | 表紙ページの `itemref` に `linear="no"`（`epub_cover_image.py` が行う） |
| 図版のキャプションが中央ではなく左に寄る | Kindleは図（`figure`）を画像の幅に縮めて組み、キャプションをその中で左に置く。テーマはキャプションの中央寄せを `display: flex` に頼っていて、Kindleは flex を解釈しない。キャプションに `text-align: center` を付けるだけでは直らない（Kindle Previewerで確認） | `figure { width: 100%; }` を指定する（紙のPDFで図の大きさが変わる場合は `@media print { figure { width: auto; } }` で戻す）。あわせて `figure figcaption { text-align: center; }` |
| Kindleの目次の一覧で、見出しの読みが語の後ろに続いて出る（「組版くみはん」） | 見出しに振ったルビが、ナビゲーションの目次（nav）に写る | `epub_toc_plain.py`（目次の中のルビの読みを外す） |
| 表紙ページが本文のPDFの1ページ目に入る | Vivliostyleの設定の `cover` は、表紙のHTMLのページも作る | `cover: { src: "images/kindle-cover.jpg", htmlPath: false }`（表紙画像だけを入れる。紙の表紙は別に入稿する）。表紙画像は原稿のフォルダ（entryContext）の中に置く |
| 外字（自作の書体の字）が、縦書きで字の枠の上の方に寄る（例：「」の中の小さな点が上に寄る） | 外字の書体（Windowsの外字エディタの EUDC 等）に、縦書きの字の位置の情報（vhea・vmtx）が無い。Chrome（PDF）は横書きの位置を元に中央に置くが、Kindle は字の上端を枠の上端に寄せる | `font_add_vertical_metrics.py` で縦書きの情報を足した書体を作って使う（PDFの見た目はほぼ変わらない） |
| KDPにEPUBを上げると、アップロードはできるが、プレビューで変換エラー。保存もできない（変換ログのダウンロードも反応しない事がある） | EPUBの中の画像のファイル名や、manifest のIDが日本語（Vivliostyle は日本語のファイル名から日本語のIDを作る）。epubcheck・Kindle Previewer は通るので気づきにくい。KDPのページの言語と、EPUBの dc:language の食い違いでも起きる | `epub_ascii_names.py`（ファイル名とIDを英数字に）。KDPの言語は「日本語」に。KPF ではなく EPUB を上げる（KDPのKPFの入稿口は Kindle Create で作った物を想定）。変換ログが落とせない時は、別のブラウザでポップアップ・ダウンロードを許可して試す |
| 縦中横で警告が出る | `text-combine-upright: all` の中が5文字以上（`::before` の中身も数える） | 縦中横にする範囲を、数字だけの `<span>` に絞る |
| 紙の本用の幅・位置の指定で、電子書籍の表示が崩れる | pt固定の幅・位置、`inline-size`、ページ中央への配置 | `@media print { … }` の中に書く（電子書籍リーダーは使わない） |
| 縦書きで、要素が天地いっぱいに伸びる | `display: block` は `inline-size` を外しても天地方向に伸びる | 電子書籍側は `display: inline-block` |
| EPUBが数十MB | 日本語の書体は1書体で数MB〜十数MB | `epub_subset_fonts.py`（使っている文字だけに絞る。ライセンスを確認） |

## 後処理の順番

```
epub_split_selectors → epub_resolve_css_vars → epub_physical_props → （本ごとの後処理） → epub_ascii_names → epub_subset_fonts → epub_toc_plain → epub_cover_image
```

- 書体の絞り込みは、本文を書き換える後処理（約物を囲む等）より後に。文字を数え直す為。
- いずれもEPUBだけを書き換え、PDFには触れない。後処理を足した・変えた時は、(1) PDFが変わっていない事、(2) 一般的なリーダー（ブラウザ）で見た目が変わらない事、(3) Kindle Previewer で直った事、の3つを確かめる。

## 確かめ方

- **見た目の修正は、Kindle Previewerの画面で実際に見る。** ブラウザでの模擬や変換の成否だけでは見落とす（キャプションの件で実際に見落とした）。確かめたいページだけを本文の先頭に置いた試験用EPUB（content.opf の spine の最初に足す）を作ると、すぐに表示を確かめられる。

- **Kindle Previewer の画面を撮る時**：画面にキー入力やクリックを送らない（窓の前後が入れ替わると、別のアプリに入力してしまう）。`open -g -a "Kindle Previewer 4" <KPF>` で裏で開き、窓の番号（Swift の `CGWindowListCopyWindowInfo` で取れる）を指定して `screencapture -x -o -l <番号>` で窓だけを撮る。確かめたいページだけを本文にした試験用の本（他の章の itemref を `linear="no"`、書名も変えて前回の表示位置を引き継がない）にすると、開いた最初の画面に出る。
- **Kindle Previewer**：`KindlePreviewer4CLI <epub> --convert --output <dir> --locale ja`。ログで Enhanced Typesetting の可否と警告を見る。`--showpreview` で画面表示。
- **ブラウザでの近似**：EPUBを展開し、ヘッドレスChromeでXHTMLを撮影する。Kindleを模擬するには、CSSから `var()` と論理プロパティを含む宣言を取り除いた版を撮影して、元と比べる（それでも同じ見た目なら、Kindleでも崩れにくい）。縦書きは右から左へ横に伸びる為、長い章は空白になる。問題の箇所だけを抜き出した小さなXHTMLで撮る。
- **実機**：Send to Kindle でEPUBを送り、Kindleアプリで開く。
