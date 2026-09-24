<div align="center">
<h1>大模型余额查询</h1>
<p><strong>查询各大模型平台余额，支持批量查询多个令牌，支持查询 Astrbot 内置的端点、传递平台或传递 API 端点、自定义的 NewAPI 站点；支持测试 OpenAI 兼容端点的模型可用性</strong></p>
<p><sub>余额查询 &nbsp;&nbsp; 多平台 &nbsp;&nbsp; 模型测试</sub></p>
<p><strong>中文</strong> &nbsp;/&nbsp; <a href="README_en.md">English</a></p>
</div>

## 功能

- 查询当前会话使用的模型余额
- 查询所有已配置模型的余额（自动去重，并发查询）
- 按平台简写查询指定平台余额（支持多密钥）
- 命令后直接传 API Key 查询（无需在 AstrBot 中配置）
- 批量查询多个 API Key（自动识别 `sk-` 开头的令牌）
- 自定义 API 端点余额查询（支持 OpenAI Billing 与 New API 兼容端点）
- 测试 OpenAI 兼容端点的模型可用性（列出模型并实测调用）
- 可自定义平台别名（用于命令匹配和 Provider 自动识别）
- 管理员权限控制
- 完全可自定义的输出模板（成功/失败/标题/分隔符）
- NEW API 多实例支持（多个中转站）

## 使用方法

```
/余额                               # 显示帮助
/余额 当前                          # 查询当前会话使用的模型余额
/余额 所有                          # 查询所有已配置模型的余额
/余额 <平台简写>                     # 查询指定 AstrBot 配置平台的余额
/余额 <平台简写> <key1> [key2]...   # 批量查询指定平台的多个密钥余额
/余额 <API端口> <key1> [key2]...   # 查询自定义 API 端点的余额（自动识别 OpenAI/New API）
/余额 <JSON配置>                    # 直接粘贴 NewAPI 复制连接信息查询余额
/测试 <API网址> <key1> [key2]... # 测试 OpenAI 兼容端点的模型可用性
```

英文别名：`/余额` = `/balance`，`/测试` = `/test`；子命令：当前 = current，所有 = all，帮助 = help。

## 支持的平台

| 平台 | 别名 |
|---|---|
| DeepSeek（深度求索） | `deepseek` / `ds` / `深度求索` |
| 硅基流动 | `siliconflow` / `siliconcloud` / `sc` / `硅基` / `硅基流动` |
| Moonshot（Kimi） | `moonshot.cn` / `moonshot` / `kimi` / `月之暗面` |
| OpenAI | `openai.com` / `openai` / `gpt` / `chatgpt` |
| ChatAnywhere | `chatanywhere` / `ca` |
| NEW API | `newapi` / `中转` / `new` |

别名可在插件配置中自定义。

## 配置项

### 基础设置

| 配置 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `admin_only` | bool | `false` | 仅管理员可用 |
| `output_language` | string | `auto` | 输出语言：`auto`（按指令语言自动切换）/ `zh`（强制中文）/ `en`（强制英文） |
| `newapi_base_url` | text | 空 | NEW API 中转站地址，每行一个 |
| `request_timeout` | float | `10.0` | 请求超时（秒） |
| `show_unsupported` | bool | `true` | `/余额 所有` 中显示未适配平台 |
| `platform_aliases` | object | — | 各平台别名，逗号分隔 |
| `platform_names` | list | — | API 连接缩写映射：每项 `API连接地址=缩写1,缩写2`（一个连接可配多个缩写，逗号分隔，可添加多行）；输出中的连接地址自动替换为第一个缩写，`/余额` 与 `/测试` 的网址参数可用任一缩写代替 |

### 输出模板

所有模板均支持 `\n` 换行和以下变量：

| 变量 | 说明 | 用于 |
|---|---|---|
| `{{api_key}}` | 脱敏后的 API 密钥 | 成功 / 失败 |
| `{{source_name}}` | 平台名称（如 DeepSeek） | 成功 / 失败 |
| `{{error}}` | 错误信息 | 失败 |
| `{{currency}}` | 币种（如 CNY / USD） | 成功 |
| `{{balance}}` | 智能余额（剩余≠总额时显示剩余） | 成功 |
| `{{total_balance}}` | 总额 | 成功 |
| `{{remaining_balance}}` | 剩余余额 | 成功 |
| `{{used_balance}}` | 已用额度 | 成功 |
| `{{raw_info}}` | 备注信息（赠送/充值详情等） | 成功 |
| `{{smart_balance}}` | 智能附加信息（自动隐藏无意义行） | 成功 |
| `{{?变量}}` | 条件变量，值为空或 `0` 时隐藏整行 | 成功 |

