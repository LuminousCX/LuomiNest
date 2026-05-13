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

esp_err_t web_config_load(ln_config_t *cfg);
esp_err_t web_config_save(const ln_config_t *cfg);
bool web_config_has_saved(void);

esp_err_t web_config_start_ap(void);
esp_err_t web_config_stop_ap(void);
bool web_config_is_ap_active(void);

#endif
