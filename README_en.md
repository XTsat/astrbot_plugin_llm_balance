<div align="center">
<h1>LLM Balance</h1>
<p><strong>Query balances across major LLM platforms with batch token support and custom relay sites, and test model availability on OpenAI-compatible endpoints</strong></p>
<p><sub>balance &nbsp;&nbsp; multi-platform &nbsp;&nbsp; model testing</sub></p>
<p><a href="README.md">中文</a> &nbsp;/&nbsp; <strong>English</strong></p>
</div>

## Features

- Query the balance of the model used by the current session
- Query the balance of all configured models (auto-deduplicated, concurrent)
- Query a specific platform's balance by its alias (multiple keys supported)
- Pass an API key directly after the command (no need to configure it in AstrBot)
- Batch-query multiple API keys (auto-detects tokens; no `sk-` prefix required; use `key:` to force a value)
- Query custom API endpoint balances (unlisted providers are probed through the generic OpenAI Billing / New API interfaces; unsupported is reported only when both fail)
- Test model availability on OpenAI-compatible endpoints (lists models and actually calls them)
- Paste the NewAPI connection info JSON directly (balance with `/balance`, model test with `/test`) without splitting out the URL and key, then append more keys if needed
- Quote a message that holds an endpoint and key, then send `/balance` or `/test` on its own to act on the quoted content
- Customizable platform aliases (used for command matching and provider auto-detection)
- Admin permission control
- Fully customizable output templates (success/failure/title/separators)
- New API multi-instance support (multiple relay sites)

## Usage

Both commands accept the same arguments: either a `<platform alias>` or an `<API endpoint>`, followed by keys (plus an optional model name for `/test`).

```
/balance                            # show help
/balance current | /balance all     # balance of the current session / all configured models
/balance <platform alias>           # balance of a platform you configured in AstrBot
/balance <platform alias> <key1> [key2]...  # batch-query that platform with the given keys
/balance <API endpoint> <key1> [key2]...    # balance of any endpoint (dedicated API for known platforms, otherwise Billing / New API probing)
/test <platform alias> <key1> [key2]... [model]  # test model availability on that platform
/test <API endpoint> <key1> [key2]... [model]     # test any OpenAI-compatible endpoint
/balance|/test <JSON config> [...]  # paste NewAPI connection info; URL and key are extracted automatically
```

English aliases: `/balance` (same as `/余额`) and `/test` (same as `/测试`); subcommand aliases: 当前 = `current`, 所有 = `all`, 帮助 = `help`.

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
| `newapi_base_url` | text | empty | New API relay site URLs, one per line |
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

## Platform Aliases and Custom Endpoints

`/balance` and `/test` share the same arguments: either a `<platform alias>` or an `<API endpoint>`, followed by keys (plus an optional model name for `/test`).

### Using a platform alias

```
/balance ds sk-xxxx     # DeepSeek balance
/test ds sk-xxxx        # DeepSeek model availability
/test kimi sk-xxxx      # Moonshot
/test openai sk-xxxx    # official OpenAI
```

Aliases come from the `platform_names` config item, which ships with common platforms preset — **both the address and the alias are fully editable and removable**:

```
https://api.deepseek.com=ds,deepseek,深度求索
https://api.siliconflow.com=sc,硅基,硅基流动
https://api.siliconflow.cn=sc-cn,硅基cn
https://api.moonshot.cn=kimi,moonshot,月之暗面
https://api.openai.com=openai,gpt,chatgpt
```

To test your own relay, just replace the address, e.g. `https://my-relay.com=ds`, and `/test ds sk-xxx` will test that relay. Remove a line and that alias stops working (`/balance` can still query the platform by its platform name such as `deepseek`).

> Note: `/balance <alias>` prefers the provider you configured for that platform in AstrBot (so a relay is queried through the relay); only a full URL triggers endpoint-mode querying.

### Using a full URL

When the command starts with `http://` or `https://`, the plugin enters custom endpoint mode:

```
/balance https://your-api.com/v1 sk-xxxx1 sk-xxxx2
/test https://your-api.com/v1 sk-xxxx1 sk-xxxx2 deepseek-chat
```

For `/balance` the endpoint is routed as follows:
1. A URL that belongs to a built-in platform (e.g. `api.deepseek.com`) uses **that platform's dedicated balance API**
2. Anything else **first** tries the OpenAI Billing-compatible API (`/v1/dashboard/billing/subscription` + `/usage`, implemented by relay sites), **then** falls back to the New API format (`/api/usage/token`)
3. Only when both generic interfaces fail does the plugin report the endpoint as unsupported

That means one-api, new-api, AIProxy and similar relay sites work right away without waiting for a plugin update. An account whose balance is `0` is reported as `0`, not as unsupported.

> Note: the Billing-compatible API is implemented by **relay sites** (New API / One API) to stay compatible with the legacy OpenAI dashboard. The official OpenAI domain does not expose it, so pointing the plugin at the official endpoint always reports no balance — that is not a plugin failure. Use the OpenAI dashboard to check usage and balance for official accounts.

## Querying OpenAI Official Spend

OpenAI does **not** provide an API for reading remaining account balance, but it does provide usage and cost statistics (`/organization/costs`, `/organization/usage/*`). Those endpoints only accept an **admin key**; a regular project key returns 403.

