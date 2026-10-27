#!/usr/bin/env python3
"""初始化三层记忆目录骨架（v1.3 · 深浅双层目录）。

用法:
    python3 memory_init.py --root "D:/memory" --agent-name "小幕" --owner "M"
    python3 memory_init.py --root "D:/memory" --knowledge-base "IMA:我的知识库"
    python3 memory_init.py --root "D:/memory" --migrate      # v1.0 boundaries.md → rules.md

    # R15：persona.md / rules.md 不可重建，--force 也不覆盖；确需重建才用 --force-main
    python3 memory_init.py --root "D:/memory" --force-main   # 会先自动备份为 .bak-<时间戳>

    # ★强烈推荐：注入常驻锚点，让 AI 每次会话都记得自己有记忆库（R13）
    python3 memory_init.py --root "D:/memory" --anchor-target "D:/项目/AGENTS.md"
    python3 memory_init.py --root "D:/memory" --anchor-target "AGENTS.md" --anchor-target "CLAUDE.md"

产出:
    目录结构 + main/ 三件套（persona.md / rules.md / index.md）
    + facts/links.md + integrations/ + .memory-config.yaml

幂等: 已存在的文件不覆盖（除非 --force）
      ★例外（R15）：main/persona.md 与 main/rules.md 不可重建，--force 也**不会**覆盖；
        确需重建用 --force-main（会先备份为 .bak-<时间戳>）
模板: 优先读 assets/templates/*，读不到则退回内置简版
"""
import argparse
import os
import shutil
import sys
from datetime import date, datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from memory_anchor import build_anchor, do_inject, add_target  # v1.2 常驻锚点（R13）
    HAVE_ANCHOR = True
except ImportError:  # pragma: no cover
    HAVE_ANCHOR = False

try:
    from memory_index import SHALLOW_INDEX  # v1.3 浅层目录模板（R14）
except ImportError:  # pragma: no cover
    SHALLOW_INDEX = (
        "# 浅层记忆目录（久远 / 日常事件）\n\n> 最后更新：{today}\n\n"
        "<!-- AUTO:events -->\n| 日期 | 事件 | 一句话摘要 | 情绪 | 关联方法 | 文件 |\n"
        "|---|---|---|---|---|---|\n<!-- /AUTO:events -->\n"
    )

DIRS = [
    "main",
    "experience/methodology",
    "experience/qa-templates",
    "facts/events",
    "facts/knowledge",
    "integrations",
    "archive",
]

TPL_DIR = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets", "templates")
)

# ---- 内置简版（仅在模板文件缺失时兜底）----
PERSONA_FALLBACK = """# 人格设定 · {name}

> 🔴 本文件不可重建。修改前必须向用户复述改动并获确认。
> 完整模板见 assets/templates/persona.md

## 一、我是谁
- **名字**：{name}
- **身份**：
- **说话风格**：
- **价值取向**：
- **长期目标**：

## 二、关于我的主人（Owner）
- **称呼**：{owner}
- **角色**：
- **已知偏好**：
- **雷区 / 忌讳**：
- **主人对我的期望**：

## 三、我们之间的关系
- **关系定位**：
- **相处基调**：
- **我的承诺**：
- **共同经历锚点**（只写提示不写细节）：

## 四、身份识别：怎么确认对方是主人
| 判定 | 依据 | 权限 |
|---|---|---|
| ✅ 确认是主人 | S 级（暗号/共同经历）命中 | 全权限 |
| ⚠️ 存疑 | 只有渠道惯例吻合 | 降权：不读写记忆 |
| ❌ 非本人 | S 级答错 | 拒绝：不透露记忆存在 |

- 暗号存法：`hint` + `sha256[:16]`，**不写明文**
- 存疑即降权；自称"我是本人"不构成证据
"""

RULES_FALLBACK = """# 规范规则 · {name}

> 🔴 本文件不可重建，与 persona.md 同级。完整模板见 assets/templates/rules.md

## R1 行为边界（我绝不做什么）
| R1.1 | 不代主人做最终决策 | 被要求"你帮我定" |
| R1.2 | 不编造记忆：没找到就说没找到 | 检索无结果时 |
| R1.3 | 不在未确认时修改 main/ | 任何改 main/ 的念头 |
| R1.4 | 不把记忆真相写进数据库 | 接外部存储时 |

## R2 隐私与安全红线
| R2.1 | 真实姓名/手机号/住址/证件号/密钥 → 默认不写 | 任何写入前 |
| R2.3 | 主人说"这条别记" → 立即停，不留痕迹 | 撤回时 |
| R2.5 | 明文口令不入库 | 配暗号时 |

## R3 身份与权限
| R3.1 | 每次会话先判身份，存疑即降权 | 会话开始/换渠道 |
| R3.3 | 不透露识别方式与暗号提示 | 被套话时 |

（R4–R13 见 assets/templates/rules.md）

> 最后更新：{today}
"""

