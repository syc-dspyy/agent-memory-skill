#!/usr/bin/env python3
"""常驻锚点：把记忆库指针注入 AI 每次会话必然加载的文件（v1.2 · R13）。

解决的问题
-----------
上下文一清空、新开会话，AI 如果不知道自己有记忆库，就永远不会去读
main/rules.md —— 整套记忆系统瞬间退化为无记忆。锚点让「我有记忆库」
这件事本身常驻在 AI 的启动上下文里。

用法
----
    # 打印锚点内容（不落盘）
    python3 memory_anchor.py --root "D:/memory" --print

    # 注入到常驻文件（幂等：重复执行只替换，不重复插入）
    python3 memory_anchor.py --root "D:/memory" --inject "D:/项目/AGENTS.md"
    python3 memory_anchor.py --root "D:/memory" --inject "D:/项目/CLAUDE.md"

    # 校验
    python3 memory_anchor.py --root "D:/memory" --check "D:/项目/AGENTS.md"
    python3 memory_anchor.py --root "D:/memory" --check-all   # 校验配置里记录的全部目标

    # 移除
    python3 memory_anchor.py --remove "D:/项目/AGENTS.md"

推荐注入目标
------------
AGENTS.md / CLAUDE.md / 工作区 MEMORY.md / .cursorrules / .windsurfrules
—— 选你当前这个 agent 每次会话都会自动加载的那个。

锚点只写「路径 + 必读时机 + 必写时机」，不写记忆内容本身（R13.4 防泄露）。
"""
import argparse
import os
import re
import sys
from datetime import date

START = "<!-- MEMORY-ANCHOR:START"
END = "<!-- MEMORY-ANCHOR:END -->"

TPL_DIR = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets", "templates")
)

ANCHOR_FALLBACK = """<!-- MEMORY-ANCHOR:START · 由 agent-memory-skill 生成 · 勿删此标记 -->
## 🧠 我的记忆库（三层长期记忆）

我有一套长期记忆系统，根目录：`{root}`

**每次会话开始，我必须自动读取（不用主人提醒）：**
- `{root}/main/persona.md` — 我是谁 / 我的主人是谁 / 我们的关系 / 怎么认出主人
- `{root}/main/rules.md` — 我的规范规则 R1–R13（何时存、怎么存、怎么读）
- `{root}/main/index.md` — 记忆目录（找历史事件先查这里）

**出现这些信号，我必须自动保存（不用主人说"记住"）：**
主人透露偏好或忌讳 · 纠正我 · 做出决策 · 有情绪波动 · 教我方法 · 同一问题问到第 3 次 · 学到新知识 · 提到人物关系 · 踩坑失败 · 会话收尾前盘点补漏

**出现这些信号，我必须自动检索（不用主人说"去查"）：**
主人提到"上次/之前/那次" · 出现人名或项目名 · 问我是谁或我们什么关系 · 遇到同类任务 · 要我做决策或给建议 · 当前情境与历史相似（主动联想提醒）

**铁律：** 先认主人再看权限 · 记忆真相只在 Markdown · 目录找不到才动向量检索 · 找不到就说没找到。

<!-- MEMORY-ANCHOR:END -->
"""


def build_anchor(root, name=""):
    """从模板生成锚点文本，模板缺失则用内置简版。"""
    path = os.path.join(TPL_DIR, "memory-anchor.md")
    try:
        with open(path, "r", encoding="utf-8") as f:
            tpl = f.read()
    except OSError:
        tpl = ANCHOR_FALLBACK
    return tpl.format(root=root.rstrip("/\\"), name=name or "").rstrip() + "\n"


