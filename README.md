# agent-memory-skill v1.3 · 安装说明

> Agent 记忆系统技能（原 three-layer-memory）：主记忆（人格/规则/目录）· 经验（SOP/模板）· 事实（事件/知识）
> **v1.2 核心：让 AI 自动存取记忆，并永远记得自己有这个记忆库。**
> **v1.3 核心：记忆目录分深浅两层，给常驻上下文瘦身（省 token）。**

**一句话**：给 AI Agent 装一套**活在磁盘上**的长期记忆——人格、规矩、经历全部 Markdown 明文存储，上下文清空、换会话、换模型都不会失忆，可 `git` 版本化，数据完全在你自己手里。

---

## 一、谁该用（使用人群）

| 你是谁 | 你遇到的痛点 | 本技能给你的东西 |
|---|---|---|
| **养 AI 人格的人** | 想让 agent 有稳定性格、记得住你、认得出你，但一换会话就"换了一个人" | 人格四段（它是谁 / 你是谁 / 你俩什么关系 / 怎么认出你）+ 身份识别协议 |
| **被上下文上限折磨的人** | 长对话一清空就失忆，前面聊的全白费 | 常驻锚点 + 深浅目录分层，记忆落在磁盘不落在上下文 |
| **用 Agent 干活的人** | 每次都要重新交代背景、重复踩同一个坑 | 决策留痕、踩坑自动沉淀成 SOP，经验层随取随用 |
| **多平台跑 Agent 的人** | DSH / Claude Code / Cursor / QQ 机器人各跑一个，记忆割裂 | 一份 Markdown 记忆库，跨平台共用，换平台记忆跟着走 |
| **在意数据主权的人** | 不想把记忆托管给别人家的数据库，怕哪天没了 | 纯文本 + `git` 可版本化，没有数据库、没有云服务、没有供应商锁定 |

---

## 二、什么时候用（使用场景）

### ★ 场景 1：养人格，防记忆丢失（本技能的初衷）

**例子：在 DSH 里养「大肥鱼」**

- **问题**：会话一关、上下文一清，「大肥鱼」就不认识你了，说话风格漂移，之前一起经历的事全忘光——养了很久的角色，一夜回到出厂设置。
- **怎么做**：
  1. `memory_init.py` 建库，填 `persona.md` 四段：它是谁 / 你是谁（代号不写真名）/ 你俩的关系与相处基调 / 怎么确认是你（暗号只存 hint + 哈希）
  2. `memory_anchor.py` 把记忆库指针注入 DSH 每次会话都会加载的常驻文件
  3. 之后它自己存取：你说过的话、纠正过的事、一起经历的片段，自动进 `facts/events/` 并互相串联
- **效果**：**就算这个会话没了，下次它读 `main/` 还是能认出你。** 常驻落在磁盘上，不落在上下文里——这正是本技能存在的理由。
- **代价要说清**：**对话常驻我保证不了**（会话存续归平台管），能保证的是**记忆不丢**。这是两件事。

### 场景 2：跨会话连续
换会话 / 清空上下文 / 换模型之后，仍然记得你在做什么、上次做到哪、你的偏好是什么。

### 场景 3：主人识别与权限分级
能分辨"现在跟我说话的是不是你"。S/A/B 三级信号 + 暗号校验：确认是你 → 全权限；存疑 → 降权只通用回答；不是你 → 拒绝读写并记一条安全事件。防止记忆库被人套话或污染。

### 场景 4：长期项目伴随
项目里每次决策、每次返工、每个踩过的坑都留痕；同类问题第三次出现时，自动提炼成方法论 SOP，下次直接复用不再重蹈覆辙。

### 场景 5：偏好学习与自动触发
你说"我不喜欢长篇大论"、你纠正它一次 → 自动记进主人偏好，以后不用再说第二遍。**你不需要说"记住这个""去查一下记忆"**——它扫到信号就自己做（保存信号 T1–T11 / 读取信号 U1–U8）。

### 场景 6：顺着因果链回忆
问"上次那个事怎么来着"，它不是搜到一条就完事，而是顺着 `caused_by / led_to / related` 的关系链把前因后果讲清楚。

### 场景 7：多平台共用一份记忆
同一套记忆库在 DSH、Claude Code、Cursor、QQ 机器人之间共用，换个地方跑还是同一个"它"。

### 场景 8：记忆库体检与整理
事件多了就 `memory_tier.py` 做分层整理（久远小事下沉到浅层省 token）、`memory_check.py` 查孤岛/断链/隐私泄露、`memory_index.py --rebuild` 重建目录。

### 场景 9：与外部知识库协同
绑了知识库 → 知识写进知识库、记忆库只留指针；没绑 → 知识落在事实层。两者不打架。

