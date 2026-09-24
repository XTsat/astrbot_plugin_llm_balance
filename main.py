import asyncio
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Optional

import aiohttp

from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star
from astrbot.api import logger, AstrBotConfig


# ==================== 数据模型 ====================

@dataclass
class BalanceResult:
    """统一的余额返回结果"""
    source_name: str
    currency: str
    total_balance: str
    used_balance: str = "0"
    remaining_balance: str = "0"
    is_available: bool = True
    raw_info: str = ""
    error: str = None

    def _get_default_string(self) -> str:
        """生成默认完整格式（含 source_name 标题，2空格缩进）"""
        indent = "  "
        msg = f"🟢 **{self.source_name}**\n"
        if self.remaining_balance == self.total_balance:
            msg += f"{indent}💵 {self.total_balance} {self.currency}"
        else:
            msg += f"{indent}💵 余额: {self.remaining_balance} {self.currency}\n"
            msg += f"{indent}📈 总额: {self.total_balance} {self.currency}"
            if self.used_balance != "0":
                msg += f"\n{indent}📊 已用: {self.used_balance} {self.currency}"
        if self.raw_info:
            msg += f"\n{indent}📝 {self.raw_info}"
        return msg

    def _get_default_body(self) -> str:
        """生成智能附加信息（总额/已用/备注），自动跳过无意义行。{{smart_balance}} 引用"""
        indent = "  "
        parts = []
        if self.remaining_balance != self.total_balance:
            parts.append(f"{indent}📈 总额: {self.total_balance} {self.currency}")
            if self.used_balance != "0":
                parts.append(f"{indent}📊 已用: {self.used_balance} {self.currency}")
        if self.raw_info:
            parts.append(f"{indent}📝 {self.raw_info}")
        return "\n".join(parts) if parts else ""

    def to_string(self, success_template: str = "", error_template: str = "", api_key: str = "") -> str:
        if self.error:
            return self._render_error(error_template, api_key)
        return self._render_success(success_template, api_key)

    def _render_error(self, template: str, api_key: str) -> str:
        """渲染错误模板"""
        if not template:
            template = "🔴 **{{source_name}}**\n  ❌ {{error}}"
        replacements = {
            "{{api_key}}": api_key,
            "{{source_name}}": self.source_name,
            "{{error}}": self.error,
        }
        result = template
        for key, value in replacements.items():
            result = result.replace(key, str(value))
        return result.replace("\\n", "\n")

    def _render_success(self, template: str, api_key: str) -> str:
        if not template:
            return self._get_default_string()

        # {{smart_balance}} 引用智能附加信息
        template = template.replace("{{smart_balance}}", self._get_default_body())

        smart_balance = self.remaining_balance if self.remaining_balance != self.total_balance else self.total_balance
        replacements = {
            "{{api_key}}": api_key,
            "{{source_name}}": self.source_name,
            "{{currency}}": self.currency,
            "{{balance}}": smart_balance,
            "{{total_balance}}": self.total_balance,
            "{{remaining_balance}}": self.remaining_balance,
            "{{used_balance}}": self.used_balance,
            "{{raw_info}}": self.raw_info,
        }
        # 处理 {{?变量}} 条件行：值为空或"0"时移除整行
        import re
        for key, value in replacements.items():
            cond_key = key.replace("{{", "{{?")
            if cond_key in template:
                if not str(value).strip() or str(value).strip() == "0":
                    for line in template.split("\n"):
                        if cond_key in line:
                            template = template.replace(line + "\n", "").replace("\n" + line, "").replace(line, "")
        # 常规替换
        result = template
        for key, value in replacements.items():
            result = result.replace(key, str(value))
            result = result.replace(key.replace("{{", "{{?"), str(value))
        return result.replace("\\n", "\n")


# 模型可用性测试：明显非聊天类模型名特征
NON_CHAT_HINTS = (
    "embedding", "embed", "whisper", "tts", "stt", "asr", "rerank", "rank",
    "moderation", "image", "dall-e", "dalle", "audio", "transcribe", "translate",
    "vector", "ocr", "diarize",
)
# 模型可用性测试：优先实测的聊天/生成类模型名特征
CHAT_KEY_HINTS = (
    "chat", "gpt", "deepseek", "qwen", "kimi", "glm", "moonshot", "claude",
    "llama", "gemini", "mistral", "yi-", "ernie", "doubao", "hunyuan",
)


@dataclass
class ModelTestResult:
    """统一的模型可用性测试结果"""
    source_name: str
    is_available: bool = False
    models: list = None
    tested_models: list = None
    latency_ms: int = 0
    status_code: int = 0
    raw_info: str = ""
    error: str = None
    specified: bool = False

    def to_string(self, api_key: str = "", lang: str = "zh") -> str:
        indent = "  "
        en = lang != "zh"
        head_icon = "🟢" if not self.error else "🔴"
        key_label = "Key" if en else "密钥"
        msg = f"{head_icon} **{self.source_name}**\n"
        if api_key:
            msg += f"{indent}🔑 {key_label}: {api_key}\n"
        if self.error:
            msg += f"{indent}❌ {self.error}"
            return msg
        ok_line = ("✅ Connected · Response {}ms (HTTP {})" if en
                   else "✅ 连接成功 · 响应 {}ms (HTTP {})")
        msg += f"{indent}{ok_line.format(self.latency_ms, self.status_code)}\n"
        if self.models:
            shown = "、".join(self.models[:8])
            if len(self.models) > 8:
                shown += (" ... and {} more".format(len(self.models)) if en
                          else " 等 {} 个".format(len(self.models)))
            label = "Available models" if en else "可用模型"
            msg += f"{indent}🧠 {label} {len(self.models)}: {shown}\n"
        if self.tested_models:
            label = ("Specified model" if (en and self.specified)
                     else "Tested model" if en
                     else "指定模型" if self.specified else "测试模型")
            suffix = " ✅ available" if en else " ✅ 可用"
            msg += f"{indent}🎯 {label}: " + " / ".join(self.tested_models) + suffix
        if self.raw_info:
            msg += f"\n{indent}📝 {self.raw_info}"
        return msg


# ==================== Fetcher 基类 ====================

class BaseBalanceFetcher(ABC):
    """余额查询基类"""

    # 用于关键词匹配的别名列表（小写），供"余额 平台"命令模糊匹配
    aliases: list = []

    @abstractmethod
    def match(self, api_base: str) -> bool:
        """判断当前 Fetcher 是否支持该 api_base"""
        pass

    @abstractmethod
    async def fetch(self, session: aiohttp.ClientSession, api_key: str, api_base: str) -> BalanceResult:
        """执行查询"""
        pass

    def match_by_name(self, name: str) -> bool:
        """根据用户输入的平台名称进行模糊匹配"""
        name_lower = name.lower().strip()
        if not name_lower:
            return False
        for alias in self.aliases:
            if name_lower in alias or alias in name_lower:
                return True
        return False


# ==================== 各平台 Fetcher ====================

class DeepSeekFetcher(BaseBalanceFetcher):
    aliases = ["deepseek", "ds", "深度求索"]

    def match(self, api_base: str) -> bool:
        return "deepseek" in api_base

    async def fetch(self, session: aiohttp.ClientSession, api_key: str, api_base: str) -> BalanceResult:
        url = "https://api.deepseek.com/user/balance"
        headers = {
            'Accept': 'application/json',
            'Authorization': f'Bearer {api_key}'
        }

        async with session.get(url, headers=headers) as response:
            if response.status != 200:
                text = await response.text()
                return BalanceResult("DeepSeek", "Unknown", "0", error=f"HTTP {response.status}: {text}")

            data = await response.json()
            infos = data.get("balance_infos", [])
            if not data.get("is_available"):
                # 区分"余额不足/欠费"与"账户不可用（封禁/冻结）"，避免误导用户
                if infos:
                    info = infos[0]
                    currency = info.get("currency", "CNY")
                    total = info.get("total_balance", "0")
                    try:
                        total_num = float(total)
                    except (TypeError, ValueError):
                        total_num = 0.0
                    if total_num <= 0:
                        reason = "已欠费" if total_num < 0 else "余额不足"
                        return BalanceResult("DeepSeek", currency, str(total), error=f"{reason}（当前余额 {total} {currency}）")
                return BalanceResult("DeepSeek", "Unknown", "0", error="账户状态不可用（可能被封禁或冻结）")
            if not infos:
                return BalanceResult("DeepSeek", "Unknown", "0", error="未找到余额信息")

            info = infos[0]
            currency = info.get("currency", "CNY")
            total = info.get("total_balance", "0")
            granted = info.get("granted_balance", "0")
            topped_up = info.get("topped_up_balance", "0")

            return BalanceResult(
                source_name="DeepSeek",
                currency=currency,
                total_balance=str(total),
                remaining_balance=str(total),
                raw_info=f"赠送: {granted} | 充值: {topped_up}"
            )


