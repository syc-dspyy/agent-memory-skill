#!/usr/bin/env python3
"""三层记忆结构校验。

用法:
    python3 memory_check.py --root <root>

检查项:
    E1 孤岛事件   —— facts/events/ 中没有任何关联的事件（v1.x 起**不再判为 error**，降级为提示；孤立事件只要存在即可，不算缺陷）
    E2 单向边     —— links.md 中 A→B 写了但 B→A 没写
    E3 断链       —— 关联指向的文件不存在
    E4 index 一致 —— 深层 + 浅层 目录登记与实际事件文件一一对应（v1.3 双层；★比对文件名集合，
                    不只比行数——漏登记 / 指向已删文件 / 重复登记三种情形都能查出）
    E5 缺字段     —— 事件文件缺 date / summary / emotion
    E6 重复登记   —— 同一事件同时出现在深层和浅层目录（v1.3）
    M1 缺主记忆文件 —— main/ 缺 persona.md / rules.md / index.md
    M2 persona 缺段 —— persona.md 缺「主人档案 / 关系 / 身份识别」段
    W1 知识错写   —— 已绑定外部知识库，facts/knowledge/ 却有文件
    W2 隐私扫描   —— 正文命中手机号 / 邮箱 / 身份证号
    W3 明文口令   —— persona.md 疑似写了明文暗号（应存 hint + sha256）
    W4 规则缺失   —— rules.md 缺少某个 R 编号（R1–R15）
    W5 旧文件遗留 —— 存在 v1.0 的 main/boundaries.md 未迁移
    W6 锚点失效   —— 未注入常驻锚点，或目标文件里的锚点丢失（R13）
    W7 深层过长   —— 深层目录条数超过阈值，常驻 token 压力大（v1.3 R14）
    W8 字段漂移   —— 事件缺 v1.3 起要求的 retention / importance 字段
    W9 摘要重复   —— 两条及以上事件 summary 完全相同（疑似重复记忆）
    W10 失效窗异常 —— invalidated_by 指向不存在或时间逻辑错的事件

退出码: 0 = 通过（可能有 warning）；1 = 有 error
"""
import argparse
import os
import re
import sys

try:
    from memory_index import collect_events, parse_frontmatter, parse_date
except ImportError:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from memory_index import collect_events, parse_frontmatter, parse_date


def to_slug(name):
    """文件名 → slug：去掉日期前缀和 .md。"""
    base = name[:-3] if name.endswith(".md") else name
    return re.sub(r"^\d{8}-", "", base)

PII_PATTERNS = {
    "手机号": re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)"),
    "邮箱": re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"),
    "身份证号": re.compile(r"(?<!\d)\d{17}[\dXx](?!\d)"),
    "疑似密钥": re.compile(r"(sk-[A-Za-z0-9]{16,}|ghp_[A-Za-z0-9]{20,})"),
}

MAIN_REQUIRED = ["persona.md", "rules.md", "index.md"]
PERSONA_SECTIONS = ["关于我的主人", "我们之间的关系", "身份识别"]
RULE_IDS = [f"R{i}" for i in range(1, 16)]  # v1.x：R1–R15
DEEP_MAX_ROWS = 60  # 深层目录建议上限（超过则 W7，常驻 token 压力）
# 疑似明文口令：「暗号/口令/token: xxx」且 xxx 不是哈希、也不是占位提示
PLAIN_TOKEN = re.compile(r"(?:暗号|口令|token|Token)\s*[:：]\s*([^\s`|（）(]+)")

RELATIONS = {"caused_by", "led_to", "related", "involves", "same_topic", "temporal"}
# 互为反向的关系对（其余为对称关系，双向等价）
INVERSE = {
    "caused_by": {"led_to", "caused_by"},
    "led_to": {"caused_by", "led_to"},
    "related": {"related"},
    "involves": {"involves"},
    "same_topic": {"same_topic"},
    "temporal": {"temporal"},
}


def read_links(root):
    """解析 links.md 表格，返回边列表 [(src, rel, dst)]。"""
    path = os.path.join(root, "facts", "links.md")
    edges = []
    if not os.path.exists(path):
        return edges
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line.startswith("|") or "---" in line or "源事件" in line:
                continue
            cells = [c.strip() for c in line.strip("|").split("|")]
            if len(cells) < 3:
                continue
            src, rel, dst = cells[0], cells[1], cells[2]
            if rel in RELATIONS:
                edges.append((src, rel, dst))
    return edges