---

## 三、什么时候**不**用

| 情况 | 为什么不适合 |
|---|---|
| 一次性问答、临时草稿 | 会话态内容**不入库**是本技能的设计（R12 留存分级），硬记只会稀释记忆 |
| 团队共享知识库 | 这是**单 agent 的人格记忆**，不是多人协作 wiki；多人共写会污染人格 |
| 百万级文档的语义搜索 | 记忆库定位是"小而准的个人记忆"，海量检索请交给专业 RAG / 向量库 |
| 要毫秒级响应的在线服务 | 它是文件读写 + 目录优先检索，不是为高并发设计的 |

---

## v1.3 新增了什么（相比 v1.2）

| 新增 | 解决什么问题 |
|---|---|
| **R14 目录分层** | 事件越多，常驻目录加载的 token 越多。现在目录拆成**深层**（近期 + 重要，每次必读）和**浅层**（久远 + 日常，按需读），久远小事不再天天占着上下文 |

**新事件默认进深层**；久远（超 90 天）且不重要的自动下沉到浅层。

★ 关键点：**事件文件本身不移动，只是目录行换了个位置**——所以 `links.md` 关联、事件路径、git 历史全部不受影响。

规则从 R1–R13 扩到 **R1–R14**。

### 前版特性（v1.2 保留）

| 特性 | 解决什么问题 |
|---|---|
| **R11 自动触发** | AI 扫到信号就自己存取，不用你说"记住这个""去查记忆" |
| **R12 留存分级** | 四级留存 + 四问判据，明确什么该长期记、什么不该入库 |
| **R13 常驻锚点** | 上下文清空后 AI 也记得自己有记忆库（指针注入 `AGENTS.md`） |

---

## 四、安装技能

1. 解压整个 `agent-memory-skill` 文件夹
2. 放到：`C:\Users\<你的用户名>\.workbuddy\skills\agent-memory-skill\`
3. **重启 WorkBuddy**（技能需重启才生效）

装好后对话里说「记住这件事」「初始化记忆」等即会自动加载本技能。

---

## 五、三步建起你的记忆库

### 第 1 步：初始化（★ 一定要带 `--anchor-target`）

```bash
cd agent-memory-skill/scripts

python memory_init.py --root "D:/memory" --agent-name "小幕" --owner "M" \
  --anchor-target "D:/你的项目/AGENTS.md"
```

- `--root` 记忆库放哪
- `--agent-name` agent 名字
- `--owner` 主人代号（**不写真名**）
- `--anchor-target` **常驻锚点注入到哪个文件**，可多次传入

选哪个文件？选**你这个 agent 每次会话都会自动加载的那个**：

| 你在用什么 | 注入到 |
|---|---|
| WorkBuddy / Claude Code | `AGENTS.md` 或 `CLAUDE.md` |
| Cursor | `.cursorrules` |
| 其他 | 工作区 `MEMORY.md` |

初始化会自动生成两份目录：

```
main/index.md           深层目录（近期 + 重要）—— 每次会话必读
main/index-shallow.md   浅层目录（久远 + 日常）—— 按需读，起步时是空的
```

### 第 2 步：填两份不可重建的文件

- `main/persona.md` —— 四段：我是谁 / 关于我的主人 / 我们的关系 / 身份识别（暗号只存 hint + sha256，**不写明文**）
- `main/rules.md` —— R1–R14，重点看 **R11 自动触发 / R12 留存分级 / R13 常驻锚点 / R14 目录分层**，删掉不适用项、补你自己的标准

其余文件（目录、知识、向量索引）都能重建，这两份不能。**填完立刻 `git init` 并提交。**

### 第 3 步：校验

```bash
python memory_check.py --root "D:/memory"
```

看到 `0 error` 且 `W6 常驻锚点正常` 才算完成。

---

## 六、日常怎么用（AI 自动做，你不用管）

装好 + 注入锚点后，AI 会**自动**：

- 你说「我不喜欢长篇大论」→ 自动记进主人偏好（会先跟你确认）
- 你纠正它 → 自动写事件，可复用的提炼成 SOP
- 你提到「上次那个项目」→ 自动检索记忆目录后回答
- 它要做决策/给建议 → 自动先读你的偏好和相关历史
- 长会话结束前 → 自动盘点「这轮有什么该记的」

**你不需要再说"记住这个""去查一下记忆"。** 如果还要你说，说明锚点没生效：

```bash
python memory_anchor.py --root "D:/memory" --check-all
```

---

## 七、目录分层：深层与浅层（v1.3）

| | **深层** `main/index.md` | **浅层** `main/index-shallow.md` |
|---|---|---|
| 装什么 | 近期（90 天内）+ 重要 + 手动锁定 | 久远且不重要 |
| 读取 | 每次会话必读 | 深层没找到且问题涉久远小事时才读 |
| 新记忆 | **默认进这里** | 只接收下沉的旧条目 |

**什么时候启用浅层**：起步不用管（浅层是空的）；事件跨过几个月后 `rebuild` 会自动把老的不重要的沉下去；深层超过 60 条时 `memory_check.py` 会报 **W7** 提醒整理。

**怎么手动调整**：

```bash
python memory_tier.py --root "D:/memory" --plan              # 看分层方案（不改）
python memory_tier.py --root "D:/memory" --stats             # token 估算
python memory_tier.py --root "D:/memory" --pin <slug>        # 锁定在深层，永不下沉
python memory_tier.py --root "D:/memory" --promote <slug>    # 标重要 → 拉回深层
python memory_tier.py --root "D:/memory" --demote <slug>     # 标日常 → 立即下沉
python memory_index.py --root "D:/memory" --rebuild          # ★ 改完必须重建
```

**省多少 token**：每行目录约 30 token。100 条事件全常驻 ≈ 3000 token，分层后若深层 40 条 ≈ 1200，**省 60%**。时间窗改 `.memory-config.yaml` 的 `deep_window_days`。

---

## 八、常用命令

```bash
# 初始化（含锚点注入）
python memory_init.py --root "D:/memory" --agent-name "小幕" --owner "M" --anchor-target "AGENTS.md"

