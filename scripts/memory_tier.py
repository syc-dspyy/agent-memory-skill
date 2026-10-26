#!/usr/bin/env python3
"""深浅目录分层管理（v1.3 · R14）。

解决的问题
-----------
记忆目录是常驻上下文的一部分——事件越多，每次会话加载的 token 越多。
分层让「近期 + 重要」留在深层常驻，「久远 + 日常」沉到浅层按需读。

★ 关键设计：事件文件本身不移动，只是目录行归到哪一层。
  所以 links.md、事件详情路径、git 历史全部不受影响。

用法
----
    python3 memory_tier.py --root <root> --plan                 # 看分层方案（不改动）
    python3 memory_tier.py --root <root> --stats                # token 估算
    python3 memory_tier.py --root <root> --pin <slug>           # 🔒 锁定在深层（永不下沉）
    python3 memory_tier.py --root <root> --unpin <slug>         # 解锁
    python3 memory_tier.py --root <root> --promote <slug>       # ⭐ 标为重要（浅层→深层）
    python3 memory_tier.py --root <root> --demote <slug>        # 标为日常（立即下沉）

    改完 frontmatter 后需 `memory_index.py --rebuild` 才生效（本脚本会提示）。

slug 是什么：事件 frontmatter 的 slug 字段（不是文件名，文件名带日期前缀）。
"""
import argparse
import os
import re
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from memory_index import (  # noqa: E402
    TOKEN_PER_ROW,
    collect_events,
    is_true,
    parse_date,
    read_window_days,
    tier_of,
)


def find_file(root, slug):
    """按 slug 找事件文件路径。"""
    ev_dir = os.path.join(root, "facts", "events")
    for it in collect_events(root):
        if it["slug"] == slug:
            return os.path.join(ev_dir, it["file"]), it
    return None, None


def set_field(path, key, value):
    """在 frontmatter 里设置字段（存在则替换，不存在则追加）。"""
    with open(path, "r", encoding="utf-8") as f:
        txt = f.read()
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n", txt, re.S)
    if not m:
        print(f"  ✗ 文件无 frontmatter：{os.path.basename(path)}")
        return False
    fm = m.group(1)
    if re.search(rf"^{re.escape(key)}\s*:", fm, re.M):
        new_fm = re.sub(rf"^{re.escape(key)}\s*:.*$", f"{key}: {value}", fm, count=1, flags=re.M)
        act = "更新"
    else:
        new_fm = fm.rstrip() + f"\n{key}: {value}"
        act = "新增"
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(f"---\n{new_fm}\n---\n" + txt[m.end():])
    print(f"  ✓ {act} {key}: {value} → {os.path.basename(path)}")
    return True


def drop_field(path, key):
    """从 frontmatter 删除字段。"""
    with open(path, "r", encoding="utf-8") as f:
        txt = f.read()
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n", txt, re.S)
    if not m:
        return False
    fm = m.group(1)
    new_fm = re.sub(rf"^{re.escape(key)}\s*:.*\n?", "", fm, count=1, flags=re.M).rstrip()
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(f"---\n{new_fm}\n---\n" + txt[m.end():])
    print(f"  ✓ 移除 {key} → {os.path.basename(path)}")
    return True


def reason_of(it, w):
    """标注这条为什么在深层。"""
    if is_true(it.get("pinned", "")):
        return "🔒 已锁定"
    if str(it.get("importance", "")).lower() == "high":
        return "⭐ 重要"
    d = parse_date(it.get("date", ""))
    if d is not None:
        left = w - (date.today() - d).days
        return f"🕐 近期（{max(left, 0)} 天后下沉）"
    return "—"


