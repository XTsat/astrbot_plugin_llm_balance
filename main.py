import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Optional

import aiohttp

from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
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
        """生成默认格式的字符串"""
        msg = f"🟢 **{self.source_name}**\n"
        if self.remaining_balance == self.total_balance:
            msg += f"  💵 {self.total_balance} {self.currency}"
        else:
            msg += f"  💵 余额: {self.remaining_balance} {self.currency}\n"
            msg += f"  📈 总额: {self.total_balance} {self.currency}"
            if self.used_balance != "0":
                msg += f"\n  📊 已用: {self.used_balance} {self.currency}"
        if self.raw_info:
            msg += f"\n  📝 {self.raw_info}"
        return msg

    def to_string(self, template: str = "") -> str:
        if self.error:
            return f"🔴 **{self.source_name}**\n  ❌ {self.error}"
        if not template:
            return self._get_default_string()

        smart_balance = self.remaining_balance if self.remaining_balance != self.total_balance else self.total_balance
        replacements = {
            "{{source_name}}": self.source_name,
            "{{currency}}": self.currency,
            "{{balance}}": smart_balance,
            "{{total_balance}}": self.total_balance,
            "{{remaining_balance}}": self.remaining_balance,
            "{{used_balance}}": self.used_balance,
            "{{raw_info}}": self.raw_info,
        }
        result = template
        for key, value in replacements.items():
            result = result.replace(key, str(value))
        return result.replace("\\n", "\n")


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
            if not data.get("is_available"):
                return BalanceResult("DeepSeek", "Unknown", "0", error="账户状态不可用")
            infos = data.get("balance_infos", [])
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


NEWAPI_TOKEN_USAGE_PATH = "/api/usage/token"


class NewApiFetcher(BaseBalanceFetcher):
    aliases = ["newapi", "new api", "new_api", "中转"]

    def match(self, api_base: str) -> bool:
        # NEW API 没有固定的域名特征，需要用户在配置中指定或通过名称匹配
        return False

    async def fetch(self, session: aiohttp.ClientSession, api_key: str, api_base: str) -> BalanceResult:
        if not api_base:
            return BalanceResult("NEW API", "Unknown", "0", error="未配置 API Base URL")

        url = api_base.rstrip('/') + NEWAPI_TOKEN_USAGE_PATH
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

