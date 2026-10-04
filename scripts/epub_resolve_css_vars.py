"""EPUB内のCSSのvar()（CSS変数）を、解決済みの値に置き換える後処理。

Kindleの変換エンジンはvar()を解釈できず、テーマ（theme-base/theme-bunko）が
CSS変数経由で指定している書式（縦書き・文字サイズ・行間・字下げ等）が
全て無視されてしまう。PDF（Vivliostyle）は変数を正しく扱える為、EPUBだけを
対象に、変数を画面表示用（@media screen）の値で解決して書き戻す。

- ルート（:root / html。:lang(ja)付きを含む）で定義された変数を、
  CSSの読み込み順（@importを展開した順）に集めて使う。@media printの中の
  定義は使わない（電子書籍リーダーは画面表示として扱う為）。
- :root以外の要素で変数を上書きしている箇所（例: 目次だけ字間を変える .toc）は、
  置き換えると違いが失われる為、その範囲に限定したルールを別に足して補う。
- @page・@font-face・@media printの中は、電子書籍リーダーが使わない為そのまま。

使い方: python3 scripts/epub_resolve_css_vars.py <EPUBファイル>
"""
import posixpath
import re
import sys
import zipfile
from pathlib import Path

ROOT_SELECTORS = {":root", "html", ":root:lang(ja)", "html:lang(ja)"}
SKIP_AT = ("@page", "@font-face", "@media print")
VAR_RE = re.compile(r"var\(\s*(--[\w-]+)\s*(?:,([^()]*(?:\([^()]*\)[^()]*)*))?\)")


def blank_comments(text):
    """コメントを同じ長さの空白に置き換える（位置を保つ為）。文字列内は触らない。"""
    out, i, n = [], 0, len(text)
    while i < n:
        c = text[i]
        if c in "\"'":
            j = i + 1
            while j < n and text[j] != c:
                j += 2 if text[j] == "\\" else 1
            out.append(text[i:j + 1])
            i = j + 1
        elif text.startswith("/*", i):
            j = text.find("*/", i + 2)
            j = n if j < 0 else j + 2
            out.append(re.sub(r"[^\n]", " ", text[i:j]))
            i = j
        else:
            out.append(c)
            i += 1
    return "".join(out)


def skip_string(s, i):
    q, j = s[i], i + 1
    while j < len(s) and s[j] != q:
        j += 2 if s[j] == "\\" else 1
    return j + 1


def parse_blocks(s, start, end, context, rules):
    """s[start:end]内のルールを走査し、(文脈, セレクタ, 本文開始, 本文終了)を集める。"""
    i, prelude_start = start, start
    while i < end:
        c = s[i]
        if c in "\"'":
            i = skip_string(s, i)
            continue
        if c == ";":
            prelude_start = i + 1
        elif c == "{":
            prelude = " ".join(s[prelude_start:i].split())
            depth, j = 1, i + 1
            while j < end and depth:
                if s[j] in "\"'":
                    j = skip_string(s, j)
                    continue
                depth += {"{": 1, "}": -1}.get(s[j], 0)
                j += 1
            body_start, body_end = i + 1, j - 1
            if prelude.startswith("@"):
                if prelude.startswith(("@media", "@supports")):
                    parse_blocks(s, body_start, body_end, context + (prelude,), rules)
                else:
                    rules.append((context + (prelude,), None, body_start, body_end))
            else:
                rules.append((context, prelude, body_start, body_end))
            i, prelude_start = j, j
            continue
        elif c == "}":
            prelude_start = i + 1
        i += 1


def declarations(s, body_start, body_end):
    """本文内の宣言を (名前, 値, 宣言開始, 値開始, 値終了) で返す。"""
    out, i, decl_start, depth = [], body_start, body_start, 0
    while i <= body_end:
        c = s[i] if i < body_end else ";"
        if c in "\"'" and i < body_end:
            i = skip_string(s, i)
            continue
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
        elif c == ";" and depth == 0:
            chunk = s[decl_start:i]
            if ":" in chunk:
                colon = decl_start + chunk.index(":")
                name = s[decl_start:colon].strip()
                if name:
                    lead = len(s[decl_start:colon]) - len(s[decl_start:colon].lstrip())
                    vstart = colon + 1
                    out.append((name, s[vstart:i].strip(), decl_start + lead, vstart, i))
            decl_start = i + 1
        i += 1
    return out