class SiliconCloudFetcher(BaseBalanceFetcher):
    aliases = ["siliconflow", "siliconcloud", "硅基", "硅基流动"]

    def match(self, api_base: str) -> bool:
        return "siliconflow" in api_base

    async def fetch(self, session: aiohttp.ClientSession, api_key: str, api_base: str) -> BalanceResult:
        domain = "api.siliconflow.com"
        if "siliconflow.cn" in api_base:
            domain = "api.siliconflow.cn"

        url = f"https://{domain}/v1/user/info"
        headers = {
            'Authorization': f'Bearer {api_key}'
        }

        async with session.get(url, headers=headers) as response:
            if response.status != 200:
                text = await response.text()
                return BalanceResult("硅基流动", "Unknown", "0", error=f"HTTP {response.status}: {text}")

            data = await response.json()
            if data.get("code") != 20000:
                return BalanceResult("硅基流动", "Unknown", "0", error=f"API Error: {data.get('message')}")
            data_inner = data.get("data", {})

            total = data_inner.get("totalBalance")
            if not total:
                total = data_inner.get("balance", "0")
            charge = data_inner.get("chargeBalance", "0")

            return BalanceResult(
                source_name="硅基流动(SiliconCloud)",
                currency="USD",
                total_balance=str(total),
                remaining_balance=str(total),
                raw_info=f"充值余额: {charge}"
            )


class MoonshotFetcher(BaseBalanceFetcher):
    aliases = ["moonshot", "kimi", "月之暗面"]

    def match(self, api_base: str) -> bool:
        return "moonshot.cn" in api_base

    async def fetch(self, session: aiohttp.ClientSession, api_key: str, api_base: str) -> BalanceResult:
        url = "https://api.moonshot.cn/v1/users/me/balance"
        headers = {
            'Authorization': f'Bearer {api_key}'
        }

        async with session.get(url, headers=headers) as response:
            if response.status != 200:
                text = await response.text()
                return BalanceResult("Moonshot(Kimi)", "Unknown", "0", error=f"HTTP {response.status}: {text}")

            data = await response.json()
            if data.get("code") != 0 or not data.get("status"):
                return BalanceResult("Moonshot(Kimi)", "Unknown", "0", error=f"API Error: {data}")
            data_inner = data.get("data", {})
            available = data_inner.get("available_balance", 0)

            return BalanceResult(
                source_name="Moonshot(Kimi)",
                currency="CNY",
                total_balance=str(available),
                remaining_balance=str(available)
            )


