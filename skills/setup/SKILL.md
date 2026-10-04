---
name: setup
description: 日本語の本をVivliostyleで組版するプロジェクトを、ゼロから立ち上げる。書名・著者・縦書きか横書きか・判型を聞き、原稿フォルダ・設定・CSS・書体・Kindle向けの後処理・検査を揃え、PDF（紙の本）とEPUB（電子書籍）が1回のビルドでできる状態にする。「本を作りたい」「原稿を本にしたい」「Vivliostyleで本を組みたい」「KindleやKDPで出版したい本の準備」「縦書きの本」「同人誌・小説・技術書を組版したい」など、新しく本を作り始める時は、Vivliostyleという言葉が出なくても使う。既にある本の修正は revision、電子書籍の確認は kindle を使う。
---

# 本の立ち上げ

著者の原稿から、紙の本（PDF）と電子書籍（EPUB）を同じ原稿・同じCSSで作るプロジェクトを用意する。
使う人はコマンドを打たない前提で、道具の導入からビルド・確認までAIが行い、結果を見せて判断だけを仰ぐ。

このスキルのフォルダ（読み込み時に表示される Base directory）を `SKILL_DIR` と呼ぶ。
共通の道具は `SKILL_DIR/../../scripts/`、共通の知識は `SKILL_DIR/../../references/` にある。

## 1. 道具を確かめる

次を確かめ、無いものは、何の為に入れるかを一言添えて、了承を得てから入れる（macOSなら Homebrew、Windowsなら winget 等）。

| 道具 | 用途 | 必須 |
| --- | --- | --- |
| Node.js（18以上） | Vivliostyle CLI を動かす | 必須 |
| Python 3 | EPUBの後処理・検査 | 必須 |
| Git | 版の記録（いつ何を直したかを残す） | 強く推奨 |
| epubcheck | EPUBの検証（ストアに出す前に必須） | 推奨 |
| qpdf | PDFの検証 | 推奨 |

Pythonの追加の部品（PyMuPDF・fontTools・python-docx 等）は、システムのPythonに直接入れず、プロジェクトの外の仮想環境（例: `python3 -m venv ~/.venvs/kumihan`）に入れる。macOSのPythonは直接の導入を拒む事がある（PEP 668）為。

## 2. 決める事を聞く

まとめて1回で尋ねる。各項目に推奨を添え、迷う人は推奨のままでよいと伝える。

| 項目 | 選択肢と推奨 |
| --- | --- |
| 書名・著者名 | 仮のままでよい（後で変えられる） |
| 書字方向 | 小説・随筆・歴史・宗教書等は**縦書き**（右綴じ）、コードや英字・数式が多い本は**横書き**（左綴じ） |
| 判型 | 横書きの実用書・技術書は**A5**、縦書きの読み物は**四六判**（127×188mm）か**A5**、文庫は**A6**（105×148mm）。KDPのペーパーバックで出すなら、KDPの「標準」判型（A5・四六判・B6等）から選ぶ |
| 本文の文字サイズ | A5なら横書き10pt・縦書き10〜12pt。年配の読者が多い本は大きめ。決めかねる時は、同じ原稿を候補の大きさで組んだ見本を作って見比べてもらう |
| 出版先 | KDP（Kindle＋ペーパーバック）、印刷所、PDF配布のみ、等。後の手順（塗り足し・ISBN）が変わる |

原稿が既にあれば、先に受け取って中身（章の数・ルビ・図・表の有無）を見てから聞くと、推奨を具体的にできる。

## 3. プロジェクトを作る

`SKILL_DIR/assets/` の雛形をコピーし、`{{…}}` を埋める。

```
<本のフォルダ>/
  package.json            ← assets/package.json
  vivliostyle.config.js   ← assets/vivliostyle.config.js
  custom.css              ← assets/custom-yoko.css か assets/custom-tate.css
  CLAUDE.md               ← assets/CLAUDE.md（この本での決まり事。以降のAIの作業の拠り所）
  .gitignore              ← assets/gitignore
  draft/                  ← 原稿（VFM）。assets/draft/ の見本から始める
  fonts/                  ← 書体（下記）
  received/               ← 著者から届いた原稿・修正依頼を、届いた日付ごとにそのまま保存
  releases/               ← 著者に渡す確認版を、日付ごとに保存
  tools/kumihan-kit/      ← SKILL_DIR/../../scripts/ をコピー
```

`tools/kumihan-kit/` には、プラグインのスクリプトを**コピーして**本に含める。ビルドの度にプラグインの場所を探さずに済み、後でプラグインが更新されても、この本の出力が勝手に変わらない為。更新を取り込む時は、コピーし直してから出力を見比べる。

雛形の置き換え：

- `{{TITLE}}` 書名、`{{AUTHOR}}` 著者名、`{{SLUG}}` 出力ファイル名（英数字。例 `my-novel`）
- `{{SIZE}}` 判型（`A5`・`A6`・`B6`、四六判は `127mm 188mm`）
- `{{PROGRESSION}}` 縦書きは `rtl`、横書きは `ltr`
- `{{THEME}}` 縦書きは `@vivliostyle/theme-bunko@2.0.2`、横書きは `@vivliostyle/theme-techbook@2.0.2`
- `{{WRITING_MODE_ARGS}}` 縦書きは `--writing-mode vertical-rl --horizontal figure`、横書きは `--writing-mode horizontal-tb`
- `{{FONT_SIZE}}` 本文の文字サイズ（例 `10pt`）
- `{{DIRECTION}}` `縦書き` か `横書き`（CLAUDE.md の説明文用）