def skipped(context):
    return any(p.startswith(SKIP_AT) for p in context)


def resolve(value, env, depth=0):
    if depth > 20:
        return None
    while True:
        m = VAR_RE.search(value)
        if not m:
            return value
        name, fallback = m.group(1), m.group(2)
        if name in env:
            rep = resolve(env[name], env, depth + 1)
        elif fallback is not None:
            rep = resolve(fallback.strip(), env, depth + 1)
        else:
            rep = None
        if rep is None:
            return None
        value = value[:m.start()] + rep + value[m.end():]


def split_list(selector):
    """セレクタのまとめ書きを、括弧の外のカンマで分ける（:is(a, b) の中では分けない）。"""
    parts, depth, cur = [], 0, ""
    for c in selector:
        depth += (c == "(") - (c == ")")
        if c == "," and depth == 0:
            parts.append(cur.strip())
            cur = ""
        else:
            cur += c
    parts.append(cur.strip())
    return [p for p in parts if p]


def scoped_selectors(scope, selector):
    """範囲（scope）で上書きされた変数を、ルール（selector）に適用する為のセレクタの一覧。"""
    out = []
    for t in split_list(scope):
        for sel in split_list(selector):
            # セレクタが最終的に指す要素（最後の複合セレクタ）が範囲の要素そのものなら
            # そのまま、そうでなければ範囲の子孫として限定する
            subject = re.split(r"\s*[\s>+~]\s*", sel)[-1]
            if subject == t or (subject.startswith(t) and subject[len(t)] in ":.[#"):
                out.append(sel)
            else:
                out.append(f"{t} {sel}")
    return list(dict.fromkeys(out))


def css_order(files, entry_paths):
    """<link>で読み込まれる順に、@importを展開したCSSファイルの並びを返す。"""
    order = []

    def visit(path):
        if path in order or path not in files:
            return
        text = blank_comments(files[path])
        for m in re.finditer(r"@import\s+(?:url\()?\s*['\"]?([^'\")\s]+)", text):
            visit(posixpath.normpath(posixpath.join(posixpath.dirname(path), m.group(1))))
        order.append(path)

    for p in entry_paths:
        visit(p)
    return order


