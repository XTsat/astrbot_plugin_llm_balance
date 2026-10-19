# AGENTS.md — astrbot_plugin_llm_balance 工作说明书

> 本文件是任何 AI 编码代理（agent）进入 **astrbot_plugin_llm_balance** 仓库时的**必读**工作说明书。
> 它约定本插件的架构、代码规范、文档维护规则、部署与热重载流程。任何对代码、配置、行为的改动，都必须同时遵守本文档的规则。
>
> **来源**：本文件是 [agent-templates](https://github.com/XTsat/agent-templates) 的 `templates/astrbot-plugin/AGENTS.md` 副本，按本仓库实际情况本地化，最新版见该仓库 `main` 分支。
> 用户说「更新 AGENTS」时按此流程：① 拉取来源模板最新版 → ② 与本地逐节比对 → ③ 合并（保留本项目已回填的插件名、命令名、目录结构与项目特有约定）→ ④ 展示 diff 与改动清单，等用户确认后再落盘。**禁止整文件覆盖**。

---

## 1. 项目概览

**插件功能**：AstrBot 插件，支持多平台（DeepSeek / OpenAI / New API 等）大模型余额查询与 OpenAI 兼容端点模型可用性测试。基于 `astrbot.api.star` 框架，以 `Star` 子类为核心，通过装饰器注册命令，在 AstrBot 运行时中加载。

核心文件清单：

| 文件 | 必选 | 职责 |
|------|------|------|
| `main.py` | ✅ | 插件主体（单文件，约 1750 行，全部后端逻辑） |
| `metadata.yaml` | ✅ | 插件元数据（name/version/author/desc/tags/repo），也是插件注册信息与版本源 |
| `_conf_schema.json` | ✅ | WebUI 配置 Schema |
| `README.md` | ✅ | 中文文档（权威源，双语对的源侧） |
| `README_en.md` | ✅ | 英文文档（跟随中文版单向同步） |
| `CHANGELOG.md` | ✅ | 变更日志（分组式） |
| `LICENSE` | ✅ | 许可证 |
| `logo.png` | ✅ | 插件图标 |
| `AGENTS.md` | ✅ | 本工作说明书 |
| `requirements.txt` | 无 | 本仓库不声明运行时依赖（依赖 AstrBot 自带 aiohttp） |

## 2. 目录结构与架构

### 2.1 项目结构

```
astrbot_plugin_llm_balance/
├── main.py             # 全部后端逻辑（单文件风格）
├── metadata.yaml       # 插件元数据（注册信息 + 版本源）
├── _conf_schema.json   # 配置 Schema
├── CHANGELOG.md        # 变更日志（分组式）
├── README.md           # 中文文档（权威源）
├── README_en.md        # 英文文档（跟随中文）
├── AGENTS.md           # 本工作说明书
├── LICENSE
├── logo.png
```

### 2.2 架构倾向

**单文件风格**（当前已约 1750 行，仍保持单文件，不拆分）。文件内部按职责分层，用 `# ==================== 分区名 ====================` 分隔条组织，分区顺序固定：

1. 模块常量（`NON_CHAT_HINTS` / `CHAT_KEY_HINTS` / `KEY_PREFIXES` / 密钥与模型名相关正则）
2. 数据模型（`BalanceResult` / `ModelTestResult`）
3. Fetcher 基类（`BaseBalanceFetcher(ABC)`）与各平台 Fetcher（`DeepSeekFetcher` / `SiliconCloudFetcher` / `MoonshotFetcher` / `ChatAnywhereFetcher` / `OpenAIFetcher` / `NewApiFetcher`）
4. 余额查询管理器（`BalanceManager`）
5. 主插件类（`BalancePlugin(Star)`）：配置解析与工具方法 → 参数解析 → 余额查询实现（`_query_*`）→ 命令 handler（`balance` / `test_model`）→ 模型测试 → 文案与生命周期

- 新增平台 → 新增一个 `XxxFetcher(BaseBalanceFetcher)` 子类并登记到第 3 区，命令层不动
- 新增方法按职责放入对应分区，保持分区顺序稳定
- 单文件风格一旦确定即贯穿整个生命周期，不中途改为分层多文件；也不要新增 `pages/`、`.astrbot-plugin/` 等本插件未使用的目录

## 3. 技术栈与依赖

- **Python 3.10+**（AstrBot 4.x 最低要求）
- **AstrBot API**：`astrbot.api.star`（Context, Star）、`astrbot.api.event`（filter, AstrMessageEvent）、`astrbot.api`（logger, AstrBotConfig）
- **运行时依赖**：aiohttp（AstrBot 自带，顶层 import）；本仓库不声明 `requirements.txt`
- **禁止引入**：不引入与原功能无关的依赖，不新增 `requirements.txt` 声明。若确需新增依赖，必须惰性 import（方法内 import），并在 import 失败时优雅降级、保证插件仍能加载

## 4. 核心代码规范

### 4.1 插件骨架

```python
import ...

import aiohttp

from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star
from astrbot.api import logger, AstrBotConfig


# ==================== 主插件类 ====================

class BalancePlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig = None) -> None:
        super().__init__(context)
        self.config = config or {}
```

> 本插件**不使用** `@register` 装饰器：插件注册信息（name/author/desc/version）由 `metadata.yaml` 提供，版本源也只有它一处（见 7.1、8.2）。

### 4.2 命名约定

| 元素 | 本仓库约定 |
|------|------------|
| 模块级常量 | `UPPER_SNAKE`（`NON_CHAT_HINTS`、`CHAT_KEY_HINTS`、`KEY_PREFIXES`） |
| 私有方法 | `_` 前缀 + `snake_case`（`_query_all`、`_mask_key`、`_short_error`、`_pick_chat_models`） |
| 平台 Fetcher 类 | `PascalCase` + `Fetcher` 后缀（`DeepSeekFetcher`），基类固定为 `BaseBalanceFetcher` |
| 命令 handler | **语义名直名**（`balance`、`test_model`），不强制 `cmd_` 前缀——与既有代码一致，避免命令名与函数名强行耦合 |
| 类名 | `PascalCase`（`BalancePlugin`、`BalanceManager`） |
| 文件名 | `snake_case` |

### 4.3 类型与语法

- Python 3.10+ 现代联合类型写法（`dict | None`、`list[str]`）；存量代码仍有 `typing.List` / `typing.Optional` 的写法，新增或重写的签名优先现代写法，但不在无关改动里批量替换
- 函数签名**必须完整类型注解**（参数 + 返回类型）；`yield` 返回结果的命令方法标注返回类型与既有风格一致
- 禁止 `Any` 作为类型注解（除非调用方签名强制要求）
- 禁止 `# type: ignore`

### 4.4 注释规范

见第 7 章 [7.3 注释规范](#73-注释规范)。

### 4.5 日志

- 统一 `logger.info/warning/error`，**必须带 `[astrbot_plugin_llm_balance]` 前缀**
- 错误信息带 emoji 前缀（`❌`、`⚠️`）
- 精确捕获异常类型（`asyncio.TimeoutError`、`aiohttp.ClientError`），禁止空 `except: pass`
- 异常分类记录：参数非法（`ValueError`）与 IO 失败（`OSError` / `aiohttp.ClientError`）分开记，单请求失败不影响其它请求

### 4.6 错误处理与防御性编程

- 外部 HTTP IO 必须 try/except 并记录日志，**不允许静默吞异常**
- API 响应错误提取用 `_short_error(resp)`（取 error.message/message 前 150 字符）与 `_safe_resp_text(resp)`
- 降级链路清晰：成功结果 → 部分失败提示（`⚠️ 另有模型不可用: ...`）→ 明确报错文案
- 配置值防御式校验：`self.config.get(k, 默认值)` 读取，类型不符或缺失时回落到默认值，不抛裸异常

### 4.7 并发

- 异步方法使用 `async/await`，**禁止阻塞事件循环**
- 多密钥/多模型并发用 `asyncio.gather`；HTTP 请求全部带超时（models 探测 10s、chat 实测 20s），禁止无限等待
- 单请求失败不影响其它请求，最后统一分组汇总

### 4.8 回复消息

- 统一 `yield event.plain_result(...)`
- 默认中文 + emoji 图标风格（🟢/🔴/✅/⚠️/🔑/🧠/🎯）；`output_language`（`auto` / `zh` / `en`）可切换英文本地化，文案统一走 `_get_template`，不在 handler 里手写双语分支
- 报告排版复用模块内模板：`_header`、`_sep`、`_item_sep`、`_section_sep`
- 密钥输出必须脱敏（`_mask_key`），安全提醒文本在帮助中固定出现

### 4.9 权限控制

- 管理类命令使用自定义 `_is_admin(event)` 检查（既有风格，保留原因：兼容既有群聊/私聊管理员识别语义），命令 handler 开头统一：
  ```python
  if not self._is_admin(event):
      yield event.plain_result("🚫 只有管理员可以使用此指令。")
      return
  ```

## 5. 配置与数据文件

### 5.1 配置 Schema（_conf_schema.json）

- 新增配置项 → 先在 `_conf_schema.json` 补 schema（type/hint/default/options），再在代码中实现读写
- 文档正文引用配置项时，**中文名在前、英文 key 在后**：统一写成「简明中文名（`key`）」，例如「请求超时（`request_timeout`）」「输出语言（`output_language`）」「API 连接缩写映射（`platform_names`）」，key 用反引号包裹。本仓库 schema 的 `hint` 是整句使用说明（不是短名称），README 配置表首列保持 `key`、「说明」列取 `hint` 要点，正文引用处补简明中文名

### 5.2 配置读取模式

- 直接 `self.config.get(k, 默认值)` 读取；本插件**没有** `DEFAULT_SETTINGS` 合并表，不要在新增代码里引入第二套读取机制
- 多值/结构化配置（如 `platform_names` 的 `地址=缩写1,缩写2`）解析失败时按空处理并 `logger.warning`，不中断命令

### 5.3 数据文件

- 本插件**无** `plugin_data/` 持久化需求，不新增数据文件

## 6. 指令注册与命令清单

### 6.1 指令注册模式

```python
@filter.command("余额", alias={"balance"})
async def balance(self, event: AstrMessageEvent):
    ...

@filter.command("测试", alias={"test"})
async def test_model(self, event: AstrMessageEvent):
    ...
```

> 本插件**只有命令**，不注册事件监听器（无 `@filter.event_message_type`）。若将来新增全量消息监听，按模板写法注册，且因需要处理全部消息而标注 `AsyncGenerator[MessageEventResult, None]` 返回类型。

### 6.2 命令 handler 内部解析约定（两个 handler 共用模式）

1. `full_text = event.message_str.strip()`，去掉前导 `/`
2. 依次剥命令前缀（中英都支持）：`for cmd in ("余额", "balance"): if full_text.startswith(cmd): full_text = full_text[len(cmd):].strip(); break`
3. `split(maxsplit=1)` 拆出首参数与剩余参数，按子命令分派
4. 密钥串与模型名混在一起时走 `_extract_keys` / `_split_key_and_model_args` 统一解析（`key:` / `model:` 前缀可强制指定），不在各 handler 里重复实现

### 6.3 命令表

| 命令 | 权限 | 说明 |
|------|------|------|
| `/余额`（别名 `/balance`） | 管理员 | 查询余额；空参数/帮助 显示帮助 |
| `/余额 当前` | 管理员 | 查询当前会话使用模型的余额 |
| `/余额 所有` | 管理员 | 查询所有已配置模型的余额（多 key 并发、去重） |
| `/余额 <平台简写>` | 管理员 | 查询指定平台余额（配置中的或自带站点） |
| `/余额 <平台简写> <key1> [key2]...` | 管理员 | 批量查询自带平台的多个密钥余额 |
| `/余额 <API端口> <key1> [key2]...` | 管理员 | 查询自定义 API 端点余额（自动识别 OpenAI/New API） |
| `/余额 <JSON>` | 管理员 | 粘贴 NewAPI 连接信息直接查询 |
| `/测试`（别名 `/test`） | 管理员 | 测试 OpenAI 兼容端点的模型可用性 |
| `/测试 <API网址> <key1> [key2]...` | 管理员 | 自动模式：拉模型列表 → 过滤聊天类 → 实测前 3 个（遇失败即停） |
| `/测试 <API网址> <key1> [key2]... <模型名>` | 管理员 | 指定模型模式：末尾非密钥参数即模型名（可用 `model:` 强制指定），直接实测（不在模型列表也硬测） |

## 7. 文档维护规范（强制，不可省略）

> 本项目的**硬性要求**：任何改动在合并前，必须同步维护 `README.md`、`README_en.md` 与 `CHANGELOG.md`。未同步文档 = 任务未完成。

### 7.1 CHANGELOG 维护

#### 流程

- 日常改动先记在 `## [Unreleased]` 段（顶部固定）；**发版时**再移动到带版本号的新段
- **先记后合**：记录阶段同一工作周期内的改动各自独立记入 `[Unreleased]`（同一功能的多处调整也先各记一条，避免遗漏）；提交或发版前的整理阶段统一过一遍，把描述同一件事的多条合并成一条，不相关改动保持独立（判断标准：用户会不会把它当成同一件事）
- **发版日期**：版本段日期 `(YYYY-MM-DD)` 填**发版当天**的系统日期

#### 格式

统一**分组式**：`### 新增 / 修复 / 变更 / 移除 / 性能`（只保留本次有内容的分类），条目格式「`- 标题：说明`」，**仅重点条目加粗**（核心功能、重要修复、破坏性变更；其余一律不加粗）。版本标题与分类子标题之间可加一行 `> 一句话总结`（可选）。

```markdown
# Changelog

## [Unreleased]

> 一句话总结这个版本（可选）

### 新增
- 功能 A：说明
- **功能 B**：说明

### 修复
- 问题 C：说明

## v1.4.2 (2026-09-25)

### 新增
- **API 连接缩写映射**：新增配置项 `platform_names`，连接地址自动替换为缩写
```

#### 写作视角（面向用户）

CHANGELOG 的读者是**插件使用者**（服务器管理员、群成员），不是开发者。条目只写「用户能感知到的变化」：

- **写用户视角的结果**：用户能做什么、会看到什么、行为/默认值/配置有什么不同
- **禁止内部实现细节**：类名/函数名、Fetcher 拆分、数据结构、算法、缓存与并发策略、日志埋点、依赖升级、重构过程，一律不写
- **禁止出现代码标识符与文件路径**；用户直接接触的**命令名**、**配置项 key** 除外
- **无用户感知的改动不记入 CHANGELOG**：纯内部重构、格式化、注释与测试调整
- **只写相对上一版的变化**：不复述仍然有效的旧功能，不写「继续优化」「体验更好」这类没有信息量的空话
- **同一个变化合并成一条**：同一功能的多处调整、跨多个提交的同一件事，在整理阶段合并为一条，不在不同分类或版本段里重复
- **一句话说清改了什么**：按「做了什么 + 用户得到什么」写完，不加背景、动机与实现过程；用户扫一眼就能对上自己关心的功能

正反例：

```markdown
### 新增
- ✅ 支持 `/余额 <平台简写> <key1> <key2>` 一次查询多个密钥的余额
- ❌ 新增 `_query_and_format` 复用查询汇总逻辑，改用 `asyncio.gather` 并发

### 修复
- ✅ 修复余额不足时提示为「账户不可用」、容易误判为封号的问题
- ❌ 修复 `_short_error` 未捕获 `aiohttp.ClientError` 导致的 `finally` 泄漏
```

#### 版本号（准备发布时才确认）

- **日常开发不碰版本号**：只往 `[Unreleased]` 追加条目，`metadata.yaml` 的 `version` 保持原值；每个功能、每个修复各自独立提交，提交里不带版本号变更
- **准备发布时才确认并递增一次**：一次发版汇总多个提交，等把 `[Unreleased]` 内容移入 `## vX.Y.Z (YYYY-MM-DD)` 的同一次操作里，才确认版本号（SemVer 见 8.2），并打 `git tag vX.Y.Z`；**不能每改一点就递增**
- **唯一版本源**：`metadata.yaml` 的 `version` 字段（`vX.Y.Z` 格式）。需要「插件版本」时一律以它为准
- 辅助位置**不是版本源、不决定版本号**，但发版时必须同步到同一版本号：本插件 README 目前无版本徽章与版本字样（若将来新增则发版同步），展示版本时从 `metadata.yaml` 读取，不手写重复版本号

#### 多会话并行开发

**⚠️ 更新 `CHANGELOG.md` 前必须先读取当前文件内容**，识别并保留其他会话已写入的既有条目（含 `[Unreleased]` 下未提交的功能），只追加自己的条目，**严禁整文件覆盖或删除他人记录**。

### 7.2 README 维护

#### 7.2.1 写作视角（面向用户）

README 的读者是**插件使用者**，不是开发者。只写用户能直接用到的东西：

- **该写的**：能做什么（能力清单）、怎么装、怎么配（配置表）、怎么用（指令表与示例）、出问题怎么办（常见问题、前置条件与限制）
- **不该写的**：实现原理与设计理念、Fetcher/Manager 分层、算法与数据结构、内部调用流程、类名/函数名/文件路径、性能优化手段
- **代码只贴用户要用的最小片段**：安装命令、配置项、指令示例；不贴内部实现代码
- **技术细节翻译成用户语言**：不写「用 `asyncio.gather` 并发查多个密钥」，写「同时查询多个密钥，结果统一汇总」
- 判断标准：使用者只读 README，就能独立完成安装 → 配置 → 使用 → 排障

正反例：

```markdown
- ✅ 支持一次传入多个密钥批量查询余额（需管理员权限）
- ❌ 密钥经 `_extract_keys` 正则提取后由 `_query_and_format` 并发汇总
```

#### 7.2.2 头部表头格式

维护**两个** README（中文 `README.md` + 英文 `README_en.md`），中文版为权威源。表头用 `<div align="center">`，**元素间不留空行**：

**中文版（`README.md`）：**

```html
<div align="center">
<h1>大模型余额查询</h1>
<p><strong>查询各大模型平台余额，支持批量查询多个令牌…</strong></p>
<p><sub>余额查询 &nbsp;&nbsp; 多平台 &nbsp;&nbsp; 模型测试</sub></p>
<p><strong>中文</strong> &nbsp;/&nbsp; <a href="README_en.md">English</a></p>
</div>
```

**英文版（`README_en.md`）：**

```html
<div align="center">
<h1>LLM Balance</h1>
<p><strong>Query balances across major LLM platforms…</strong></p>
<p><sub>balance &nbsp;&nbsp; multi-platform &nbsp;&nbsp; model testing</sub></p>
<p><a href="README.md">中文</a> &nbsp;/&nbsp; <strong>English</strong></p>
</div>
```

命名规则：

- **中文版 h1** = `metadata.yaml` 的 `display_name`（`大模型余额查询`）
- **英文版 h1** = 插件名 `astrbot_plugin_llm_balance` 中 `llm_balance` 部分按词拆分后首字母大写（`LLM` 视为缩略词全大写）→ `LLM Balance`
- **desc**：中文版取 `metadata.yaml` 的 `desc`；英文版做地道翻译，禁止逐字机翻
- **tags**：取 `metadata.yaml` 的 `tags`，用 `&nbsp;&nbsp;` 分隔；英文版用英文标签
- 语言切换链接互相指向对方文件

#### 7.2.3 正文四大板块

| 板块 | 内容 | 说明 |
|------|------|------|
| **一、功能/介绍** | 功能介绍、特性列表、用户使用场景、截图/演示 | 独立板块 |
| **二、指令** | 命令表格（命令、权限、说明）、使用示例 | 独立板块 |
| **三、配置** | 配置项表格（配置项、类型、默认值、说明） | 独立板块 |
| **四、其它** | 安装、快速开始、运行环境与依赖要求、贡献指南、常见问题、许可证、鸣谢 | 兜底区域，安装/快速开始放最前 |

- **板块一/板块四只写用户视角**：写「运行环境与依赖要求」而非框架选型理由、内部架构
- 更新后通读一遍 README，确保与新行为一致（示例、默认值、超时说明等）

#### 7.2.4 何时必须更新 README

| 改动类型 | 必须更新的板块 |
|----------|--------------|
| 功能新增/删除 | 一、功能/介绍 |
| 使用方式/命令变化 | 二、指令 |
| 配置项变化 | 三、配置 |
| 依赖/版本要求变化 | 四、其它（安装/依赖部分） |
| 已知问题/行为变化 | 四、其它（常见问题部分） |

**何时不需要更新 README**：纯内部重构（行为完全不变）、样式调整、不改变用户可见行为的 bug 修复。

#### 7.2.5 双语文档同步

- **中文为主（单向同步）**：中文版是权威版本（源），所有改动**先落中文版，再从中文同步到英文版**；**禁止反向**，禁止用英文版覆盖中文版
- 章节结构两文件保持一致，新增章节两个文件都要加
- 中文版用自然中文，英文版用地道英文，**禁止**逐字机翻、禁止半翻译残留
- 修改时逐条 diff，确保无内容遗漏或错位

#### 7.2.6 格式与多会话约束

- **禁止无意义的换行**：HTML 头部区块内元素间不留空行；正文一段文字保持一行（不要人为软换行），空行只用于分隔标题、表格、列表、代码块等结构性区块
- **多会话约束**：更新前必须先读当前内容，保留其他会话已写入的记录，只追加/修改自己的部分，**严禁整文件覆盖**

### 7.3 注释规范

- **注释只写 non-obvious reason**（解释「为什么」，不解释「做了什么」）
  - 坏：`# 设置超时时间为30秒`
  - 好：`# 30 秒超时，因为上游 API 的 SLA 承诺 P99 为 25 秒`
- **禁止残留 intermediate attempts**：不保留被注释掉的旧代码、未完成 TODO、调试输出
- 方法级 docstring 用中文说明用途/参数/返回（仅对用途足够明显的 `_` 私有方法可省略）
- 代码分区用 `# ==================== 分区名 ====================` 分隔条

### 7.4 PR 描述规范

- 提交信息/PR 描述只写最终行为，不写尝试过程与被否定的方案
- 禁止提及从未合入的中间状态与废弃设计
- 只写 diff 里看不出来的取舍理由

## 8. 提交与发布流程

### 8.1 提交规范

- 提交信息遵循 **Conventional Commits**：`<type>(<scope>): <中文短句式 subject>`（如 `feat: 新增 API 连接缩写映射配置`、`fix: 余额不足提示改为显示具体余额`）
- 历史提交（v1.4.x 及更早）为「`vX.Y.Z` + 中文短句」风格，本规范生效后按 Conventional Commits 书写
- **禁止**将未完成功能、多轮迭代的中间状态、被废弃方案写进提交信息
- **提交前必须先向用户展示，等用户确认后再执行 commit**，展示内容缺一不可：
  - 待提交文件清单
  - 改动概要（如 `git diff --stat`）
  - **提交标题，尽量给 2–3 个候选**（同一改动的不同侧重点：做了什么 / 为什么改 / 是否带 scope），逐条注明侧重供用户挑选并标出推荐项；确实只有一种合理写法时才只给一个
  - 用户选定标题（或自拟）后才 commit；涉及推送时另附提交 hash、提交信息、目标分支与改动概要
- 推荐顺序：完成功能代码 → 验证 → 更新 CHANGELOG 与 README → 提交
- 文档更新与代码改动**在同一提交中完成**（不单独拆「补文档」提交）
- 只有用户明确要求时才 commit / push
- **授权一次性，不延续**（「上一轮说过推送」≠ 本轮可以提交）：
  - 用户的确认**只对当次动作生效**；下一次改动必须重新展示改动内容与提交标题，重新确认
  - 展示后改动内容又变了（用户提了新要求、你又改了文件，哪怕只改一行），**原确认立即失效**，必须重新展示并再次确认
  - 下列情形**都不算授权**：上一轮 / 上一个任务 / 上一个会话说过「提交」「推送」；会话恢复（resume / fork）后继承的历史授权；用户对功能或代码表示满意；用户正在讨论其它需求；用户未回复
  - 授权范围逐项独立：确认 commit ≠ 授权 push；确认推送某分支 ≠ 授权后续继续提交或推送；确认一个 commit ≠ 授权 `--amend` 或追加提交
  - 执行前自检：能指出用户**本轮**对**本次改动**的明确同意原话；指不出来就先问，不要执行

### 8.2 版本号规范

- 采用 **SemVer**：新功能 → `minor` 递增；bug 修复/小改进 → `patch` 递增
- **只在准备发布时递增**（规则见 7.1）：单个功能/修复提交不碰版本号；一次发版汇总多个独立提交、合并到指定版本时才确认版本号
- 发版一致性：`metadata.yaml` version = `CHANGELOG.md` 新版本段号 = `git tag vX.Y.Z`，tag 推送同样需用户确认
- README / i18n 中出现版本字样属辅助位置，发版时一并同步（当前两个 README 无版本字样）

### 8.3 测试与验证（本仓库实际流程）

- **语法自检**：`python3 -m py_compile main.py`，通过后继续
- **本地逻辑验证**（可选）：stub `astrbot` 模块（sys.modules 注入 filter.command 装饰器 / AstrMessageEvent / Star 基类 / logger / AstrBotConfig）+ 本地 mock HTTP 服务器验证查询/测试逻辑
- **部署同步**：`rsync -a --delete --exclude=.git --exclude=.notes --exclude='__pycache__' --exclude='*.pyc' SRC/ DST/`，随后 `diff -rq --exclude=.git --exclude=__pycache__ --exclude=.notes SRC DST` 确认无差异
  - SRC = `/vol1/@appdata/deepseek.harness/home/astrbot_plugin/astrbot_plugin_llm_balance`
  - DST = `/vol1/1000/Docker/AstrBot/data/plugins/astrbot_plugin_llm_balance`（容器 `astrbot` 挂载，容器内路径 `/AstrBot/data/plugins/...`）
- **热重载**：`docker exec astrbot python3` 读取 `/AstrBot/data/cmd_config.json`（utf-8-sig）签发 JWT（`dashboard.username` + `dashboard.jwt_secret`，HS256，exp 7 天），`curl -X POST http://127.0.0.1:6185/api/v1/plugins/astrbot_plugin_llm_balance/reload -H "Authorization: Bearer $TOKEN"`，期望返回 `{"status":"ok","message":"重载成功。"}`
- **日志检查**：`docker logs astrbot --since 20s`，确认出现 `Loading plugin astrbot_plugin_llm_balance` 且无 `error`/`traceback`（日志含 ANSI 色码时用 `sed 's/\x1b\[[0-9;]*m//g'` 清洗）
- 纯文档改动（README/CHANGELOG）只需 rsync 同步，不需要热重载

## 9. 最终检查清单（每次任务完成前）

- [ ] 架构：单文件分层，新方法/新 Fetcher 放入既有分区，分区顺序稳定，未引入新目录
- [ ] 命名：模块常量 UPPER_SNAKE、私有方法 `_` 前缀、Fetcher 类 `XxxFetcher`、命令 handler 语义名
- [ ] 注释：只写 non-obvious reason，无残留中间状态、无被注释掉的旧代码
- [ ] 日志：`[astrbot_plugin_llm_balance]` 前缀，异常分类记录，无空 catch
- [ ] 权限：管理命令开头 `_is_admin` 检查
- [ ] 配置：新增配置项已在 `_conf_schema.json` 和代码中同步，文档按「中文名（`key`）」写法引用
- [ ] CHANGELOG：`[Unreleased]` 已追加条目（分组式），**只写相对上一版的变化**、同一变化已合并为一条，条目面向用户（无内部实现细节），保留了他人既有记录
- [ ] README：按 7.2.4 判定是否需更新；需更新时中文版先行并同步英文版，且面向用户书写（无实现原理与内部细节）
- [ ] 版本号：日常任务不递增版本号；仅发版任务改 `metadata.yaml` 的 `version`（与 CHANGELOG 新版本段、tag 一致）
- [ ] 提交信息：Conventional Commits 格式（`type: 中文短句式`），只描述最终行为
- [ ] 提交前展示：已给出待提交文件清单、`git diff --stat`、2–3 个候选提交标题（逐条注明侧重并标出推荐项），并取得用户对本次改动的明确确认（一次性授权，未沿用上一轮）
- [ ] 本地测试：`python3 -m py_compile main.py` 通过
- [ ] 部署：rsync 同步 + diff 无差异；代码改动已热重载并查日志确认无 error
