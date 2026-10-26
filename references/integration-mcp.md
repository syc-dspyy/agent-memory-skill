# 外部接口：MCP 与平台对接

> 读这份的时机：要让其他 AI / 平台读写这套记忆时。

## 定位

`integrations/` 在**三层结构之外**，是可选的对外通道。它不存记忆，只做翻译层：

```
外部 AI / 平台
      ↓ MCP / HTTP / 文件
integrations/
      ↓ 读写
main/ · experience/ · facts/
```

**铁律**：接口层禁止持有任何记忆数据。外部请求一律落到 Markdown 文件，接口只是通路。

---

## MCP 工具声明

在 `integrations/mcp.md` 声明暴露的工具。建议最小集：

| 工具 | 作用 | 落到哪层 | 是否需要确认 |
|---|---|---|---|
| `memory_recall` | 按三级漏斗检索记忆 | 只读 | 否 |
| `memory_verify_owner` | 身份核验：比对暗号哈希；**不落盘、不回显答案** | 无 | 否（失败时写一条安全事件） |
| `memory_write_event` | 写事件详情 | facts/events + index + links | 否（但会同步更新目录与关联） |
| `memory_write_method` | 写方法论 | experience/methodology | 否（需含验收标准） |
| `memory_link` | 补一条事件关联 | facts/links.md | 否（双向自动互写） |
| `memory_read_persona` | 读人格 + 主人档案 + 规范规则 | main/ | 否 |
| `memory_update_persona` | 改人格 / 主人档案 / 身份识别 / 规范规则 | main/ | **是**（必须人工确认） |

**`memory_update_persona` 必须走确认**——这是唯一不可重建的层，被外部 AI 改坏就真坏了。

### 接口侧的身份规则（v1.1）★

- **经接口进来的请求默认按「存疑」降权**（rules.md R3.5）：可通用回答，但不读记忆细节、不写记忆。
- 提权必须**主人当场过 S 级**（`memory_verify_owner` 抛 hint、比对 hash），且**只对当前会话有效**——不写进记忆、不长期保留。
- `memory_verify_owner` 的实现要点：只回传 `hint` 与比对结果（true/false），**绝不回传暗号答案或哈希原文**；失败时按 R3.4 记一条 `tags: [安全]` 事件（只记现象）。
- 对外暴露（非 localhost）必须加鉴权；本机 stdio 模式无需鉴权。

### MCP 服务器最小实现要点

- 三个工具就够跑通闭环：`memory_recall` / `memory_write_event` / `memory_read_persona`
- 实现参考本机已有的零依赖写法：`D:/bendibushu/tools/ollama-mcp-server.mjs`（stdio 协议，直接复用其骨架）
- 注册位置：`~/.workbuddy/mcp.json`（**注意：只在应用启动时读取，改完需重启**）
- 若对外暴露（非 localhost），必须加鉴权；本机 stdio 模式无需鉴权

---

## 平台对接记录 `integrations/platforms.md`

记录每个对接平台的：用途、读写范围、鉴权方式、最后一次验证时间。

```markdown
| 平台 | 用途 | 读写范围 | 鉴权 | 最后验证 |
|---|---|---|---|---|
| WorkBuddy MCP | 本机 agent 读写记忆 | 全层（改 main 需确认） | stdio 本地 | 2026-10-26 |
| IMA 知识库 | 外部知识库（绑定后知识写这边） | 只读 + 追加 | API Key | 2026-10-26 |
```

---

## 与知识库的边界

绑定外部知识库后，分工是：

| 内容 | 去哪 |
|---|---|
| 事件、感受、因果、人格 | **本记忆库**（这是"我的经历"） |
| 学到的客观知识、资料文档 | **外部知识库**（这是"世界的知识"） |

判定一句话：**跟"我"有关 → 记忆库；跟"我"无关 → 知识库。**

`.memory-config.yaml` 里配置 `knowledge_base`，脚本会据此校验有没有把知识错写进 `facts/knowledge/`。
