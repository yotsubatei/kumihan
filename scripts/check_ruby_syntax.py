#!/usr/bin/env python3
"""
原稿（VFMのMarkdown）内のルビ（`{漢字|よみ}` 記法）が、正しく変換される書き方に
なっているかを検証する。

背景:
  `{漢字|よみ}` は、通常のMarkdownの段落内でのみ変換される。段落が `<p ...>`
  `<div ...>` 等のブロック要素のタグで始まると、VFMはその段落全体を生HTMLとして
  そのまま出力する為、中の `{漢字|よみ}` は変換されず、記号のままPDF/EPUBに出る。
  生HTMLの段落は複数行にまたがる事があり（例: `<p class="note">1行目\n2行目</p>`）、
  問題の箇所が2行目以降にあると「行頭が `<` か」だけを見る簡易な確認では見逃す。
  その為、行単位ではなく段落（ブロック）単位で生HTMLかどうかを判定する。

  あわせて次の2つも検査する:
    - 見出しの直後（空行なし）に `{漢字|よみ}` で始まる段落が続くと、VFMの解析が
      誤動作してHTMLが壊れる。
    - 機械的なルビの追加で、既にルビのある箇所に重ねてしまう「二重ルビ」
      （`{{漢字|よみ}|よみ}` のような入れ子）。

使い方:
  python3 check_ruby_syntax.py [原稿のディレクトリ]   （既定: draft）
      ディレクトリ内の *.md を全て検査する。問題があれば一覧を表示して終了コード1、
      無ければ終了コード0。package.json の prebuild に入れておくと、不具合が
      入り込んだ時点でビルドが止まる。
"""

import re
import sys
import glob

RUBY_PATTERN = re.compile(r'\{([^{}|]+)\|([^{}|]+)\}')


SELF_CONTAINED_TAG = re.compile(r'^<(\w+)(?:\s[^>]*)?>.*</\1>\s*$')
BLOCK_START_TAG = re.compile(r'^<(\w+)')

# VFM（remark、CommonMarkのHTMLブロック規則）は、段落の先頭が
# <ruby> <span> <strong> 等の「インライン」要素で始まっていても、それだけ
# では生HTMLブロックとして扱わない（あくまで通常のMarkdown段落の中に
# インラインHTMLが混ざっているだけで、{漢字|よみ}は正しく変換される）。
# 生HTMLとして丸ごとパススルーされる（内部の{漢字|よみ}が変換されない）
# のは、段落の先頭が <p> <div> <blockquote> <figure> 等の「ブロック」
# 要素で始まっている場合のみ。<ruby>で始まる通常の段落
# （例:「<ruby>漢字<rt>かんじ</rt></ruby>とは…」）を生HTMLと誤判定しない
# よう、段落の先頭に使われるブロック要素の一覧を明示的に用意している
# （新しいブロック要素を段落の先頭に使い始めた場合は、この一覧に追加する）
BLOCK_LEVEL_TAGS = {
    'p', 'div', 'blockquote', 'figure', 'figcaption',
    'nav', 'ol', 'ul', 'li',
    'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
    'table', 'thead', 'tbody', 'tr', 'td', 'th',
}


def is_block_level_start(line):
    m = BLOCK_START_TAG.match(line.lstrip())
    return bool(m) and m.group(1).lower() in BLOCK_LEVEL_TAGS


