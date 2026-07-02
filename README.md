# astrbot_plugin_llm_balance

AstrBot 多平台 LLM 余额查询插件。支持查询 DeepSeek、硅基流动、Moonshot、OpenAI、ChatAnywhere、NEW API 等平台的余额/用量。

## 功能

- 查询当前会话使用的模型余额
- 查询所有已配置模型的余额（自动去重，并发查询）
- 按平台名/简写查询指定平台余额，支持多密钥
- 支持在命令后直接传入 API Key 查询（无需在 AstrBot 配置）
- 可自定义平台别名（同时用于命令匹配和 Provider 自动识别）
- 支持管理员权限控制
- 完全可自定义的输出模板（成功/失败/标题/分隔符）
- NEW API 多实例支持（多个中转站）

## 使用方法

```
/余额                    # 显示帮助
/余额 当前               # 查询当前会话使用的模型余额
/余额 所有               # 查询所有已配置模型的余额
/余额 <平台简写>          # 查询指定 AstrBot 配置平台的余额
/余额 <平台简写> <API密钥> # 直接用指定密钥查询该平台余额
```

## 支持的平台

| 平台 | 默认别名 |
|---|---|
| DeepSeek（深度求索） | `deepseek` / `ds` / `深度求索` |
| 硅基流动 | `siliconflow` / `siliconcloud` / `硅基` / `硅基流动` |
| Moonshot（Kimi） | `moonshot.cn` / `moonshot` / `kimi` / `月之暗面` |
| OpenAI | `openai.com` / `openai` / `gpt` / `chatgpt` |
| ChatAnywhere | `chatanywhere` / `ca` |
| NEW API | `newapi` / `中转` |

## 配置项

### 基础设置

| 配置 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `admin_only` | bool | `false` | 是否仅管理员可用 |
| `newapi_base_url` | text | 空 | NEW API 中转站地址，每行一个，支持多个 |
| `request_timeout` | float | `10.0` | API 请求超时时间（秒） |
| `show_unsupported` | bool | `true` | /余额 所有 中是否显示未适配的平台 |

### 输出模板

插件输出由以下模板控制，全部支持 `\n` 换行：

#### success_template — 成功查询模板

变量：`{{api_key}}` `{{source_name}}` `{{currency}}` `{{balance}}` `{{total_balance}}` `{{remaining_balance}}` `{{used_balance}}` `{{raw_info}}` `{{smart_balance}}`（智能附加信息，仅在有意义时显示）

`{{?变量}}` 语法：值为空或 `0` 时自动隐藏该行。

默认：
```
🟢 **{{source_name}}**
  🔑 密钥: {{api_key}}
  💵 {{balance}} {{currency}}
{{smart_balance}}
```

#### error_template — 失败查询模板

变量：`{{api_key}}` `{{source_name}}` `{{error}}`

默认：
```
🔴 **{{source_name}}**
  🔑 密钥: {{api_key}}
  ❌ {{error}}
```

#### header_template — 标题模板

变量：`{{title}}`

默认：`💰 **{{title}}**`

#### separator_template — 标题分隔符

标题与内容之间的分隔线。默认：`━━━━━━━━━━━━━━`

#### item_separator_template — 项间分隔符

同一区块内多条结果之间的分隔符，留空则为空行。默认：空

#### section_separator_template — 区块分隔符

成功/失败/未适配区块之间的分隔线。默认：`════════════════════`

### 模板变量说明

| 变量 | 说明 |
|---|---|
| `{{api_key}}` | 脱敏后的 API 密钥 |
| `{{source_name}}` | 平台名称（如 DeepSeek） |
| `{{currency}}` | 币种（如 CNY / USD） |
| `{{balance}}` | 智能余额（剩余≠总额时显示剩余） |
| `{{total_balance}}` | 总额 |
| `{{remaining_balance}}` | 剩余余额 |
| `{{used_balance}}` | 已用额度 |
| `{{raw_info}}` | 备注信息（如赠送/充值详情） |
| `{{smart_balance}}` | 智能附加信息（📈 总额 / 📊 已用 / 📝 备注），仅在需要时显示 |
| `{{?变量}}` | 条件变量，值为空或 `0` 时隐藏整行 |

### 平台别名

`platform_aliases`：为每个平台设置别名，多个用逗号分隔，同时用于命令匹配和 Provider 识别。

## NEW API 多实例配置

在 `newapi_base_url` 中每行填写一个中转站地址：

```
http://192.168.1.1:3000
http://192.168.1.2:3000
```

插件会为每个地址找到对应的 Provider 密钥并分别查询。

## 安全提醒

包含 API 密钥的查询建议私聊使用，避免在群聊中泄露。