def slug_of(filename):
    return filename[:-3] if filename.endswith(".md") else filename


def resolve_node(node, slugs):
    """把 links.md 里的节点名解析成事件 slug。

    规范写法是 slug（文件名主体，如 gpu-upgrade），也接受「日期-slug」前缀写法
    （20261020-gpu-upgrade）。写中文标题无法自动解析，会判为断链——所以规范和
    报错信息都要求用 slug。
    """
    node = node.strip()
    if node in slugs:
        return node
    for s in slugs:
        if node.endswith("-" + s):
            return s
    return None


def parse_event_links(root):
    """解析事件文件末尾「关联」段里的链接，返回 [(来源 slug, 目标相对路径)]。

    事件内关联与 links.md 是同一张图的两个视图，断链检查必须同时覆盖两者，
    只在 links.md 上检查会漏掉"事件里写了、全局表里没有"的半截关联。
    """
    ev_dir = os.path.join(root, "facts", "events")
    out = []
    if not os.path.isdir(ev_dir):
        return out
    for fn in sorted(os.listdir(ev_dir)):
        if not fn.endswith(".md"):
            continue
        fm = parse_frontmatter(os.path.join(ev_dir, fn))
        src = fm.get("slug") or to_slug(fn)
        try:
            txt = open(os.path.join(ev_dir, fn), "r", encoding="utf-8").read()
        except OSError:
            continue
        m = re.search(r"^##\s*关联\s*$(.*?)(?=^##\s|\Z)", txt, re.M | re.S)
        if not m:
            continue
        for link in re.finditer(r"\[([^\]]*)\]\(([^)]+)\)", m.group(1)):
            out.append((src, link.group(2)))
    return out


def check_main_layer(root, errors, warnings, info):
    """主记忆层（L1）校验：三件套齐全、persona 四段、规则编号、明文口令。"""
    main_dir = os.path.join(root, "main")

    for fn in MAIN_REQUIRED:
        if not os.path.exists(os.path.join(main_dir, fn)):
            errors.append(f"M1 主记忆层缺文件 main/{fn}（跑 memory_init.py 补全）")

    persona_path = os.path.join(main_dir, "persona.md")
    if os.path.exists(persona_path):
        txt = open(persona_path, "r", encoding="utf-8").read()
        miss = [s for s in PERSONA_SECTIONS if s not in txt]
        if miss:
            errors.append(
                f"M2 persona.md 缺段：{'、'.join(miss)}"
                f"（v1.1 四段：我是谁 / 主人 / 关系 / 身份识别）"
            )
        else:
            info.append("M2 persona.md 四段齐全（含主人档案与身份识别）")
        for m in PLAIN_TOKEN.finditer(txt):
            val = m.group(1)
            if re.fullmatch(r"[0-9a-fA-F]{16,64}", val):  # 哈希，合规
                continue
            if val.startswith(("<", "（", "(", "见", "hint")):
                continue
            warnings.append(
                f"W3 疑似明文口令「{val}」：暗号应只存 hint + sha256[:16]，"
                f"不要写答案（rules.md R2.5）"
            )

    rules_path = os.path.join(main_dir, "rules.md")
    if os.path.exists(rules_path):
        txt = open(rules_path, "r", encoding="utf-8").read()
        miss = [r for r in RULE_IDS if not re.search(rf"{r}\b", txt)]
        if miss:
            warnings.append(f"W4 rules.md 缺规则编号：{', '.join(miss)}")

    if os.path.exists(os.path.join(main_dir, "boundaries.md")):
        warnings.append(
            "W5 发现旧文件 main/boundaries.md（v1.0）→ 加 --migrate 并入 rules.md 后删除"
        )


def _index_rows(path):
    """目录文件里的事件行数（以 | YYYY-MM-DD | 开头的表格行）。"""
    try:
        txt = open(path, "r", encoding="utf-8").read()
    except OSError:
        return 0
    return len(re.findall(r"^\|\s*\d{4}-\d{2}-\d{2}\s*\|", txt, re.M))


