# astrbot_plugin_llm_balance

AstrBot 多平台 LLM 余额查询插件。支持查询 DeepSeek、硅基流动、Moonshot、OpenAI、ChatAnywhere、NEW API 等平台的余额/用量。

## 功能

- 查询当前会话使用的模型余额
- 查询所有已配置模型的余额（自动去重，并发查询）
- 按平台名/简写查询指定平台余额
- 支持在命令后直接传入 API Key 查询（无需配置）
- 可自定义平台别名（同时用于命令匹配和 Provider 识别）
- 支持管理员权限控制

## 使用方法

```
/余额                    # 显示帮助
/余额 当前               # 查询当前会话使用的模型余额
/余额 所有               # 查询所有已配置模型的余额
/余额 <平台简写>          # 查询指定平台（AstrBot 配置中的）的余额
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

在 AstrBot 管理面板中可配置：

- **admin_only**：是否仅管理员可用（默认关闭）
- **newapi_base_url**：NEW API 中转站基地址
- **request_timeout**：API 请求超时时间（秒）
- **platform_aliases**：各平台的别名列表，多个用逗号分隔，同时用于命令匹配和 Provider 自动识别

## 安全提醒

包含 API 密钥的查询建议私聊使用，避免在群聊中泄露密钥。
