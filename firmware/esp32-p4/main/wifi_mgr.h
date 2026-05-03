#ifndef WIFI_MGR_H
#define WIFI_MGR_H

#include "esp_err.h"
#include <stdbool.h>

typedef void (*wifi_connected_cb_t)(void);
typedef void (*wifi_disconnected_cb_t)(void);

esp_err_t wifi_mgr_init(void);
esp_err_t wifi_mgr_connect(const char *ssid, const char *password);
esp_err_t wifi_mgr_register_connected_cb(wifi_connected_cb_t cb);
esp_err_t wifi_mgr_register_disconnected_cb(wifi_disconnected_cb_t cb);
bool wifi_mgr_is_connected(void);
int8_t wifi_mgr_get_rssi(void);
void wifi_mgr_get_ip_str(char *buf, size_t buf_len);

#endif