# 常驻锚点
python memory_anchor.py --root "D:/memory" --print                  # 只看锚点内容
python memory_anchor.py --root "D:/memory" --inject "AGENTS.md"     # 注入（幂等，不破坏原文件）
python memory_anchor.py --root "D:/memory" --check-all              # 校验全部锚点
python memory_anchor.py --remove "AGENTS.md"                        # 移除

# 目录分层（v1.3）
python memory_tier.py --root "D:/memory" --plan                     # 分层方案
python memory_tier.py --root "D:/memory" --stats                    # token 估算
python memory_tier.py --root "D:/memory" --pin <slug>               # 锁定在深层

# 目录与校验
python memory_index.py --rebuild --root "D:/memory"                 # 写完事件后重建（自动分层）
python memory_index.py --stats --root "D:/memory"                   # 分层统计
python memory_check.py --root "D:/memory"                           # 每次写入后校验
```

---

## 九、文件清单

```
agent-memory-skill/
├── SKILL.md                        主入口（v1.3）
├── README.md                       本文件
├── LICENSE                         MIT 许可证
├── references/
│   ├── layer-spec.md               三层字段定义、persona 四段、正反例
│   ├── rules-spec.md               R1–R14 完整条文与违反处置
│   ├── auto-trigger.md             ★v1.2 保存 T1–T11 / 读取 U1–U8 / 每轮流程 / 自检三问
│   ├── retention-spec.md           ★v1.2 四级留存、四问判据、必写与不写清单
│   ├── index-tiering.md            ★v1.3 深浅目录方案、分层判据、token 账、常见错误
│   ├── retrieval-protocol.md       漏斗详解（含浅层缓冲）、向量检索接法、降级策略
│   ├── linking-spec.md             串联六种关系、links.md 规范
│   ├── integration-mcp.md          MCP 与外部平台对接
│   └── anti-loss.md                备份、重建演练、git 化
├── scripts/
│   ├── memory_init.py              初始化（--anchor-target / --owner / --migrate）
│   ├── memory_anchor.py            ★v1.2 常驻锚点：注入 / 校验 / 移除
│   ├── memory_tier.py              ★v1.3 目录分层：plan / stats / pin / promote / demote
│   ├── memory_index.py             目录索引重建（双层 + --stats）
│   └── memory_check.py             校验（含 W6 锚点、E6 重复登记、W7 深层过长）
└── assets/templates/
    ├── persona.md       人格四段
    ├── rules.md         规范规则 R1–R15
    ├── memory-anchor.md ★v1.2 常驻锚点
    ├── event.md         事件五段（含 retention / importance 字段）
    ├── methodology.md   方法论 SOP
    └── qa-template.md   问答模板
```

---

## 十、v1.2 用户升级须知

1. 覆盖 `scripts/`、`references/`、`assets/` 全部文件
2. `main/rules.md` 追加 **R14 目录分层** 一段（从 `assets/templates/rules.md` 拷）
3. 跑一次 `memory_index.py --rebuild`，会自动生成 `main/index-shallow.md` 并完成分层
4. 跑 `memory_check.py`，确认 0 error、W6 通过

**旧库数据完全不受影响**——事件文件一个都不会动，只是目录行多了个去处。
