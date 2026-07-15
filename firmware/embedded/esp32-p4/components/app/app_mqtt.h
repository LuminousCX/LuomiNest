/**
 * LuomiNest P4 - MQTT 客户端
 * 从旧 esp32-p4/main/app_mqtt.c 移植
 * P4 通过以太网直连 broker (不经过 C6)
 */

#ifndef APP_MQTT_H
#define APP_MQTT_H

#include "esp_err.h"
#include <stdbool.h>

typedef enum {
    MQTT_STATE_DISCONNECTED = 0,
    MQTT_STATE_CONNECTING,
    MQTT_STATE_CONNECTED,
} mqtt_state_t;

typedef void (*mqtt_message_cb_t)(const char *topic, const char *data, int data_len);
typedef void (*mqtt_connected_cb_t)(void);
typedef void (*mqtt_disconnected_cb_t)(void);

/** 初始化 MQTT 客户端并连接 broker */
esp_err_t app_mqtt_init(const char *broker_uri, const char *client_id);

/** 订阅 topic */
esp_err_t app_mqtt_subscribe(const char *topic, int qos);

/** 发布消息 */
esp_err_t app_mqtt_publish(const char *topic, const char *data, int len, int qos);

/** 注册回调 */
esp_err_t app_mqtt_register_message_cb(mqtt_message_cb_t cb);
esp_err_t app_mqtt_register_connected_cb(mqtt_connected_cb_t cb);
esp_err_t app_mqtt_register_disconnected_cb(mqtt_disconnected_cb_t cb);

/** 是否已连接 */
bool app_mqtt_is_connected(void);

/** 获取连接状态 */
mqtt_state_t app_mqtt_get_state(void);

#endif /* APP_MQTT_H */
