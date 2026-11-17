<div align="center">
<h1>大模型余额查询与测试</h1>
<p><strong>查询各大模型平台余额，支持多令牌批量查询与自定义中转站；并可测试 OpenAI 兼容端点的模型可用性</strong></p>
<p><sub>余额查询 &nbsp;&nbsp; 多平台 &nbsp;&nbsp; 模型测试</sub></p>
<p><strong>中文</strong> &nbsp;/&nbsp; <a href="README_en.md">English</a></p>
</div>

## 功能

- 查询当前会话使用的模型余额，或一次性查询所有已配置模型的余额（自动去重、并发查询）
- 按平台简写查询指定平台余额，支持一次传多个密钥批量查询（不要求 `sk-` 前缀，可用 `key:` 强制指定）
- 查询任意 API 端点的余额：内置平台走专用接口，未适配平台自动按 OpenAI Billing / New API 两种通用接口探测，都查不到才提示不支持
- 测试 OpenAI 兼容端点的模型可用性（列出模型并实测调用，可一次测多个密钥、指定模型）
- 粘贴 NewAPI 连接信息 JSON 或引用一条含网址与密钥的消息，即可直接查询/测试，无需手动拆分
- 自定义平台别名（同时用于命令匹配与端点地址），可自由增删改
- 完全可自定义的输出模板（成功/失败/标题/分隔符），支持中英文输出
- 管理员权限控制

## 使用方法

两条命令接受相同的参数：`<平台简写>` 或 `<API网址>` 二选一，后跟密钥（`/测试` 末尾还可加模型名）。

```
/余额                               # 显示帮助
/余额 当前 | /余额 所有              # 查当前会话 / 全部已配置模型的余额
/余额 <平台简写>                     # 查指定平台余额（用你在 AstrBot 里配置的 provider）
/余额 <平台简写|API网址> <key1> [key2]...  # 用指定密钥批量查余额
/测试 <平台简写|API网址> <key1> [key2]... [模型名]  # 实测模型可用性
/余额|/测试 <NewAPI连接信息JSON> [...]  # 粘贴连接信息，自动取其中的网址与密钥
```

英文别名：`/余额` = `/balance`，`/测试` = `/test`；子命令：当前 = current，所有 = all，帮助 = help。

## 支持的平台

| 平台 | 可用简写 |
|---|---|
| DeepSeek（深度求索） | `deepseek` / `ds` / `深度求索` |
| 硅基流动 | `siliconflow` / `sc` / `硅基` / `硅基流动` / `sc-cn` / `硅基cn` |
| Moonshot（Kimi） | `moonshot` / `kimi` / `月之暗面` |
| OpenAI | `openai` / `gpt` / `chatgpt` |
| ChatAnywhere | `chatanywhere` |
| NEW API | `newapi` |

简写来自配置项 `platform_names`，`/余额` 与 `/测试` 共用同一份配置，可自由增删改。没有固定域名的平台（ChatAnywhere、NEW API）只能用它自己的平台名。

## 配置项

### 基础设置

| 配置 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `admin_only` | bool | `false` | 仅管理员可用 |
| `output_language` | string | `auto` | 输出语言：`auto`（按指令语言自动切换）/ `zh`（强制中文）/ `en`（强制英文） |
| `newapi_base_url` | text | 空 | NEW API 中转站地址，每行一个；多个实例时用于 `/余额 newapi` 聚合查询 |
| `openai_admin_key` | string | 空 | OpenAI 官方 Admin Key（`sk-admin-` 开头，可选）：填写后查询 OpenAI 官方端点会显示**本月累计花费**（官方无余额接口，此项为花费而非剩余额度） |
| `request_timeout` | float | `10.0` | 请求超时（秒） |
| `show_unsupported` | bool | `true` | `/余额 所有` 中显示未适配平台 |
| `platform_names` | list | 预置 5 条常用平台 | API 连接与平台简写映射：每项 `API连接地址=缩写1,缩写2`（一个连接可配多个缩写，逗号分隔，可添加多行）。缩写同时用于 `/余额 <简写>` 与 `/测试 <简写>`，输出中的连接地址也会替换为第一个缩写。默认预置 DeepSeek / 硅基流动 / Moonshot / OpenAI，地址与缩写都可自由修改或删除 |

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

<details>
<summary>各模板的默认值（7 项）</summary>

**成功模板（`success_template`）**

```
🟢 **{{source_name}}**
  🔑 密钥: {{api_key}}
  💵 {{balance}} {{currency}}
{{smart_balance}}
```

**失败模板（`error_template`）**

```
🔴 **{{source_name}}**
  🔑 密钥: {{api_key}}
  ❌ {{error}}
```

- 标题模板（`header_template`）：`💰 **{{title}}**`（变量：`{{title}}`）
- 标题分隔符（`separator_template`）：`════════════════════════════════════════`（标题与内容之间）
- 项间分隔符（`item_separator_template`）：空（同区块内多条结果之间，留空则为空行）
- 区块分隔符（`section_separator_template`）：`════════════════════════════════════════`（成功/失败/未适配区块之间）

</details>

## 用法示例

### 平台简写与自定义端点

```
/余额 ds sk-xxxx        # 查 DeepSeek 余额
/测试 ds sk-xxxx        # 测 DeepSeek 模型可用性
/测试 kimi sk-xxxx      # Moonshot
/测试 openai sk-xxxx    # OpenAI 官方
/余额 https://your-api.com/v1 sk-xxxx1 sk-xxxx2
/测试 https://your-api.com/v1 sk-xxxx1 sk-xxxx2 deepseek-chat
```