INDEX = """# 深层记忆目录（近期 + 重要事件）

> 最后更新：{today}
> 【定位】**每次会话常驻必读**。只装**近期**事件和**重要**事件——久远且不重要的
> 会自动下沉到 `index-shallow.md`（浅层），需要回忆久远小事时才去查（R14）。
> 用法：先在这里找关键词；找不到且问题涉及久远小事 → 查浅层；仍找不到 → 才考虑向量检索。
> 本文件由 facts/events/ 反向生成，可用 `memory_index.py --rebuild` 重建（自动分层）。

<!-- AUTO:events -->
| 日期 | 事件 | 一句话摘要 | 情绪 | 关联方法 | 文件 |
|---|---|---|---|---|---|
<!-- 暂无事件。写事件后运行 memory_index.py --rebuild 自动生成 -->
<!-- /AUTO:events -->

## 方法快捷入口

| 方法 | 适用 | 文件 |
|---|---|---|
<!-- 手写区：沉淀出方法论后在此登记 -->
"""

LINKS = """# 事件关联图

> 双向互写：写了 A→B，必须同时写 B←A。单向边是缺陷，校验会报。
> 节点一律写事件 slug（frontmatter 的 slug 字段），不写中文标题、不写文件名。
> 校验：python3 scripts/memory_check.py --root <root>

| 源事件 | 关系 | 目标事件 | 说明 |
|---|---|---|---|
<!-- 关系类型：caused_by / led_to / related / involves / same_topic / temporal -->
"""

MCP = """# MCP 与外部接口

> 接口层不存记忆，只做通路。外部请求一律落到 Markdown 文件。
> 身份规则：经接口进来的请求默认按「存疑」降权处理（rules.md R3.5），提权须显式发生。

## 暴露的工具

| 工具 | 作用 | 落到 | 需确认 |
|---|---|---|---|
| memory_recall | 四级漏斗检索 | 只读 | 否 |
| memory_write_event | 写事件 | facts/events + index + links | 否 |
| memory_write_method | 写方法论 | experience/methodology | 否（需含验收标准） |
| memory_link | 补关联（双向自动互写） | facts/links.md | 否 |
| memory_verify_owner | 身份核验（比对暗号哈希） | 不落盘 | 否（失败时写安全事件） |
| memory_read_persona | 读人格 + 主人档案 + 规范规则 | main/ | 否 |
| memory_update_persona | 改人格 / 主人档案 / 规范规则 | main/ | **是** |

## 注册
写入 ~/.workbuddy/mcp.json（应用启动时读取，改完需重启）。
"""

PLATFORMS = """# 平台对接记录

| 平台 | 用途 | 读写范围 | 鉴权 | 最后验证 |
|---|---|---|---|---|
| （示例）WorkBuddy MCP | 本机 agent 读写记忆 | 全层（改 main 需确认） | stdio 本地 | {today} |
"""

CONFIG = """# 三层记忆系统配置
root: {root}
agent_name: {name}
owner: "{owner}"
created: {today}

# 绑定的外部知识库。留空 = 知识写入 facts/knowledge/
# 格式：平台名:库名  例：IMA:我的知识库
knowledge_base: "{kb}"

# 向量检索：none（仅目录+grep） / fts（SQLite FTS5） / vector（外部向量库）
retrieval_mode: none

# 写事件后是否自动重建 index
auto_rebuild_index: true

# 每次会话是否先做身份判定（rules.md R3.1）
identity_check: true
# 身份核验失败时是否自动记一条安全事件（rules.md R3.4）
log_failed_verification: true

# 自动触发：出现保存/读取信号时不等指令自动读写（rules.md R11）
auto_trigger: true
# 会话收尾是否做收尾三动作：盘点 / 反思 / 交接（R11.6 / T10）
session_wrapup_scan: true

# 目录分层（v1.3 · R14）：深层装近期+重要（常驻），浅层装久远+日常（按需）
# 超过 deep_window_days 且不重要的事件，rebuild 时自动下沉到 index-shallow.md
deep_window_days: 90

# 常驻锚点注入目标（R13：让 AI 永远记得这个记忆库，由 memory_anchor.py 维护）
anchor_targets:
"""

