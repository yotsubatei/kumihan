# kumihan-kit

Vivliostyleで作る日本語の本を、Kindle等の電子書籍リーダーでも崩れずに読めるようにする為の道具集です。縦書き・横書きの両方に使えます。

Claude Code のプラグイン（`kumihan`）として、本作りの手順をまとめたスキルも同梱しています。

## スキル（Claude Code プラグイン）

| スキル | 使う場面 |
| --- | --- |
| `kumihan:setup` | 新しい本のプロジェクトを立ち上げる（設定・CSS・書体・後処理・検査を揃え、PDFとEPUBができる状態にする） |
| `kumihan:revision` | 著者の修正依頼を反映し、検査・新旧の見比べ・日付付きの確認版の作成まで行う |
| `kumihan:kindle` | EPUBをKindleで崩れないように整え、Kindle Previewer で確かめ、テスターへの配布とKDPへの提出を準備する |

導入（Claude Code の中で）:

```
/plugin marketplace add yotsubatei/kumihan
/plugin install kumihan@kumihan-kit
```

スキルは頼み方（「本を作りたい」「著者から修正依頼が来ました」「Kindleで縦書きにならない」等）に応じて自動で使われます。共通の知識は `references/`（`kindle.md`：Kindleで崩れる原因と直し方、`japanese-typesetting.md`：日本語組版の要点）にあります。

## 道具

| スクリプト | 役割 |
| --- | --- |
| `scripts/epub_split_selectors.py` | まとめて書いたセレクタ（`a, b:is(c)`）のうち、Kindleが解釈できない `:is()` `:where()` `:has()` を含むものがあるルールを、セレクタ1つずつに分ける。1つでも解釈できないとルール全体が捨てられ、例えば箇条書きの点が消えずに二重に出る為。後処理の最初に実行する |
| `scripts/epub_resolve_css_vars.py` | EPUB内のCSSの `var()`（CSS変数）を解決済みの値に置き換える。Kindleは `var()` を解釈できず、テーマの書式（縦書き・文字サイズ・行間・字下げ等）が無視される為 |
| `scripts/epub_physical_props.py` | 論理プロパティ（`margin-block` 等）の直前に、同じ値の物理プロパティ（上下左右）を補う。Kindleは論理プロパティを一部解釈できない為 |
| `scripts/build_word.py` | EPUBから、ルビ（Wordのルビ機能）付きの全文Word（.docx）を作る |
| `scripts/epub_cover_image.py` | EPUBの表紙を、PDFの1ページ目を画像化したJPEGに差し替え、表紙ページを本文の流れから外す。表紙画像が無効（空・WebP等）だとKindleが新しい組版エンジンを使えず、書式全般が崩れる為。依存: PyMuPDF（fitz） |
| `scripts/epub_subset_fonts.py` | EPUBに埋め込んだ書体を、本で使っている文字（本文・ルビ・CSSで追加する記号）だけに絞り込む。縦書き用の字形等の組版機能は残す。日本語の書体は1書体で数MBあり、Kindleは配信の料金がファイルサイズで変わる為。依存: fontTools。書体のライセンスが改変を許すかは使う側で確認する |
| `scripts/check_kindle_epub.py` | 出来上がったEPUBに、Kindleで崩れる原因になる書き方（残った `var()`、物理プロパティの無い論理プロパティ、`:is()` を含むまとめ書き、`unicode-range`、固定の値の無い `calc()`・`leader()`、WebP、表紙の有無、可変フォント）が残っていないかを検査する。EPUBは書き換えない |
| `scripts/pdf_diff_pages.py` | 新旧のPDFを1ページずつ画像で比べ、見た目の変わったページを通し番号とノンブルで一覧にする（`--out` で旧｜新を並べた画像）。依存: PyMuPDF |
| `scripts/check_layout.py` | 出来上がったPDFから、泣き別れの候補（見出しがページの最後に残る、段落の1行だけがページの頭・終わりに分かれる、段落の最後の行が1〜2文字だけ）を、ページ番号付きで一覧にする。縦書き・横書きの両方。依存: PyMuPDF |
| `scripts/unzip_ja.py` | Windowsで作られたZIPを、日本語のファイル名が化けないように展開する |
| `scripts/check_ruby_syntax.py` | 原稿のルビ（`{漢字\|よみ}`）が変換されない書き方（生HTMLの段落の中、見出しの直後、二重ルビ）になっていないかを検査する。ビルドの前処理に入れる |

EPUBを書き換える後処理（`epub_*.py`）は、いずれもEPUBだけを書き換え、PDFには手を加えません。

## 使い方

`npm run build` の後処理（`package.json` の `postbuild`）として、次の順に実行します。

```sh
python3 kumihan-kit/scripts/epub_split_selectors.py 本.epub
python3 kumihan-kit/scripts/epub_resolve_css_vars.py 本.epub
# 縦書きの本（テーマが図版だけ横書きにしている場合）
python3 kumihan-kit/scripts/epub_physical_props.py 本.epub --writing-mode vertical-rl --horizontal figure
# 横書きの本
python3 kumihan-kit/scripts/epub_physical_props.py 本.epub --writing-mode horizontal-tb
```

表紙の画像化（表紙のある本）とルビの検査は次のとおりです。

```sh
python3 kumihan-kit/scripts/epub_subset_fonts.py 本.epub               # 書体を埋め込む本（postbuildの最後の方に）
python3 kumihan-kit/scripts/epub_cover_image.py 本.epub 本.pdf          # 代替テキストは書名
python3 kumihan-kit/scripts/check_ruby_syntax.py draft                 # prebuild に入れる
```

Word書き出しは、EPUBを展開してから実行します（依存: python-docx beautifulsoup4 lxml pillow。システムのPythonに入れず仮想環境を使う）。

```sh
python3 -m venv --clear /tmp/docx_venv && /tmp/docx_venv/bin/pip install python-docx beautifulsoup4 lxml pillow
unzip 本.epub -d 展開先
/tmp/docx_venv/bin/python kumihan-kit/scripts/build_word.py 展開先/EPUB 本_全文.docx
```

## 確認

- `epubcheck 本.epub`（エラー・警告0件）
- Kindle Previewer 4：`"/Applications/Kindle Previewer 4.app/Contents/MacOS/KindlePreviewer4CLI" 本.epub --convert --output 出力先 --locale ja`（変換ログと Enhanced Typesetting の可否）

## 由来

縦書きの書籍の制作で作った後処理を、本の中身に依存しない形に切り出したもの。切り出す際、元のスクリプトと同じ入力に対して同じ出力（EPUB内の全ファイル、Wordの本文）になる事を確認している。

## ライセンス

MIT License（[LICENSE](LICENSE)）。著作権表示を残せば、利用・改変・再配布は自由です。無保証です。

この道具で作る本の原稿・書体・図版のライセンスは、それぞれの権利者の条件に従ってください（例えば、書体をEPUBに埋め込む・絞り込む事が許されているか）。
