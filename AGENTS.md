# AGENTS.md — astrbot_plugin_llm_balance 工作说明书

> 本文件是任何 AI 编码代理（agent）进入 **astrbot_plugin_llm_balance** 仓库时的**必读**工作说明书。
> 它约定本插件的架构、代码规范、文档维护规则、部署与热重载流程。任何对代码、配置、行为的改动，都必须同时遵守本文档的规则。
>
> 本文件由通用模板 `agent-templates/templates/astrbot-plugin/AGENTS.md` 对齐而来，结构与其保持一致，内容按本仓库实际情况本地化。

---

## 1. 项目概览

**插件功能**：AstrBot 插件，支持多平台（DeepSeek / OpenAI / New API 等）大模型余额查询与 OpenAI 兼容端点模型可用性测试。基于 `astrbot.api.star` 框架，以 `Star` 子类为核心，通过装饰器注册命令，在 AstrBot 运行时中加载。

核心文件清单：

| 文件 | 必选 | 职责 |
|------|------|------|
| `main.py` | ✅ | 插件主体（单文件，约 1500 行，全部后端逻辑） |
| `metadata.yaml` | ✅ | 插件元数据（name/version/author/desc/tags/repo） |
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
├── metadata.yaml       # 插件元数据
├── _conf_schema.json   # 配置 Schema
├── CHANGELOG.md        # 变更日志（分组式）
├── README.md           # 中文文档（权威源）
├── README_en.md        # 英文文档（跟随中文）
├── AGENTS.md           # 本工作说明书
├── LICENSE
├── logo.png
```

### 2.2 架构倾向

**单文件风格**（当前已约 1500 行，接近模板 1500 行边界，仍保持单文件，不拆分）：

- 所有逻辑在 `main.py`，通过 `# ---- 分区名 ----` 分隔条组织。现有分区大致顺序：模块常量（NON_CHAT_HINTS / CHAT_KEY_HINTS）→ dataclass（BalanceResult / ModelTestResult）→ 配置与工具方法 → 查询实现（`_query_*`）→ 命令 handler（`balance` / `test_model`）→ 生命周期
- 新增方法按职责放入对应分区，保持分区顺序稳定

## 3. 技术栈与依赖

- **Python 3.10+**（AstrBot 4.x 最低要求）
- **AstrBot API**：`astrbot.api.star`（register, Star, Context）、`astrbot.api.event`（filter, AstrMessageEvent）、`astrbot.api`（logger, AstrBotConfig）
- **运行时依赖**：aiohttp（AstrBot 自带，顶层 import）
- **禁止引入**：不引入与原功能无关的依赖；不新增 `requirements.txt` 声明

## 4. 核心代码规范

### 4.1 插件骨架

```python
import time
from dataclasses import dataclass, field

import aiohttp

from astrbot.api.star import register, Star, Context
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api import AstrBotConfig, logger

@register("astrbot_plugin_llm_balance", "XTsat", "多平台大模型余额查询与模型可用性测试", "v1.4.0")
class LLMBalancePlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig) -> None:
        super().__init__(context)
        self.config = config
```

### 4.2 命名约定

| 元素 | 本仓库约定 |
|------|------------|
| 模块级常量 | `UPPER_SNAKE`（`NON_CHAT_HINTS`、`CHAT_KEY_HINTS`） |
| 私有方法 | `_` 前缀 + `snake_case`（`_query_all`、`_mask_key`、`_short_error`、`_pick_chat_models`） |
| 命令 handler | **语义名直名**（`balance`、`test_model`），不强制 `cmd_` 前缀——与既有代码一致，避免命令名与函数名强行耦合 |
| 类名 | `PascalCase`（`LLMBalancePlugin`） |
| 文件名 | `snake_case` |

### 4.3 类型与语法

- Python 3.10+ 现代联合类型写法（`dict | None`、`list[str]`）
- 函数签名**必须完整类型注解**（参数 + 返回类型）；`yield` 返回结果的命令方法标注返回类型与既有风格一致
- 禁止 `Any` 作为类型注解（除非调用方签名强制要求）
- 禁止 `# type: ignore`

### 4.4 注释规范

