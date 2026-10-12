#!/usr/bin/env python3
"""共通の道具（scripts/）と知識（references/）を、3つのスキルのフォルダの中へ写す。

スキルは、どのAIで使っても動くように、フォルダ単体で完結させる（Codex などに
`npx skills add` で入れると、スキルのフォルダだけが写され、外の scripts/・references/ は入らない為）。
元は、このリポジトリの直下の scripts/ と references/。直したら、このスクリプトを実行する。

使い方:
  python3 tools/sync_skills.py          写す
  python3 tools/sync_skills.py --check  写した物が元と同じかを確かめる（違えば終了コード1）
"""
import filecmp
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SHARED = ["scripts", "references"]


def skills():
    return sorted(p.parent for p in (ROOT / "skills").glob("*/SKILL.md"))


def same(a: Path, b: Path) -> bool:
    if not b.is_dir():
        return False
    cmp = filecmp.dircmp(a, b, ignore=["__pycache__"])
    if cmp.left_only or cmp.right_only or cmp.diff_files or cmp.funny_files:
        return False
    return all(same(a / d, b / d) for d in cmp.common_dirs)


def main():
    check = "--check" in sys.argv[1:]
    stale = []
    for skill in skills():
        for name in SHARED:
            src, dst = ROOT / name, skill / name
            if same(src, dst):
                continue
            if check:
                stale.append(f"{skill.name}/{name}")
                continue
            if dst.exists():
                shutil.rmtree(dst)
            shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__"))
            print(f"写しました: skills/{skill.name}/{name}")
    if stale:
        print("元と違うスキルの写しがあります（python3 tools/sync_skills.py で写し直す）: " + ", ".join(stale))
        sys.exit(1)


if __name__ == "__main__":
    main()
