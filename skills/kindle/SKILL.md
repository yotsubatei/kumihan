---
name: kindle
description: Vivliostyleで作ったEPUBを、Kindle（KDP）で崩れずに読めるように整え、Kindle Previewerで確かめ、テスターに配り、KDPに出せる状態にする。「Kindleで縦書きにならない」「Kindleだと書式が崩れる・字下げが消える・余白が無い」「箇条書きの点が二重に出る」「Kindle Previewerで確認したい」「KPFを作って」「表紙が出ない」「EPUBが大きすぎる」「Kindle版を他の人に見てもらいたい」「KDPに出したい」と言われた時に使う。EPUBの見た目の問題なら、Kindleと明言されなくても、電子書籍の確認として使う。
---

# 電子書籍とKindle対応

Vivliostyle が作るEPUBは、ブラウザやVivliostyleでは正しく表示されるが、Kindleの変換エンジンは CSS の一部を**黙って無視する**。縦書きが横書きになる、字下げや余白が消える、と崩れても警告は出ない。
そこで、(1) 後処理でKindleが解釈できる書き方に置き換え、(2) 検査で残りを見つけ、(3) Kindle Previewer で実際の表示を確かめる。

このスキルのフォルダ（読み込み時に表示される Base directory）を `SKILL_DIR` と呼ぶ。道具は `SKILL_DIR/../../scripts/`（本に `tools/kumihan-kit/` としてコピーしてあれば、そちらを使う）。Kindleが解釈しない書き方と直し方の詳細は `SKILL_DIR/../../references/kindle.md` にある。崩れの原因を探す時は先に読む。

## 1. 後処理が入っているか確かめる

`package.json` の `postbuild` に、次の順で入っているか確かめる。無ければ足す（PDFには触れず、EPUBだけを書き換える）。

1. `epub_split_selectors.py <本>.epub` — `:is()` 等を含むまとめ書きのセレクタを分ける
2. `epub_resolve_css_vars.py <本>.epub` — `var()` を値に置き換える
3. `epub_physical_props.py <本>.epub --writing-mode vertical-rl --horizontal figure`（縦書き）／`--writing-mode horizontal-tb`（横書き） — 論理プロパティの前に物理プロパティを補う
4. （書体を埋め込む本）`epub_subset_fonts.py <本>.epub` — 書体を使っている文字だけに絞り込む。依存: fontTools
5. （表紙のある本）`epub_cover_image.py <本>.epub <本>.pdf` — PDFの1ページ目をJPEGにして表紙画像にする。依存: PyMuPDF

縦書きの本は、`custom.css` の `html` に `-epub-writing-mode: vertical-rl` と `writing-mode: vertical-rl` を**直接**書く（テーマは `var()` 経由の為、Kindleでは効かない）。

## 2. 検査する

```
npm run build
epubcheck <本>.epub
python3 <道具>/check_kindle_epub.py <本>.epub
```

`check_kindle_epub.py` は、後処理で直しきれていない書き方（残った `var()`、物理プロパティの無い論理プロパティ、`:is()` を含むまとめ書き、`unicode-range`、固定の値の無い `calc()`・`leader()`、WebP の画像、表紙の有無、可変フォント）を一覧にする。

- 「要修正」は直す。
- 「注意」は、テーマの中の使っていない書式（脚注・コード等）の物が多い。この本で使っている要素（見出し・段落・箇条書き・図・表・目次）に関わる物だけを直す。直す時は、テーマではなく `custom.css` に、Kindleが解釈できる書き方で上書きする（例: `calc()` の直前に固定の値を書く）。

## 3. Kindle Previewer で確かめる

Kindle Previewer 3/4（Amazonの無料のアプリ。Mac・Windows）で、KDPと同じ変換をかける。

```
# macOS（Kindle Previewer 4）
"/Applications/Kindle Previewer 4.app/Contents/MacOS/KindlePreviewer4CLI" <本>.epub --convert --output <出力先> --locale ja
```