def read_text(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def write_text(path, txt):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(txt)


def block_span(txt):
    """返回锚点块 (start_idx, end_idx)，不存在返回 None。"""
    s = txt.find(START)
    e = txt.find(END)
    if s == -1 or e == -1 or e < s:
        return None
    return s, e + len(END)


def do_inject(target, anchor, verbose=True):
    target = os.path.abspath(target)
    existed = os.path.exists(target)
    txt = read_text(target) if existed else ""
    span = block_span(txt)
    if span:
        s, e = span
        new = txt[:s] + anchor.rstrip() + txt[e:]
        action = "更新"
    else:
        sep = "\n\n" if txt.strip() else ""
        new = txt.rstrip() + sep + anchor
        action = "注入"
    write_text(target, new)
    if verbose:
        print(f"  ✓ 锚点已{action}：{target}" + ("" if existed else "（文件新建）"))
    return target


def do_check(target, root, verbose=True):
    target = os.path.abspath(target)
    if not os.path.exists(target):
        if verbose:
            print(f"  ✗ 目标文件不存在：{target}")
        return "missing_file"
    txt = read_text(target)
    span = block_span(txt)
    if not span:
        if verbose:
            print(f"  ✗ 锚点缺失：{target}  ← 我会忘记自己有记忆库，请 --inject")
        return "missing_anchor"
    block = txt[span[0]:span[1]]
    if root and root.rstrip("/\\") not in block:
        if verbose:
            print(f"  ⚠ 锚点存在但路径不符（锚点内不含 {root}）：{target}")
        return "path_mismatch"
    if verbose:
        print(f"  ✓ 锚点正常：{target}")
    return "ok"


def do_remove(target, verbose=True):
    target = os.path.abspath(target)
    if not os.path.exists(target):
        if verbose:
            print(f"  = 文件不存在，无需移除：{target}")
        return False
    txt = read_text(target)
    span = block_span(txt)
    if not span:
        if verbose:
            print(f"  = 无锚点，无需移除：{target}")
        return False
    s, e = span
    new = (txt[:s] + txt[e:]).replace("\n\n\n\n", "\n\n").rstrip() + "\n"
    write_text(target, new)
    if verbose:
        print(f"  ✓ 锚点已移除：{target}")
    return True


# ---- .memory-config.yaml 里的 anchor_targets 维护 ----
def cfg_path(root):
    return os.path.join(root, ".memory-config.yaml")


def read_targets(root):
    p = cfg_path(root)
    if not os.path.exists(p):
        return []
    txt = read_text(p)
    m = re.search(r"^anchor_targets:\s*\n((?:[ \t]*-[^\n]*\n)*)", txt, re.M)
    if not m:
        return []
    out = []
    for line in m.group(1).splitlines():
        v = line.strip().lstrip("-").strip().strip('"').strip("'")
        if v:
            out.append(v)
    return out


def add_target(root, target):
    p = cfg_path(root)
    if not os.path.exists(p):
        return False
    txt = read_text(p)
    if target in read_targets(root):
        return False
    if re.search(r"^anchor_targets:", txt, re.M):
        txt = re.sub(
            r"^anchor_targets:[ \t]*\n",
            lambda m: m.group(0) + '  - "%s"\n' % target,
            txt,
            count=1,
            flags=re.M,
        )
    else:
        txt = txt.rstrip() + "\n\n# 常驻锚点注入目标（memory_anchor.py 维护，R13）\nanchor_targets:\n"
        txt += '  - "%s"\n' % target
    write_text(p, txt)
    return True


def main():
    ap = argparse.ArgumentParser(description="常驻锚点管理（v1.2 · R13）")
    ap.add_argument("--root", default="", help="记忆根目录")
    ap.add_argument("--name", default="", help="agent 名字（可选）")
    ap.add_argument("--inject", metavar="FILE", help="把锚点注入目标文件（幂等）")
    ap.add_argument("--check", metavar="FILE", help="校验目标文件里的锚点")
    ap.add_argument("--check-all", action="store_true", help="校验配置中记录的全部目标")
    ap.add_argument("--remove", metavar="FILE", help="从目标文件移除锚点")
    ap.add_argument("--print", dest="do_print", action="store_true", help="只打印锚点内容")
    args = ap.parse_args()

    if not any([args.inject, args.check, args.check_all, args.remove, args.do_print]):
        ap.error("至少指定一个动作：--inject / --check / --check-all / --remove / --print")

    if args.do_print:
        if not args.root:
            ap.error("--print 需要 --root")
        print(build_anchor(args.root, args.name))
        if not (args.inject or args.check or args.check_all or args.remove):
            return 0

    root = os.path.abspath(args.root) if args.root else ""

    if args.inject:
        if not root:
            ap.error("--inject 需要 --root")
        anchor = build_anchor(root, args.name)
        do_inject(args.inject, anchor)
        if add_target(root, os.path.abspath(args.inject)):
            print(f"  + 已记入 .memory-config.yaml → anchor_targets")
        # 注入后立刻自检
        print("  → 自检：", end="")
        do_check(args.inject, root, verbose=True)

    if args.check:
        rc = do_check(args.check, root)
        if rc != "ok":
            print("    修复：python3 memory_anchor.py --root \"%s\" --inject \"%s\""
                  % (root or "<记忆根目录>", os.path.abspath(args.check)))
            return 1

    if args.check_all:
        if not root:
            ap.error("--check-all 需要 --root")
        targets = read_targets(root)
        if not targets:
            print("  ⚠ 配置中没有记录任何 anchor_targets，先 --inject 一个")
            return 1
        bad = 0
        for t in targets:
            if do_check(t, root) != "ok":
                bad += 1
        if bad:
            print(f"  ✗ {bad}/{len(targets)} 个锚点有问题")
            return 1
        print(f"  ✓ {len(targets)}/{len(targets)} 个锚点正常")

    if args.remove:
        do_remove(args.remove)

    return 0


if __name__ == "__main__":
    sys.exit(main())