@register("astrbot_plugin_llm_balance", "YourName", "查询大模型平台余额", "v1.0.0")
class BalancePlugin(Star):
    """大模型余额查询插件

    支持命令：
        /余额 当前      - 查询当前会话使用的模型余额
        /余额 所有      - 查询所有已配置模型的余额
        /余额 <平台名>  - 查询指定平台的余额（如 deepseek、硅基、kimi 等）
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

    def _insert_key_label(self, text: str, masked_key: str) -> str:
        """把密钥标签插入到首行（平台名）下方"""
        if not masked_key:
            return text
        lines = text.split("\n", 1)
        if len(lines) > 1:
            return f"{lines[0]}\n  🔑 密钥{masked_key}\n{lines[1]}"
        return f"{text}\n  🔑 密钥{masked_key}\n"

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

    @filter.command("余额")
    async def balance(self, event: AstrMessageEvent):
        """查询大模型平台余额

        用法：
            /余额 当前      - 查询当前会话使用的模型余额
            /余额 所有      - 查询所有已配置模型的余额
            /余额 <平台名>  - 查询指定平台的余额
            /余额          - 显示帮助
        """
        # 权限检查
        if not self._is_admin(event):
            yield event.plain_result("🚫 只有管理员可以使用此指令。")
            return

        # 解析子命令
        full_text = event.message_str.strip()
        if full_text.startswith("/"):
            full_text = full_text[1:]
        if full_text.startswith("余额"):
            full_text = full_text[len("余额"):].strip()
        parts = full_text.split(maxsplit=1)
        sub_command = parts[0].lower() if parts else ""

        if sub_command == "" or sub_command == "帮助" or sub_command == "help":
            yield event.plain_result(self._get_help_text())
        elif sub_command == "当前":
            async for msg in self._query_current(event):
                yield msg
        elif sub_command == "所有":
            async for msg in self._query_all(event):
                yield msg
        else:
            # 视为平台名称，支持后面跟 API Key 参数
            extra = parts[1].strip() if len(parts) > 1 else ""
            async for msg in self._query_by_platform(event, sub_command, extra):
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

        logger.info(f"查询当前余额 - 平台: {display_name}, Base: {api_base}, Key: {self._mask_key(api_key)}")

        yield event.plain_result(f"🔄 正在查询 {display_name} 的余额，请稍候...")

        result = await self.manager.query(api_key, api_base)
        if not result.error:
            result.source_name = display_name

        msg = "💰 **当前余额查询**\n"
        msg += "━━━━━━━━━━━━━━\n"
        msg += result.to_string()
        yield event.plain_result(msg)

    async def _query_all(self, event: AstrMessageEvent):
        """查询所有已配置模型的余额"""
        providers = self.context.get_all_providers()
        if not providers:
            yield event.plain_result("⚠️ 当前未配置任何模型提供商。")
            return

        logger.info(f"_query_all: 获取到 {len(providers)} 个 provider")
        for i, p in enumerate(providers):
            cfg = p.provider_config
            # 打印所有配置字段，方便确认 api_base 对应哪个字段
            cfg_keys = {k: (self._mask_key(v) if isinstance(v, str) and ('key' in k.lower() or 'secret' in k.lower() or 'token' in k.lower()) else v) for k, v in cfg.items()}
            logger.info(f"  provider[{i}]: {cfg_keys}")

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

        logger.info(f"_query_all: 展开所有 key 后共 {len(unique_credentials)} 个唯一凭证")

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
            text = self._insert_key_label(res.to_string(), masked_key)
            if res.error:
                if "暂不支持" in res.error:
                    unsupported_ids.append(display_name)
                else:
                    res.source_name = display_name
                    error_msgs.append(text)
            else:
                res.source_name = display_name
                success_msgs.append(text)

        msg = "💰 **全平台余额汇总**\n"
        msg += "━━━━━━━━━━━━━━\n"

        if success_msgs:
            msg += "**查询成功:**\n"
            msg += "\n\n".join(success_msgs)

        if error_msgs:
            msg += "\n" + "━━━━━━━━━━━━━━\n"
            msg += "**查询失败:**\n"
            msg += "\n\n".join(error_msgs)

        if unsupported_ids:
            unique_unsupported = sorted(list(set(unsupported_ids)))
            msg += "\n" + "━━━━━━━━━━━━━━\n"
            msg += "⚪ **未适配平台**:\n  " + ", ".join(unique_unsupported)

        if not success_msgs and not error_msgs and not unsupported_ids:
            msg += "⚠️ 未检测到有效的平台配置。"

        yield event.plain_result(msg)

    async def _query_by_platform(self, event: AstrMessageEvent, platform_name: str, custom_api_key: str = ""):
        """根据平台简写/名称查询余额，支持传入自定义 API Key"""
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

        # 2. 如果用户传入了自定义 API Key，直接用它查询
        if custom_api_key:
            yield event.plain_result(f"🔄 正在查询 {display_name} 的余额，请稍候...")
            session = await self.manager._get_session()

            # 通过 platform_key 找到对应的 fetcher
            fetcher_map = {
                "deepseek": DeepSeekFetcher,
                "siliconflow": SiliconCloudFetcher,
                "moonshot": MoonshotFetcher,
                "openai": OpenAIFetcher,
                "chatanywhere": ChatAnywhereFetcher,
                "newapi": NewApiFetcher,
            }
            fetcher_cls = fetcher_map.get(platform_key)
            if not fetcher_cls:
                yield event.plain_result(f"❌ 找不到 {display_name} 的查询器。")
                return

            # 对于 NEW API，需要用配置的 base_url
            api_base = ""
            if platform_key == "newapi":
                if not self.manager.newapi_urls:
                    yield event.plain_result(f"❌ 请先在配置中设置 newapi_base_url。")
                    return
                api_base = self.manager.newapi_urls[0]

            result = await fetcher_cls().fetch(session, custom_api_key, api_base)
            result.source_name = display_name

            msg = f"💰 **{display_name} 余额查询**\n"
            msg += "━━━━━━━━━━━━━━\n"
            msg += result.to_string()
            yield event.plain_result(msg)
            return

        # 3. 没有自定义 API Key，从已配置的 provider 中查找
        providers = self.context.get_all_providers()
        logger.info(f"_query_by_platform [{platform_name}]: 共 {len(providers)} 个 provider, 平台key={platform_key}")
        matched_providers = []
        for p in providers:
            api_base = p.provider_config.get("api_base", "")
            matched_key = self._match_platform_by_api_base(api_base)
            logger.info(f"  provider id={p.provider_config.get('id')}, api_base={api_base}, matched_key={matched_key}, key_count={len(self._get_all_api_keys(p))}")
            if matched_key == platform_key:
                matched_providers.append(p)

        logger.info(f"_query_by_platform [{platform_name}]: 匹配到 {len(matched_providers)} 个 provider")

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
                msg = f"💰 **{display_name} 余额查询**\n"
                msg += "━━━━━━━━━━━━━━\n"
                msg += results[0].to_string()
                yield event.plain_result(msg)
            else:
                msg = f"💰 **{display_name} 余额查询** ({len(results)} 个实例)\n"
                msg += "━━━━━━━━━━━━━━\n"
                for res, (url, key, label) in zip(results, url_key_pairs):
                    msg += f"**{label}**\n"
                    msg += res.to_string() + "\n\n"
                yield event.plain_result(msg.strip())
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

        logger.info(f"_query_by_platform [{platform_name}]: 展开后 {len(all_entries)} 个 key, 去重后 {len(deduped_entries)} 个")
        yield event.plain_result(f"🔄 匹配到 {len(deduped_entries)} 个 {display_name} 密钥，正在并发查询...")

        # 并发查询所有 key
        tasks = [self.manager.query(key, base) for base, key in deduped_entries]
        results = await asyncio.gather(*tasks)

        # 组装输出
        if len(deduped_entries) == 1:
            res = results[0]
            if not res.error:
                res.source_name = display_name
            msg = f"💰 **{display_name} 余额查询**\n"
            msg += "━━━━━━━━━━━━━━\n"
            msg += res.to_string()
            yield event.plain_result(msg)
        else:
            # 排序：成功的在前，失败的在后
            paired = list(zip(results, deduped_entries))
            paired.sort(key=lambda x: (x[0].error != "", self._mask_key(x[1][1])))

            msg = f"💰 **{display_name} 余额查询** ({len(deduped_entries)} 个密钥)\n"
            msg += "━━━━━━━━━━━━━━\n"

            success_list = []
            error_list = []
            for res, (base, key) in paired:
                if not res.error:
                    res.source_name = display_name
                text = self._insert_key_label(res.to_string(), self._mask_key(key))
                if res.error:
                    error_list.append(text)
                else:
                    success_list.append(text)

            if success_list:
                msg += "\n\n".join(success_list)
            if error_list:
                msg += "\n" + "━━━━━━━━━━━━━━\n"
                msg += "**查询失败:**\n"
                msg += "\n\n".join(error_list)
            yield event.plain_result(msg)

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
            "💰 **余额查询插件**\n"
            "━━━━━━━━━━━━━━\n"
            "**使用方法:**\n"
            "  /余额 当前 - 查询当前会话使用的模型余额\n"
            "  /余额 所有 - 查询所有已配置模型的余额\n"
            "  /余额 <平台简写> - 查询指定平台（配置中的）的余额\n"
            "  /余额 <平台简写> <API密钥> - 直接用指定密钥查询该平台余额\n"
            "\n"
            "**支持的平台:**\n"
            f"  {platforms}\n"
            "\n"
            f"{self._get_platform_aliases_text()}\n"
            "\n"
            "⚠️ **安全提醒**：包含 API 密钥的查询建议私聊使用，避免在群聊中泄露。"
        )

    async def terminate(self):
        """插件销毁时清理资源"""
        await self.manager.close()