见第 7 章 [7.3 注释规范](#73-注释规范)。

### 4.5 日志

- 统一 `logger.info/warning/error`，**必须带 `[astrbot_plugin_llm_balance]` 前缀**
- 错误信息带 emoji 前缀（`❌`、`⚠️`）
- 精确捕获异常类型（`asyncio.TimeoutError`、`aiohttp.ClientError`），禁止空 `except: pass`

### 4.6 错误处理与防御性编程

- 外部 HTTP IO 必须 try/except 并记录日志，**不允许静默吞异常**
- API 响应错误提取用 `_short_error(resp)`（取 error.message/message 前 150 字符）与 `_safe_resp_text(resp)`
- 降级链路清晰：成功结果 → 部分失败提示（`⚠️ 另有模型不可用: ...`）→ 明确报错文案
- 配置值防御式校验（`self.config.get(k, 默认值)` 合并只保留已知字段）

### 4.7 并发

- 异步方法使用 `async/await`，**禁止阻塞事件循环**
- 多密钥/多模型并发用 `asyncio.gather`；HTTP 请求全部带超时（models 探测 10s、chat 实测 20s），禁止无限等待
- 单请求失败不影响其它请求，最后统一分组汇总

### 4.8 回复消息

- 统一 `yield event.plain_result(...)`
- 用户可读输出用中文 + emoji 图标风格（🟢/🔴/✅/⚠️/🔑/🧠/🎯）
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

- 配置项定义在 `_conf_schema.json`；新增配置项 → 先补 schema，再在代码中实现读写
- 读取模式：`{k: self.config.get(k, v) for k, v in DEFAULT_SETTINGS.items()}` 合并已知字段
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

### 6.2 命令 handler 内部解析约定（两个 handler 共用模式）

1. `full_text = event.message_str.strip()`，去掉前导 `/`
2. 依次剥命令前缀（中英都支持）：`for cmd in ("余额", "balance"): if full_text.startswith(cmd): full_text = full_text[len(cmd):].strip(); break`
3. `split(maxsplit=1)` 拆出首参数与剩余参数，按子命令分派

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
| `/测试 <API网址> <key1> [key2]... <模型名>` | 管理员 | 指定模型模式：末尾非 `sk-` 参数即模型名，直接实测（不在模型列表也硬测） |

## 7. 文档维护规范（强制，不可省略）

> 本项目的**硬性要求**：任何改动在合并前，必须同步维护 `README.md`、`README_en.md` 与 `CHANGELOG.md`。未同步文档 = 任务未完成。

### 7.1 CHANGELOG 维护

- 日常改动先记在 `## [Unreleased]` 段（顶部固定）；**发版时**再移动到带版本号的新段
- 多个不相关改动各自独立记入 `[Unreleased]`，**不要**合并为一条
- **发版日期**：版本段日期 `(YYYY-MM-DD)` 填**发版当天**系统日期
- 统一**分组式**：`### 新增 / 修复 / 变更 / 移除 / 性能`（只保留有内容的分类），条目格式「`- **标题**：说明`」
- 版本号三处联动：`metadata.yaml` version、`CHANGELOG.md` 版本段、README 版本徽章（如有）
- **更新前必须先读取当前文件内容**，识别并保留其他会话已写入的条目（含 `[Unreleased]` 下未提交内容），只追加自己的条目，**严禁整文件覆盖或删除他人记录**

### 7.2 README 维护

- 维护**两个** README（`README.md` 中文 + `README_en.md` 英文），**中文版为权威版本（源）**：改动**先落中文版、再同步英文版**；**禁止反向**，禁止用英文版覆盖中文版
- 头部 `<div align="center">` 表头（元素间不留空行）：中文 h1 = `大模型余额查询`；英文 h1 = `LLM Balance`；desc 取自 `metadata.yaml`；tags 用 `&nbsp;&nbsp;` 分隔；语言切换链接互相指向对方文件
- 正文四大板块：一、功能/介绍；二、指令；三、配置；四、其它（安装/快速开始放最前）
- 命令变化 → 更新二、指令板块；功能变化 → 更新一；配置变化 → 更新三；行为/依赖变化 → 更新四
- 章节结构两文件保持一致；英文版用地道英文，禁止逐字机翻、禁止半翻译残留
- **多会话约束**：更新前先读当前内容，保留他人记录，严禁整文件覆盖

### 7.3 注释规范

- **注释只写 non-obvious reason**（解释「为什么」，不解释「做了什么」）
- **禁止残留 intermediate attempts**：不保留被注释掉的旧代码、未完成 TODO、调试输出
- 方法级 docstring 用中文说明用途/参数/返回（`_` 开头私有方法用途足够明显时可省略）
- 代码分区用 `# ---- 分区名 ----` 分隔条

### 7.4 提交信息描述规范

- 提交信息/PR 描述只写最终行为，不写尝试过程与被否定的方案
- 只写 diff 看不出来的取舍理由

## 8. 提交与发布流程

### 8.1 提交规范

- **提交信息用中文短句式**，与历史风格一致（如 `v1.4.0 新增 /测试 命令测试 OpenAI 兼容端点的模型可用性`、`对齐 agent-templates 插件规范...`）
- **禁止**将未完成功能、中间状态、被废弃方案写进提交信息
- **提交前必须先向用户展示改动内容和提交标题**，等用户确认后再执行 commit
- 推荐顺序：完成功能代码 → 验证 → 更新 CHANGELOG 与 README → 提交
- 文档更新与代码改动**在同一提交中完成**
- 只有用户明确要求时才 commit / push

### 8.2 版本号规范

- **SemVer**：新功能 → minor 递增；bug 修复/小改进 → patch 递增
- `metadata.yaml` version 与 `CHANGELOG.md` 最新版本必须一致
- 发版时打 `git tag vX.Y.Z`，tag 推送同样需用户确认

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

- [ ] 架构：单文件风格，新方法放入既有分区，分区顺序稳定
- [ ] 命名：模块常量 UPPER_SNAKE、私有方法 `_` 前缀、命令 handler 语义名
- [ ] 注释：只写 non-obvious reason，无残留中间状态、无被注释掉的旧代码
- [ ] 日志：`[astrbot_plugin_llm_balance]` 前缀，异常分类记录，无空 catch
- [ ] 权限：管理命令开头 `_is_admin` 检查
- [ ] CHANGELOG：`[Unreleased]` 已追加条目（分组式），保留他人既有记录
- [ ] README：涉及用户可见变更时中文版已更新并同步英文版
- [ ] 版本号：`metadata.yaml` 与 `CHANGELOG` 最新版本一致
- [ ] 配置：新增配置项已在 `_conf_schema.json` 和代码中同步
- [ ] 提交信息：中文短句式，只描述最终行为，提交前已向用户展示
- [ ] 本地测试：`python3 -m py_compile main.py` 通过
- [ ] 部署：rsync 同步 + diff 无差异；代码改动已热重载并查日志确认无 error