class ChatAnywhereFetcher(BaseBalanceFetcher):
    aliases = ["chatanywhere", "ca"]

    def match(self, api_base: str) -> bool:
        return "chatanywhere" in api_base

    async def fetch(self, session: aiohttp.ClientSession, api_key: str, api_base: str) -> BalanceResult:
        base_url = api_base
        if "/v1" in base_url:
            base_url = base_url.split("/v1")[0]

        sub_url = f"{base_url}/v1/dashboard/billing/subscription"
        headers = {
            'Authorization': f'Bearer {api_key}'
        }

        total_balance = 0.0
        currency = "USD"

        try:
            async with session.get(sub_url, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    total_balance = data.get("hard_limit_usd", 0.0)
        except Exception:
            pass

        usage_url = f"{base_url}/v1/dashboard/billing/usage"
        end_date = datetime.now()
        start_date = end_date - timedelta(days=99)
        params = {
            "start_date": start_date.strftime("%Y-%m-%d"),
            "end_date": end_date.strftime("%Y-%m-%d")
        }

        used_balance = 0.0
        try:
            async with session.get(usage_url, headers=headers, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    total_usage_cents = data.get("total_usage", 0)
                    used_balance = total_usage_cents / 100
        except Exception:
            pass

        remaining = total_balance - used_balance

        if total_balance == 0 and used_balance == 0:
            return BalanceResult("ChatAnywhere", "Unknown", "0", error="无法获取余额信息 (API不支持或返回为空)")

        return BalanceResult(
            source_name="ChatAnywhere",
            currency=currency,
            total_balance=f"{total_balance:.2f}",
            remaining_balance=f"{remaining:.2f}",
            used_balance=f"{used_balance:.2f}"
        )


class OpenAIFetcher(BaseBalanceFetcher):
    aliases = ["openai", "gpt", "chatgpt"]

    def match(self, api_base: str) -> bool:
        return "openai.com" in api_base

    async def fetch(self, session: aiohttp.ClientSession, api_key: str, api_base: str) -> BalanceResult:
        base_url = "https://api.openai.com"
        if api_base and "openai.com" in api_base:
            base_url = api_base.rstrip("/")
            if "/v1" in base_url:
                base_url = base_url.split("/v1")[0]

        headers = {
            'Authorization': f'Bearer {api_key}'
        }

        today = datetime.today().strftime('%Y-%m-%d')

        # 获取订阅信息
        subscription_url = f"{base_url}/v1/dashboard/billing/subscription"
        account_balance = 0.0
        has_payment = False
        access_until = "无限制"

        try:
            async with session.get(subscription_url, headers=headers) as resp:
                if resp.status == 200:
                    sub_data = await resp.json()
                    if isinstance(sub_data, list) and sub_data:
                        account_balance = sub_data[0].get("soft_limit_usd", 0)
                        has_payment = sub_data[0].get("has_payment_method", False)
                        access_until = sub_data[0].get("access_until", "无限制")
        except Exception:
            pass

        # 获取使用量
        usage_url = f"{base_url}/v1/dashboard/billing/usage?start_date={today}&end_date={today}"
        used_balance = 0.0
        try:
            async with session.get(usage_url, headers=headers) as resp:
                if resp.status == 200:
                    usage_data = await resp.json()
                    used_balance = usage_data.get("total_usage", 0) / 100
        except Exception:
            pass

        remaining = account_balance - used_balance

        if account_balance == 0 and used_balance == 0:
            return BalanceResult("OpenAI", "Unknown", "0", error="无法获取余额信息 (API不支持或返回为空)")

        return BalanceResult(
            source_name="OpenAI",
            currency="USD",
            total_balance=f"{account_balance:.2f}",
            remaining_balance=f"{remaining:.2f}",
            used_balance=f"{used_balance:.2f}",
            raw_info=f"支付: {'是' if has_payment else '否'} | 到期: {access_until}"
        )


class NewApiFetcher(BaseBalanceFetcher):
    aliases = ["newapi", "new api", "new_api", "中转"]

    def match(self, api_base: str) -> bool:
        # NEW API 没有固定的域名特征，需要用户在配置中指定或通过名称匹配
        return False

    async def fetch(self, session: aiohttp.ClientSession, api_key: str, api_base: str) -> BalanceResult:
        if not api_base:
            return BalanceResult("NEW API", "Unknown", "0", error="未配置 API Base URL")

        url = api_base.rstrip('/') + "/api/usage/token"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json"
        }

        try:
            async with session.get(url, headers=headers) as resp:
                try:
                    data = await resp.json()
                except Exception:
                    text = await resp.text()
                    return BalanceResult("NEW API", "Unknown", "0", error=f"非JSON数据(HTTP {resp.status}): {text[:200]}")

            ok_flag = bool(data.get("code", False) or data.get("success", False))
            if not ok_flag or "data" not in data:
                err = data.get("message") or f"HTTP {resp.status}"
                return BalanceResult("NEW API", "Unknown", "0", error=err)

            d = data["data"] or {}
            name = d.get("name", "-")
            total_granted = d.get("total_granted", 0)
            total_used = d.get("total_used", 0)
            total_available = d.get("total_available", 0)
            unlimited = d.get("unlimited_quota", False)
            expires_at = d.get("expires_at", 0)

            expires_str = "永不过期" if not expires_at else datetime.fromtimestamp(expires_at).strftime("%Y-%m-%d %H:%M:%S")

            return BalanceResult(
                source_name=f"NEW API ({name})",
                currency="",
                total_balance=str(total_granted),
                used_balance=str(total_used),
                remaining_balance=str(total_available),
                raw_info=f"无限额度: {'是' if unlimited else '否'} | 到期: {expires_str}"
            )
        except aiohttp.ClientError as e:
            return BalanceResult("NEW API", "Unknown", "0", error=f"网络错误: {e}")


# ==================== 余额查询管理器 ====================

class BalanceManager:
    """余额查询管理器，管理所有平台的 Fetcher"""

    def __init__(self, newapi_base_url: str = ""):
        # 支持多个 NEW API 地址，换行分隔
        self.newapi_base_url = newapi_base_url
        self.newapi_urls: List[str] = []
        if newapi_base_url:
            for url in newapi_base_url.replace(",", "\n").split("\n"):
                url = url.strip().rstrip("/")
                if url:
                    self.newapi_urls.append(url)
        self.fetchers: List[BaseBalanceFetcher] = [
            DeepSeekFetcher(),
            SiliconCloudFetcher(),
            MoonshotFetcher(),
            ChatAnywhereFetcher(),
            OpenAIFetcher(),
            NewApiFetcher(),
        ]
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()

    async def query(self, api_key: str, api_base: str) -> BalanceResult:
        """根据 api_base 自动匹配 Fetcher 并查询"""
        if not api_key:
            return BalanceResult("Unknown", "Unknown", "0", error="未提供 API Key")

        session = await self._get_session()

        # 优先匹配特定平台
        for fetcher in self.fetchers:
            if fetcher.match(api_base):
                try:
                    return await fetcher.fetch(session, api_key, api_base)
                except aiohttp.ClientError as e:
                    return BalanceResult("Unknown", "Unknown", "0", error=f"网络错误: {e}")
                except Exception as e:
                    return BalanceResult("Unknown", "Unknown", "0", error=f"内部错误: {e}")

        # NEW API 只在 provider 的 api_base 包含某个配置的 newapi URL 时才查询
        for newapi_url in self.newapi_urls:
            if newapi_url.lower() in api_base.lower():
                result = await NewApiFetcher().fetch(session, api_key, newapi_url)
                return result

        return BalanceResult("Unknown", "Unknown", "0", error=f"暂不支持该 API Base: {api_base}")


# ==================== 主插件类 ====================

class BalancePlugin(Star):
    """大模型余额查询插件

    支持命令：
        /余额 当前      - 查询当前会话使用的模型余额
        /余额 所有      - 查询所有已配置模型的余额
        /余额 <平台名>  - 查询指定平台的余额（如 deepseek、硅基、kimi 等）
        /测试 <API网址> <key> - 测试 OpenAI 兼容端点的模型可用性
        /余额          - 显示帮助信息
    """

    # 平台基础信息：key -> display_name（match_keywords 从配置读取）
    PLATFORMS = {
        "deepseek": {"display_name": "DeepSeek（深度求索）"},
        "siliconflow": {"display_name": "硅基流动"},
        "moonshot": {"display_name": "Moonshot（Kimi）"},
        "openai": {"display_name": "OpenAI"},
        "chatanywhere": {"display_name": "ChatAnywhere"},
        "newapi": {"display_name": "NEW API"},
    }

    FETCHER_MAP = {
        "deepseek": DeepSeekFetcher,
        "siliconflow": SiliconCloudFetcher,
        "moonshot": MoonshotFetcher,
        "openai": OpenAIFetcher,
        "chatanywhere": ChatAnywhereFetcher,
        "newapi": NewApiFetcher,
    }

    def __init__(self, context: Context, config: AstrBotConfig = None):
        super().__init__(context)
        self.config = config or {}
        newapi_base_url = self.config.get("newapi_base_url", "")
        self.manager = BalanceManager(newapi_base_url=newapi_base_url)
        self._build_platform_config()

    def _build_platform_config(self):
        """根据配置构建别名映射表和匹配关键词表（两者使用同一个配置源）"""
        self.alias_map = {}
        self.match_keywords = {}

        aliases_config = self.config.get("platform_aliases", {}) or {}

        for platform_key in self.PLATFORMS:
            # 平台名本身始终作为别名
            self.alias_map[platform_key.lower()] = platform_key
            self.match_keywords[platform_key] = [platform_key.lower()]

            # 读取用户配置的别名列表（同时用于命令匹配和 api_base 识别）
            aliases_str = aliases_config.get(platform_key, "") if isinstance(aliases_config, dict) else ""
            if isinstance(aliases_str, str) and aliases_str.strip():
                for alias in aliases_str.split(","):
                    alias = alias.strip().lower()
                    if alias:
                        self.alias_map[alias] = platform_key
                        self.match_keywords[platform_key].append(alias)

    def _match_platform_by_api_base(self, api_base: str) -> Optional[str]:
        """根据 api_base 匹配平台 key，返回 None 表示未匹配"""
        api_base_lower = api_base.lower()
        for platform_key, keywords in self.match_keywords.items():
            for kw in keywords:
                if kw in api_base_lower:
                    return platform_key
        # 如果配置了 newapi_urls，检查是否匹配
        for newapi_url in self.manager.newapi_urls:
            if newapi_url.lower() in api_base_lower:
                return "newapi"
        return None

    def _is_admin(self, event: AstrMessageEvent) -> bool:
        """检查是否满足管理员权限要求"""
        if not self.config.get("admin_only", False):
            return True
        user_id = event.get_sender_id()
        admins = self.context.get_config().admins_id
        return user_id in admins

    def _get_api_key(self, provider) -> str:
        """安全地获取当前 API Key"""
        try:
            return provider.get_current_key()
        except Exception:
            keys = provider.provider_config.get("key", [])
            return keys[0] if keys else ""

    def _get_all_api_keys(self, provider) -> List[str]:
        """获取 Provider 中所有 API Key（去重）"""
        keys = provider.provider_config.get("key", [])
        if not keys:
            return []
        seen = set()
        unique = []
        for k in keys:
            if k and k not in seen:
                seen.add(k)
                unique.append(k)
        return unique

    def _mask_key(self, key: str) -> str:
        """脱敏 API Key"""
        if not key:
            return ""
        if len(key) <= 9:
            return "****"
        return key[:6] + "*" * (len(key) - 9) + key[-3:]

    def _item_sep(self) -> str:
        """获取项间分隔符（默认空行）"""
        sep = self._get_template("item_separator_template")
        if not sep:
            return "\n\n"
        return "\n" + sep + "\n"

    def _sep(self) -> str:
        """获取标题分隔线"""
        return "\n" + self._get_template("separator_template") + "\n"

    def _section_sep(self) -> str:
        """获取区块分隔线"""
        return "\n" + self._get_template("section_separator_template") + "\n"

    def _header(self, title: str) -> str:
        """根据模板生成标题"""
        template = self._get_template("header_template")
        return template.replace("{{title}}", title)

    @staticmethod
    def _norm_base(url: str) -> str:
        """规范化 API 连接地址：去首尾空白、尾斜杠与 /v1 后缀，用于缩写映射匹配"""
        u = url.strip().rstrip("/")
        if "/v1" in u:
            u = u.split("/v1")[0].rstrip("/")
        return u

    def _build_platform_name_maps(self) -> tuple[dict, dict]:
        """解析 platform_names（list 每项 `连接=缩写1,缩写2`，兼容 dict 嵌套结构），返回 (连接→显示缩写, 缩写→连接) 两映射；同连接多缩写时显示取第一个，缩写冲突先到者优先"""
        display: dict = {}
        abbr: dict = {}

        def add(base: str, val: str) -> None:
            if not base or not val:
                return
            abbrs = [a.strip() for a in val.split(",") if a.strip()]
            if not abbrs:
                return
            display.setdefault(base, abbrs[0])
            for a in abbrs:
                abbr.setdefault(a, base)

        raw = self.config.get("platform_names") or {}
        if isinstance(raw, dict):
            for k, v in raw.items():
                val = v if isinstance(v, str) else (v.get("default") if isinstance(v, dict) else None)
                if isinstance(val, str) and val.strip():
                    add(self._norm_base(str(k)), val)
        elif isinstance(raw, list):
            for item in raw:
                if isinstance(item, str) and "=" in item:
                    k, v = item.split("=", 1)
                    add(self._norm_base(k.strip()), v.strip())
        return display, abbr

    def _apply_platform_name_map(self, name: str) -> str:
        """应用 platform_names 连接→缩写显示映射：命中返回缩写（多缩写取第一个），未命中保持原样"""
        if getattr(self, "_platform_name_map", None) is None:
            self._platform_name_map, self._endpoint_abbr_map = self._build_platform_name_maps()
        return self._platform_name_map.get(self._norm_base(name), name)

    def _resolve_endpoint_abbr(self, token: str) -> Optional[str]:
        """按 platform_names 缩写反向解析 API 连接地址（缩写→规范化连接）；未命中返回 None"""
        if not token:
            return None
        if getattr(self, "_endpoint_abbr_map", None) is None:
            self._platform_name_map, self._endpoint_abbr_map = self._build_platform_name_maps()
        return self._endpoint_abbr_map.get(token)

    def _format_result(self, res: "BalanceResult", masked_key: str = "") -> str:
        """根据模板格式化余额结果（source_name 经平台名称映射）"""
        res.source_name = self._apply_platform_name_map(res.source_name)
        success_tpl = self._get_template("success_template")
        error_tpl = self._get_template("error_template")
        return res.to_string(success_tpl, error_tpl, api_key=masked_key)

    def _get_template(self, key: str) -> str:
        """获取并处理模板（处理 \\n 转义）"""
        DEFAULT_TEMPLATES = {
            "success_template": "",
            "error_template": "🔴 **{{source_name}}**\n  ❌ {{error}}",
            "header_template": "💰 **{{title}}**",
            "separator_template": "════════════════════════════════════════",
            "item_separator_template": "",
            "section_separator_template": "════════════════════════════════════════",
        }
        default = DEFAULT_TEMPLATES.get(key, "")
        tpl = self.config.get(key, "")
        if not tpl:
            tpl = default
        return tpl

    def _extract_keys(self, text: str) -> List[str]:
        """从文本中提取以 sk- 开头的 API Key"""
        return [t for t in text.split() if t.startswith("sk-")]

    def _format_multi_results(self, title: str, results, keys, display_name: str = "") -> str:
        """将多个查询结果格式化为结果字符串（按成功/失败分组）"""
        success_list = []
        error_list = []
        for res, key in zip(results, keys):
            if display_name and not res.error:
                res.source_name = display_name
            text = self._format_result(res, self._mask_key(key))
            (error_list if res.error else success_list).append(text)

        if len(keys) == 1:
            msg = self._header(title)
            msg += self._sep()
            msg += (success_list[0] if success_list else error_list[0])
            return msg

        msg = self._header(f"{title} ({len(keys)} 个密钥)")
        msg += self._sep()
        if success_list:
            msg += self._item_sep().join(success_list)
        if error_list:
            if success_list:
                msg += self._section_sep()
            msg += "**查询失败:**\n"
            msg += self._item_sep().join(error_list)
        return msg

    async def _query_and_format(self, title, keys, fetch_fn, display_name="") -> str:
        """并发查询多个 key 并格式化"""
        session = await self.manager._get_session()
        tasks = [fetch_fn(session, key) for key in keys]
        results = await asyncio.gather(*tasks)
        return self._format_multi_results(title, results, keys, display_name)

    def _get_provider_display_name(self, provider) -> str:
        """获取 Provider 的显示名称"""
        cfg = provider.provider_config
        provider_id = cfg.get("id", "unknown")
        provider_type = cfg.get("type", "unknown")
        api_base = cfg.get("api_base", "")
        # 优先使用 api_base 识别
        platform_key = self._match_platform_by_api_base(api_base)
        if platform_key:
            return self.PLATFORMS[platform_key]["display_name"]
        # 回退到 provider_id
        if "/" in provider_id:
            provider_id = provider_id.split("/")[0]
        return provider_id or provider_type

    @filter.command("余额", alias={"balance"})
    async def balance(self, event: AstrMessageEvent):
        """查询大模型平台余额。输入 /余额 查看完整帮助。"""
        # 权限检查
        if not self._is_admin(event):
            yield event.plain_result("🚫 只有管理员可以使用此指令。")
            return

        # 解析子命令
        full_text = event.message_str.strip()
        if full_text.startswith("/"):
            full_text = full_text[1:]
        for cmd in ("余额", "balance"):
            if full_text.startswith(cmd):
                full_text = full_text[len(cmd):].strip()
                break
        parts = full_text.split(maxsplit=1)
        raw_sub = parts[0] if parts else ""
        sub_command = raw_sub.lower()

        if sub_command == "" or sub_command == "帮助" or sub_command == "help":
            yield event.plain_result(self._get_help_text())
        elif sub_command == "当前" or sub_command == "current":
            async for msg in self._query_current(event):
                yield msg
        elif sub_command == "所有" or sub_command == "all":
            async for msg in self._query_all(event):
                yield msg
        elif sub_command.startswith("http://") or sub_command.startswith("https://"):
            extra = parts[1].strip() if len(parts) > 1 else ""
            async for msg in self._query_custom(event, sub_command, extra):
                yield msg
        elif raw_sub.startswith("{"):
            extra = parts[1].strip() if len(parts) > 1 else ""
            async for msg in self._query_newapi_conn_info(event, raw_sub, extra):
                yield msg
        else:
            extra = parts[1].strip() if len(parts) > 1 else ""
            resolved = self._resolve_endpoint_abbr(raw_sub) or self._resolve_endpoint_abbr(sub_command)
            if resolved:
                async for msg in self._query_custom(event, resolved, extra):
                    yield msg
            else:
                async for msg in self._query_by_platform(event, sub_command, extra):
                    yield msg

    def _get_output_lang(self, event: AstrMessageEvent) -> str:
        """决定输出语言：配置 output_language（auto/zh/en）优先，auto 时按指令语言推断"""
        cfg = (self.config.get("output_language") or "auto").lower()
        if cfg in ("zh", "en"):
            return cfg
        text = (event.message_str or "").strip()
        if text.startswith("/"):
            text = text[1:]
        if text.startswith("余额") or text.startswith("测试"):
            return "zh"
        if text.startswith("balance") or text.startswith("test"):
            return "en"
        return "zh"

    @filter.command("测试", alias={"test"})
    async def test_model(self, event: AstrMessageEvent):
        """测试 OpenAI 兼容端点的模型是否可用。用法：/测试 <API网址> <API Key>"""
        # 权限检查
        if not self._is_admin(event):
            yield event.plain_result("🚫 只有管理员可以使用此指令。")
            return

        lang = self._get_output_lang(event)
        # 解析参数：指令 + 网址 + API Key
        full_text = event.message_str.strip()
        if full_text.startswith("/"):
            full_text = full_text[1:]
        for cmd in ("测试", "test"):
            if full_text.startswith(cmd):
                full_text = full_text[len(cmd):].strip()
                break
        parts = full_text.split(maxsplit=1)
        raw = parts[0] if parts else ""
        url = raw.lower()

        if raw == "" or raw in ("帮助", "help"):
            if lang == "en":
                usage = (
                    "ℹ️ **Test Model Availability**\n"
                    "Usage: /test <API endpoint> <API Key> [Key2]... [Model name]\n"
                    "Examples: /test https://api.example.com/v1 sk-xxxxxxxx\n"
                    "          /test https://api.example.com sk-xxxxxxxx deepseek-chat\n"
                    "Auto-detects OpenAI-compatible endpoints: lists models and runs chat calls to verify the key.\n"
                    "Auto mode tests up to 3 chat models (stops on first failure);\n"
                    "An optional trailing model name tests that model directly (hard-tested even if not in the model list).\n"
                    "Chinese alias: /测试"
                )
            else:
                usage = (
                    "ℹ️ **测试模型可用性**\n"
                    "用法：/测试 <API网址> <API Key> [API Key2]... [模型名]\n"
                    "示例：/测试 https://api.example.com/v1 sk-xxxxxxxx\n"
                    "      /测试 https://api.example.com sk-xxxxxxxx deepseek-chat\n"
                    "自动识别 OpenAI 兼容端点：列出可用模型并实测调用，验证 Key 是否有效。\n"
                    "自动模式最多实测前 3 个聊天类模型（遇失败即停）；\n"
                    "末尾可指定模型名，直接实测该模型（不在模型列表中也会硬测）。\n"
                    "英文别名：/test"
                )
            yield event.plain_result(usage)
            return
        if not (url.startswith("http://") or url.startswith("https://")):
            resolved = self._resolve_endpoint_abbr(raw) or self._resolve_endpoint_abbr(url)
            if resolved:
                raw = url = resolved
            elif lang == "en":
                yield event.plain_result(
                    f"❌ Please enter an API endpoint, format: /test <API endpoint> <API Key>\n"
                    f"Input: {raw}"
                )
                return
            else:
                yield event.plain_result(
                    f"❌ 请输入 API 网址，格式：/测试 <API网址> <API Key>\n"
                    f"输入内容: {raw}"
                )
                return

        extra = parts[1].strip() if len(parts) > 1 else ""
        async for msg in self._query_model_test(event, raw, extra, lang):
            yield msg

    async def _query_current(self, event: AstrMessageEvent):
        """查询当前会话使用的模型余额"""
        try:
            provider = self.context.get_using_provider(umo=event.unified_msg_origin)
        except Exception as e:
            yield event.plain_result(f"❌ 获取当前模型配置失败: {e}")
            return

        provider_config = provider.provider_config
        api_base = provider_config.get("api_base", "")
        api_key = self._get_api_key(provider)
        display_name = self._get_provider_display_name(provider)

        if not api_key:
            yield event.plain_result(f"❌ 无法获取 {display_name} 的 API Key。")
            return

        logger.info(f"[astrbot_plugin_llm_balance] 查询当前余额 - 平台: {display_name}, Base: {api_base}, Key: {self._mask_key(api_key)}")

        yield event.plain_result(f"🔄 正在查询 {display_name} 的余额，请稍候...")

        result = await self.manager.query(api_key, api_base)
        if not result.error:
            result.source_name = display_name

        msg = self._header("当前余额查询")
        msg += self._sep()
        msg += self._format_result(result, self._mask_key(api_key))
        yield event.plain_result(msg)

    async def _query_all(self, event: AstrMessageEvent):
        """查询所有已配置模型的余额"""
        providers = self.context.get_all_providers()
        if not providers:
            yield event.plain_result("⚠️ 当前未配置任何模型提供商。")
            return

        logger.info(f"[astrbot_plugin_llm_balance] _query_all: 获取到 {len(providers)} 个 provider")
        for i, p in enumerate(providers):
            cfg = p.provider_config
            # 打印所有配置字段，方便确认 api_base 对应哪个字段
            cfg_keys = {k: (self._mask_key(v) if isinstance(v, str) and ('key' in k.lower() or 'secret' in k.lower() or 'token' in k.lower()) else v) for k, v in cfg.items()}
            logger.info(f"[astrbot_plugin_llm_balance]   provider[{i}]: {cfg_keys}")

        # 按 (api_base, api_key) 去重，遍历每个 provider 的所有 key
        unique_credentials = {}  # (api_base, api_key) -> provider
        for p in providers:
            cfg = p.provider_config
            api_base = cfg.get("api_base", "")
            all_keys = self._get_all_api_keys(p)
            if not all_keys:
                all_keys = [self._get_api_key(p)]
            for api_key in all_keys:
                if not api_key:
                    continue
                unique_credentials[(api_base, api_key)] = p

        logger.info(f"[astrbot_plugin_llm_balance] _query_all: 展开所有 key 后共 {len(unique_credentials)} 个唯一凭证")

        if not unique_credentials:
            yield event.plain_result("⚠️ 未找到有效的 API Key 配置。")
            return

        yield event.plain_result(f"🔄 正在查询 {len(unique_credentials)} 个平台的余额，请稍候...")

        # 并发查询
        tasks = []
        provider_list = []
        key_list = []
        for (base, key), p in unique_credentials.items():
            tasks.append(self.manager.query(key, base))
            provider_list.append(p)
            key_list.append(key)

        results = await asyncio.gather(*tasks)

        # 拼接结果
        success_msgs = []
        error_msgs = []
        unsupported_ids = []

        for i, res in enumerate(results):
            display_name = self._get_provider_display_name(provider_list[i])
            masked_key = self._mask_key(key_list[i])
            # 把密钥标签插入到首行（平台名）下方
            text = self._format_result(res, masked_key)
            if res.error:
                if "暂不支持" in res.error:
                    unsupported_ids.append(display_name)
                else:
                    res.source_name = display_name
                    error_msgs.append(text)
            else:
                res.source_name = display_name
                success_msgs.append(text)

        msg = self._header("全平台余额汇总")
        msg += self._sep()

        if success_msgs:
            msg += "**查询成功:**\n"
            msg += self._item_sep().join(success_msgs)

        if error_msgs:
            msg += self._section_sep()
            msg += "**查询失败:**\n"
            msg += self._item_sep().join(error_msgs)

        if unsupported_ids and self.config.get("show_unsupported", True):
            unique_unsupported = sorted(list(set(unsupported_ids)))
            msg += self._section_sep()
            msg += "⚪ **未适配平台**:\n  " + ", ".join(unique_unsupported)

        if not success_msgs and not error_msgs and not unsupported_ids:
            msg += "⚠️ 未检测到有效的平台配置。"

        yield event.plain_result(msg)

    async def _query_by_platform(self, event: AstrMessageEvent, platform_name: str, extra_args: str = ""):
        """根据平台简写/名称查询余额，支持传入自定义 API Key 列表（自动识别 sk- 开头的令牌）"""
        name_lower = platform_name.lower().strip()

        # 1. 通过简写映射查找平台 key
        platform_key = self.alias_map.get(name_lower)

        if not platform_key:
            yield event.plain_result(
                f"❌ 未找到匹配的平台: {platform_name}\n\n"
                f"{self._get_platform_aliases_text()}"
            )
            return

        platform_info = self.PLATFORMS[platform_key]
        display_name = platform_info["display_name"]

        # 2. 如果用户传入了额外参数，尝试提取其中的 API Key
        if extra_args:
            valid_keys = self._extract_keys(extra_args)
            if not valid_keys:
                yield event.plain_result(
                    f"❌ 在参数中未检测到有效的 API Key（需要以 sk- 开头）。\n"
                    f"输入内容: {extra_args}"
                )
                return

            fetcher_cls = self.FETCHER_MAP.get(platform_key)
            if not fetcher_cls:
                yield event.plain_result(f"❌ 找不到 {display_name} 的查询器。")
                return

            api_base = ""
            if platform_key == "newapi":
                if not self.manager.newapi_urls:
                    yield event.plain_result(f"❌ 请先在配置中设置 newapi_base_url。")
                    return
                api_base = self.manager.newapi_urls[0]

            yield event.plain_result(f"🔄 正在查询 {len(valid_keys)} 个 {display_name} 密钥的余额，请稍候...")
            msg = await self._query_and_format(
                f"{display_name} 余额查询", valid_keys,
                lambda s, k: fetcher_cls().fetch(s, k, api_base),
                display_name,
            )
            yield event.plain_result(msg)
            return

        # 3. 没有自定义 API Key，从已配置的 provider 中查找
        providers = self.context.get_all_providers()
        logger.info(f"[astrbot_plugin_llm_balance] _query_by_platform [{platform_name}]: 共 {len(providers)} 个 provider, 平台key={platform_key}")
        matched_providers = []
        for p in providers:
            api_base = p.provider_config.get("api_base", "")
            matched_key = self._match_platform_by_api_base(api_base)
            logger.info(f"[astrbot_plugin_llm_balance]   provider id={p.provider_config.get('id')}, api_base={api_base}, matched_key={matched_key}, key_count={len(self._get_all_api_keys(p))}")
            if matched_key == platform_key:
                matched_providers.append(p)

        logger.info(f"[astrbot_plugin_llm_balance] _query_by_platform [{platform_name}]: 匹配到 {len(matched_providers)} 个 provider")

        # 4. NEW API 特殊处理：没有匹配到 provider 但配置了 newapi_urls
        if not matched_providers and platform_key == "newapi":
            if not self.manager.newapi_urls:
                yield event.plain_result(
                    f"⚠️ 平台 {display_name} 未在 AstrBot 中配置，也未设置 newapi_base_url。"
                )
                return

            # 为每个配置的 newapi URL 找到匹配的 provider + key
            # （NEW API 在 AstrBot 中通常配置为 OpenAI 兼容端点，其 API Key 即为 NEW API 的管理员令牌）
            url_key_pairs = []  # [(newapi_url, api_key, display_label), ...]
            for newapi_url in self.manager.newapi_urls:
                newapi_lower = newapi_url.lower()
                for p in providers:
                    api_base = p.provider_config.get("api_base", "").lower()
                    if newapi_lower in api_base:
                        all_keys = self._get_all_api_keys(p)
                        for key in all_keys:
                            if key:
                                label = f"{newapi_url} [{self._mask_key(key)}]"
                                url_key_pairs.append((newapi_url, key, label))
                        break  # 每个 URL 只取第一个匹配 provider 的密钥

            if not url_key_pairs:
                yield event.plain_result(
                    f"⚠️ 找不到匹配 {display_name} 的 API Key，请在 AstrBot 中配置对应 provider，或在命令后直接传入 API Key。"
                )
                return

            yield event.plain_result(f"🔄 正在查询 {len(url_key_pairs)} 个 {display_name} 实例的余额，请稍候...")
            session = await self.manager._get_session()
            tasks = [NewApiFetcher().fetch(session, key, url) for url, key, _ in url_key_pairs]
            results = await asyncio.gather(*tasks)

            if len(results) == 1:
                msg = self._header(f"{display_name} 余额查询")
                msg += self._sep()
                msg += self._format_result(results[0], self._mask_key(url_key_pairs[0][1]))
                yield event.plain_result(msg)
            else:
                msg = self._header(f"{display_name} 余额查询 ({len(results)} 个实例)")
                msg += self._sep()
                parts = []
                for res, (url, key, label) in zip(results, url_key_pairs):
                    parts.append(f"**{label}**\n" + self._format_result(res, self._mask_key(key)))
                msg += self._item_sep().join(parts)
            return
        if not matched_providers:
            yield event.plain_result(
                f"⚠️ 平台 {display_name} 未在 AstrBot 中配置。\n"
                f"💡 也可以直接使用：/余额 {platform_name} <你的API密钥>"
            )
            return

        # 5. 把每个匹配的 provider 展开为 (api_base, api_key) 列表（一个 provider 可能有多个密钥）
        all_entries = []  # [(api_base, api_key), ...]
        for p in matched_providers:
            api_base = p.provider_config.get("api_base", "")
            all_keys = self._get_all_api_keys(p)
            if not all_keys:
                all_keys = [self._get_api_key(p)]  # fallback
            for key in all_keys:
                if key:
                    all_entries.append((api_base, key))

        if not all_entries:
            yield event.plain_result(f"❌ 无法获取 {display_name} 的 API Key。")
            return

        # 按 api_key 去重（不同 provider 可能共用同一个 key）
        seen_keys = set()
        deduped_entries = []
        for base, key in all_entries:
            if key not in seen_keys:
                seen_keys.add(key)
                deduped_entries.append((base, key))

        logger.info(f"[astrbot_plugin_llm_balance] _query_by_platform [{platform_name}]: 展开后 {len(all_entries)} 个 key, 去重后 {len(deduped_entries)} 个")
        yield event.plain_result(f"🔄 匹配到 {len(deduped_entries)} 个 {display_name} 密钥，正在并发查询...")

        # 并发查询所有 key
        keys = [k for _, k in deduped_entries]
        tasks = [self.manager.query(key, base) for base, key in deduped_entries]
        results = await asyncio.gather(*tasks)

        # 排序：成功的在前，失败的在后
        paired = list(zip(results, keys))
        paired.sort(key=lambda x: (x[0].error != "", self._mask_key(x[1])))
        results = [r for r, _ in paired]
        keys = [k for _, k in paired]

        msg = self._format_multi_results(f"{display_name} 余额查询", results, keys, display_name)
        yield event.plain_result(msg)

    async def _query_custom(self, event: AstrMessageEvent, api_base: str, extra_args: str = ""):
        """查询自定义 API 端点的余额"""
        api_base = api_base.rstrip("/")
        if "/v1" in api_base:
            api_base = api_base.split("/v1")[0]

        valid_keys = self._extract_keys(extra_args)
        if not valid_keys:
            yield event.plain_result(
                f"❌ 未检测到有效的 API Key（需要以 sk- 开头）。\n"
                f"输入内容: {extra_args}"
            )
            return

        yield event.plain_result(f"🔄 正在查询 {len(valid_keys)} 个密钥的余额，请稍候...")
        msg = await self._query_and_format(
            f"{api_base} 余额查询", valid_keys,
            lambda s, k: self._query_openai_compatible(s, k, api_base),
        )
        yield event.plain_result(msg)

    async def _query_newapi_conn_info(self, event: AstrMessageEvent, json_text: str, extra_args: str = ""):
        """解析 NewAPI 复制连接信息 JSON 并查询余额"""
        import json
        try:
            config = json.loads(json_text)
        except json.JSONDecodeError:
            yield event.plain_result(f"❌ 无法解析 JSON 配置。")
            return

        if config.get("_type") != "newapi_channel_conn":
            yield event.plain_result(f"❌ 不支持的配置类型: {config.get('_type')}")
            return

        api_key = config.get("key", "")
        api_url = config.get("url", "")
        if not api_key or not api_url:
            yield event.plain_result(f"❌ 配置中缺少 key 或 url。")
            return

        yield event.plain_result(f"🔄 正在查询 {api_url} 的余额，请稍候...")
        session = await self.manager._get_session()
        result = await NewApiFetcher().fetch(session, api_key, api_url)
        msg = self._header(f"{api_url} 余额查询")
        msg += self._sep()
        msg += self._format_result(result, self._mask_key(api_key))
        yield event.plain_result(msg)

    async def _query_openai_compatible(self, session: aiohttp.ClientSession, api_key: str, base_url: str) -> BalanceResult:
        """查询自定义端点余额，优先 OpenAI Billing API，降级 New API 格式"""
        headers = {
            "Authorization": f"Bearer {api_key}",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
        }

        # 尝试 OpenAI Billing API
        account_balance = 0.0
        has_payment = False
        access_until = "无限制"

        try:
            sub_url = f"{base_url}/v1/dashboard/billing/subscription"
            async with session.get(sub_url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    sub_data = await resp.json()
                    if isinstance(sub_data, dict):
                        account_balance = float(sub_data.get("soft_limit_usd", sub_data.get("hard_limit_usd", 0)))
                        has_payment = sub_data.get("has_payment_method", False)
                        access_until = sub_data.get("access_until", "无限制")
                    elif isinstance(sub_data, list) and sub_data:
                        account_balance = float(sub_data[0].get("soft_limit_usd", 0))
                        has_payment = sub_data[0].get("has_payment_method", False)
                        access_until = sub_data[0].get("access_until", "无限制")

            if account_balance != 0:
                usage_url = f"{base_url}/v1/dashboard/billing/usage?start_date={datetime.today().strftime('%Y-%m-%d')}&end_date={datetime.today().strftime('%Y-%m-%d')}"
                used_balance = 0.0
                try:
                    async with session.get(usage_url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                        if resp.status == 200:
                            usage_data = await resp.json()
                            used_balance = float(usage_data.get("total_usage", 0)) / 100
                except Exception:
                    pass

                remaining = account_balance - used_balance
                return BalanceResult(
                    source_name="自定义端点",
                    currency="USD",
                    total_balance=f"{account_balance:.2f}",
                    remaining_balance=f"{remaining:.2f}",
                    used_balance=f"{used_balance:.2f}",
                    raw_info=f"{self._apply_platform_name_map(base_url)} | 支付: {'是' if has_payment else '否'} | 到期: {access_until}"
                )
        except Exception:
            pass

        # 降级尝试 New API 格式
        try:
            url = base_url.rstrip('/') + "/api/usage/token"
            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                try:
                    data = await resp.json()
                except Exception:
                    text = await resp.text()
                    return BalanceResult("自定义端点", "Unknown", "0",
                        error=f"New API 返回非JSON(HTTP {resp.status}): {text[:200]}")

            ok_flag = bool(data.get("code", False) or data.get("success", False))
            if ok_flag and "data" in data:
                d = data["data"] or {}
                total_granted = d.get("total_granted", 0)
                total_used = d.get("total_used", 0)
                total_available = d.get("total_available", 0)
                unlimited = d.get("unlimited_quota", False)
                expires_at = d.get("expires_at", 0)
                expires_str = "永不过期" if not expires_at else datetime.fromtimestamp(expires_at).strftime("%Y-%m-%d %H:%M:%S")

                return BalanceResult(
                    source_name="自定义端点",
                    currency="",
                    total_balance=str(total_granted),
                    used_balance=str(total_used),
                    remaining_balance=str(total_available),
                    raw_info=f"{self._apply_platform_name_map(base_url)} | 无限额度: {'是' if unlimited else '否'} | 到期: {expires_str}"
                )

            err = data.get("message", "未知错误") if isinstance(data, dict) else str(data)[:200]
            return BalanceResult("自定义端点", "Unknown", "0", error=f"New API 返回错误: {err}")
        except aiohttp.ClientError as e:
            return BalanceResult("自定义端点", "Unknown", "0", error=f"New API 请求失败: {e}")
        except Exception as e:
            return BalanceResult("自定义端点", "Unknown", "0", error=f"New API 处理异常: {e}")

        return BalanceResult("自定义端点", "Unknown", "0", error="无法获取余额信息 (API不支持或返回为空)")

    async def _query_model_test(self, event: AstrMessageEvent, api_base: str, extra_args: str = "", lang: str = "zh"):
        """测试指定 API 端点的模型可用性（OpenAI 兼容），支持多个 API Key，可选指定模型名"""
        en = lang != "zh"
        api_base = api_base.rstrip("/")
        if "/v1" in api_base:
            api_base = api_base.split("/v1")[0]

        tokens = extra_args.split()
        valid_keys = [t for t in tokens if t.startswith("sk-")]
        non_key_tokens = [t for t in tokens if not t.startswith("sk-")]

        if len(non_key_tokens) > 1:
            if en:
                yield event.plain_result(
                    f"❌ Too many model name arguments, only one allowed (tokens starting with sk- are API keys).\n"
                    f"Input: {extra_args}"
                )
            else:
                yield event.plain_result(
                    f"❌ 模型名参数过多，只能指定一个（以 sk- 开头的是 API Key）。\n"
                    f"输入内容: {extra_args}"
                )
            return
        model_name = non_key_tokens[0] if non_key_tokens else ""

        if not valid_keys:
            if en:
                yield event.plain_result(
                    f"❌ No valid API key detected (must start with sk-).\n"
                    f"Input: {extra_args}"
                )
            else:
                yield event.plain_result(
                    f"❌ 未检测到有效的 API Key（需要以 sk- 开头）。\n"
                    f"输入内容: {extra_args}"
                )
            return

        target_desc = f", model {model_name}" if model_name else ""
        if en:
            yield event.plain_result(f"🔄 Testing {len(valid_keys)} key(s) against {self._apply_platform_name_map(api_base)}{target_desc}, please wait...")
        else:
            yield event.plain_result(f"🔄 正在测试 {len(valid_keys)} 个密钥连接 {self._apply_platform_name_map(api_base)}{target_desc}，请稍候...")
        session = await self.manager._get_session()
        tasks = [self._test_model_openai_compatible(session, key, api_base, model_name, lang) for key in valid_keys]
        results = await asyncio.gather(*tasks)
        shown_base = self._apply_platform_name_map(api_base)
        title = f"Model Test: {shown_base}" if en else f"{shown_base} 模型测试"
        msg = self._format_model_test_results(title, results, valid_keys, lang)
        yield event.plain_result(msg)

    def _format_model_test_results(self, title: str, results, keys: List[str], lang: str = "zh") -> str:
        """将多个模型测试结果格式化为结果字符串（按成功/失败分组）"""
        en = lang != "zh"
        success_list = []
        error_list = []
        for res, key in zip(results, keys):
            text = res.to_string(self._mask_key(key), lang)
            (error_list if res.error else success_list).append(text)

        if len(keys) == 1:
            msg = self._header(title)
            msg += self._sep()
            msg += (success_list[0] if success_list else error_list[0])
            return msg

        if en:
            msg = self._header(f"{title} ({len(keys)} key(s))")
        else:
            msg = self._header(f"{title} ({len(keys)} 个密钥)")
        msg += self._sep()
        if success_list:
            msg += self._item_sep().join(success_list)
        if error_list:
            if success_list:
                msg += self._section_sep()
            msg += "**Failed tests:**\n" if en else "**测试失败:**\n"
            msg += self._item_sep().join(error_list)
        return msg

    def _pick_chat_models(self, models: List[str], limit: int = 3) -> List[str]:
        """挑选用于实测的候选模型：过滤明显非聊天类，优先聊天/生成类"""
        cleaned = [m for m in models if not any(h in m.lower() for h in NON_CHAT_HINTS)]
        chat_priority = [m for m in cleaned if any(k in m.lower() for k in CHAT_KEY_HINTS)]
        pool = chat_priority or cleaned or models
        picked = []
        seen = set()
        for m in pool:
            if m not in seen:
                seen.add(m)
                picked.append(m)
            if len(picked) >= limit:
                break
        return picked

    async def _test_model_openai_compatible(self, session: aiohttp.ClientSession, api_key: str, base_url: str,
                                            model_name: str = "", lang: str = "zh") -> ModelTestResult:
        """测试 OpenAI 兼容端点：拉取模型列表 + 实测 chat 调用，验证模型可用性。
        指定 model_name 时直接实测该模型（即使不在模型列表中）；否则自动挑选聊天类模型。"""
        en = lang != "zh"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
        }
        source = base_url
        specified = bool(model_name)

        # 1. 拉取模型列表（同时验证 Key 有效性；指定模型时列表不可用不阻塞实测）
        data = None
        models_latency_ms = 0
        status = 0
        try:
            url = f"{base_url}/v1/models"
            start = time.perf_counter()
            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                models_latency_ms = int((time.perf_counter() - start) * 1000)
                status = resp.status
                if status in (401, 403):
                    err = await self._short_error(resp)
                    if en:
                        return ModelTestResult(source, False, status_code=status,
                                               error=f"Invalid or unauthorized API key (HTTP {status}){err}")
                    return ModelTestResult(source, False, status_code=status,
                                           error=f"API Key 无效或无权限 (HTTP {status}){err}")
                if status != 200 and not specified:
                    err = await self._short_error(resp)
                    if en:
                        return ModelTestResult(source, False, status_code=status,
                                               error=f"Failed to fetch model list (HTTP {status}){err}")
                    return ModelTestResult(source, False, status_code=status,
                                           error=f"获取模型列表失败 (HTTP {status}){err}")
                try:
                    data = await resp.json()
                except Exception:
                    text = await self._safe_resp_text(resp)
                    if not specified:
                        if en:
                            return ModelTestResult(source, False, status_code=status,
                                                   error=f"Non-JSON response (HTTP {status}): {text[:200]}")
                        return ModelTestResult(source, False, status_code=status,
                                               error=f"返回内容非 JSON (HTTP {status}): {text[:200]}")
        except aiohttp.ClientError as e:
            if en:
                return ModelTestResult(source, False, error=f"Connection failed: {e}")
            return ModelTestResult(source, False, error=f"连接失败: {e}")
        except Exception as e:
            if en:
                return ModelTestResult(source, False, error=f"Exception fetching model list: {e}")
            return ModelTestResult(source, False, error=f"获取模型列表异常: {e}")

        # 2. 解析模型 ID 列表（兼容 data 列表 / models 列表 / 对象键名）
        ids = []
        if isinstance(data, dict):
            entries = data.get("data") or data.get("models") or []
            if isinstance(entries, dict):
                ids = [str(k) for k in entries.keys()]
            elif isinstance(entries, list):
                for m in entries:
                    mid = m.get("id") or m.get("model") if isinstance(m, dict) else None
                    if not mid and isinstance(m, dict):
                        mid = next(iter(m.keys()), None)
                    if mid:
                        ids.append(str(mid))
        elif isinstance(data, list):
            for m in data:
                if isinstance(m, dict):
                    mid = m.get("id") or m.get("model") or next(iter(m.keys()), None)
                else:
                    mid = str(m)
                if mid:
                    ids.append(str(mid))
        ids = list(dict.fromkeys(ids))  # 去重保序

        # 3. 确定实测目标：指定模型优先，否则自动挑选，列表为空且未指定则报错
        if specified:
            candidates = [model_name]
        elif not ids:
            if en:
                return ModelTestResult(source, False, status_code=status,
                                       error="Empty model list (this endpoint may not be OpenAI-compatible)")
            return ModelTestResult(source, False, status_code=status,
                                   error="模型列表为空（该端点可能不是 OpenAI 兼容 API）")
        else:
            candidates = self._pick_chat_models(ids)

        # 4. 实测调用
        tested_ok = []
        fail_msg = None
        chat_latency_ms = models_latency_ms
        for model in candidates:
            try:
                url = f"{base_url}/v1/chat/completions"
                payload = {
                    "model": model,
                    "messages": [{"role": "user", "content": "ping"}],
                    "max_tokens": 1,
                    "stream": False,
                }
                start = time.perf_counter()
                async with session.post(url, json=payload, headers=headers,
                                        timeout=aiohttp.ClientTimeout(total=20)) as resp:
                    chat_latency_ms = int((time.perf_counter() - start) * 1000)
                    if resp.status == 200:
                        tested_ok.append(model)
                        continue
                    err = await self._short_error(resp)
                    if en:
                        fail_msg = f"Model {model} call failed (HTTP {resp.status}){err}"
                    else:
                        fail_msg = f"模型 {model} 调用失败 (HTTP {resp.status}){err}"
                    break
            except aiohttp.ClientError as e:
                fail_msg = f"Model {model} request error: {e}" if en else f"模型 {model} 请求异常: {e}"
                break
            except Exception as e:
                fail_msg = f"Model {model} processing error: {e}" if en else f"模型 {model} 处理异常: {e}"
                break

        if not tested_ok and fail_msg:
            return ModelTestResult(source, False, models=ids, status_code=status,
                                   latency_ms=chat_latency_ms, error=fail_msg, specified=specified)

        raw_info = ""
        if specified and ids and model_name not in ids:
            if en:
                raw_info = f"ℹ️ Model {model_name} not in /v1/models list, tested directly"
            else:
                raw_info = f"ℹ️ 模型 {model_name} 未出现在 /v1/models 列表中，已直接实测"
        if tested_ok and fail_msg:
            if en:
                raw_info = (raw_info + "; " if raw_info else "") + f"⚠️ Other model unavailable: {fail_msg}"
            else:
                raw_info = (raw_info + "；" if raw_info else "") + f"⚠️ 另有模型不可用: {fail_msg}"

        return ModelTestResult(source, True, models=ids, tested_models=tested_ok,
                               latency_ms=chat_latency_ms, status_code=status,
                               raw_info=raw_info, specified=specified)

    async def _short_error(self, resp) -> str:
        """从错误响应中提取简短错误信息，返回形如 ': 具体错误' 的字符串，失败返回空串"""
        try:
            data = await resp.json()
        except Exception:
            try:
                text = (await resp.text()).strip()
            except Exception:
                return ""
            return f": {text[:150]}" if text else ""
        if isinstance(data, dict):
            err = data.get("error")
            if isinstance(err, dict):
                err = err.get("message", "")
            elif not isinstance(err, str):
                err = data.get("message", "")
            if err:
                return f": {str(err)[:150]}"
        return ""

    async def _safe_resp_text(self, resp) -> str:
        """安全读取响应文本（供非 JSON 分支使用）"""
        try:
            return await resp.text()
        except Exception:
            return ""

    def _get_unique_platform_display_names(self) -> List[str]:
        """获取所有支持平台的显示名称列表"""
        return [info["display_name"] for info in self.PLATFORMS.values()]

    def _get_platform_aliases_text(self) -> str:
        """生成平台简写列表文本，用于帮助和错误提示"""
        aliases_config = self.config.get("platform_aliases", {}) or {}
        lines = []
        for platform_key, info in self.PLATFORMS.items():
            default_aliases = [platform_key]
            aliases_str = aliases_config.get(platform_key, "") if isinstance(aliases_config, dict) else ""
            if isinstance(aliases_str, str) and aliases_str.strip():
                default_aliases.extend([a.strip() for a in aliases_str.split(",") if a.strip()])
            # 去重保持顺序
            seen = set()
            unique_aliases = []
            for a in default_aliases:
                if a.lower() not in seen:
                    seen.add(a.lower())
                    unique_aliases.append(a)
            lines.append(f"  {' / '.join(unique_aliases)} -> {info['display_name']}")
        return "**支持的平台简写:**\n" + "\n".join(lines)

    def _get_help_text(self) -> str:
        """获取帮助文本"""
        platforms = "、".join(self._get_unique_platform_display_names())
        return (
            self._header("余额查询插件")
            + self._sep()
            + "**使用方法:**\n"
            + "  /余额 当前 - 查询当前会话使用的模型余额\n"
            + "  /余额 所有 - 查询所有已配置模型的余额\n"
            + "  /余额 <平台简写> - 查询指定平台余额（配置中的或自带站点）\n"
            + "  /余额 <平台简写> <key1> [key2]... - 批量查询自带平台的多个密钥余额\n"
            + "  /余额 <API端口> <key1> [key2]... - 查询自定义 API 端点的余额（自动识别 OpenAI/New API）\n"
            + "  /测试 <API网址> <key1> [key2]... [模型名] - 测试 OpenAI 兼容端点的模型可用性（列出模型并实测调用，可指定模型）\n"
            + "  英文别名：/余额 = /balance，/测试 = /test\n"
            + "  子命令英文别名：当前 = current，所有 = all，帮助 = help\n"
            + "\n"
            + "**支持的平台:**\n"
            + f"  {platforms}\n"
            + "\n"
            + f"{self._get_platform_aliases_text()}\n"
            + "\n"
            + "⚠️ **安全提醒**：包含 API 密钥的查询建议私聊使用，避免在群聊中泄露。"
        )

    async def terminate(self):
        """插件销毁时清理资源"""
        await self.manager.close()