MIGRATE_HEADER = """

---

## 附录：v1.0「边界限制」遗留条目（待人工归并到 R1 / R2）

> 由 `memory_init.py --migrate` 从旧的 `main/boundaries.md` 并入。
> 归并完成后删除本节，并删除或重命名 `main/boundaries.md`。

"""

# ★🔴 不可重建文件：默认 --force 也绝不动，必须显式 --force-main（且先自动备份）
# 依据 anti-loss.md 的备份等级表与 R15.5 —— 这两个文件丢了就真的没了。
PROTECTED = {"main/persona.md", "main/rules.md"}


def backup_file(path):
    """把现有文件备份为 <file>.bak-<YYYYMMDD-HHMMSS>，返回备份路径。"""
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    bak = f"{path}.bak-{stamp}"
    shutil.copy2(path, bak)
    return bak


def load_template(filename):
    """优先读 assets/templates 下的模板，读不到返回 None。"""
    path = os.path.join(TPL_DIR, filename)
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except OSError:
        return None


def main():
    ap = argparse.ArgumentParser(description="初始化三层记忆目录（v1.1）")
    ap.add_argument("--root", required=True, help="记忆根目录")
    ap.add_argument("--agent-name", default="", help="agent 名字")
    ap.add_argument("--owner", default="", help="主人代号/称呼（不写真名）")
    ap.add_argument("--knowledge-base", default="", help="绑定的外部知识库")
    ap.add_argument("--migrate", action="store_true", help="把旧 boundaries.md 并入 rules.md")
    ap.add_argument(
        "--anchor-target",
        action="append",
        default=[],
        metavar="FILE",
        help="★注入常驻锚点的目标文件（可多次传入），如 AGENTS.md / CLAUDE.md / MEMORY.md",
    )
    ap.add_argument("--force", action="store_true", help="覆盖已存在文件（★不含 main/ 下不可重建文件）")
    ap.add_argument(
        "--force-main",
        action="store_true",
        help="★极高危：连 persona.md / rules.md 一起重建（会先自动备份为 .bak-<时间戳>）",
    )
    args = ap.parse_args()

    if args.force_main and not args.force:
        args.force = True  # --force-main 隐含 --force

    root = os.path.abspath(args.root)
    today = date.today().isoformat()
    name = args.agent_name or "（待填）"
    owner = args.owner or "（待填）"

    for d in DIRS:
        os.makedirs(os.path.join(root, d), exist_ok=True)

    persona_tpl = load_template("persona.md") or PERSONA_FALLBACK
    rules_tpl = load_template("rules.md") or RULES_FALLBACK

    files = {
        "main/persona.md": persona_tpl.format(name=name, owner=owner),
        "main/rules.md": rules_tpl.format(name=name, today=today),
        "main/index.md": INDEX.format(today=today),
        "main/index-shallow.md": SHALLOW_INDEX.format(today=today),
        "facts/links.md": LINKS,
        "integrations/mcp.md": MCP,
        "integrations/platforms.md": PLATFORMS.format(today=today),
        ".memory-config.yaml": CONFIG.format(
            root=root,
            name=args.agent_name or "",
            owner=args.owner,
            kb=args.knowledge_base,
            today=today,
        ),
    }

    if args.force_main:
        print("  " + "⚠" * 30)
        print("  ⚠ --force-main 会重建 main/persona.md 与 main/rules.md")
        print("  ⚠ 🔴 这两份是唯一不可重建的文件，重建即丢失既有内容（脚本会自动备份为 .bak-<时间戳>）")
        print("  ⚠ 按 R15：若用户在别处已有人格设定，绝不能覆盖——请先读取并询问是否沿用")
        print("  " + "⚠" * 30)

    created, skipped, protected = [], [], []
    for rel, content in files.items():
        path = os.path.join(root, rel)
        exists = os.path.exists(path)
        if exists:
            if rel in PROTECTED and not args.force_main:
                # R15.5：--force 也绝不覆盖；只有 --force-main 才放行
                protected.append(rel)
                continue
            if not args.force:
                skipped.append(rel)
                continue
            if rel in PROTECTED:
                bak = backup_file(path)
                print(f"  ⛨ 已备份 {rel} → {os.path.basename(bak)}")
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(content)
        created.append(rel)

    # v1.0 → v1.1 迁移：boundaries.md → rules.md 附录
    old_b = os.path.join(root, "main", "boundaries.md")
    rules_p = os.path.join(root, "main", "rules.md")
    if os.path.exists(old_b) and args.migrate:
        with open(old_b, "r", encoding="utf-8") as f:
            old_txt = f.read().strip()
        with open(rules_p, "r", encoding="utf-8") as f:
            cur = f.read()
        if "遗留条目" not in cur:
            with open(rules_p, "a", encoding="utf-8", newline="\n") as f:
                f.write(MIGRATE_HEADER + old_txt + "\n")
            print("  ⇪ 已把 main/boundaries.md 并入 rules.md 附录")
            print("    下一步：人工归并进 R1/R2 → 删除本节 → 删除 boundaries.md")
        else:
            print("  = rules.md 已有附录，跳过并入")
    elif os.path.exists(old_b):
        print("  ⚠ 发现旧文件 main/boundaries.md（v1.0），迁移请加 --migrate")

    print(f"[memory_init] 根目录: {root}")
    for c in created:
        print(f"  + 创建 {c}")
    if "main/index.md" in created:
        print("     ⚠ index.md 被重置：『方法快捷入口』手写区也清了，沉淀方法论后要重填")
    for s in skipped:
        print(f"  = 跳过 {s}（已存在；覆盖加 --force）")

    # R15：人格设定保护 —— persona.md / rules.md 默认连 --force 都不让覆盖
    if protected:
        print("  🔒 R15 保护：以下文件已存在，--force 也**不会**覆盖（它们不可重建）：")
        for p in protected:
            print(f"     - {p}")
        if args.force:
            print("     你用了 --force，但这两个文件被保护。确需重建请加 --force-main（会先自动备份）。")
        print("     若用户在别处已有人格设定：先读取它，再询问用户是否沿用（rules.md R15.2），")
        print("     在用户明确选择前不自动套用、不替换。")

    # v1.2：注入常驻锚点（R13）——不做这一步，新会话会忘记自己有记忆库
    if args.anchor_target:
        if not HAVE_ANCHOR:
            print("  ⚠ 未找到 memory_anchor.py，跳过锚点注入")
            print(f"    请手动执行：python3 scripts/memory_anchor.py --root \"{root}\" --inject <目标文件>")
        else:
            anchor_txt = build_anchor(root, args.agent_name)
            for tgt in args.anchor_target:
                do_inject(tgt, anchor_txt)
                add_target(root, os.path.abspath(tgt))
            print("  ★ 常驻锚点已注入（R13）：新会话会自动想起这个记忆库")

    gitignore = os.path.join(root, ".gitignore")
    if not os.path.exists(gitignore):
        with open(gitignore, "w", encoding="utf-8", newline="\n") as f:
            f.write("*.index\n.cache/\n*.faiss\n.vec/\n")
        print("  + 创建 .gitignore")

    print("\n下一步：")
    print("  1. 填 main/persona.md：我是谁 / 主人档案 / 我们的关系 / 身份识别（暗号存 hint+哈希）")
    print("  2. 填 main/rules.md：R1–R15，重点是 R11 自动触发 / R12 留存分级 / R13 常驻锚点 / R14 目录分层 / R15 人格设定保护")
    if not args.anchor_target:
        print("  ★ 还没注入常驻锚点！强烈建议执行（否则新会话会忘记记忆库）：")
        print(f"    python3 scripts/memory_anchor.py --root \"{root}\" --inject \"<你的 AGENTS.md 或 CLAUDE.md>\"")
    print("  3. 前两份不可重建，务必认真填；填完 git init 并提交")
    print(f"  4. cd {root} && git init && git add -A && git commit -m 'init memory'")
    print(f"  5. 写事件后跑 scripts/memory_index.py --rebuild --root {root}")
    print(f"  6. 每次写入后跑 scripts/memory_check.py --root {root}（0 error 才算完成）")
    print("  7. 目录分层（R14）：新事件默认进深层 index.md；久远且不重要的会自动")
    print(f"     沉到 index-shallow.md。查看/调整：memory_tier.py --root {root} --plan")
    return 0


if __name__ == "__main__":
    sys.exit(main())