def do_plan(root):
    w = read_window_days(root)
    items = collect_events(root)
    deep = [i for i in items if tier_of(i, w) == "deep"]
    shallow = [i for i in items if tier_of(i, w) == "shallow"]

    print(f"[分层方案] {root}")
    print(f"  深层时间窗 {w} 天 / 事件总数 {len(items)}\n")
    print(f"  深层 index.md（常驻必读）{len(deep)} 条：")
    for i in deep:
        print(f"    {reason_of(i, w):<22} {i['date']}  {i['summary']}")
    print(f"\n  浅层 index-shallow.md（按需读）{len(shallow)} 条：")
    for i in shallow:
        print(f"    · {i['date']}  {i['summary']}")
    if not shallow:
        print("    （暂无——事件都在时间窗内，或都被标为重要/锁定）")

    # 即将下沉：深层里仅因"近期"留下的，按剩余天数升序
    soon = []
    for i in deep:
        if is_true(i.get("pinned", "")) or str(i.get("importance", "")).lower() == "high":
            continue
        d = parse_date(i.get("date", ""))
        if d is None:
            continue
        left = w - (date.today() - d).days
        if left <= 14:
            soon.append((left, i))
    if soon:
        print(f"\n  ⏳ 即将下沉（≤14 天）：")
        for left, i in sorted(soon):
            print(f"    · {max(left,0)} 天后 → {i['date']} {i['summary']}")
        print("      想留住它：`--pin <slug>`（锁定）或 `--promote <slug>`（标重要）")

    print(f"\n  常驻目录 token 估算：约 {len(deep) * TOKEN_PER_ROW} token"
          f"（浅层 {len(shallow) * TOKEN_PER_ROW} token 已移出常驻）")
    if len(deep) > 60:
        print(f"  ⚠ 深层 {len(deep)} 条偏多（建议 ≤60），可用 --demote 把日常条目沉下去")
    return 0


def do_stats(root):
    w = read_window_days(root)
    items = collect_events(root)
    deep = sum(1 for i in items if tier_of(i, w) == "deep")
    shallow = len(items) - deep
    total = len(items)
    print(f"[目录 token 估算] 时间窗 {w} 天")
    print(f"  若全部常驻：{total} 条 ≈ {total * TOKEN_PER_ROW} token")
    print(f"  分层后常驻：{deep} 条 ≈ {deep * TOKEN_PER_ROW} token")
    if total:
        print(f"  ★ 节省：{shallow * TOKEN_PER_ROW} token（{round(100.0*shallow/total)}%）")
    return 0


def main():
    ap = argparse.ArgumentParser(description="深浅目录分层管理（v1.3 · R14）")
    ap.add_argument("--root", required=True, help="记忆根目录")
    ap.add_argument("--plan", action="store_true", help="显示分层方案")
    ap.add_argument("--stats", action="store_true", help="token 估算")
    ap.add_argument("--pin", metavar="SLUG", help="锁定在深层，永不下沉")
    ap.add_argument("--unpin", metavar="SLUG", help="解除锁定")
    ap.add_argument("--promote", metavar="SLUG", help="标为重要（浅层→深层）")
    ap.add_argument("--demote", metavar="SLUG", help="标为日常（立即下沉）")
    args = ap.parse_args()

    root = os.path.abspath(args.root)
    if not os.path.isdir(root):
        print(f"[error] 目录不存在: {root}")
        return 1

    changed = False
    for act, slug, key, val in (
        ("pin", args.pin, "pinned", "true"),
        ("promote", args.promote, "importance", "high"),
        ("demote", args.demote, "importance", "low"),
    ):
        if not slug:
            continue
        path, it = find_file(root, slug)
        if not path:
            print(f"  ✗ 找不到 slug 为「{slug}」的事件")
            return 1
        print(f"[{act}] {slug}")
        set_field(path, key, val)
        changed = True

    if args.unpin:
        path, it = find_file(root, args.unpin)
        if not path:
            print(f"  ✗ 找不到 slug 为「{args.unpin}」的事件")
            return 1
        print(f"[unpin] {args.unpin}")
        drop_field(path, "pinned")
        changed = True

    if changed:
        print(f"\n  → 跑 `memory_index.py --root \"{root}\" --rebuild` 让分层生效")
        return 0

    if args.stats:
        return do_stats(root)
    if args.plan or True:
        return do_plan(root)


if __name__ == "__main__":
    sys.exit(main())
