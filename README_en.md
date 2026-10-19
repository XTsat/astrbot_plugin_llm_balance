<div align="center">
<h1>LLM Balance</h1>
<p><strong>Query balances across major LLM platforms, batch-query multiple tokens, query built-in AstrBot endpoints, pass a platform or an API endpoint, and query custom NewAPI sites; also supports testing model availability on OpenAI-compatible endpoints</strong></p>
<p><sub>balance &nbsp;&nbsp; multi-platform &nbsp;&nbsp; model testing</sub></p>
<p><a href="README.md">中文</a> &nbsp;/&nbsp; <strong>English</strong></p>
</div>

## Features

- Query the balance of the model used by the current session
- Query the balance of all configured models (auto-deduplicated, concurrent)
- Query a specific platform's balance by its alias (multiple keys supported)
- Pass an API key directly after the command (no need to configure it in AstrBot)
- Batch-query multiple API keys (auto-detects tokens; no `sk-` prefix required; use `key:` to force a value)
- Query custom API endpoint balances (OpenAI Billing and New API compatible endpoints)
- Test model availability on OpenAI-compatible endpoints (lists models and actually calls them)
- Customizable platform aliases (used for command matching and provider auto-detection)
- Admin permission control
- Fully customizable output templates (success/failure/title/separators)
- New API multi-instance support (multiple relay sites)

## Usage

```
/balance                               # show help
/balance current                    # query the balance of the model used by the current session
/balance all                        # query the balance of all configured models
/balance <platform alias>             # query the balance of a configured AstrBot platform
/balance <platform alias> <key1> [key2]...   # batch-query multiple keys of a platform
/balance <API endpoint> <key1> [key2]...     # query a custom API endpoint (auto-detects OpenAI/New API)
/balance <JSON config>                # paste NewAPI connection info directly to query balance
/test <API endpoint> <key1> [key2]... # test model availability on an OpenAI-compatible endpoint
```

English aliases: `/balance` (same as `/余额`) and `/test` (same as `/测试`); subcommand aliases: 当前 = `current`, 所有 = `all`, 帮助 = `help`.

## Supported Platforms

| Platform | Aliases |
|---|---|
| DeepSeek | `deepseek` / `ds` |
| SiliconFlow | `siliconflow` / `siliconcloud` / `sc` |
| Moonshot (Kimi) | `moonshot.cn` / `moonshot` / `kimi` |
| OpenAI | `openai.com` / `openai` / `gpt` / `chatgpt` |
| ChatAnywhere | `chatanywhere` / `ca` |
| NEW API | `newapi` / `new` |

Aliases can be customized in the plugin config.

## Configuration

### Basic Settings

| Setting | Type | Default | Description |
|---|---|---|---|
| `admin_only` | bool | `false` | Restrict to admins only |
| `output_language` | string | `auto` | Output language: `auto` (switch by command language) / `zh` (force Chinese) / `en` (force English) |
| `newapi_base_url` | text | empty | New API relay site URLs, one per line |
| `request_timeout` | float | `10.0` | Request timeout (seconds) |
| `show_unsupported` | bool | `true` | Show unsupported platforms in `/balance all` |
| `platform_aliases` | object | — | Per-platform aliases, comma-separated |
| `platform_names` | list | — | API endpoint abbreviation map: each item `endpoint=abbr1,abbr2` (one endpoint may have multiple comma-separated abbreviations, multiple rows allowed); shown endpoints are replaced by the first abbreviation, and `/balance` `/test` accept any abbreviation as the endpoint argument |

### Output Templates

All templates support `\n` newlines and the following variables:

| Variable | Description | Used in |
|---|---|---|
| `{{api_key}}` | Masked API key | success / failure |
| `{{source_name}}` | Platform name (e.g. DeepSeek) | success / failure |
| `{{error}}` | Error message | failure |
| `{{currency}}` | Currency (e.g. CNY / USD) | success |
| `{{balance}}` | Smart balance (shows remaining when it differs from total) | success |
| `{{total_balance}}` | Total balance | success |
| `{{remaining_balance}}` | Remaining balance | success |
| `{{used_balance}}` | Used quota | success |
| `{{raw_info}}` | Extra info (bonus/recharge details, etc.) | success |
| `{{smart_balance}}` | Smart extra info (auto-hides meaningless lines) | success |
| `{{?variable}}` | Conditional variable; hides the whole line when empty or `0` | success |

