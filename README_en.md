<div align="center">
<h1>LLM Balance</h1>
<p><strong>Query balances across major LLM platforms with batch token support and custom relay sites, and test model availability on OpenAI-compatible endpoints</strong></p>
<p><sub>balance &nbsp;&nbsp; multi-platform &nbsp;&nbsp; model testing</sub></p>
<p><a href="README.md">中文</a> &nbsp;/&nbsp; <strong>English</strong></p>
</div>

## Features

- Query the balance of the model used by the current session, or of all configured models at once (auto-deduplicated, concurrent)
- Query a specific platform's balance by its alias, with multiple keys in one command (no `sk-` prefix required; use `key:` to force a value)
- Query any API endpoint's balance: built-in platforms use their dedicated API, unlisted ones are probed through the generic OpenAI Billing / New API interfaces, and unsupported is reported only when both fail
- Test model availability on OpenAI-compatible endpoints (lists models and actually calls them; supports multiple keys and a specific model)
- Paste the NewAPI connection info JSON or quote a message holding an endpoint and key, and query/test it directly without splitting anything by hand
- Customizable platform aliases (used for both command matching and endpoint addresses), freely editable
- Fully customizable output templates (success/failure/title/separators), Chinese or English output
- Admin permission control

## Usage

Both commands accept the same arguments: either a `<platform alias>` or an `<API endpoint>`, followed by keys (plus an optional model name for `/test`).

```
/balance                            # show help
/balance current | /balance all     # balance of the current session / all configured models
/balance <platform alias>           # balance via the provider configured for that platform in AstrBot
/balance <alias|endpoint> <key1> [key2]...   # batch-query balance with given keys
/test <alias|endpoint> <key1> [key2]... [model]  # test model availability
/balance|/test <NewAPI connection JSON> [...]  # paste connection info; URL and key are picked up automatically
```

English aliases: `/余额` = `/balance`, `/测试` = `/test`; subcommands: current / all / help (also 当前 / 所有 / 帮助).

## Supported Platforms

| Platform | Available aliases |
|---|---|
| DeepSeek | `deepseek` / `ds` / `深度求索` |
| SiliconFlow | `siliconflow` / `sc` / `硅基` / `硅基流动` / `sc-cn` / `硅基cn` |
| Moonshot (Kimi) | `moonshot` / `kimi` / `月之暗面` |
| OpenAI | `openai` / `gpt` / `chatgpt` |
| ChatAnywhere | `chatanywhere` |
| NEW API | `newapi` |

Aliases come from the `platform_names` config item and are shared by `/balance` and `/test`; add, edit or remove them freely. Platforms without a fixed domain (ChatAnywhere, NEW API) can only be addressed by their own platform name.

## Configuration

### Basic Settings

| Setting | Type | Default | Description |
|---|---|---|---|
| `admin_only` | bool | `false` | Restrict to admins only |
| `output_language` | string | `auto` | Output language: `auto` (switch by command language) / `zh` (force Chinese) / `en` (force English) |
| `newapi_base_url` | text | empty | New API relay site URLs, one per line; used by `/balance newapi` to aggregate multiple instances |
| `openai_admin_key` | string | empty | OpenAI admin key (`sk-admin-…`, optional): when set, querying the official OpenAI endpoint reports **this month's accumulated spend** (OpenAI has no balance API, so this is spend, not remaining credit) |
| `request_timeout` | float | `10.0` | Request timeout (seconds) |
| `show_unsupported` | bool | `true` | Show unsupported platforms in `/balance all` |
| `platform_names` | list | 5 presets for common platforms | API endpoint and platform alias map: each item `endpoint=abbr1,abbr2` (one endpoint may have multiple comma-separated abbreviations, multiple rows allowed). Abbreviations work for both `/balance <abbr>` and `/test <abbr>`, and shown endpoints are replaced by the first one. Ships with DeepSeek / SiliconFlow / Moonshot / OpenAI presets, all editable or removable |

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

<details>
<summary>Default templates (7 items)</summary>

**success_template**

```
🟢 **{{source_name}}**
  🔑 密钥: {{api_key}}
  💵 {{balance}} {{currency}}
{{smart_balance}}
```

**error_template**

```
🔴 **{{source_name}}**
  🔑 密钥: {{api_key}}
  ❌ {{error}}
```

- header_template: `💰 **{{title}}**` (variable: `{{title}}`)
- separator_template: `════════════════════════════════════════` (between title and content)
- item_separator_template: empty (between multiple results in the same section; blank line when empty)
- section_separator_template: `════════════════════════════════════════` (between success/failure/unsupported sections)

</details>

## Usage Examples

### Platform aliases and custom endpoints

```
/balance ds sk-xxxx     # DeepSeek balance
/test ds sk-xxxx        # DeepSeek model availability
/test kimi sk-xxxx      # Moonshot
/test openai sk-xxxx    # official OpenAI
/balance https://your-api.com/v1 sk-xxxx1 sk-xxxx2
/test https://your-api.com/v1 sk-xxxx1 sk-xxxx2 deepseek-chat
```

