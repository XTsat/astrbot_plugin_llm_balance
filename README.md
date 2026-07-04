# astrbot_plugin_llm_balance

AstrBot 多平台 LLM 余额查询插件。支持 DeepSeek、硅基流动、Moonshot、OpenAI、ChatAnywhere、NEW API 等平台。

## 功能

- 查询当前会话使用的模型余额
- 查询所有已配置模型的余额（自动去重，并发查询）
- 按平台简写查询指定平台余额（支持多密钥）
- 命令后直接传 API Key 查询（无需在 AstrBot 中配置）
- 批量查询多个 API Key（自动识别 `sk-` 开头的令牌）
- 自定义 API 端点余额查询（支持 OpenAI Billing 与 New API 兼容端点）
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
/余额 <API端口> <key1> [key2]...    # 查询自定义 API 端点的余额（自动识别 OpenAI/New API）
```

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
| `newapi_base_url` | text | 空 | NEW API 中转站地址，每行一个 |
| `request_timeout` | float | `10.0` | 请求超时（秒） |
| `show_unsupported` | bool | `true` | `/余额 所有` 中显示未适配平台 |
| `platform_aliases` | object | — | 各平台别名，逗号分隔 |

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

## 批量查询

在平台简写或 API 端点后跟多个以 `sk-` 开头的密钥，自动识别并并发查询：

```
/余额 ds sk-xxx1 sk-xxx2 sk-xxx3
/余额 https://api.example.com/v1 sk-xxx1 sk-xxx2
```

查询结果按成功/失败分组展示。

## NEW API 多实例

在 `newapi_base_url` 中每行一个地址：

```
http://192.168.1.1:3000
http://192.168.1.2:3000
```

插件为每个地址匹配对应 Provider 的密钥并分别查询。

## 安全提醒

包含 API 密钥的查询建议私聊使用，避免在群聊中泄露。
