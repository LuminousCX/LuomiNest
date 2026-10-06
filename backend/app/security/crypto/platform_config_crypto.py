"""platform_instances.config 凭据字段级加密（链路审查 P1-6）。

platform_instances 的 config JSON 列此前明文存储全部适配器凭据
（bot_token/app_secret/token/rcon_password/ws_token/webhook_token 等），
与 provider_credentials.api_key_encrypted 的 AES 链路（get_cipher()，
SECRET_KEY 派生 Fernet）形成双标。本模块补齐同一套「字段级加密 + 读时解密」：

- encrypt_config：写入路径调用，凭据类字段加密并带 ``enc:v1:`` 前缀标记
  （幂等判定依据：已带前缀的值原样跳过，不会二次加密）
- decrypt_config：读取路径调用，带前缀的字段解密还原明文——对 registry/
  适配器透明，适配器拿到的仍是明文 dict（契约不变）。解密失败（换机后
  SECRET_KEY 变化）时保留密文原样返回，绝不静默清空销毁凭据
- mask_config：/instances 端点响应脱敏，凭据字段返回掩码哨兵值
- strip_masked_values：PATCH 合并前剔除掩码哨兵（前端把 GET 到的 config
  原样回传时，哨兵值视为「未修改」，不覆盖真实凭据）

加密字段集合 SENSITIVE_CONFIG_KEYS 按「凭据类配置键」判定：各适配器
config_metadata 中 type=password 的键 + 报告点名的 encoding_aes_key
（wechat_work/mp 消息加解密密钥，metadata 标记为 text 但属凭据）。
普通配置（ws_host/port/enable 等）不加密。静态集合由单元测试与适配器
注册元数据交叉校验（test_platform_config_encryption.py），新增 password
字段漏登记会在测试期暴露。
"""
from loguru import logger

from app.security.crypto.aes_cipher import get_cipher

# 密文前缀标记：幂等迁移/防二次加密的判定依据（Fernet token 本身无稳定
# 可读前缀，显式加前缀让「是否已加密」的判断可靠）
CONFIG_ENC_PREFIX = "enc:v1:"

# 掩码哨兵：/instances 响应中凭据字段的脱敏值；PATCH 原样回传视为未修改
CONFIG_VALUE_MASK = "******"

# 凭据类配置键（详见模块 docstring 的判定规则；各适配器 password 字段的并集
# + 报告点名的 encoding_aes_key）
SENSITIVE_CONFIG_KEYS: frozenset[str] = frozenset({
    "password",         # mqtt_terminal
    "api_key",          # rest_api
    "access_token",     # qq_onebot
    "app_secret",       # qq_official / wechat_mp
    "token",            # qq_official / wechat_work / wechat_mp / wechat_personal
    "secret",           # wechat_work
    "encoding_aes_key", # wechat_work / wechat_mp（报告点名；metadata 为 text）
    "webhook_token",    # wechat_personal
    "ws_token",         # minecraft
    "rcon_password",    # minecraft
    "auth_token",       # game_websocket
    "bot_token",        # telegram / discord
    "ha_token",         # home_assistant
    "mi_pass",          # xiaomi_iot
})


def is_encrypted_config_value(value: object) -> bool:
    """判断单个配置值是否为已加密形态（带 enc:v1: 前缀）。"""
    return isinstance(value, str) and value.startswith(CONFIG_ENC_PREFIX)


def _transform_config(config: dict, transform) -> dict:
    """对 config 顶层凭据类字符串值应用 transform，返回新 dict（不原地修改）。"""
    if not isinstance(config, dict):
        return config
    result = dict(config)
    for key, value in config.items():
        if key in SENSITIVE_CONFIG_KEYS and isinstance(value, str) and value:
            result[key] = transform(key, value)
    return result


def encrypt_config(config: dict) -> dict:
    """加密 config 中的凭据类字段（写入路径；幂等，已加密的值跳过）。

    仅处理顶层凭据键的非空字符串值；嵌套结构（如 model_config）与普通
    配置原样保留。空字符串凭据无需加密（无内容可保护）。
    """

    def _enc(_key: str, value: str) -> str:
        if is_encrypted_config_value(value):
            return value
        return CONFIG_ENC_PREFIX + get_cipher().encrypt(value)

    return _transform_config(config, _enc)


def decrypt_config(config: dict) -> dict:
    """解密 config 中的凭据类字段（读取路径；对适配器透明，返回明文 dict）。

    Fail-safe：解密失败（SECRET_KEY 变化/密文损坏）时保留密文原样返回——
    适配器鉴权会以明确错误失败，但密文不被清空覆写，恢复密钥后仍可用。
    """

    def _dec(_key: str, value: str) -> str:
        if not is_encrypted_config_value(value):
            return value
        cipher = get_cipher()
        plaintext = cipher.decrypt(value[len(CONFIG_ENC_PREFIX):])
        if not plaintext:
            # 密文非空但解密结果为空 = 解密失败（cipher 已记日志）；
            # 保留密文，绝不把空串写回销毁凭据
            logger.error(
                "[PlatformConfigCrypto] 凭据字段解密失败，保留密文原样"
                "（SECRET_KEY 变化或密文损坏；恢复密钥后可继续解密）"
            )
            return value
        return plaintext

    return _transform_config(config, _dec)


def mask_config(config: dict) -> dict:
    """脱敏 config 中的凭据类字段（/instances 响应；非空凭据返回掩码哨兵）。"""
    return _transform_config(config, lambda _key, _value: CONFIG_VALUE_MASK)


def strip_masked_values(config: dict) -> dict:
    """剔除 config 中值为掩码哨兵的凭据字段（PATCH 合并前调用）。

    前端把 GET /instances 返回的 config 原样回传时，未修改的凭据字段是
    掩码哨兵而非真实值，直接合并会用哨兵覆盖真实凭据；此处按「哨兵 =
    未修改」语义剔除，其余字段正常合并。
    """
    if not isinstance(config, dict):
        return config
    return {
        key: value
        for key, value in config.items()
        if not (key in SENSITIVE_CONFIG_KEYS and value == CONFIG_VALUE_MASK)
    }
