# 防丢失：备份、重建、git 化

> 读这份的时机：搭建完成后必读一次；之后每季度体检时重读。

## 核心判断：什么能重建，什么不能

| 层 | 能否重建 | 依据 | 备份等级 |
|---|---|---|---|
| `main/persona.md` | ❌ **不能** | 人格、主人档案、关系、身份识别都是人写的，事件里推不出来 | 🔴 最高 |
| `main/rules.md` | ❌ **不能** | 规范标准是人定的，写成什么样推不出来 | 🔴 最高 |
| `main/index.md` | ✅ 能 | 由 `facts/events/` 反向生成 | 🟡 中 |
| `experience/` | ⚠️ 难 | 方法论可从事件重新总结，但总结本身是智力成果 | 🟠 高 |
| `facts/events/` | ❌ **不能**（若是原始记录） | 事件一旦没记就永远没了 | 🔴 最高 |
| `facts/links.md` | ✅ 能（部分） | 可由事件内关联段重建，但手写说明会丢 | 🟡 中 |
| 向量索引 | ✅ 能 | 纯派生物 | ⚪ 无需备份 |

**记住这张表**：备份精力花在 🔴 上，🟡 以下的丢了也能恢复。

---

## 三条铁律

1. **Markdown 是唯一真相。** 数据库、索引、缓存全是派生物，删了能重建。
2. **整个记忆根目录进 git。** 每次写入后提交，`git diff` 能看见人格是怎么一步步变的——这本身就是一种记忆。
3. **定期真跑一次重建演练。** 别等丢了才发现重建不了。

---

## git 化步骤

```bash
cd <memory-root>
git init
# .gitignore 里排除向量索引与缓存
printf "*.index\n.cache/\n*.faiss\n" > .gitignore
git add -A
git commit -m "init memory"
```

**提交粒度**：一次事件一次提交，信息写事件 slug。例如 `git commit -m "event: local-model-speedup"`。

**为什么必须 git**：
- 人格漂移可追溯（哪天把"直接"改成了"委婉"，为什么改）
- 误删可回滚
- 多机同步（记忆跟着人走，不跟着机器走）

---

## git 提交钩子：写入前自动校验（v1.3.3 优化）

手动 `git commit` 容易忘跑 `memory_check.py`。用 **pre-commit 钩子**把校验绑到提交动作上：有 error 直接拦截提交，强制先修再提交。

在记忆根目录建 `.git/hooks/pre-commit`（建完 `chmod +x`）：

```bash
#!/bin/sh
# 记忆库提交前校验：有 error 则阻断提交，强制先修
root="$(git rev-parse --show-toplevel)"
python3 "$root/scripts/memory_check.py" --root "$root" >&2
if [ $? -ne 0 ]; then
  echo "✗ memory_check 有 error，提交已阻断。先修复再 commit。" >&2
  exit 1
fi
```

要点：

- 钩子**只拦 error，不拦 warning**（W6 / W7 等提示不阻断日常提交）——校验脚本的退出码正是按此设计。
- 脚本路径用 `git rev-parse --show-toplevel` 定位，钩子放记忆库任意子目录都能跑。
- 临时要跳过（如紧急 fix）可用 `git commit --no-verify`，但事后务必补跑 `memory_check.py`。

---

## 重建演练（每季度一次）

```bash
# 1. 备份当前 index（防演练失败）
cp main/index.md /tmp/index.bak

# 2. 真删
rm main/index.md

# 3. 重建
python3 scripts/memory_index.py --rebuild --root <root>

# 4. 对比：内容应与备份一致（顺序可能不同）
diff <(sort /tmp/index.bak) <(sort main/index.md)

# 5. 校验
python3 scripts/memory_check.py --root <root>
```

**这一步的意义**：如果重建出来的 index 缺行，说明有事件文件没写规范字段——趁现在修，而不是等真丢记忆那天。

---

## 隐私红线细则

写入任何文件前，先过这道检查：

| 内容类型 | 处理 |
|---|---|
| 真实姓名 | 脱敏（张三 → Z 先生）或经用户明确同意后写 |
| 手机号 / 邮箱 | **不写** |
| 住址 / 具体位置 | **不写**（可写"本市"级别） |
| 身份证号 / 证件号 | **不写** |
| 账号 / 密码 / 密钥 / Token | **绝对不写**，任何情况 |
| 第三方身份信息 | 不写具体身份，用角色代称 |
| 用户说"这条别记" | 立即停止，不留摘要、不留指针 |

**执行方式**：把这张表原样放进 `rules.md` R2，并在写入协议里设检查点。脚本 `memory_check.py` 会做关键词扫描（手机号、邮箱、身份证正则），命中即告警（W2）。

**v1.1 补一条**：**暗号答案属于密钥级信息**，只存 `hint` + `sha256[:16]`，写明文即违规（W3 会告警）。备份 `main/` 时哈希可以跟着备份，**但别把 hint 和答案写在同一个地方**——两者分开才叫暗号。

---

## 与数据库方案的对比（选型依据备忘）

| 维度 | 本方案（Markdown） | 数据库方案（如 Hindsight） |
|---|---|---|
| 记忆真相 | 文件，可读可 diff | PostgreSQL，需工具才能看 |
| 索引损坏 | 重建，零损失 | 取决于实现 |
| 数据库损坏 | 文件还在，无影响 | **真丢** |
| 自动巩固 | 无（需手动总结方法论） | 有（后台自动） |
| 图检索 | 手写 links.md | 自动知识图谱 |
| 运维成本 | 极低（git 即可） | 需跑服务、需备份 DB |

**当初选择 Markdown 流派的理由**：用户的第一诉求是"绝不能丢"，且已有人格文件常驻的实践基础。若日后需要自动巩固，可叠加外部方案做**派生层**，但真相仍留在 Markdown。