想测自己的中转站，把 `platform_names` 里对应行的地址换掉即可，例如 `https://my-relay.com=ds`，之后 `/测试 ds sk-xxx` 就测这个中转站。删掉某一行后，该缩写不再可用（`/余额` 仍可用平台名如 `deepseek` 查询已配置的 provider）。

> 注意：`/余额 <简写>` 优先查你在 AstrBot 里为该平台配置的 provider（走中转站就查中转站）；只有写完整网址时才按网址查询。

### 批量查询

在平台简写或 API 端点后跟多个密钥，自动识别并并发查询，结果按成功/失败分组展示：

```
/余额 ds sk-xxx1 sk-xxx2 sk-xxx3
/余额 https://api.example.com/v1 sk-xxx1 sk-xxx2
```

含特殊字符或过短的密钥写成 `key:<密钥>` 强制指定；网址与密钥顺序不限，从面板分几行复制也可以（换行当空格用）。

### 测试流程

`/测试` 会先拉取模型列表再实测调用，用来确认密钥是否有效、模型是否真能跑通：

1. 请求 `/v1/models` 拉取可用模型列表（同时验证 API Key 是否有效）
2. **未指定模型名**：自动挑选聊天/生成类模型，**最多实测前 3 个**（遇失败即停），实测调用 `/v1/chat/completions`（`max_tokens=1`）
3. **指定模型名**（最后一个非密钥参数）：直接实测该模型；即使它不在模型列表中、甚至 `/v1/models` 接口不可用也会硬测
4. 返回连接状态、响应延迟、可用模型列表和实测结果

```
/测试 https://api.example.com/v1 sk-xxxx
/测试 https://api.example.com sk-xxxx1 sk-xxxx2
/测试 https://api.example.com sk-xxxx deepseek-chat
/测试 https://api.example.com/v1 key:my-custom-key
/测试 https://api.example.com key:my-custom-key model:my-finetune-v3
```

密钥不要求 `sk-` 前缀：自建网关、小众平台的自定义密钥可直接传入。含特殊字符、过短或与模型名互相误判的密钥，用 `key:`（或 `密钥:`）前缀强制指定；`/测试` 中模型名则用 `model:`（或 `模型:`）前缀。前缀后的内容按原样使用，不再做格式判断。

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

### 粘贴 NewAPI 连接信息与引用消息

在 NewAPI 面板中复制连接信息后，直接粘到 `/余额` 或 `/测试` 后面即可，插件自动取 JSON 里的 `key` 和 `url`，不用手动拆开：

```
/余额 {"_type":"newapi_channel_conn","key":"sk-xxx","url":"https://new.xinjianya.top"}
/测试 {"_type":"newapi_channel_conn","key":"sk-xxx","url":"https://new.xinjianya.top"} deepseek-chat
```

`/余额` 自动挑该站支持的余额接口（Billing 或 New API 格式），JSON 之后还能继续追加更多密钥一起查；`/测试` 照常拉取模型列表并实测调用，末尾可再跟模型名。

群里已经有人发过一条带站点和密钥的消息（文本或 NewAPI JSON 都行）时，也可以**引用那条消息、只发 `/余额`（或 `/测试`）**，直接处理被引用的内容：

```
（引用一条含 sk-xxx 与 https://api.example.com 的消息）
/余额
/测试 deepseek-chat        # 引用后仍可追加模型名
```

### NEW API 多实例

想一次查看所有 NEW API 实例的余额，在 `newapi_base_url` 中每行一个地址（也可直接用 `/余额 <地址> <key>` 或别名逐个查询）：

```
http://192.168.1.1:3000
http://192.168.1.2:3000
```

配置后发 `/余额 newapi`，插件为每个地址匹配对应 Provider 的密钥并分别查询。

### 查询 OpenAI 官方花费

OpenAI 官方**不提供**查询账户剩余余额的接口，但它提供用量与花费统计。这类接口只接受 **Admin Key**，普通项目密钥会返回 403。

在插件配置里填写 `openai_admin_key`（`sk-admin-` 开头，在 OpenAI 后台 Organization → Admin API Keys 创建）后，查询 OpenAI 官方端点会显示**本月累计花费**。请注意这是**花费**而不是**余额**：OpenAI 采用预付额度制，剩余额度仍需到 OpenAI 后台查看。未填写 `openai_admin_key` 时，查询官方端点会提示查不到余额并说明原因。

## 常见问题

**查询 OpenAI 官方接口提示「无法获取余额信息」，是插件坏了吗？**
不是。插件的这个余额接口（`/v1/dashboard/billing/*`）是 **New API / One API 等中转站**为兼容旧面板自行实现的，OpenAI 官方从未提供过，因此在官方域名上必然查不到，换任何工具都一样。官方账户请到 OpenAI 后台的 Billing 页查看余额与用量；中转站则不受影响，照常可查。

如果希望在聊天里看到官方账户的金额数据，可以配置 `openai_admin_key`（需 Admin Key），插件会显示**本月累计花费**——注意是花费，不是剩余余额，官方没有余额接口。插件现在会把接口返回的状态写进提示里，据此可区分「该端点没有这个接口」与「密钥无效」。

**查不到余额，想确认插件到底请求了哪些网址？**
把 AstrBot 日志级别调到 `DEBUG`，再执行一次查询。日志里会以 `🔍 余额探测` 标出每一级探测的接口与返回状态、`🔀 余额选路` 标出该站点最终走了哪个查询器，据此就能判断是站点不支持余额接口，还是密钥/网络的问题。

## 安全提醒

包含 API 密钥的查询建议私聊使用，避免在群聊中泄露。