def main():
    if len(sys.argv) != 2:
        sys.exit("使い方: python3 epub_resolve_css_vars.py <EPUBファイル>")
    epub = Path(sys.argv[1])
    with zipfile.ZipFile(epub) as z:
        infos = z.infolist()
        data = {i.filename: z.read(i.filename) for i in infos}

    css_files = {n: d.decode("utf-8") for n, d in data.items() if n.endswith(".css")}
    entries = []
    for n, d in data.items():
        if n.endswith(".xhtml"):
            for href in re.findall(r'<link[^>]+href="([^"]+\.css)"', d.decode("utf-8")):
                p = posixpath.normpath(posixpath.join(posixpath.dirname(n), href))
                if p not in entries:
                    entries.append(p)
    order = css_order(css_files, entries)
    order += [n for n in css_files if n not in order]

    parsed = {}
    for name in order:
        s = blank_comments(css_files[name])
        rules = []
        parse_blocks(s, 0, len(s), (), rules)
        parsed[name] = (s, rules)

    env, scopes = {}, []
    for name in order:
        s, rules = parsed[name]
        for context, selector, b0, b1 in rules:
            if selector is None or skipped(context):
                continue
            defs = {n: v for n, v, *_ in declarations(s, b0, b1) if n.startswith("--")}
            if not defs:
                continue
            if all(x.strip() in ROOT_SELECTORS for x in selector.split(",")):
                env.update(defs)
            else:
                scopes.append((selector, defs))

    total = unresolved = extra_rules = 0
    for name in order:
        s, rules = parsed[name]
        text = css_files[name]
        edits, extras = [], []
        for context, selector, b0, b1 in rules:
            if selector is None or skipped(context):
                continue
            for dname, value, dstart, vstart, vend in declarations(s, b0, b1):
                if dname.startswith("--") or "var(" not in value:
                    continue
                resolved = resolve(value, env)
                if resolved is None:
                    unresolved += 1
                    continue
                edits.append((vstart, vend, " " + resolved))
                total += 1
                for scope, defs in scopes:
                    scoped = resolve(value, {**env, **defs})
                    if scoped is not None and scoped != resolved:
                        # セレクタ1つずつのルールにする（まとめ書きに :is() 等が1つでも
                        # 混ざると、Kindleがルール全体を捨てる為。詳細度・順番は変わらない）
                        for sel in scoped_selectors(scope, selector):
                            rule = f"{sel} {{ {dname}: {scoped}; }}"
                            for p in reversed(context):
                                rule = f"{p} {{ {rule} }}"
                            extras.append(rule)
        if not edits and not extras:
            continue
        for vstart, vend, rep in sorted(edits, reverse=True):
            text = text[:vstart] + rep + text[vend:]
        if extras:
            extra_rules += len(extras)
            text += ("\n/* 以下、epub_resolve_css_vars.pyが追加（要素の範囲で上書きされた"
                     "CSS変数の値を、範囲を限定したルールとして補ったもの） */\n")
            text += "\n".join(extras) + "\n"
        data[name] = text.encode("utf-8")

    # 要素のstyle属性で変数の値を個別に指定している箇所（例: .narrowの
    # style="--narrow: -0.05em"）は、CSS側を既定値で置き換えると個別の値が失われる為、
    # 解決済みの値をstyle属性に書き足す。対象はクラス1つだけのセレクタで使われる変数に限る
    class_uses = {}
    for name in order:
        s, rules = parsed[name]
        for context, selector, b0, b1 in rules:
            if selector is None or skipped(context):
                continue
            for dname, value, *_ in declarations(s, b0, b1):
                if dname.startswith("--") or "var(" not in value:
                    continue
                for var in {m[0] for m in VAR_RE.findall(value)}:
                    class_uses.setdefault(var, []).append((selector, dname, value))
    inline = 0
    for n, d in list(data.items()):
        if not n.endswith(".xhtml"):
            continue
        html = d.decode("utf-8")

        def fix(m):
            nonlocal inline
            tag = m.group(0)
            style = re.search(r'style="([^"]*)"', tag)
            if not style or "--" not in style.group(1):
                return tag
            defs = dict(re.findall(r"(--[\w-]+)\s*:\s*([^;]+)", style.group(1)))
            classes = set((re.search(r'class="([^"]*)"', tag) or [None, ""])[1].split())
            added = []
            for var, val in defs.items():
                for selector, dname, value in class_uses.get(var, []):
                    if re.fullmatch(r"\.[\w-]+", selector.strip()) and selector.strip()[1:] in classes:
                        resolved = resolve(value, {**env, **defs})
                        if resolved is not None:
                            added.append(f"{dname}: {resolved}")
                    else:
                        print(f"警告: style属性の変数{var}を使うルール「{selector}」は自動で補えません（{n}）")
            if not added:
                return tag
            inline += 1
            new_style = style.group(1).rstrip("; ") + "; " + "; ".join(dict.fromkeys(added))
            return tag.replace(style.group(0), f'style="{new_style}"')

        html = re.sub(r"<[a-zA-Z][^<>]*\sstyle=\"[^\"]*--[^\"]*\"[^<>]*>", fix, html)
        data[n] = html.encode("utf-8")
    if inline:
        print(f"style属性で個別に指定された変数を補いました: {inline}箇所")

    tmp = epub.with_suffix(".epub.tmp")
    with zipfile.ZipFile(tmp, "w") as out:
        for info in infos:
            method = zipfile.ZIP_STORED if info.filename == "mimetype" else zipfile.ZIP_DEFLATED
            out.writestr(info, data[info.filename], compress_type=method)
    tmp.replace(epub)
    print(f"EPUBのCSS変数を解決しました: {total}箇所（解決できず残した箇所 {unresolved}、"
          f"範囲限定で補ったルール {extra_rules}）")


if __name__ == "__main__":
    main()