版は固定する（`@vivliostyle/cli` 11.2.0、テーマも版を指定）。版が上がると組版の結果（改行位置・ページ数）が変わり、著者の確認済みのページがずれる為。theme-techbook 3.0.0 は CLI 11.2.0 で読み込めなかった。上げる時は、新旧のPDFを見比べてから。

### 書体

既定は Noto Serif JP（本文）と Noto Sans JP（見出し）。SIL Open Font License で、商用の本に埋め込んで販売できる。可変フォントではなく、太さごとの静的なOTF（Regular・Bold）を使う（Kindleが可変フォントに対応していない可能性がある為）。

```
https://github.com/notofonts/noto-cjk/raw/main/Serif/SubsetOTF/JP/NotoSerifJP-Regular.otf
https://github.com/notofonts/noto-cjk/raw/main/Serif/SubsetOTF/JP/NotoSerifJP-Bold.otf
https://github.com/notofonts/noto-cjk/raw/main/Sans/SubsetOTF/JP/NotoSansJP-Regular.otf
https://github.com/notofonts/noto-cjk/raw/main/Sans/SubsetOTF/JP/NotoSansJP-Bold.otf
https://github.com/notofonts/noto-cjk/raw/main/Serif/LICENSE  （fonts/OFL.txt として保存）
```

著者が商用の書体（モリサワ、フォントワークス、字游工房等）を使いたい場合は、**電子書籍への埋め込みと販売がライセンスで許されているか**を著者に確かめてもらう。許されていない書体は、PDFだけに使い、EPUBは Noto にする等の分け方を提案する。

## 4. ビルドして確かめる

```
npm install
npm run build
```

`npm run build` は、前処理（ルビの書き方の検査、書体のコピー）→ PDF・EPUBの書き出し → 後処理（EPUBをKindle向けに整える）を続けて行う。後処理の中身は `SKILL_DIR/../../references/kindle.md` を参照。

確かめる事：

1. `qpdf --check <SLUG>.pdf` と `epubcheck <SLUG>.epub`（エラー・警告0件）
2. `python3 tools/kumihan-kit/check_kindle_epub.py <SLUG>.epub`（表紙が無い間の「表紙画像がありません」は、表紙ができるまで残ってよい）
3. PDFの最初の数ページを画像にして**自分の目で見る**（PyMuPDF か `pdftoppm -png -r 60 -f 1 -l 4`）。縦書きなら文字が縦に並び、ページが右から左へ進むか。書体が明朝になっているか（豆腐〈□〉や代替書体になっていないか）。
4. 同じ画像を使う人に見せ、1行の字数・1ページの行数・総ページ数を添えて、文字の大きさと余白の印象を聞く。

## 5. 版の記録を始める

`git init` して最初のコミットをする。GitHub等に置く場合は、**出版前の原稿を含むので非公開**で作る（公開範囲は使う人に確かめる）。

## 6. 使う人に伝える事

立ち上げが終わったら、次の頼み方を例として伝える（コマンドは伝えなくてよい）。

- 「この原稿（Wordのファイル）を第1章として取り込んで」
- 「ルビは『漢字（よみ）』の形で書いてあるので、ルビにして」
- 「著者から修正依頼が来ました」→ revision スキル
- 「Kindleでの見え方を確かめたい」→ kindle スキル

## 立ち上げでつまずきやすい点

- **章のファイル名を数字で始めたまま出力名にしない。** `vivliostyle.config.js` の各章に `output: "chapter1.html"` のように英字始まりの名前を付ける。数字始まりだとEPUBの中の識別子が不正になり、epubcheck でエラーになる。
- **書体の名前は、パソコンに入っている書体と被らない独自の名前で登録する**（雛形は `KMNotoSerifJP`）。同じ名前だと、手元ではパソコンの書体で表示され、埋め込みの失敗に気づけない。
- 書体は `fonts/` に置き、前処理で `.vivliostyle/themes/fonts/` にコピーしてから参照する（Vivliostyle CLI がEPUBに同梱するのはテーマのフォルダの中の為）。
- 縦書きの本は、`html` に `writing-mode` と `-epub-writing-mode` の**両方**を書く（雛形にある）。片方だとKindleで横書きになる。
- 縦書きでは、上下左右の向きの言葉が入れ替わる（`margin-block-start` は右、`text-align` は天地の揃え）。`SKILL_DIR/../../references/japanese-typesetting.md` を参照。
- 原稿の記法（ルビ・圏点・縦中横・改ページ）は、最初に決めて `CLAUDE.md` に書く。途中で変えると、原稿全体を書き換える事になる。
- 表の中にルビを振る時は `{漢字|よみ}` ではなく `<ruby>` で書く（縦棒が表の列の区切りとぶつかる）。表を足したら `table_nowrap.py` を通す。
- 表紙は、本文のページ数が固まってから仕上げる（背の幅がページ数で変わる）。作り方は `SKILL_DIR/../../references/cover.md`。