- 変換ログ（出力先の `Summary_Log.csv` 等）で、**Enhanced Typesetting が Supported** か確かめる。Not Supported だと古い組版エンジンになり、書式全般が崩れる。主な原因は表紙画像（WebP・空・無効）と、対応していない画像形式。
- 警告の一覧を読む。縦書きの `text-combine-upright`（縦中横）で5文字以上を組んでいる、等が出る。
- `--showpreview` を付けると画面で開く。タブレット・スマートフォン・Kindle端末の表示を切り替え、文字サイズを変えて、次を見る：縦書きか、段落の字下げ、見出しの余白、箇条書きの点、ルビ、図版の大きさ、目次から各章へ飛べるか、表紙。
- 使う人にも、画面を開いて見てもらう（見るべき点を上の箇条で伝える）。

崩れを見つけたら、`references/kindle.md` で症状から原因を引き、直して、再ビルド→検査→Previewer をやり直す。直した時は、PDF（紙の本）の見た目が変わっていない事も確かめる（`pdf_diff_pages.py` で前のPDFと比べ、変わったページが0）。

## 4. 目次

Kindleには、本文の目次ページとは別に、メニューから開くナビゲーション目次がある。EPUBの `nav`（Vivliostyle が自動で作る）が使われる。

- 紙の本の目次にページ番号や点線（リーダー）があると、電子書籍では意味をなさない。EPUBだけ、ページ番号を取り除いたリンクの一覧にする（EPUB内の目次ページを書き換える後処理を作る）。
- 電子書籍に目次ページは必須ではないが、ナビゲーション目次は必要（KDPの推奨）。
- 見出しにルビを振った本は、ナビゲーション目次に読みが続いて出る（「組版くみはん」）。`epub_toc_plain.py` で目次の中のルビの読みを外す（雛形の後処理に入っている）。

## 5. KPF とテスターへの配布

- **KPF**：Kindle Previewer で変換したファイル（`.kpf`）。KDPに EPUB の代わりに出せる。中身は KDP 側の変換と同じ。
- **テスターに見てもらう**：KPFは端末に入れられない。EPUBを「Send to Kindle」で送ってもらうのが簡単。
  - iPhone・Android：Kindleアプリを入れ、Send to Kindle（Amazonのウェブページ、またはメール添付で各自の Send to Kindle アドレスへ）でEPUBを送る。アプリのライブラリに届く。
  - Windows：Send to Kindle for PC（アプリ）か、ウェブページ。Kindle for PC で読める。
  - Amazonの変換を通る為、KDPでの見え方に近い。テスターには、端末の種類・文字サイズを変えた時の見え方を見てもらう。
- 出版前の原稿である事を伝え、ファイルの扱い（他に渡さない）を頼む。

## 6. KDPに出す前に

- EPUBのサイズ：Kindleは配信の料金がファイルサイズで決まる（ロイヤリティ70%の場合）。書体を埋め込むと数十MBになる事があるので、`epub_subset_fonts.py` で絞り込む。**書体のライセンスが埋め込み・改変（サブセット化）を許しているか**を確かめる。
- KDPに上げてプレビューが変換エラーになる時：EPUBの中のファイル名・IDに日本語が残っていないか（`epub_ascii_names.py` を後処理に入れる）、KDPのページの言語が「日本語」か、KPFではなくEPUBを上げているかを確かめる。
- 外字（著者が作った書体の字）を使う本は、Kindle Previewer で縦書きの位置を見る。枠の上に寄るなら `font_add_vertical_metrics.py`。
- 表紙：KDPには、EPUBの中の表紙とは別に、表紙画像（JPEG、推奨 1600×2560 ピクセル以上）を登録する。ペーパーバックの表紙一式（裏表紙・背・表表紙）と合わせた作り方は `SKILL_DIR/../../references/cover.md`。
- ISBN：Kindle（電子書籍）には不要。
- 書誌情報（書名・著者名・説明・キーワード・カテゴリ）は、使う人と決める。価格は使う人の判断。