def check_ruby_in_raw_html(lines):
    """段落（ブロック）単位で生HTMLかどうかを判定し、生HTMLブロック内に
    未変換のルビ記法が無いかを調べる。

    ブロックの区切りは単純な空行だけでは不十分（見出し行の直後に空行を
    挟まず `<p class="note">...{漢字|かんじ}...</p>` という生HTMLの1行が
    続くと、空行だけで区切ると見逃す）。見出し行（`#`で始まる行）はVFM上、前後に
    空行が無くても常にそれ単体で独立したブロックになる為、見出し行は
    それ単体で1ブロックとして区切る。同様に、開始タグと終了タグが
    同じ行の中で閉じている自己完結した1行のHTML要素
    （例: `<p class="note">...</p>`）も、前後に空行が無くてもそこで
    ブロックが終わる（次の行は独立した新しいブロックとして扱われる）。 """
    issues = []
    i = 0
    while i < len(lines):
        if lines[i].strip() == '':
            i += 1
            continue
        block_start = i
        block_lines = []
        # 見出し行は単独で1ブロック
        if lines[i].lstrip().startswith('#'):
            block_lines.append(lines[i])
            i += 1
        else:
            while i < len(lines) and lines[i].strip() != '' and not lines[i].lstrip().startswith('#'):
                block_lines.append(lines[i])
                i += 1
                # 自己完結した1行のブロック要素の直後でブロックを区切る
                stripped = block_lines[-1].strip()
                if is_block_level_start(stripped) and SELF_CONTAINED_TAG.match(stripped):
                    break
        # VFMは、ブロックの先頭行が<p><div>等の「ブロック要素」タグで
        # 始まる場合のみ、そのブロック全体を生HTMLとして扱う（内部の
        # 空行なし複数行も含めて）。<ruby>等のインライン要素で始まる
        # だけでは生HTMLにはならない（is_block_level_startを参照）
        if is_block_level_start(block_lines[0]):
            block_text = '\n'.join(block_lines)
            for m in RUBY_PATTERN.finditer(block_text):
                line_no = block_start + block_text[:m.start()].count('\n') + 1
                issues.append((line_no, f"生HTMLブロック内の未変換ルビ記法: {m.group(0)}"))
    return issues


def check_heading_adjacency(lines):
    """見出し直後（空行なし）に {ruby} で始まる段落が続くと、VFMの
    パースが誤動作する不具合を検査する。"""
    issues = []
    for i in range(len(lines) - 1):
        if lines[i].startswith('#') and lines[i + 1].startswith('{'):
            issues.append((i + 1, f"見出し直後に空行なしでルビ記法が続いている: {lines[i]!r} -> {lines[i+1]!r}"))
    return issues


def check_nested_ruby(lines):
    """{{漢字|よみ}|よみ} のような二重ルビ（波括弧の入れ子）を検査する。
    行の途中で一時的に深さ2以上に達して同じ行内で閉じるケース（同一行内の
    入れ子）も見逃さないよう、行末時点の深さだけでなく、行を処理する
    過程で到達した最大深さを見る（1行ずつではなく、ファイル全体を通して
    深さを追跡する事で、複数行にまたがる入れ子も検出できる）。"""
    issues = []
    depth = 0
    for i, line in enumerate(lines):
        max_depth_this_line = depth
        for ch in line:
            if ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
            max_depth_this_line = max(max_depth_this_line, depth)
        if max_depth_this_line > 1:
            issues.append((i + 1, f"二重ルビの疑い（波括弧の深さ{max_depth_this_line}）: {line[:80]!r}"))
        depth = max(depth, 0)
    return issues


INLINE_CODE = re.compile(r'`+[^`]*`+')


def mask_code(lines):
    """コードブロック（``` で囲んだ部分）とインラインコード（`...`）の中は、VFMが
    ルビとして変換しない（記法の例を書く場所）為、空白に置き換えて検査から外す。
    行番号を保つ為、行の数と長さは変えない。"""
    out, in_fence = [], False
    for line in lines:
        if line.lstrip().startswith('```'):
            in_fence = not in_fence
            out.append(' ' * len(line))
        elif in_fence:
            out.append(' ' * len(line))
        else:
            out.append(INLINE_CODE.sub(lambda m: ' ' * len(m.group(0)), line))
    return out


def main():
    draft = sys.argv[1] if len(sys.argv) > 1 else 'draft'
    files = sorted(glob.glob(f'{draft}/*.md'))
    all_issues = []
    for path in files:
        lines = mask_code(open(path, encoding='utf-8').read().split('\n'))
        checks = [
            check_ruby_in_raw_html(lines),
            check_heading_adjacency(lines),
            check_nested_ruby(lines),
        ]
        for issues in checks:
            for line_no, message in issues:
                all_issues.append((path, line_no, message))

    if all_issues:
        print("ルビ構文の不具合が見つかりました:")
        for path, line_no, message in sorted(all_issues):
            print(f"  {path}:{line_no}: {message}")
        print(f"\n合計 {len(all_issues)} 件。{draft}/*.md を修正してください。")
        sys.exit(1)

    print(f"OK: {draft}/*.md（{len(files)}ファイル）でルビ構文の不具合は見つかりませんでした。")
    sys.exit(0)


if __name__ == "__main__":
    main()
