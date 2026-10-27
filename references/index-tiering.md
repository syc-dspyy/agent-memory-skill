# 目录分层：深层与浅层（R14）

> 读这份的时机：目录变长、想省 token、或拿不准某条事件该在哪层时。
> 对应 `main/rules.md` 的 **R14**。读取顺序见 `retrieval-protocol.md`。

## 一、为什么要把目录拆成两层

记忆目录是**常驻上下文**的一部分——事件越多，每次会话加载的 token 越多。但绝大多数时候，AI 需要想起的是**近期的事**和**重要的事**，三个月前某次无关紧要的对话不该天天占着上下文。

所以拆成两层：

| | **深层** `main/index.md` | **浅层** `main/index-shallow.md` |
|---|---|---|
| 装什么 | 近期 + 重要 + 手动锁定 | 久远 + 日常 + 不重要 |
| 读取方式 | **每次会话必读**（L0 常驻） | **按需读**：深层没找到且涉久远小事时 |
| token | 计入常驻开销 | 不计入常驻开销 |
| 事件变多时 | 会增长 → 需要整理 | 自然承接下沉的条目 |

**新记忆一律先进深层。** 只有"久远且不重要"的才会沉下去——这保证了新事不可能一写进去就被埋掉。

## 二、分层判据（满足任一 → 深层）

1. `pinned: true` —— 手动锁定，永不下沉
2. `importance: high` —— 重要事件
3. 事件日期在 `deep_window_days` 内（默认 **90 天**，见 `.memory-config.yaml`）

其余归入浅层。日期解析失败（没写 `date`）的视为久远 → 浅层。

## 三、★ 只动目录行，不动事件文件

```
facts/events/20250115-old-trivial.md   ← 文件永远在这里，不动
        │
        ├─ 深层 index.md 里有这一行        → 常驻可见
        └─ 浅层 index-shallow.md 里有这一行 → 按需可见
                 （同一时刻只能在一层，重复登记 = E6 缺陷）
```

**这是本设计的关键**：迁移的是"入口"，不是"内容"。所以

- `facts/links.md` 的关联**完全不受影响**（关联指向事件文件，与目录无关）
- 事件详情路径不变，git 历史干净
- 想任何时候恢复可见性，改个字段 rebuild 即可

## 四、怎么调整分层

```bash
python3 scripts/memory_tier.py --root <root> --plan              # 看方案（不改）
python3 scripts/memory_tier.py --root <root> --stats             # token 估算
python3 scripts/memory_tier.py --root <root> --pin <slug>        # 🔒 锁定，永不下沉
python3 scripts/memory_tier.py --root <root> --unpin <slug>      # 解锁
python3 scripts/memory_tier.py --root <root> --promote <slug>    # ⭐ 标重要 → 拉回深层
python3 scripts/memory_tier.py --root <root> --demote <slug>     # 标日常 → 立即下沉
python3 scripts/memory_index.py --root <root> --rebuild          # ★ 改完必须重建才生效
```

`--plan` 会标注每条留深层的原因（🔒 锁定 / ⭐ 重要 / 🕐 近期还剩几天），并预告 14 天内即将下沉的条目——想留住就趁早 `--pin`。

## 五、什么时候启用浅层

- **起步阶段不用管**：事件少，全部在深层，`index-shallow.md` 是空的
- **事件跨过几个月**：`rebuild` 会自动把老的不重要的沉下去（无需手动操作）
- **深层超过 60 条**：`memory_check.py` 报 **W7**，此时该整理了
- 时间窗不合手？改 `.memory-config.yaml` 的 `deep_window_days`（想要"半年内的都算近期"就填 180）

## 六、token 账（经验估算）

每行目录摘要约 **30 token**。

| 事件总数 | 全部常驻 | 分层后（深层 40 条） | 节省 |
|---|---|---|---|
| 100 条 | ~3000 | ~1200（深层 40）+ 按需 1800 | **60%** |
| 300 条 | ~9000 | ~1200（深层 40）+ 按需 7800 | **87%** |

深层维持在一个稳定量级，常驻开销就不再随记忆增长而线性膨胀——这是分层最大的收益。

## 七、常见错误

| 错误 | 后果 | 正确做法 |
|---|---|---|
| 重要事件没标 `importance: high` 也没 `pinned` | 90 天后沉进浅层，日常检索不到 | 重要的事**当场**标 high 或 pin |
| 手动去浅层找近期事件 | 浪费时间——近期的一定在深层 | 先查深层，找不到再查浅层 |
| "转移"时把事件文件也移动了 | links.md 断链、git 历史脏 | **只动目录行**，文件永不移动 |
| 同一事件两层都写了 | 检索重复、统计错乱（报 E6） | rebuild 会自动去重，别手抄 |
| 深层堆到几百条还不整理 | 常驻 token 爆掉 | 看 W7 提醒，用 `--demote` 或调小时间窗 |

## 八、热度分层：常用的旧事不下沉（v1.3.3 优化）

时间窗和 `importance` 决定分层，但有个盲区：**被反复查阅的旧事件**会随时间长沉进浅层，每次要用又得去浅层捞。热度分层补上这一维——给事件记"被读过几次、上次读是什么时候"，让**常用旧事可凭热度拉回深层**。

事件 frontmatter 新增两个可选字段（由脚本维护，不手填）：

```yaml
access_count: 0          # 被读取次数（memory_tier --bump 自增）
last_access: 2026-10-27  # 上次读取日期（--bump 自动写）
```

用法：

```bash
python3 scripts/memory_tier.py --root <root> --heat           # 按访问次数排，看谁常用
python3 scripts/memory_tier.py --root <root> --bump <slug>    # 读完一个事件后自增其热度
```

**判定建议**（人工决策，不在 rebuild 自动改层）：

- 浅层里 `access_count` 高（如 ≥5）且近期 `last_access` 近的事件 → 该 `--promote` 回深层
- 深层里 `access_count` 长期为 0、又超时间窗、又非重要的事件 → 可考虑 `--demote`

⚠️ 热度**只作建议**，不自动改层——分层最终仍以时间窗 + 重要性为主，避免"读一次就被钉死在深层"。

---

## 九、深层标签速览：事件多时扫得更快（v1.3.3 优化）

深层事件一旦超过 30 条，逐行扫目录就变慢。`memory_index.py --rebuild` 会在 `main/index.md` 自动追加一个「🏷️ 标签速览」分组块（标记 `AUTO:tags`），按**主标签**聚合事件 slug：

```markdown
### 🏷️ 标签速览（深层 · 按主标签分组 · 快速定位）
- **记忆系统**（12）：agent-memory-skill-v12, memory-system-rebuild, …
- **性能优化**（5）：local-model-speedup, gpu-upgrade, …
```

- 只在深层 ≥30 条时生成；事件变少会自动移除（rebuild 幂等）
- 它与下方事件表互补：表看"具体发生了什么"，速览看"哪类事多、该先扫哪类"
- 浅层不生成（浅层本就按需、量少）

---

## 十、与检索漏斗的关系

```
L0 常驻  →  persona + rules + 【深层 index.md】        ← 浅层不在这里
L1 定向  →  扫深层目录 → 命中直达事件 + links
L1.5     →  深层未命中 且 涉久远/小事 → 读【浅层 index-shallow.md】
L2 向量  →  两层都无 → 才动向量检索（并说明"目录未命中"）
```

**浅层是 L1 和 L2 之间的缓冲层**：它比向量检索便宜（读个文件而已）、比直接说"没找到"靠谱（其实记得，只是不在常驻区）。