#### success_template — successful query

Default:
```
🟢 **{{source_name}}**
  🔑 密钥: {{api_key}}
  💵 {{balance}} {{currency}}
{{smart_balance}}
```

#### error_template — failed query

Default:
```
🔴 **{{source_name}}**
  🔑 密钥: {{api_key}}
  ❌ {{error}}
```

#### header_template — title

Default: `💰 **{{title}}**` (variable: `{{title}}`)

#### separator_template — title separator

Between the title and the content. Default: `════════════════════════════════════════`

#### item_separator_template — separator between items

Between multiple results in the same section; empty means a blank line. Default: empty

#### section_separator_template — section separator

Between success/failure/unsupported sections. Default: `════════════════════════════════════════`

## Custom API Endpoint Query

Supports querying the balance of API relay sites not in the preset list. When the command starts with `http://` or `https://`, the plugin enters custom endpoint mode:

```
/balance https://your-api.com/v1 sk-xxxx1 sk-xxxx2
```

The query flow degrades automatically:
1. **First** tries the OpenAI Billing API (`/v1/dashboard/billing/subscription` + `/usage`)
2. **Falls back** to the New API format (`/api/usage/token`)

Works with one-api, new-api, AIProxy and similar relay sites.

## Testing Model Availability

The `/test` command tests whether models on any OpenAI-compatible endpoint are usable. The format matches the custom endpoint balance query: `command + URL + API key`, with an optional **model name** at the end.

```
/test https://api.example.com/v1 sk-xxxx
/test https://api.example.com sk-xxxx1 sk-xxxx2
/test https://api.example.com sk-xxxx deepseek-chat
/test https://api.example.com sk-xxxx1 sk-xxxx2 glm-4-flash
```

Keys no longer need an `sk-` prefix: custom keys from self-hosted gateways and niche platforms can be passed directly. For keys containing special characters, keys that are too short, or a key misdetected as a model name, prefix the value with `key:` (or `密钥:`); in `/test`, prefix a model name with `model:` (or `模型:`). The value after the prefix is used verbatim, with no further format checks:

```
/test https://api.example.com/v1 key:my-custom-key
/test https://api.example.com key:my-custom-key model:my-finetune-v3
/balance https://api.example.com/v1 key:abc!@#def
```

Test flow:
1. Request `/v1/models` to fetch the available model list (also validates the API key)
2. **Without a model name**: automatically picks chat/generation models, **tests at most the first 3** (stops on the first failure), calling `/v1/chat/completions` (`max_tokens=1`)
3. **With a model name** (the last non-key argument): tests that model directly; it is tested even if it is not in the model list or the `/v1/models` endpoint is unavailable
4. Returns connection status, response latency, the available model list and the test results

Output example:

```
💰 **https://api.example.com model test**
════════════════════════════════════════
🟢 **https://api.example.com**
  🔑 密钥: sk-abc***
  ✅ 连接成功 · 响应 350ms (HTTP 200)
  🧠 可用模型 3: deepseek-chat、deepseek-reasoner、deepseek-coder
  🎯 测试模型: deepseek-chat ✅ 可用
```

Multiple keys are tested concurrently, and results are grouped by success/failure.

## Batch Query

Append multiple keys (no `sk-` prefix required) after a platform alias or API endpoint; they are auto-detected and queried concurrently. Write a key containing special characters or a very short key as `key:<key>`:

```
/balance ds sk-xxx1 sk-xxx2 sk-xxx3
/balance https://api.example.com/v1 sk-xxx1 sk-xxx2
```

Results are grouped by success/failure.

## Pasting NewAPI Connection Info

Copy the connection info from the NewAPI panel and paste it directly after `/balance`:

```
/balance {"_type":"newapi_channel_conn","key":"sk-xxx","url":"https://new.xinjianya.top"}
```

The plugin parses the `key` and `url` from the JSON and queries the balance using the New API format.

## New API Multiple Instances

Put one URL per line in `newapi_base_url`:

```
http://192.168.1.1:3000
http://192.168.1.2:3000
```

The plugin matches each URL to its corresponding provider key and queries them separately.

## Security Note

Queries containing API keys are best done in private chats to avoid leaking them in group chats.
