# 事件串联规范

> 读这份的时机：写完事件后要补关联，或想判断事件网是否健康。

## 为什么要串联

孤立的事件等于没记。真正有价值的记忆是"这件事导致了那件事"——因果链才是 agent 能拿来推理的东西。

本系统的串联是**显式手写**的（不是自动图数据库），代价是要维护，收益是**完全可读、可改、可版本化**。

---

## 六种关系类型

| 关系 | 含义 | 方向 | 例子 |
|---|---|---|---|
| `caused_by` | 由某事件引起 | 结果 → 原因 | 客户投诉 ← 项目延期 |
| `led_to` | 导致了某事件 | 原因 → 结果 | 项目延期 → 客户投诉 |
| `related` | 主题相关（无因果） | 双向等价 | 两次面试同一家公司 |
| `involves` | 涉及同一人物/实体 | 双向等价 | 都涉及 Z 先生 |
| `same_topic` | 同一议题的延续 | 双向等价 | 连续三次讨论同一个 bug |
| `temporal` | 时间邻近 | 双向等价 | 同一周发生 |

**选关系的判据**：能说出因果就用 `caused_by`/`led_to`，说不出才用 `related`。不要用 `related` 偷懒。

---

## ⚠️ 节点标识：一律用 slug

**`links.md` 的源/目标列必须写事件的 slug，即 frontmatter 里的 `slug` 字段**（如 `gpu-upgrade`）。

不能写中文标题（显卡更换），也不能写文件名（20261020-gpu-upgrade.md）——脚本按 slug 匹配，写别的会全部判成断链。这是实测踩过的坑。

slug 是**权威标识**，文件名只是容器（文件名带日期前缀，与 slug 不相等）。

## `facts/links.md` 格式

```markdown
# 事件关联图

> 双向互写：写了 A→B，必须同时写 B←A。单向边是缺陷，校验会报。
> 节点一律写 slug，不写中文标题。校验：python3 scripts/memory_check.py --root <root>

| 源事件 | 关系 | 目标事件 | 说明 |
|---|---|---|---|
| gpu-upgrade | led_to | local-model-speedup | 换 1660 后才有调参空间 |
| local-model-speedup | caused_by | gpu-upgrade | 同上（反向行必须存在） |
| hindsight-research | led_to | memory-system-rebuild | 调研后决定自建 |
| memory-system-rebuild | caused_by | hindsight-research | 同上 |
| local-model-speedup | same_topic | memory-system-rebuild | 都属本地 AI 能力建设 |
```

---

## 事件文件内的「关联」段

每个事件文件末尾也要写关联（与 links.md 保持一致，links.md 是全局视图，事件内是局部视图）：

```markdown
## 关联
- ← 起因：[显卡更换](20261020-gpu-upgrade.md)
- → 导致：[沉淀出调参 SOP](../../experience/methodology/local-model-tuning.md)
- ～ 相关：[另一次性能优化](20261001-perf-tuning.md)
```

符号约定：`←` 起因 / `→` 导致 / `～` 相关。

---

## 成网判据（健康度）

跑 `memory_check.py` 看三项：

| 指标 | 健康 | 说明 |
|---|---|---|
| **孤岛事件** | 0 | 有事件没有任何关联 = 未来检索不到上下文 |
| **单向边** | 0 | 写了 A→B 没写 B←A = 从 B 侧看不出联系 |
| **断链** | 0 | 关联指向的文件不存在 |

**新库的现实预期**：刚建库时孤岛多是正常的。判定标准是**每次写新事件都必须至少补一条关联**——增量保证不新增孤岛，存量慢慢补。

---

## 常见错误

| 错误 | 后果 | 正确做法 |
|---|---|---|
| 只写 links.md 不写事件内关联段 | 读单个事件时看不到上下文 | 两处都写 |
| 用 `related` 兜底所有关系 | 因果信息丢失 | 能判因果就用因果 |
| 关联到方法论不写进 links.md | 方法与事件脱节 | 方法论也是节点，可关联 |
| 删除事件文件不清理 links.md | 产生断链 | 删除时同步清理，或标记归档 |