#### success_template — 成功查询

默认值：
```
🟢 **{{source_name}}**
  🔑 密钥: {{api_key}}
  💵 {{balance}} {{currency}}
{{smart_balance}}
```

#### error_template — 失败查询

默认值：
```
🔴 **{{source_name}}**
  🔑 密钥: {{api_key}}
  ❌ {{error}}
```

#### header_template — 标题

默认值：`💰 **{{title}}**` （变量：`{{title}}`）

#### separator_template — 标题分隔符

标题与内容之间。默认值：`════════════════════════════════════════`

#### item_separator_template — 项间分隔符

同区块内多条结果之间，留空则为空行。默认值：空

#### section_separator_template — 区块分隔符

成功/失败/未适配区块之间。默认值：`════════════════════════════════════════`

## 自定义 API 端点查询

支持查询未在预置列表中的 API 中转站余额。命令以 `http://` 或 `https://` 开头时自动进入自定义端点模式：

```
/余额 https://your-api.com/v1 sk-xxxx1 sk-xxxx2
```

查询流程自动降级：
1. **优先**尝试 OpenAI Billing API（`/v1/dashboard/billing/subscription` + `/usage`）
2. **降级**尝试 New API 格式（`/api/usage/token`）

适用于 one-api、new-api、AIProxy 等各类中转站。

## 测试模型可用性

使用 `/测试` 命令测试任意 OpenAI 兼容端点的模型是否可用。命令格式与自定义端点余额查询一致：`指令 + 网址 + API Key`，末尾可**指定模型名**。

```
/测试 https://api.example.com/v1 sk-xxxx
/测试 https://api.example.com sk-xxxx1 sk-xxxx2
/测试 https://api.example.com sk-xxxx deepseek-chat
/测试 https://api.example.com sk-xxxx1 sk-xxxx2 glm-4-flash
```

测试流程：
1. 请求 `/v1/models` 拉取可用模型列表（同时验证 API Key 是否有效）
2. **未指定模型名**：自动挑选聊天/生成类模型，**最多实测前 3 个**（遇失败即停），实测调用 `/v1/chat/completions`（`max_tokens=1`）
3. **指定模型名**（最后一个非 `sk-` 参数）：直接实测该模型；即使它不在模型列表中、甚至 `/v1/models` 接口不可用也会硬测
4. 返回连接状态、响应延迟、可用模型列表和实测结果

输出示例：

```
💰 **https://api.example.com 模型测试**
════════════════════════════════════════
🟢 **https://api.example.com**
  🔑 密钥: sk-abc***
  ✅ 连接成功 · 响应 350ms (HTTP 200)
  🧠 可用模型 3: deepseek-chat、deepseek-reasoner、deepseek-coder
  🎯 测试模型: deepseek-chat ✅ 可用
```

支持多个密钥并发测试，结果按成功/失败分组展示。

## 批量查询

在平台简写或 API 端点后跟多个以 `sk-` 开头的密钥，自动识别并并发查询：

```
/余额 ds sk-xxx1 sk-xxx2 sk-xxx3
/余额 https://api.example.com/v1 sk-xxx1 sk-xxx2
```

查询结果按成功/失败分组展示。

## 粘贴 NewAPI 连接信息

在 NewAPI 面板中复制连接信息后，直接粘贴到 `/余额` 后面即可查询：

```
/余额 {"_type":"newapi_channel_conn","key":"sk-xxx","url":"https://new.xinjianya.top"}
```

插件自动解析 JSON 中的 key 和 url 并用 NewAPI 格式查询余额。

## NEW API 多实例

在 `newapi_base_url` 中每行一个地址：

```
http://192.168.1.1:3000
http://192.168.1.2:3000
```

插件为每个地址匹配对应 Provider 的密钥并分别查询。

## 安全提醒

包含 API 密钥的查询建议私聊使用，避免在群聊中泄露。