Once `openai_admin_key` is configured (`sk-admin-…`, created under Organization → Admin API Keys in the OpenAI dashboard), querying the official OpenAI endpoint reports **this month's accumulated spend**:

```
💰 **Current balance**
════════════════════════════════════════
🟢 **OpenAI official spend**
  🔑 Key: sk-adm********************abc
  💵 1.23 USD
  📝 Spend since 2026-11-01 | OpenAI has no balance API; this is spend, not remaining credit
```

Note this is **spend**, not **balance**: OpenAI bills against prepaid credit, and `/organization/costs` only reports consumed amounts — check the remaining credit in the OpenAI dashboard. Without `openai_admin_key`, querying the official endpoint reports that no balance is available and explains why.

## Test Flow

`/test` first lists the models and then makes a real call, confirming both that the key works and that a model actually responds:

1. Requests `/v1/models` to list available models (which also validates the API key)
2. **No model name given**: picks chat/generation models automatically and tests **up to 3** (stops on the first failure) via `/v1/chat/completions` with `max_tokens=1`
3. **Model name given** (the last non-key argument): tests that model directly, even if it is absent from the model list or `/v1/models` itself is unavailable
4. Reports connection status, latency, the model list and the test result

```
/test https://api.example.com/v1 sk-xxxx
/test https://api.example.com sk-xxxx1 sk-xxxx2
/test https://api.example.com sk-xxxx deepseek-chat
```

The URL and the key can come in **any order**, and pasting one value per line works too (newlines count as spaces):

```
/test sk-xxxx https://api.example.com deepseek-chat
/test sk-xxxx
https://api.example.com
deepseek-chat
```

Keys no longer need an `sk-` prefix: custom keys from self-hosted gateways and niche platforms can be passed directly. For keys containing special characters, keys that are too short, or a key misdetected as a model name, prefix the value with `key:` (or `密钥:`); in `/test`, prefix a model name with `model:` (or `模型:`). The value after the prefix is used verbatim, with no further format checks:

```
/test https://api.example.com/v1 key:my-custom-key
/test https://api.example.com key:my-custom-key model:my-finetune-v3
/balance https://api.example.com/v1 key:abc!@#def
```

You can also paste the connection info copied from the NewAPI panel (the JSON holding `key` and `url`) right after `/test`; the plugin picks up the URL and key automatically, and a model name can still follow:

```
/test {"_type":"newapi_channel_conn","key":"sk-xxx","url":"https://api.example.com"}
/test {"_type":"newapi_channel_conn","key":"sk-xxx","url":"https://api.example.com"} deepseek-chat
```

If someone already posted a message with the endpoint and key (plain text or NewAPI JSON), **quote that message and send `/test` on its own** to test it without copying anything again — append a model name to target one model:

```
(quoting a message that contains sk-xxx and https://api.example.com)
/test
/test deepseek-chat
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

Copy the connection info from the NewAPI panel and paste it straight after `/balance` or `/test`; the plugin reads the `key` and `url` out of the JSON for you:

```
/balance {"_type":"newapi_channel_conn","key":"sk-xxx","url":"https://new.xinjianya.top"}
/balance {"_type":"newapi_channel_conn","key":"sk-xxx","url":"https://new.xinjianya.top"} sk-yyy
/test {"_type":"newapi_channel_conn","key":"sk-xxx","url":"https://new.xinjianya.top"}
/test {"_type":"newapi_channel_conn","key":"sk-xxx","url":"https://new.xinjianya.top"} deepseek-chat
```

`/balance` picks whichever balance API that site supports (Billing or New API format), and extra keys may follow the JSON; `/test` still lists the models and runs a real call, and a model name may follow.

If someone already posted a message with the endpoint and key (plain text or NewAPI JSON), **quote that message and send `/balance` on its own** to query the quoted content:

```
(quote a message containing sk-xxx and https://api.example.com)
/balance
```

## New API Multiple Instances

Put one URL per line in `newapi_base_url`:

```
http://192.168.1.1:3000
http://192.168.1.2:3000
```

The plugin matches each URL to its corresponding provider key and queries them separately.

## FAQ

**The official OpenAI endpoint reports "unable to get balance info" — is the plugin broken?**
No. The balance API this plugin uses (`/v1/dashboard/billing/*`) is implemented by **relay sites such as New API / One API** for compatibility with the legacy OpenAI dashboard; OpenAI has never provided it, so it can never work against the official domain — no tool can retrieve it there. For official accounts, check balance and usage in the OpenAI dashboard (Billing page); relay sites are unaffected and keep working.

If you want monetary data for an official account inside the chat, configure `openai_admin_key` (an admin key is required) and the plugin reports **this month's accumulated spend** — spend, not remaining balance, since OpenAI has no balance API. The plugin now includes the returned status in the message, so you can tell "this endpoint has no such API" apart from an invalid key.

**I get no balance and want to see which URLs the plugin actually called.**
Set the AstrBot log level to `DEBUG` and run the query again. Log lines tagged `🔍 余额探测` show each probe endpoint and its response status, and `🔀 余额选路` shows which fetcher the site finally used — enough to tell an unsupported balance API apart from a key or network problem.

## Security Note

Queries containing API keys are best done in private chats to avoid leaking them in group chats.
