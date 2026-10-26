#!/usr/bin/env python3
"""记忆目录维护与重建（v1.3 · 深浅双层目录）。

★ v1.3 分层设计（省 token 的关键）
---------------------------------
深层 main/index.md          近期 + 重要事件 —— **每次会话常驻必读**
浅层 main/index-shallow.md  久远 + 日常事件 —— **按需读取**，不占常驻上下文

新事件默认进深层；深层积累到一定量后，久远且不重要的条目下沉到浅层。
★ 事件文件本身不移动，只是"目录行"归到哪一层 —— 所以 links.md 完全不受影响。

用法
----
    python3 memory_index.py --root <root> --rebuild    # 重建两层目录
    python3 memory_index.py --root <root> --check      # 只检查一致性，不写
    python3 memory_index.py --root <root> --stats      # 分层统计与 token 估算

分层判据（满足任一 → 深层）
--------------------------
    1. frontmatter `pinned: true`    手动锁定，永不下沉
    2. `importance: high`            重要事件
    3. 事件日期在 `deep_window_days` 内（默认 90 天，见 .memory-config.yaml）
其余归入浅层。
"""
import argparse
import os
import re
import sys
from datetime import date, datetime

AUTO_START = "<!-- AUTO:events -->"
AUTO_END = "<!-- /AUTO:events -->"

# 浅层目录模板（memory_init.py 也从这里取，保持唯一真相）
SHALLOW_INDEX = """# 浅层记忆目录（久远 / 日常事件）

> 最后更新：{today}
> 【定位】装**久远且不重要**的事件摘要。日常回忆**不读本文件**，只在深层找不到、
> 且问题涉及久远小事时才来查——这是给常驻上下文瘦身用的（R14）。
> 【与深层的关系】事件文件仍在 `facts/events/`，只有目录行在这里；
> 一件事要么在深层、要么在浅层，不会重复登记。
> 本文件由 `facts/events/` 反向生成，可用 `memory_index.py --rebuild` 重建。
> 想让某条回到深层：`memory_tier.py --root <root> --pin <slug>` 或 `--promote <slug>`

<!-- AUTO:events -->
| 日期 | 事件 | 一句话摘要 | 情绪 | 关联方法 | 文件 |
|---|---|---|---|---|---|
<!-- 暂无事件。事件超出深层时间窗且非重要后会自动归入此处 -->
<!-- /AUTO:events -->
"""

# 每行目录摘要的大致 token 数（用于估算常驻开销，经验值）
TOKEN_PER_ROW = 30


def parse_frontmatter(path):
    """解析 YAML frontmatter（极简实现，只取 key: value 一级字段）。"""
    data = {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
    except OSError:
        return data
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.S)
    if not m:
        return data
    for line in m.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            data[k.strip()] = v.strip().strip("\"'")
    # 标题取第一个 # 行
    h = re.search(r"^#\s+(.+)$", text[m.end():], re.M)
    if h:
        data["_title"] = h.group(1).strip()
    return data


def parse_date(s):
    """'2026-10-25' → date；解析失败返回 None（视为久远，归浅层）。"""
    try:
        return datetime.strptime(str(s).strip()[:10], "%Y-%m-%d").date()
    except Exception:
        return None


def read_window_days(root):
    """读 .memory-config.yaml 的 deep_window_days，默认 90。"""
    cfg = os.path.join(root, ".memory-config.yaml")
    if os.path.exists(cfg):
        try:
            txt = open(cfg, "r", encoding="utf-8").read()
        except OSError:
            return 90
        m = re.search(r"deep_window_days:\s*(\d+)", txt)
        if m:
            return int(m.group(1))
    return 90


def is_true(v):
    return str(v).strip().lower() in ("true", "yes", "1")


def tier_of(item, window_days):
    """判定事件属于 deep 还是 shallow。见模块 docstring 三条判据。"""
    if is_true(item.get("pinned", "")):
        return "deep"
    if str(item.get("importance", "")).strip().lower() == "high":
        return "deep"
    d = parse_date(item.get("date", ""))
    if d is None:
        return "shallow"
    return "deep" if (date.today() - d).days <= window_days else "shallow"


def collect_events(root):
    ev_dir = os.path.join(root, "facts", "events")
    if not os.path.isdir(ev_dir):
        return []
    items = []
    for name in sorted(os.listdir(ev_dir)):
        if not name.endswith(".md"):
            continue
        fm = parse_frontmatter(os.path.join(ev_dir, name))
        items.append(
            {
                "file": name,
                "slug": fm.get("slug") or re.sub(r"^\d{8}-", "", name[:-3]),
                "date": fm.get("date", ""),
                "title": fm.get("_title", name[:-3]),
                "summary": fm.get("summary", "（缺 summary）"),
                "emotion": fm.get("emotion", ""),
                "method": fm.get("method", ""),
                "importance": fm.get("importance", ""),
                "pinned": fm.get("pinned", ""),
            }
        )
    items.sort(key=lambda x: x["date"], reverse=True)
    return items