To test your own relay, just replace the address of the matching line in `platform_names`, e.g. `https://my-relay.com=ds`, and `/test ds sk-xxx` will test that relay. Remove a line and that alias stops working (`/balance` can still query the platform by its platform name such as `deepseek`).

> Note: `/balance <alias>` prefers the provider you configured for that platform in AstrBot (so a relay is queried through the relay); only a full URL triggers endpoint-mode querying.

### Batch query

Append multiple keys after a platform alias or API endpoint; they are auto-detected and queried concurrently, and results are grouped by success/failure:

```
/balance ds sk-xxx1 sk-xxx2 sk-xxx3
/balance https://api.example.com/v1 sk-xxx1 sk-xxx2
```

Write a key containing special characters or a very short key as `key:<key>` to force it. The URL and the key can come in **any order**, and pasting one value per line works too (newlines count as spaces).

### Test flow

`/test` first lists the models and then makes a real call, confirming both that the key works and that a model actually responds:

1. Requests `/v1/models` to list available models (which also validates the API key)
2. **No model name given**: picks chat/generation models automatically and tests **up to 3** (stops on the first failure) via `/v1/chat/completions` with `max_tokens=1`
3. **Model name given** (the last non-key argument): tests that model directly, even if it is absent from the model list or `/v1/models` itself is unavailable
4. Reports connection status, latency, the model list and the test result

```
/test https://api.example.com/v1 sk-xxxx
/test https://api.example.com sk-xxxx1 sk-xxxx2
/test https://api.example.com sk-xxxx deepseek-chat
/test https://api.example.com/v1 key:my-custom-key
/test https://api.example.com key:my-custom-key model:my-finetune-v3
```

Keys no longer need an `sk-` prefix: custom keys from self-hosted gateways and niche platforms can be passed directly. For keys containing special characters, keys that are too short, or a key misdetected as a model name, prefix the value with `key:` (or `密钥:`); in `/test`, prefix a model name with `model:` (or `模型:`). The value after the prefix is used verbatim, with no further format checks.

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

### Pasting NewAPI connection info and quoting messages

Copy the connection info from the NewAPI panel and paste it straight after `/balance` or `/test`; the plugin reads the `key` and `url` out of the JSON for you:

```
/balance {"_type":"newapi_channel_conn","key":"sk-xxx","url":"https://new.xinjianya.top"}
/test {"_type":"newapi_channel_conn","key":"sk-xxx","url":"https://new.xinjianya.top"} deepseek-chat
```

`/balance` picks whichever balance API that site supports (Billing or New API format), and extra keys may follow the JSON; `/test` still lists the models and runs a real call, and a model name may follow.

If someone already posted a message with the endpoint and key (plain text or NewAPI JSON), **quote that message and send `/balance` (or `/test`) on its own** to act on the quoted content:

```
(quote a message containing sk-xxx and https://api.example.com)
/balance
/test deepseek-chat        # a model name can still be appended after quoting
```

### New API multiple instances

To check the balances of all your New API instances in one go, put one URL per line in `newapi_base_url` (you can also query them one by one with `/balance <url> <key>` or aliases):

```
http://192.168.1.1:3000
http://192.168.1.2:3000
```

After configuring, send `/balance newapi`; the plugin matches each URL to its corresponding provider key and queries them separately.

### Querying OpenAI official spend

OpenAI does **not** provide an API for reading remaining account balance, but it does provide usage and cost statistics. Those endpoints only accept an **admin key**; a regular project key returns 403.

Once `openai_admin_key` is configured (`sk-admin-…`, created under Organization → Admin API Keys in the OpenAI dashboard), querying the official OpenAI endpoint reports **this month's accumulated spend**. Note this is **spend**, not **balance**: OpenAI bills against prepaid credit, so the remaining credit must be checked in the OpenAI dashboard. Without `openai_admin_key`, querying the official endpoint reports that no balance is available and explains why.

## FAQ

**The official OpenAI endpoint reports "unable to get balance info" — is the plugin broken?**
No. The balance API this plugin uses (`/v1/dashboard/billing/*`) is implemented by **relay sites such as New API / One API** for compatibility with the legacy OpenAI dashboard; OpenAI has never provided it, so it can never work against the official domain — no tool can retrieve it there. For official accounts, check balance and usage in the OpenAI dashboard (Billing page); relay sites are unaffected and keep working.

If you want monetary data for an official account inside the chat, configure `openai_admin_key` (an admin key is required) and the plugin reports **this month's accumulated spend** — spend, not remaining balance, since OpenAI has no balance API. The plugin now includes the returned status in the message, so you can tell "this endpoint has no such API" apart from an invalid key.

**I get no balance and want to see which URLs the plugin actually called.**
Set the AstrBot log level to `DEBUG` and run the query again. Log lines tagged `🔍 余额探测` show each probe endpoint and its response status, and `🔀 余额选路` shows which fetcher the site finally used — enough to tell an unsupported balance API apart from a key or network problem.

## Security Note

Queries containing API keys are best done in private chats to avoid leaking them in group chats.
