/**
 * LuomiNest P4 - NVS 配置存储 + Web AP 配置门户
 * 从旧 esp32-p4/main/web_config.c 移植
 * NVS 部分独立于网络; AP/HTTP 部分需要 WiFi (P4 无 C6 时不可用)
 */

#ifndef WEB_CONFIG_H
#define WEB_CONFIG_H

#include "esp_err.h"
#include <stdbool.h>

#define LN_NVS_NAMESPACE "lnconfig"

#define LN_NVS_KEY_WIFI_SSID     "wifi_ssid"
#define LN_NVS_KEY_WIFI_PASS     "wifi_pass"
#define LN_NVS_KEY_MQTT_BROKER   "mqtt_broker"
#define LN_NVS_KEY_MQTT_CLIENT   "mqtt_client"
#define LN_NVS_KEY_BRIGHTNESS    "brightness"
#define LN_NVS_KEY_VOLUME        "volume"

#define LN_MAX_SSID_LEN      32
#define LN_MAX_PASS_LEN      64
#define LN_MAX_BROKER_LEN    128
#define LN_MAX_CLIENT_LEN    64

typedef struct {
    char wifi_ssid[LN_MAX_SSID_LEN];
    char wifi_pass[LN_MAX_PASS_LEN];
    char mqtt_broker[LN_MAX_BROKER_LEN];
    char mqtt_client[LN_MAX_CLIENT_LEN];
    int brightness;
    int volume;
} ln_config_t;

/** 从 NVS 加载配置 */
esp_err_t web_config_load(ln_config_t *cfg);

/** 保存配置到 NVS */
esp_err_t web_config_save(const ln_config_t *cfg);

/** NVS 中是否有已保存的配置 */
bool web_config_has_saved(void);

/** 启动 AP 模式配网门户 (需要 WiFi, P4 无 C6 时返回 ESP_ERR_NOT_SUPPORTED) */
esp_err_t web_config_start_ap(void);

/** 停止 AP 模式 */
esp_err_t web_config_stop_ap(void);

/** AP 是否活跃 */
bool web_config_is_ap_active(void);

#endif /* WEB_CONFIG_H */