def build_table(items, empty_hint="<!-- 暂无事件 -->"):
    lines = [
        "| 日期 | 事件 | 一句话摘要 | 情绪 | 关联方法 | 文件 |",
        "|---|---|---|---|---|---|",
    ]
    if not items:
        lines.append(empty_hint)
    for it in items:
        raw = it["method"].strip()
        if raw:
            link = raw if raw.endswith(".md") else raw + ".md"
            method = f"[{raw}](../experience/methodology/{link})"
        else:
            method = "—"
        lines.append(
            f"| {it['date']} | {it['title']} | {it['summary']} | {it['emotion']} "
            f"| {method} | [详情](../facts/events/{it['file']}) |"
        )
    return "\n".join(lines)


def write_block(path, table, today):
    """把事件表写入文件的 AUTO 区块；文件不存在则先建。"""
    if not os.path.exists(path):
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(SHALLOW_INDEX.format(today=today))
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    block = AUTO_START + "\n" + table + "\n" + AUTO_END
    if AUTO_START in content and AUTO_END in content:
        pattern = re.compile(re.escape(AUTO_START) + r".*?" + re.escape(AUTO_END), re.S)
        new_content = pattern.sub(lambda _: block, content)
    else:
        new_content = content.rstrip() + "\n\n" + block + "\n"
    new_content = re.sub(r"> 最后更新：[\d-]+", f"> 最后更新：{today}", new_content)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(new_content)


def rebuild(root, dry=False, stats=False):
    idx_path = os.path.join(root, "main", "index.md")
    if not os.path.exists(idx_path):
        print(f"[error] 找不到 {idx_path}")
        return 1

    today = date.today().isoformat()
    items = collect_events(root)
    w = read_window_days(root)
    deep = [i for i in items if tier_of(i, w) == "deep"]
    shallow = [i for i in items if tier_of(i, w) == "shallow"]

    if stats:
        total = len(items)
        print(f"[分层统计] {root}")
        print(f"  深层时间窗：{w} 天 / 事件总数 {total}")
        print(f"  深层 index.md         : {len(deep)} 条 → 常驻约 {len(deep) * TOKEN_PER_ROW} token")
        print(f"  浅层 index-shallow.md : {len(shallow)} 条 → 按需约 {len(shallow) * TOKEN_PER_ROW} token")
        if total:
            print(f"  ★ 相比全部常驻，节省约 {round(100.0 * len(shallow) / total)}% 的目录 token")
        for i in shallow[:5]:
            print(f"    · 浅层：{i['date']} {i['summary']}")
        if len(shallow) > 5:
            print(f"    · ……另 {len(shallow) - 5} 条")
        return 0

    if dry:
        print("[check] 事件文件数:", len(items))
        rows = len(deep) + len(shallow)
        print(f"[check] 分层后行数: 深层 {len(deep)} + 浅层 {len(shallow)} = {rows}")
        print("[check] 一致" if rows == len(items) else "[check] 不一致！")
        return 0

    write_block(
        idx_path,
        build_table(deep, "<!-- 暂无事件。写事件后运行 memory_index.py --rebuild 自动生成 -->"),
        today,
    )
    shal_path = os.path.join(root, "main", "index-shallow.md")
    write_block(
        shal_path,
        build_table(shallow, "<!-- 暂无事件。事件超出深层时间窗且非重要后会自动归入此处 -->"),
        today,
    )

    print(f"[rebuild] 深层 {len(deep)} 条 → main/index.md")
    print(f"[rebuild] 浅层 {len(shallow)} 条 → main/index-shallow.md")
    missing = [i["file"] for i in items if i["summary"] == "（缺 summary）"]
    if missing:
        print("[warn] 以下事件缺 summary 字段，请补 frontmatter：")
        for m in missing:
            print("  -", m)
    return 0


def main():
    ap = argparse.ArgumentParser(description="记忆目录索引维护（v1.3 深浅双层）")
    ap.add_argument("--root", required=True, help="记忆根目录")
    ap.add_argument("--rebuild", action="store_true", help="重建两层目录")
    ap.add_argument("--check", action="store_true", help="只检查一致性")
    ap.add_argument("--stats", action="store_true", help="分层统计与 token 估算")
    args = ap.parse_args()

    root = os.path.abspath(args.root)
    if not (args.rebuild or args.check or args.stats):
        ap.print_help()
        return 1
    return rebuild(root, dry=args.check, stats=args.stats)


if __name__ == "__main__":
    sys.exit(main())