def _index_files(path):
    """目录文件里登记的事件文件名集合。"""
    try:
        txt = open(path, "r", encoding="utf-8").read()
    except OSError:
        return set()
    return set(re.findall(r"\.\./facts/events/([^)\s]+\.md)", txt))


def check_anchor(root, warnings, info):
    """W6 常驻锚点校验（R13）。

    锚点丢失 = 新会话忘记自己有记忆库 = 整套系统退化。所以这项必须每次 check 都扫。
    """
    cfg = os.path.join(root, ".memory-config.yaml")
    targets = []
    if os.path.exists(cfg):
        try:
            txt = open(cfg, "r", encoding="utf-8").read()
        except OSError:
            txt = ""
        m = re.search(r"^anchor_targets:\s*\n((?:[ \t]*-[^\n]*\n)*)", txt, re.M)
        if m:
            for line in m.group(1).splitlines():
                v = line.strip().lstrip("-").strip().strip('"').strip("'")
                if v:
                    targets.append(v)
    if not targets:
        warnings.append(
            "W6 未注入常驻锚点（R13）：新会话会忘记自己有记忆库 → "
            "python3 scripts/memory_anchor.py --root <root> --inject <AGENTS.md 或 CLAUDE.md>"
        )
        return
    bad = []
    for t in targets:
        if not os.path.exists(t):
            bad.append(f"{os.path.basename(t)}（目标文件不存在）")
            continue
        try:
            txt = open(t, "r", encoding="utf-8").read()
        except OSError:
            bad.append(f"{os.path.basename(t)}（无法读取）")
            continue
        if "<!-- MEMORY-ANCHOR:START" not in txt or "<!-- MEMORY-ANCHOR:END -->" not in txt:
            bad.append(f"{os.path.basename(t)}（锚点丢失）")
    if bad:
        warnings.append(f"W6 常驻锚点失效：{'; '.join(bad)} → 重新 --inject")
    else:
        info.append(f"W6 常驻锚点正常（{len(targets)} 个目标）")


def check(root):
    errors, warnings, info = [], [], []
    check_main_layer(root, errors, warnings, info)
    events_dir = os.path.join(root, "facts", "events")
    event_files = (
        sorted(f for f in os.listdir(events_dir) if f.endswith(".md"))
        if os.path.isdir(events_dir)
        else []
    )
    # E5 缺字段
    items = collect_events(root)
    for it in items:
        miss = [
            k
            for k in ("date", "summary", "emotion")
            if not it.get(k) or it[k] == "（缺 summary）"
        ]
        if miss:
            errors.append(f"E5 缺字段 {it['file']}：{', '.join(miss)}")

    # 权威标识是 frontmatter 的 slug 字段（不是文件名，文件名带日期前缀）
    slug_map = {it["slug"]: it["file"] for it in items}
    slugs = set(slug_map)

    # 两层目录路径（E3 拉链路检查与 E4 都要用，先算好）
    idx_path = os.path.join(root, "main", "index.md")
    shal_path = os.path.join(root, "main", "index-shallow.md")

    edges = read_links(root)
    ev_links = parse_event_links(root)

    # E1 孤岛（降级为提示，不再判 error）：孤立事件只要躺在记忆目录里即可，不算缺陷。
    # 尝试新事件产生孤岛是正常探索，不应因此否定新事件（见 linking-spec.md / rules.md R7.1）。
    linked = set()
    for src, _rel, dst in edges:
        for node in (src, dst):
            r = resolve_node(node, slugs)
            linked.add(r if r else node)
    for src, target in ev_links:
        linked.add(src)
        linked.add(to_slug(os.path.basename(target)))
    orphans = sorted(s for s in slugs if s not in linked)
    if orphans:
        info.append(
            f"E1 孤岛事件 {len(orphans)} 个（允许，非缺陷）：{', '.join(orphans)} "
            f"——孤立事件合法，探索性新事件无需强求关联"
        )

    # E2 单向边（按解析后的 slug 比较，兼容「日期-slug」写法）
    resolved = [(resolve_node(s, slugs) or s, r, resolve_node(d, slugs) or d) for s, r, d in edges]
    seen = {(s, d) for s, _r, d in resolved}
    one_way = []
    for s, r, d in resolved:
        if (d, s) not in seen:
            one_way.append(f"{s} -{r}-> {d}")
    if one_way:
        errors.append(f"E2 单向边 {len(one_way)} 条：{'; '.join(one_way[:5])}")

    # E3 断链（links.md 的边 + 事件内关联段的链接）
    broken = []
    for s, r, d in edges:
        for node in (s, d):
            if resolve_node(node, slugs):
                continue
            broken.append(f"{node}（links.md 里请写事件 slug，不是中文标题）")
    for src, target in ev_links:
        if target.startswith(("http://", "https://")):
            continue
        p = os.path.normpath(os.path.join(events_dir, target))
        if not os.path.exists(p):
            broken.append(f"{src} → {target}")
    # E3 补：目录「关联方法」列 —— method 指向 experience/ 下的文件，改名/挪走后会静默失效
    # （目录是 L1 唯一入口，这里的死链最容易被忽略）
    for idx_file in (idx_path, shal_path):
        if not os.path.exists(idx_file):
            continue
        try:
            txt = open(idx_file, "r", encoding="utf-8").read()
        except OSError:
            continue
        base = os.path.dirname(os.path.abspath(idx_file))  # main/
        for _label, target in re.findall(r"\[([^\]]*)\]\((\.\./[^)\s]+)\)", txt):
            if "/facts/events/" in target:  # 事件链接由上面漏登记/错位检查负责
                continue
            p = os.path.normpath(os.path.join(base, target))
            if not os.path.exists(p):
                broken.append(f"{os.path.basename(idx_file)} 关联方法 → {target}")
    if broken:
        errors.append(f"E3 断链节点 {len(set(broken))} 个：{', '.join(sorted(set(broken))[:5])}")

    # E4 index 一致（v1.3：深层 + 浅层两层合计）
    if os.path.exists(idx_path):
        deep_rows = _index_rows(idx_path)
        shallow_rows = _index_rows(shal_path)
        total = deep_rows + shallow_rows
        registered = _index_files(idx_path) | _index_files(shal_path)
        actual = set(event_files)
        missing = sorted(actual - registered)  # 写了文件却没进目录 → 以后检索不到
        ghost = sorted(registered - actual)    # 目录有行但文件没了 → 点了进去是死的
        if missing:
            errors.append(
                f"E4 漏登记 {len(missing)} 个事件没进任何一层目录：{', '.join(missing[:5])}"
                f"（不进目录 = 以后检索不到，等于没写；跑 memory_index.py --rebuild）"
            )
        if ghost:
            errors.append(
                f"E4 目录登记了 {len(ghost)} 个不存在的事件文件：{', '.join(ghost[:5])}"
                f"（文件已删 / 已改名，跑 memory_index.py --rebuild 清掉）"
            )
        if not missing and not ghost:
            info.append(
                f"E4 index 一致（深层 {deep_rows} + 浅层 {shallow_rows}，登记与实际一一对应）"
            )
            if total != len(event_files):
                errors.append(
                    f"E4 行数不符：目录 {total} 行 vs events/ {len(event_files)} 个文件"
                    f"（文件名都对得上，说明同一事件被重复登记了；跑 --rebuild 去重）"
                )
        # E6 重复登记（同一事件不能同时在两层）
        dup = _index_files(idx_path) & _index_files(shal_path)
        if dup:
            errors.append(
                f"E6 重复登记：{', '.join(sorted(dup)[:3])} 同时出现在深浅两层"
                f"（一件事情只能在一层，跑 --rebuild）"
            )
        # W7 深层过长
        if deep_rows > DEEP_MAX_ROWS:
            warnings.append(
                f"W7 深层目录 {deep_rows} 条 > {DEEP_MAX_ROWS} 建议上限：常驻 token 压力大 → "
                f"memory_tier.py --plan 看哪些能 --demote 到浅层"
            )
    else:
        errors.append("E4 找不到 main/index.md")

    # W8 字段漂移：v1.3 起事件应有 retention / importance 字段（缺则分层判据失效）
    drift = []
    for it in items:
        miss = [k for k in ("retention", "importance") if not it.get(k)]
        if miss:
            drift.append(f"{it['file']}(缺 {', '.join(miss)})")
    if drift:
        warnings.append(
            f"W8 字段漂移 {len(drift)} 个事件缺 retention/importance 字段："
            f"{', '.join(drift[:5])}（补上以启用分层与留存分级）"
        )

    # W9 摘要重复：两条及以上事件 summary 完全相同 → 疑似重复记忆
    by_summary = {}
    for it in items:
        s = (it.get("summary") or "").strip()
        if s and s != "（缺 summary）":
            by_summary.setdefault(s, []).append(it["slug"])
    dups = {s: v for s, v in by_summary.items() if len(v) > 1}
    if dups:
        warnings.append(
            "W9 摘要重复 "
            + "；".join(f"「{s[:14]}…」{v}" for s, v in list(dups.items())[:3])
            + "（疑似重复记忆，按 R5.9 写入前三判处理）"
        )

    # W10 失效窗异常：invalidated_by 指向不存在 / 时间逻辑错的事件
    invalid = []
    for it in items:
        ib = (it.get("invalidated_by") or "").strip()
        if not ib:
            continue
        if ib not in slugs:
            invalid.append(f"{it['slug']}→{ib}(不存在)")
            continue
        d_self = parse_date(it.get("date", ""))
        tgt_item = next((x for x in items if x["slug"] == ib), None)
        d_target = parse_date(tgt_item.get("date", "")) if tgt_item else None
        if d_self and d_target and d_target < d_self:
            invalid.append(f"{it['slug']}→{ib}(推翻事件比被推翻的还早)")
    if invalid:
        warnings.append(
            f"W10 失效窗异常 {len(invalid)} 处：{', '.join(invalid[:5])}"
            f"（invalidated_by 应指向更新的、确实推翻了本事件的条目）"
        )

    # W1 知识错写
    cfg = os.path.join(root, ".memory-config.yaml")
    kb_bound = False
    if os.path.exists(cfg):
        txt = open(cfg, "r", encoding="utf-8").read()
        m = re.search(r'knowledge_base:\s*"?([^"\n]*)"?', txt)
        kb_bound = bool(m and m.group(1).strip())
    kn_dir = os.path.join(root, "facts", "knowledge")
    kn_files = (
        sorted(f for f in os.listdir(kn_dir) if f.endswith(".md"))
        if os.path.isdir(kn_dir)
        else []
    )
    if kb_bound and kn_files:
        warnings.append(
            f"W1 已绑定知识库却有 {len(kn_files)} 篇知识写在 facts/knowledge/："
            f"{', '.join(kn_files[:3])}"
        )

    # W2 隐私扫描
    scan_dirs = ["main", "experience", "facts"]
    hits = {}
    for d in scan_dirs:
        base = os.path.join(root, d)
        for dirpath, _dn, filenames in os.walk(base):
            for fn in filenames:
                if not fn.endswith(".md"):
                    continue
                p = os.path.join(dirpath, fn)
                try:
                    txt = open(p, "r", encoding="utf-8").read()
                except OSError:
                    continue
                for label, pat in PII_PATTERNS.items():
                    if pat.search(txt):
                        hits.setdefault(label, []).append(os.path.relpath(p, root))
    for label, files in hits.items():
        warnings.append(f"W2 疑似{label}：{', '.join(files[:3])}")

    # W6 常驻锚点（R13）
    check_anchor(root, warnings, info)

    return errors, warnings, info, len(event_files), len(edges)


def main():
    ap = argparse.ArgumentParser(description="三层记忆结构校验")
    ap.add_argument("--root", required=True, help="记忆根目录")
    args = ap.parse_args()
    root = os.path.abspath(args.root)

    if not os.path.isdir(root):
        print(f"[error] 目录不存在: {root}")
        return 1

    errors, warnings, info, n_ev, n_edge = check(root)

    print(f"[memory_check] {root}")
    print(f"  事件 {n_ev} 个 / 关联边 {n_edge} 条")
    for i in info:
        print(f"  ✓ {i}")
    for w in warnings:
        print(f"  ⚠ {w}")
    for e in errors:
        print(f"  ✗ {e}")

    if errors:
        print(f"\n结果：{len(errors)} 个 error，{len(warnings)} 个 warning → 未通过")
        return 1
    print(f"\n结果：0 error，{len(warnings)} 个 warning → 通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
